
import json, copy, argparse, importlib.util
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import pandapower as pp

# ============================================================
# Import existing rescue runner
# ============================================================

RESCUE_PATH = Path("/content/phase2g_rescue_runner.py")

spec = importlib.util.spec_from_file_location("rescue", str(RESCUE_PATH))
rescue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rescue)

base_runner = rescue.r

OUT_DIR = Path("/content/hiergrid_phase2/results/phase2g_llm_guided_rescue")
OUT_DIR.mkdir(parents=True, exist_ok=True)

V_MIN = 0.95
Q_SWEEP = [25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0, 250.0, 300.0]

# These are not final "hardcoded answers".
# They are candidate/control-anchor buses already seen in your successful runs.
# The LLM still chooses; physics still verifies.
ZONE_ANCHORS = {
    "MG1": [20, 21],
    "MG2": [37, 50, 51, 52],
    "MG3": [75],
    "MG4": [106, 117],
}

MAX_ITERATIONS = 10


# ============================================================
# Candidate buses shown to LLM
# ============================================================

def get_zone_candidate_buses(net, zone, zones, zone_state):
    zone_bus_set = set(int(b) for b in zones[zone])
    candidates = set()

    # Local undervoltage buses
    for b in zone_state.get("undervoltage_buses", {}).keys():
        b = int(b)
        if b in zone_bus_set:
            candidates.add(b)

    # Local lowest voltage buses
    for b in zone_state.get("lowest_voltage_buses", {}).keys():
        b = int(b)
        if b in zone_bus_set:
            candidates.add(b)

    # Worst bus
    if zone_state.get("worst_bus") is not None:
        b = int(zone_state["worst_bus"])
        if b in zone_bus_set:
            candidates.add(b)

    # Known zone support anchors from previous validated behavior
    for b in ZONE_ANCHORS.get(zone, []):
        if b in zone_bus_set and b in net.bus.index:
            candidates.add(int(b))

    return sorted(candidates)


# ============================================================
# Stronger LLM prompt: force proposal when global UV remains
# ============================================================

def build_mandatory_llm_prompt(zone_state, global_uv, candidate_buses, failed_actions):
    global_uv_count = len(global_uv)

    if candidate_buses:
        candidate_text = ", ".join(str(x) for x in candidate_buses)
    else:
        candidate_text = "None"

    failed_short = failed_actions[-8:] if failed_actions else []

    user_text = f"""
You are a microgrid zone agent inside a physics-verified multi-agent grid controller.

GLOBAL_UNDERVOLTAGE_COUNT: {global_uv_count}
GLOBAL_UNDERVOLTAGE_BUSES: {json.dumps(global_uv)}

LOCAL_ZONE_STATE:
zone: {zone_state["zone"]}
min_voltage_pu: {zone_state["min_voltage_pu"]}
max_voltage_pu: {zone_state["max_voltage_pu"]}
n_undervoltage: {zone_state["n_undervoltage"]}
n_overvoltage: {zone_state["n_overvoltage"]}
worst_bus: {zone_state["worst_bus"]}
undervoltage_buses: {json.dumps(zone_state.get("undervoltage_buses", {}))}
lowest_voltage_buses: {json.dumps(zone_state.get("lowest_voltage_buses", {}))}

CANDIDATE_BUSES_YOU_MAY_USE: [{candidate_text}]
FAILED_ACTIONS_TO_AVOID: {json.dumps(failed_short)}

TASK:
If GLOBAL_UNDERVOLTAGE_COUNT is greater than 0, you MUST propose one voltage-support action.
Do NOT return null unless GLOBAL_UNDERVOLTAGE_COUNT is 0.
Choose exactly one bus from CANDIDATE_BUSES_YOU_MAY_USE.
Use one q_mvar magnitude from this list only: [25, 50, 75, 100, 125, 150, 200, 250, 300].
Return ONLY valid JSON.

Required JSON:
{{"proposed_action": {{"add_shunts_q_mvar": {{"BUS_ID": Q_MVAR}}}}, "confidence": 0.0, "reason": "short reason"}}

Example:
{{"proposed_action": {{"add_shunts_q_mvar": {{"52": 100}}}}, "confidence": 0.85, "reason": "voltage support at a low-voltage support bus"}}
""".strip()

    return [
        {"role": "system", "content": "Return only valid JSON. No markdown. No prose. Do not return null when global undervoltage remains."},
        {"role": "user", "content": user_text},
    ]


def action_bus(action):
    if not action:
        return None
    try:
        return int(list(action["add_shunts_q_mvar"].keys())[0])
    except Exception:
        return None


def validate_action_against_candidates(action, candidate_buses):
    if not action:
        return False, "no_action"

    bus = action_bus(action)
    if bus is None:
        return False, "no_bus"

    if candidate_buses and bus not in set(int(x) for x in candidate_buses):
        return False, f"bus_{bus}_not_in_candidate_list"

    return True, "valid"


def get_llm_action_required(model, tokenizer, net, zone, zones, zone_state, global_uv, failed_actions):
    candidate_buses = get_zone_candidate_buses(net, zone, zones, zone_state)

    if len(global_uv) == 0:
        return None, {
            "candidate_buses": candidate_buses,
            "raw": None,
            "parsed": None,
            "parse_valid": False,
            "parse_error": "global_uv_zero",
            "valid_action": False,
            "valid_reason": "global_uv_zero",
        }

    if not candidate_buses:
        return None, {
            "candidate_buses": candidate_buses,
            "raw": None,
            "parsed": None,
            "parse_valid": False,
            "parse_error": "no_candidate_buses",
            "valid_action": False,
            "valid_reason": "no_candidate_buses",
        }

    # Attempt 1
    msgs = build_mandatory_llm_prompt(zone_state, global_uv, candidate_buses, failed_actions)
    raw = base_runner.generate_response(model, tokenizer, msgs)
    parsed, parse_valid, parse_error = base_runner.extract_json(raw)
    action = rescue.normalize_action(parsed)
    valid_action, valid_reason = validate_action_against_candidates(action, candidate_buses)

    if valid_action:
        return action, {
            "candidate_buses": candidate_buses,
            "raw": raw,
            "parsed": parsed,
            "parse_valid": parse_valid,
            "parse_error": parse_error,
            "valid_action": True,
            "valid_reason": valid_reason,
            "reprompted": False,
        }

    # Attempt 2: stronger reprompt
    failed_actions_2 = failed_actions + [{
        "previous_raw": raw,
        "previous_parse_valid": parse_valid,
        "previous_action": action,
        "previous_rejection": valid_reason,
    }]

    msgs2 = build_mandatory_llm_prompt(zone_state, global_uv, candidate_buses, failed_actions_2)
    msgs2[1]["content"] += "\n\nYour previous answer was invalid or null. You MUST now choose exactly one bus from CANDIDATE_BUSES_YOU_MAY_USE and return the required JSON."

    raw2 = base_runner.generate_response(model, tokenizer, msgs2)
    parsed2, parse_valid2, parse_error2 = base_runner.extract_json(raw2)
    action2 = rescue.normalize_action(parsed2)
    valid_action2, valid_reason2 = validate_action_against_candidates(action2, candidate_buses)

    return action2 if valid_action2 else None, {
        "candidate_buses": candidate_buses,
        "raw": raw2,
        "parsed": parsed2,
        "parse_valid": parse_valid2,
        "parse_error": parse_error2,
        "valid_action": valid_action2,
        "valid_reason": valid_reason2,
        "reprompted": True,
        "first_raw": raw,
        "first_parsed": parsed,
        "first_valid_reason": valid_reason,
    }


# ============================================================
# LLM-guided physics refinement
# ============================================================

def make_action(bus, q_abs):
    return {"add_shunts_q_mvar": {str(int(bus)): abs(float(q_abs))}}


def action_signature(action):
    if not action:
        return "NONE"
    return json.dumps(action, sort_keys=True)


def llm_guided_refinement_candidates(net, llm_actions, failed_sigs):
    """
    Sweep q values ONLY around buses proposed by LLM agents.
    This makes the final selected action LLM-guided, not physics-only.
    """
    proposed_buses = []
    for act in llm_actions:
        b = action_bus(act)
        if b is not None:
            proposed_buses.append(int(b))

    proposed_buses = sorted(set(proposed_buses))

    cands = []

    for bus in proposed_buses:
        for q in Q_SWEEP:
            act = make_action(bus, q)
            sig = action_signature(act)

            if sig in failed_sigs:
                continue

            verif = rescue.verify_action(net, act)

            cands.append({
                "source": "llm_guided_refinement",
                "zone": None,
                "action": act,
                "bus": str(bus),
                "q_abs": q,
                "verif": verif,
                "raw": None,
            })

    return cands


def fallback_physics_candidates(net, zones, zone_reports, llm_actions, failed_sigs):
    """
    Safety fallback. This should be counted separately.
    Use only if direct LLM and LLM-guided refinement produce no accepted action.
    """
    buses = rescue.candidate_buses_from_state(net, zones, zone_reports, llm_actions)
    cands = rescue.physics_refined_candidates(net, buses, failed_sigs)

    for c in cands:
        c["source"] = "safety_fallback_physics_refinement"

    return cands


# ============================================================
# Scenario loop
# ============================================================

def run_one_scenario_llm_guided(scenario, base_net, zones, v2, model, tokenizer):
    scenario_id = scenario.get("scenario_id", scenario.get("id", "unknown"))

    net = copy.deepcopy(base_net)
    net = v2.v0.apply_scenario_to_net(net, scenario, zones)
    conv, err = v2.v0.run_pf(net)

    if not conv:
        return {
            "scenario_id": scenario_id,
            "base_converged": False,
            "stop_reason": "base_fail",
            "base_metrics": None,
            "final_metrics": None,
            "logs": [],
            "executed_actions": [],
        }

    base_metrics = rescue.grid_metrics(net)

    result = {
        "scenario_id": scenario_id,
        "base_converged": True,
        "base_metrics": base_metrics,
        "final_metrics": None,
        "logs": [],
        "executed_actions": [],
        "stop_reason": None,
    }

    failed_sigs = set()
    failed_actions = []

    for it in range(MAX_ITERATIONS):
        current = rescue.grid_metrics(net)

        print(f"    [Iteration {it+1}] Global UV: {current['uv_count']} | Vmin={current['vmin']:.4f} | Def={current['deficit_sum']:.5f}")

        if current["uv_count"] == 0:
            result["stop_reason"] = "full_restoration"
            break

        global_uv = rescue.global_uv_buses(net)
        zone_reports = {}
        llm_actions = []
        cands = []

        # Ask all zone agents. No skipping healthy zones.
        for zone in sorted(zones.keys()):
            zs = rescue.extract_zone_state_full(net, zone, zones)
            zone_reports[zone] = zs

            act, llm_info = get_llm_action_required(
                model=model,
                tokenizer=tokenizer,
                net=net,
                zone=zone,
                zones=zones,
                zone_state=zs,
                global_uv=global_uv,
                failed_actions=failed_actions,
            )

            verif = rescue.verify_action(net, act)

            if act:
                bus_id = action_bus(act)
                llm_actions.append(act)
                print(f"      🔹 LLM {zone}: proposed bus={bus_id}, action={act}, verdict={verif['reason']}")
            else:
                print(f"      🔹 LLM {zone}: no valid proposal, reason={llm_info.get('valid_reason')}")

            log_row = {
                "iteration": it + 1,
                "source": "llm_zone_agent_direct",
                "zone": zone,
                "zone_state": zs,
                "global_uv": global_uv,
                "llm_info": llm_info,
                "action": act,
                "verif": verif,
            }

            result["logs"].append(log_row)

            cands.append({
                "source": "llm_direct",
                "zone": zone,
                "action": act,
                "bus": str(action_bus(act)) if act else None,
                "q_abs": list(act["add_shunts_q_mvar"].values())[0] if act else None,
                "verif": verif,
                "raw": llm_info.get("raw"),
            })

            if act and not verif["accepted"]:
                sig = action_signature(act)
                failed_sigs.add(sig)
                failed_actions.append({
                    "source": "llm_direct",
                    "zone": zone,
                    "action": act,
                    "reason": verif["reason"],
                })

        # First priority: direct LLM actions
        accepted_direct = [c for c in cands if c["source"] == "llm_direct" and c["verif"]["accepted"]]

        # Second priority: physics refinement ONLY around LLM-proposed buses
        guided = llm_guided_refinement_candidates(net, llm_actions, failed_sigs)
        accepted_guided = [c for c in guided if c["verif"]["accepted"]]

        print(f"      🔧 LLM-guided refinement tested {len(guided)} candidates; accepted {len(accepted_guided)}")

        cands.extend(guided)

        # Third priority: safety fallback only if the LLM layer produces nothing accepted
        fallback = []

        if not accepted_direct and not accepted_guided:
            fallback = fallback_physics_candidates(net, zones, zone_reports, llm_actions, failed_sigs)
            accepted_fallback = [c for c in fallback if c["verif"]["accepted"]]
            print(f"      🛟 Safety fallback tested {len(fallback)} candidates; accepted {len(accepted_fallback)}")
            cands.extend(fallback)

        accepted = [c for c in cands if c["verif"]["accepted"]]

        if not accepted:
            result["stop_reason"] = "no_accepted_action"
            break

        # Router: prefer direct LLM, then LLM-guided refinement, then fallback
        priority = {
            "llm_direct": 3,
            "llm_guided_refinement": 2,
            "safety_fallback_physics_refinement": 1,
        }

        def score_with_source_priority(c):
            base_score = rescue.score_candidate(c)
            return (priority.get(c["source"], 0),) + tuple(base_score)

        best = max(accepted, key=score_with_source_priority)

        print(f"      ✅ Executing {best['source']} | zone={best['zone']} | action={best['action']} | score={score_with_source_priority(best)}")

        rescue.apply_action(net, best["action"])
        conv, err = rescue.r.run_pf(net)

        if not conv:
            result["stop_reason"] = f"execution_pf_failed: {err}"
            break

        post = rescue.grid_metrics(net)

        result["executed_actions"].append({
            "iteration": it + 1,
            "source": best["source"],
            "zone": best["zone"],
            "action": best["action"],
            "post_metrics": post,
        })

    final_metrics = rescue.grid_metrics(net)
    result["final_metrics"] = final_metrics

    if result["stop_reason"] is None:
        result["stop_reason"] = "max_iterations_reached"

    result["uv_reduced"] = bool(final_metrics["uv_count"] < base_metrics["uv_count"])
    result["full_restoration"] = bool(final_metrics["uv_count"] == 0)
    result["vmin_improved"] = bool(final_metrics["vmin"] > base_metrics["vmin"] + 1e-9)
    result["deficit_reduced"] = bool(final_metrics["deficit_sum"] < base_metrics["deficit_sum"] - 1e-9)

    return result


# ============================================================
# Main
# ============================================================

def main(max_scenarios=None):
    v2 = base_runner.load_v2()
    model, tokenizer = base_runner.load_llm()

    base_net = pp.from_json(str(base_runner.FED_NET))
    meta = json.load(open(base_runner.FED_META))
    zones = {k: [int(x) for x in v] for k, v in meta["zones"].items()}

    scenario_files = sorted(base_runner.SCENARIO_DIRS[0].glob("*.json"))

    if max_scenarios is not None:
        scenario_files = scenario_files[:int(max_scenarios)]

    results = []
    log_path = OUT_DIR / "phase2g_llm_guided_rescue_logs.jsonl"

    if log_path.exists():
        log_path.unlink()

    print(f"\n🚀 Phase 2G LLM-Guided Rescue Runner Started. Running {len(scenario_files)} scenarios...")

    for i, sf in enumerate(scenario_files, 1):
        print(f"\n================ SCENARIO [{i}/{len(scenario_files)}]: {sf.stem} ================")

        scenario = json.load(open(sf))
        res = run_one_scenario_llm_guided(scenario, base_net, zones, v2, model, tokenizer)
        results.append(res)

        with open(log_path, "a") as f:
            for row in res.get("logs", []):
                row2 = dict(row)
                row2["scenario_id"] = res["scenario_id"]
                f.write(json.dumps(row2, default=str) + "\n")

        base_uv = None if res["base_metrics"] is None else res["base_metrics"]["uv_count"]
        final_uv = None if res["final_metrics"] is None else res["final_metrics"]["uv_count"]

        print(f"🎯 Result: UV {base_uv} -> {final_uv} | full={res.get('full_restoration')} | reduced={res.get('uv_reduced')} | stop={res.get('stop_reason')}")

    rows = []

    source_counts = Counter()

    for res in results:
        base = res.get("base_metrics") or {}
        final = res.get("final_metrics") or {}

        for act in res.get("executed_actions", []):
            source_counts[act.get("source")] += 1

        rows.append({
            "scenario_id": res["scenario_id"],
            "base_converged": res.get("base_converged"),
            "base_uv": base.get("uv_count"),
            "final_uv": final.get("uv_count"),
            "base_vmin": base.get("vmin"),
            "final_vmin": final.get("vmin"),
            "base_deficit": base.get("deficit_sum"),
            "final_deficit": final.get("deficit_sum"),
            "uv_reduced": res.get("uv_reduced", False),
            "full_restoration": res.get("full_restoration", False),
            "vmin_improved": res.get("vmin_improved", False),
            "deficit_reduced": res.get("deficit_reduced", False),
            "n_actions_executed": len(res.get("executed_actions", [])),
            "stop_reason": res.get("stop_reason"),
            "executed_source_sequence": " -> ".join([a.get("source", "") for a in res.get("executed_actions", [])]),
        })

    df = pd.DataFrame(rows)
    csv_path = OUT_DIR / "phase2g_llm_guided_rescue_scenario_results.csv"
    df.to_csv(csv_path, index=False)

    conv = df[df["base_converged"] == True].copy()

    summary = {
        "total_scenarios": int(len(df)),
        "base_converged": int(conv.shape[0]),
        "avg_base_uv": float(conv["base_uv"].mean()) if len(conv) else None,
        "avg_final_uv": float(conv["final_uv"].mean()) if len(conv) else None,
        "avg_base_vmin": float(conv["base_vmin"].mean()) if len(conv) else None,
        "avg_final_vmin": float(conv["final_vmin"].mean()) if len(conv) else None,
        "avg_base_deficit": float(conv["base_deficit"].mean()) if len(conv) else None,
        "avg_final_deficit": float(conv["final_deficit"].mean()) if len(conv) else None,
        "uv_reduction_rate": float(conv["uv_reduced"].mean()) if len(conv) else None,
        "full_restoration_rate": float(conv["full_restoration"].mean()) if len(conv) else None,
        "total_base_uv": int(conv["base_uv"].sum()) if len(conv) else None,
        "total_final_uv": int(conv["final_uv"].sum()) if len(conv) else None,
        "executed_action_source_counts": dict(source_counts),
    }

    summary_path = OUT_DIR / "phase2g_llm_guided_rescue_summary.json"

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    compact_path = OUT_DIR / "phase2g_llm_guided_rescue_compact_results.json"

    compact = []
    for res in results:
        rr = dict(res)
        rr.pop("logs", None)
        compact.append(rr)

    with open(compact_path, "w") as f:
        json.dump(compact, f, indent=2, default=str)

    print("\n================ SUMMARY ================")
    print(json.dumps(summary, indent=2))

    print("\nSaved:")
    print(csv_path)
    print(summary_path)
    print(log_path)
    print(compact_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_scenarios", type=int, default=None)
    args = parser.parse_args()
    main(max_scenarios=args.max_scenarios)
