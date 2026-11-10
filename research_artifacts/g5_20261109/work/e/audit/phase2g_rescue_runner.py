
import json, copy, importlib.util, argparse
from pathlib import Path
import numpy as np
import pandas as pd
import pandapower as pp

# ============================================================
# Import existing Phase 2G runner
# ============================================================

RUNNER_PATH = Path("/content/phase2g_multiagent_llm_runner.py")

spec = importlib.util.spec_from_file_location("base_runner", str(RUNNER_PATH))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

OUT_DIR = Path("/content/hiergrid_phase2/results/phase2g_rescue_llm_refined")
OUT_DIR.mkdir(parents=True, exist_ok=True)

V_MIN = 0.95
V_MAX = 1.05
HARD_OV = 1.06

MAX_ITERATIONS = 10
Q_SWEEP = [25.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0, 250.0, 300.0]
MAX_ABS_Q_PER_BUS = 450.0

ANCHOR_BUSES = [20, 37, 52, 75, 117]


# ============================================================
# Metrics
# ============================================================

def grid_metrics(net):
    vm = net.res_bus["vm_pu"].astype(float)
    return {
        "vmin": float(vm.min()),
        "vmax": float(vm.max()),
        "vmean": float(vm.mean()),
        "uv_count": int((vm < V_MIN).sum()),
        "ov_count": int((vm > V_MAX).sum()),
        "deficit_sum": float(np.clip(V_MIN - vm.values, 0, None).sum()),
    }


def global_uv_buses(net):
    vm = net.res_bus["vm_pu"].astype(float)
    return {str(int(b)): float(v) for b, v in vm.items() if v < V_MIN}


def lowest_buses(net, k=10):
    vm = net.res_bus["vm_pu"].astype(float).sort_values()
    return [int(x) for x in vm.head(k).index.tolist()]


# ============================================================
# Better zone state
# ============================================================

def extract_zone_state_full(net, zone, zones):
    buses = [int(b) for b in zones[zone] if int(b) in net.res_bus.index]
    vm = net.res_bus.loc[buses, "vm_pu"].astype(float)

    uv = {str(int(b)): float(v) for b, v in vm.items() if v < V_MIN}
    ov = {str(int(b)): float(v) for b, v in vm.items() if v > V_MAX}

    lowest = vm.sort_values().head(8)

    return {
        "zone": zone,
        "min_voltage_pu": float(vm.min()) if len(vm) else None,
        "max_voltage_pu": float(vm.max()) if len(vm) else None,
        "n_undervoltage": len(uv),
        "n_overvoltage": len(ov),
        "worst_bus": int(vm.idxmin()) if len(vm) else None,
        "undervoltage_buses": uv,
        "lowest_voltage_buses": {str(int(b)): float(v) for b, v in lowest.items()},
    }


# ============================================================
# Better prompt
# ============================================================

def build_prompt_full(zone_state, global_uv, failed_actions):
    failed_short = failed_actions[-10:] if failed_actions else []

    user_text = (
        "You are one zone agent inside a multi-agent, physics-verified grid controller.\n"
        "Your job is to propose one voltage-support action as JSON.\n"
        "The physics verifier will test your action using pandapower before execution.\n\n"

        "LOCAL_ZONE_STATE:\n"
        f"{json.dumps(zone_state)}\n\n"

        "GLOBAL_UNDERVOLTAGE_BUSES:\n"
        f"{json.dumps(global_uv)}\n\n"

        "FAILED_ACTIONS_TO_AVOID:\n"
        f"{json.dumps(failed_short)}\n\n"

        "RULES:\n"
        "1. If your zone has undervoltage, prefer the worst or nearby low-voltage bus.\n"
        "2. If your zone has no undervoltage but global undervoltage remains, you may still propose support from a known supportive bus in your zone.\n"
        "3. Do not return prose.\n"
        "4. Return exactly this JSON shape:\n"
        "{\"proposed_action\": {\"add_shunts_q_mvar\": {\"BUS_ID\": Q_MVAR}}, \"confidence\": 0.0, \"reason\": \"...\"}\n"
        "5. If no useful support is possible, return {\"proposed_action\": null, \"confidence\": 0.0, \"reason\": \"no useful local action\"}.\n"
    )

    return [
        {"role": "system", "content": "Return only valid JSON. No markdown. No prose."},
        {"role": "user", "content": user_text},
    ]


# ============================================================
# Safer action handling
# ============================================================

def normalize_action(action):
    """
    Robust normalizer for LLM-produced shunt actions.

    Supports:
      1) {"proposed_action": {"add_shunts_q_mvar": {"52": 100}}}
      2) {"action": {"add_shunts_q_mvar": {"52": 100}}}
      3) {"add_shunts_q_mvar": {"52": 100}}
      4) {"bus": "52", "q_mvar": 100}

    Malformed LLM outputs are rejected safely instead of crashing.
    """
    import json
    import math

    if action is None:
        return None

    if isinstance(action, str):
        try:
            action = json.loads(action)
        except Exception:
            return None

    if not isinstance(action, dict):
        return None

    # ------------------------------------------------------------
    # Unwrap common LLM schemas
    # ------------------------------------------------------------
    for wrapper_key in [
        "proposed_action",
        "action",
        "recommended_action",
        "candidate_action",
        "control_action",
    ]:
        wrapped = action.get(wrapper_key)
        if isinstance(wrapped, dict):
            # Prefer wrapped action if it contains the actual shunt payload
            if "add_shunts_q_mvar" in wrapped:
                action = wrapped
                break
            # Also allow one more nested level
            for inner_key in ["proposed_action", "action"]:
                inner = wrapped.get(inner_key)
                if isinstance(inner, dict) and "add_shunts_q_mvar" in inner:
                    action = inner
                    break

    payload = None

    # Standard expected payload
    if isinstance(action, dict) and "add_shunts_q_mvar" in action:
        payload = action.get("add_shunts_q_mvar")

    # Alternative compact flat schema
    elif isinstance(action, dict):
        bus = (
            action.get("bus")
            or action.get("bus_id")
            or action.get("BUS_ID")
            or action.get("target_bus")
            or action.get("target_bus_id")
        )
        q = (
            action.get("q_mvar")
            or action.get("Q_MVAR")
            or action.get("q_MVAr")
            or action.get("q")
            or action.get("mvar")
            or action.get("value")
            or action.get("reactive_power_mvar")
        )
        if bus is not None and q is not None:
            payload = {str(bus): q}

    # Critical crash fix:
    # Reject bare int/float/list/None payloads instead of crashing.
    if not isinstance(payload, dict):
        return None

    clean = {}

    for bus, q in payload.items():
        try:
            bus = str(bus).strip()
            q = float(q)
        except Exception:
            continue

        if not bus:
            continue

        if not math.isfinite(q):
            continue

        if q <= 0:
            continue

        # Snap to tested MVAr grid
        q = round(q / 25.0) * 25.0
        q = max(25.0, min(300.0, q))

        clean[bus] = float(q)

        # One compact action only
        break

    if not clean:
        return None

    return {"add_shunts_q_mvar": clean}


def llm_q_abs_at_bus(net, bus):
    if not hasattr(net, "shunt") or len(net.shunt) == 0:
        return 0.0

    total = 0.0
    for idx, row in net.shunt.iterrows():
        if int(row["bus"]) != int(bus):
            continue

        name = str(row.get("name", ""))
        if name.startswith("llm_shunt"):
            total += abs(float(row["q_mvar"]))

    return total


def apply_action(net, action):
    if not action:
        return net

    if "add_shunts_q_mvar" in action:
        for bus, q_abs in action["add_shunts_q_mvar"].items():
            bus = int(bus)
            q_abs = abs(float(q_abs))

            # pandapower capacitive support convention here: negative q_mvar
            pp.create_shunt(
                net,
                bus=bus,
                q_mvar=-q_abs,
                p_mw=0.0,
                name=f"llm_shunt_b{bus}_q{q_abs}"
            )

    return net


def verify_action(net, action):
    before = grid_metrics(net)

    if not action:
        return {
            "accepted": False,
            "reason": "no_action",
            "before": before,
            "after": None,
            "converged": None,
        }

    # Cap cumulative LLM-added support at each bus
    for bus, q_abs in action.get("add_shunts_q_mvar", {}).items():
        if llm_q_abs_at_bus(net, int(bus)) + abs(float(q_abs)) > MAX_ABS_Q_PER_BUS:
            return {
                "accepted": False,
                "reason": "q_cap_exceeded",
                "before": before,
                "after": None,
                "converged": None,
            }

    test_net = copy.deepcopy(net)
    apply_action(test_net, action)
    conv, err = r.run_pf(test_net)

    if not conv:
        return {
            "accepted": False,
            "reason": "pf_failed",
            "before": before,
            "after": None,
            "converged": False,
        }

    after = grid_metrics(test_net)

    reasons = []

    if after["vmax"] > HARD_OV:
        reasons.append("hard_overvoltage")

    if after["uv_count"] > before["uv_count"]:
        reasons.append("uv_increased")

    if after["deficit_sum"] > before["deficit_sum"] + 1e-9:
        reasons.append("deficit_increased")

    improved = (
        after["uv_count"] < before["uv_count"]
        or after["deficit_sum"] < before["deficit_sum"] - 1e-9
        or after["vmin"] > before["vmin"] + 1e-9
    )

    if not improved:
        reasons.append("no_improvement")

    return {
        "accepted": len(reasons) == 0,
        "reason": "ACCEPTED" if not reasons else ";".join(reasons),
        "before": before,
        "after": after,
        "converged": True,
    }


def make_action(bus, q_abs):
    return {"add_shunts_q_mvar": {str(int(bus)): abs(float(q_abs))}}


# ============================================================
# Candidate expansion
# ============================================================

def action_signature(action):
    if not action:
        return "NONE"
    return json.dumps(action, sort_keys=True)


def candidate_buses_from_state(net, zones, zone_reports, llm_actions):
    buses = set()

    # Remaining global UV buses
    for b in global_uv_buses(net).keys():
        buses.add(int(b))

    # Lowest-voltage global buses
    for b in lowest_buses(net, k=12):
        buses.add(int(b))

    # Zone worst buses
    for z, st in zone_reports.items():
        if st.get("worst_bus") is not None:
            buses.add(int(st["worst_bus"]))

    # LLM-proposed buses
    for act in llm_actions:
        if act and "add_shunts_q_mvar" in act:
            for b in act["add_shunts_q_mvar"].keys():
                buses.add(int(b))

    # Known useful support anchors from your runs
    for b in ANCHOR_BUSES:
        if b in net.bus.index:
            buses.add(int(b))

    return sorted([b for b in buses if b in net.bus.index])


def physics_refined_candidates(net, candidate_buses, failed_sigs):
    cands = []

    for bus in candidate_buses:
        for q in Q_SWEEP:
            act = make_action(bus, q)
            sig = action_signature(act)

            if sig in failed_sigs:
                continue

            verif = verify_action(net, act)

            cands.append({
                "source": "physics_refinement",
                "zone": None,
                "action": act,
                "bus": str(bus),
                "q_abs": q,
                "verif": verif,
                "raw": None,
            })

    return cands


def score_candidate(c):
    v = c["verif"]

    if not v["accepted"]:
        return (-999, -999, -999, -999, -999)

    before = v["before"]
    after = v["after"]

    full_restore = int(after["uv_count"] == 0)
    uv_gain = before["uv_count"] - after["uv_count"]
    deficit_gain = before["deficit_sum"] - after["deficit_sum"]
    vmin_gain = after["vmin"] - before["vmin"]

    q_abs = 0.0
    if c.get("action"):
        for q in c["action"]["add_shunts_q_mvar"].values():
            q_abs += abs(float(q))

    return (full_restore, uv_gain, deficit_gain, vmin_gain, -q_abs)


# ============================================================
# Scenario loop
# ============================================================

def run_one_scenario_rescue(scenario, base_net, zones, v2, model, tokenizer):
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

    base_metrics = grid_metrics(net)

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
        current = grid_metrics(net)

        print(f"    [Iteration {it+1}] Global UV: {current['uv_count']} | Vmin={current['vmin']:.4f} | Def={current['deficit_sum']:.5f}")

        if current["uv_count"] == 0:
            result["stop_reason"] = "full_restoration"
            break

        global_uv = global_uv_buses(net)
        zone_reports = {}
        llm_actions = []
        cands = []

        # Ask all agents, not only locally violating agents
        for zone in sorted(zones.keys()):
            zs = extract_zone_state_full(net, zone, zones)
            zone_reports[zone] = zs

            msgs = build_prompt_full(zs, global_uv, failed_actions)
            raw = r.generate_response(model, tokenizer, msgs)
            parsed, valid, parse_err = r.extract_json(raw)
            act = normalize_action(parsed)
            verif = verify_action(net, act)

            if act:
                llm_actions.append(act)
                bus_id = list(act["add_shunts_q_mvar"].keys())[0]
                print(f"      🔹 LLM {zone}: bus={bus_id}, verdict={verif['reason']}")
            else:
                print(f"      🔹 LLM {zone}: null, verdict={verif['reason']}")

            row = {
                "iteration": it + 1,
                "source": "llm_zone_agent",
                "zone": zone,
                "zone_state": zs,
                "global_uv": global_uv,
                "raw": raw,
                "parse_valid": valid,
                "parse_error": parse_err,
                "parsed": parsed,
                "action": act,
                "verif": verif,
            }

            result["logs"].append(row)

            cands.append({
                "source": "llm_zone_agent",
                "zone": zone,
                "action": act,
                "bus": list(act["add_shunts_q_mvar"].keys())[0] if act else None,
                "q_abs": list(act["add_shunts_q_mvar"].values())[0] if act else None,
                "verif": verif,
                "raw": raw,
            })

            if act and not verif["accepted"]:
                sig = action_signature(act)
                failed_sigs.add(sig)
                failed_actions.append({"action": act, "reason": verif["reason"]})

        # Physics-guided refinement: this is the anti-stall layer
        buses = candidate_buses_from_state(net, zones, zone_reports, llm_actions)
        refined = physics_refined_candidates(net, buses, failed_sigs)

        accepted_refined = [c for c in refined if c["verif"]["accepted"]]
        print(f"      🔧 Physics refinement tested {len(refined)} candidates; accepted {len(accepted_refined)}")

        cands.extend(refined)

        accepted = [c for c in cands if c["verif"]["accepted"]]

        if not accepted:
            result["stop_reason"] = "no_accepted_action"
            break

        best = max(accepted, key=score_candidate)

        print(f"      ✅ Executing {best['source']} | zone={best['zone']} | action={best['action']} | score={score_candidate(best)}")

        apply_action(net, best["action"])
        conv, err = r.run_pf(net)

        if not conv:
            result["stop_reason"] = f"execution_pf_failed: {err}"
            break

        post = grid_metrics(net)

        result["executed_actions"].append({
            "iteration": it + 1,
            "source": best["source"],
            "zone": best["zone"],
            "action": best["action"],
            "post_metrics": post,
        })

    final_metrics = grid_metrics(net)
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
    v2 = r.load_v2()
    model, tokenizer = r.load_llm()

    base_net = pp.from_json(str(r.FED_NET))
    meta = json.load(open(r.FED_META))
    zones = {k: [int(x) for x in v] for k, v in meta["zones"].items()}

    scenario_files = sorted(r.SCENARIO_DIRS[0].glob("*.json"))
    if max_scenarios is not None:
        scenario_files = scenario_files[:int(max_scenarios)]

    results = []
    log_path = OUT_DIR / "phase2g_rescue_logs.jsonl"

    if log_path.exists():
        log_path.unlink()

    print(f"\n🚀 Phase 2G Rescue Runner Started. Running {len(scenario_files)} scenarios...")

    for i, sf in enumerate(scenario_files, 1):
        print(f"\n================ SCENARIO [{i}/{len(scenario_files)}]: {sf.stem} ================")

        scenario = json.load(open(sf))
        res = run_one_scenario_rescue(scenario, base_net, zones, v2, model, tokenizer)
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

    for res in results:
        base = res.get("base_metrics") or {}
        final = res.get("final_metrics") or {}

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
        })

    df = pd.DataFrame(rows)
    csv_path = OUT_DIR / "phase2g_rescue_scenario_results.csv"
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
    }

    summary_path = OUT_DIR / "phase2g_rescue_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    compact_path = OUT_DIR / "phase2g_rescue_compact_results.json"
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
