
import json, copy, re, warnings, importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pandapower as pp
import torch
from unsloth import FastLanguageModel

warnings.filterwarnings("ignore")

# ============================================================
# CONFIG (Will be dynamically patched by Step 2)
# ============================================================
MAX_SEQ_LENGTH = 4096

FED_NET = Path("/content/hiergrid_phase1/testbeds/saved_nets/federation_4mg_ieee118.json")
FED_META = Path("/content/hiergrid_phase1/testbeds/metadata/federation_4mg_ieee118_metadata.json")
V2_SCRIPT = Path("/content/phase2d_iterative_blackboard_v2_deficit_aware.py")
SCENARIO_DIRS = [
    Path("/content/hiergrid_phase1/scenarios/federation")
]
ADAPTER_DIR = Path("/content/content/hiergrid_phase2/models/zone_agent_shared_lora_qwen05b_ultra_v1")

OUT_DIR = Path("/content/hiergrid_phase2/results/phase2g_multiagent_llm")
OUT_DIR.mkdir(parents=True, exist_ok=True)

V_MIN, V_MAX, HARD_OV = 0.95, 1.05, 1.06
MAX_ITERATIONS = 5
MAX_NEW_TOKENS = 384

def load_v2():
    import sys
    sys.path.insert(0, str(V2_SCRIPT.parent))
    sys.path.insert(0, "/content")
    spec = importlib.util.spec_from_file_location("v2trusted", str(V2_SCRIPT))
    v2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v2)
    return v2

def load_llm():
    print("[INFO] Loading ultra-compact zone-agent LoRA:", ADAPTER_DIR)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(ADAPTER_DIR),
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)
    return model, tokenizer

# ============================================================
# GRID METRICS
# ============================================================
def run_pf(net):
    try:
        pp.runpp(net, algorithm="nr", init="auto", enforce_q_lims=True, max_iteration=80, calculate_voltage_angles=True)
        return bool(net.converged), None
    except Exception as e:
        return False, repr(e)

def grid_metrics(net):
    vm = net.res_bus["vm_pu"].astype(float)
    return {
        "vmin": float(vm.min()), "vmax": float(vm.max()), "vmean": float(vm.mean()),
        "uv_count": int((vm < V_MIN).sum()), "ov_count": int((vm > V_MAX).sum()),
        "deficit_sum": float(np.clip(V_MIN - vm.values, 0, None).sum()),
    }

def extract_zone_state(net, zone, zones):
    buses = [int(b) for b in zones[zone] if int(b) in net.res_bus.index]
    vm = net.res_bus.loc[buses, "vm_pu"].astype(float)
    uv = {str(int(b)): float(v) for b, v in vm.items() if v < V_MIN}
    ov = {str(int(b)): float(v) for b, v in vm.items() if v > V_MAX}
    return {
        "zone": zone,
        "min_voltage_pu": float(vm.min()) if len(vm) else None,
        "max_voltage_pu": float(vm.max()) if len(vm) else None,
        "n_undervoltage": len(uv),
        "n_overvoltage": len(ov),
        "worst_bus": int(vm.idxmin()) if len(vm) else None
    }

# ============================================================
# LLM ZONE AGENT (WITH NEW MEMORY/TABOO LOGIC)
# ============================================================
def build_prompt(zone_state, taboo_actions):
    # MEMORY: Tell the model which buses we already touched
    history_str = ", ".join([str(b) for b in taboo_actions]) if taboo_actions else "None"

    summary = f"Worst bus is {zone_state['worst_bus']}." if zone_state['n_undervoltage'] > 0 else "Normal."

    user_text = (
        "You are a microgrid zone agent for physics-verified grid operation.\n"
        "Read the local zone state and output ONLY valid JSON using the required schema.\n"
        "Do not copy the input. Do not explain in prose.\n\n"
        "LOCAL_ZONE_STATE:\n"
        f"zone: {zone_state['zone']}\n"
        f"min_voltage_pu: {zone_state['min_voltage_pu']}\n"
        f"max_voltage_pu: {zone_state['max_voltage_pu']}\n"
        f"n_undervoltage: {zone_state['n_undervoltage']}\n"
        f"n_overvoltage: {zone_state['n_overvoltage']}\n"
        f"state_summary: {summary}\n"
        f"PREVIOUSLY_MODIFIED_BUSES: {history_str}\n\n"
        "TASK:\n"
        "Decide whether this zone needs no action, a local voltage-support action, "
        "or coordinator review. Return compact JSON only."
    )

    return [
        {"role": "system", "content": "You are a microgrid zone agent. Return only valid JSON. No prose."},
        {"role": "user", "content": user_text}
    ]

def generate_response(model, tokenizer, messages):
    inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
    attention_mask = torch.ones_like(inputs)
    outputs = model.generate(
        input_ids=inputs, attention_mask=attention_mask, max_new_tokens=MAX_NEW_TOKENS,
        do_sample=False, use_cache=True, pad_token_id=tokenizer.eos_token_id,
    )
    return tokenizer.decode(outputs[0][inputs.shape[-1]:], skip_special_tokens=True).strip()

def extract_json(text):
    text = text.replace("```json", "").replace("```", "").strip()
    try: return json.loads(text), True, None
    except: pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start: return None, False, "no_json"
    try: return json.loads(text[start:end+1]), True, None
    except Exception as e: return None, False, repr(e)

def normalize_action(parsed):
    if not isinstance(parsed, dict): return None
    action = parsed.get("proposed_action")
    if isinstance(action, dict) and "add_shunts_q_mvar" in action:
        return {"add_shunts_q_mvar": {str(int(b)): float(q) for b, q in action["add_shunts_q_mvar"].items()}}
    return None

# ============================================================
# PHYSICS VERIFIER (WITH INCREMENTAL SHUNT UPDATES)
# ============================================================
def apply_action(net, action):
    if action and "add_shunts_q_mvar" in action:
        for bus, q in action["add_shunts_q_mvar"].items():
            bus_idx = int(bus)
            val = float(q)
            # SAFEGUARD: Targets are positive, pandapower expects negative for injection
            if val > 0: val = -val

            # NEW: Check if we already have an LLM shunt here.
            # If yes, update it (increments support) instead of creating a new one (stacking).
            existing = net.shunt[net.shunt.bus == bus_idx]
            if not existing.empty:
                idx = existing.index[0]
                net.shunt.at[idx, "q_mvar"] += val
            else:
                pp.create_shunt(net, bus=bus_idx, q_mvar=val, p_mw=0.0, name=f"llm_shunt_b{bus}")
    return net

def verify_action(net, action):
    before = grid_metrics(net)
    if not action: return {"accepted": False, "reason": "no_action", "before": before, "converged": None}

    test_net = copy.deepcopy(net)
    apply_action(test_net, action)
    conv, err = run_pf(test_net)
    if not conv: return {"accepted": False, "reason": "pf_failed", "before": before, "converged": False}

    after = grid_metrics(test_net)
    # NEW: Selection logic based on deficit improvement (more granular than uv_count)
    improved = after["uv_count"] < before["uv_count"] or after["deficit_sum"] < before["deficit_sum"] - 1e-9
    reasons = []
    if after["vmax"] > HARD_OV: reasons.append("hard_ov")
    if after["uv_count"] > before["uv_count"]: reasons.append("uv_inc")
    if not improved: reasons.append("no_improvement")

    return {"accepted": len(reasons)==0, "reason": "ACCEPTED" if not reasons else ";".join(reasons), "before": before, "after": after}

# ============================================================
# MULTI-AGENT LOOP
# ============================================================
def run_one_scenario(scenario, base_net, zones, v2, model, tokenizer):
    net = copy.deepcopy(base_net)
    net = v2.v0.apply_scenario_to_net(net, scenario, zones)
    conv, _ = v2.v0.run_pf(net)
    if not conv: return {"success": False, "stop_reason": "base_fail"}

    result = {"base_metrics": grid_metrics(net), "logs": []}
    taboo = [] # MEMORY: Tracks modified buses

    for it in range(MAX_ITERATIONS):
        current_metrics = grid_metrics(net)
        if current_metrics["uv_count"] == 0: break

        print(f"    [Iteration {it+1}] Current Global Undervoltage Buses: {current_metrics['uv_count']}")
        cands = []

        for zone in sorted(zones.keys()):
            zs = extract_zone_state(net, zone, zones)
            if zs["n_undervoltage"] == 0:
                continue

            msgs = build_prompt(zs, taboo)
            raw = generate_response(model, tokenizer, msgs)
            parsed, valid, err = extract_json(raw)
            act = normalize_action(parsed)
            verif = verify_action(net, act)

            bus_id = None
            if act:
                bus_id = list(act["add_shunts_q_mvar"].keys())[0]
                print(f"      🔹 {zone} -> Model Proposed Bus {bus_id}")
                print(f"         Verifier Verdict: {verif['reason']}")

            cands.append({"zone": zone, "action": act, "verif": verif, "bus": bus_id})
            result["logs"].append({"zone": zone, "act": act, "verif": verif["accepted"]})

        accepted = [c for c in cands if c["verif"]["accepted"]]
        if not accepted:
            print("      ❌ No proposals were accepted by the physics verifier in this step.")
            break

        # Router picks the action that reduces the reactive power deficit the most
        best = max(accepted, key=lambda x: x["verif"]["before"]["deficit_sum"] - x["verif"]["after"]["deficit_sum"])
        print(f"      ✅ Router executed best proposal from {best['zone']}: {best['action']}")
        apply_action(net, best["action"])
        if best["bus"]: taboo.append(best["bus"]) # Update memory
        run_pf(net)

    result["final_metrics"] = grid_metrics(net)
    result["success"] = result["final_metrics"]["uv_count"] < result["base_metrics"]["uv_count"]
    return result

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_scenarios", type=int, default=None)
    args = parser.parse_args()

    v2 = load_v2()
    model, tokenizer = load_llm()
    base_net = pp.from_json(str(FED_NET))
    meta = json.load(open(FED_META))
    zones = {k: [int(x) for x in v] for k, v in meta["zones"].items()}

    scenarios = sorted(SCENARIO_DIRS[0].glob("*.json"))[:args.max_scenarios]
    print(f"\n🚀 Phase 2G LLM Grid Inference Started. Running {len(scenarios)} scenarios...")

    successes = 0
    for i, sf in enumerate(scenarios):
        print(f"\nSCENARIO [{i+1}/{len(scenarios)}]: {sf.stem}")
        scen = json.load(open(sf))
        res = run_one_scenario(scen, base_net, zones, v2, model, tokenizer)
        print(f"🎯 Result: Success={res.get('success', False)} | UV: {res['base_metrics']['uv_count']} -> {res.get('final_metrics', {}).get('uv_count', 'N/A')}")
        successes += int(res.get('success', False))

    print(f"\n" + "="*60)
    print(f"🏁 DONE! {successes}/{len(scenarios)} scenarios showed improvement.")
    print("="*60)
