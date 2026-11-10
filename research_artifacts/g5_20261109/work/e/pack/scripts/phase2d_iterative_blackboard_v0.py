
import json
import copy
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pandapower as pp


PHASE1_ROOT = Path("/content/hiergrid_phase1")
PHASE2_ROOT = Path("/content/hiergrid_phase2")

FED_NET_PATH = PHASE1_ROOT / "testbeds/saved_nets/federation_4mg_ieee118.json"
FED_META_PATH = PHASE1_ROOT / "testbeds/metadata/federation_4mg_ieee118_metadata.json"

SCENARIO_DIR_CANDIDATES = [
    PHASE1_ROOT / "scenarios/federation",
    PHASE1_ROOT / "scenarios/federation_4mg_ieee118",
]

OUT_DIR = PHASE2_ROOT / "results/phase2d_iterative_blackboard_v0"
OUT_DIR.mkdir(parents=True, exist_ok=True)

VMIN = 0.95
VMAX = 1.05
MAX_ITERATIONS = 8

# Negative q_mvar in pandapower shunt = capacitive reactive support.
Q_CANDIDATES_MVAR = [-5.0, -10.0, -20.0, -30.0, -50.0, -80.0, -100.0]


def load_metadata(meta_path):
    with open(meta_path) as f:
        meta = json.load(f)

    if "zones" in meta:
        raw_zones = meta["zones"]
    elif "zone_buses" in meta:
        raw_zones = meta["zone_buses"]
    else:
        raise KeyError("Metadata must contain 'zones' or 'zone_buses'.")

    zones = {}
    for z, val in raw_zones.items():
        if isinstance(val, dict) and "buses" in val:
            buses = val["buses"]
        else:
            buses = val
        zones[z] = [int(b) for b in buses]

    return meta, zones


def find_scenario_dir():
    for d in SCENARIO_DIR_CANDIDATES:
        if d.exists():
            return d
    raise FileNotFoundError(f"No scenario directory found among: {SCENARIO_DIR_CANDIDATES}")


def get_zone_for_bus(bus_idx, zones):
    bus_idx = int(bus_idx)
    for zone, buses in zones.items():
        if bus_idx in set(buses):
            return zone
    return "UNKNOWN"


def run_pf(net):
    try:
        pp.runpp(
            net,
            algorithm="nr",
            init="auto",
            enforce_q_lims=True,
            max_iteration=50,
        )
        return bool(net.converged), None
    except Exception as e:
        return False, str(e)


def apply_scenario_to_net(net, scenario, zones):
    for mod in scenario.get("modifications", []):
        action = mod.get("action")

        if action == "scale_all_loads":
            factor = float(mod["factor"])
            net.load["scaling"] = net.load["scaling"].astype(float) * factor

        elif action == "scale_loads_by_zone":
            zone = mod["zone"]
            factor = float(mod["factor"])
            zone_buses = set(zones[zone])

            for load_idx, row in net.load.iterrows():
                if int(row["bus"]) in zone_buses:
                    net.load.at[load_idx, "scaling"] = float(net.load.at[load_idx, "scaling"]) * factor

        elif action == "open_line":
            line_idx = int(mod["line_idx"])
            if line_idx in net.line.index:
                net.line.at[line_idx, "in_service"] = False

        elif action == "drop_sgen_indices":
            for idx in mod.get("sgen_indices", []):
                idx = int(idx)
                if idx in net.sgen.index:
                    net.sgen.at[idx, "p_mw"] = 0.0

        elif action == "drop_all_sgens":
            if len(net.sgen):
                net.sgen["p_mw"] = 0.0

        elif action == "metadata_only_fault_event":
            # These are not actual impedance/current fault injections.
            # Keep as metadata only.
            continue

        else:
            # Unknown modification: do not crash silently.
            print(f"[WARN] Unknown scenario modification skipped: {mod}")

    return net


def grid_metrics(net):
    vm = net.res_bus["vm_pu"].astype(float)

    n_overloaded_lines = 0
    line_loading_max = 0.0
    if hasattr(net, "res_line") and len(net.res_line):
        line_loading = net.res_line["loading_percent"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        n_overloaded_lines = int((line_loading > 100.0).sum())
        line_loading_max = float(line_loading.max())

    n_overloaded_trafos = 0
    trafo_loading_max = 0.0
    if hasattr(net, "res_trafo") and len(net.res_trafo):
        trafo_loading = net.res_trafo["loading_percent"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        n_overloaded_trafos = int((trafo_loading > 100.0).sum())
        trafo_loading_max = float(trafo_loading.max())

    return {
        "vm_min_pu": float(vm.min()),
        "vm_max_pu": float(vm.max()),
        "n_undervoltage": int((vm < VMIN).sum()),
        "n_overvoltage": int((vm > VMAX).sum()),
        "n_overloaded_lines": n_overloaded_lines,
        "n_overloaded_trafos": n_overloaded_trafos,
        "line_loading_max_pct": line_loading_max,
        "trafo_loading_max_pct": trafo_loading_max,
    }


def zone_report(net, zone, zone_buses):
    vm = net.res_bus.loc[zone_buses, "vm_pu"].astype(float)
    uv = vm[vm < VMIN]
    ov = vm[vm > VMAX]

    return {
        "zone": zone,
        "n_buses": len(zone_buses),
        "min_voltage_pu": float(vm.min()),
        "max_voltage_pu": float(vm.max()),
        "mean_voltage_pu": float(vm.mean()),
        "n_undervoltage": int(len(uv)),
        "n_overvoltage": int(len(ov)),
        "worst_bus": int(vm.idxmin()),
        "undervoltage_buses": {int(k): float(v) for k, v in uv.items()},
        "overvoltage_buses": {int(k): float(v) for k, v in ov.items()},
    }


def candidate_buses_for_zone(report, zone_buses, net, max_buses=8):
    """
    Fallback candidate search:
    1. all undervoltage buses in the zone, sorted by lowest voltage
    2. if too few, add other low-voltage zone buses
    """
    zone_vm = net.res_bus.loc[zone_buses, "vm_pu"].astype(float).sort_values()

    buses = []
    for b in zone_vm.index:
        buses.append(int(b))
        if len(buses) >= max_buses:
            break

    return buses


def is_safe_transition(before, after):
    """
    Strict safety rule:
    - Do not worsen global minimum voltage.
    - Do not increase overvoltage count.
    - Do not increase line overload count.
    - Do not increase transformer overload count.
    - Do not exceed hard VMAX.
    """
    if after["vm_min_pu"] < before["vm_min_pu"] - 1e-5:
        return False, "rejected_worsened_min_voltage"

    if after["n_overvoltage"] > before["n_overvoltage"]:
        return False, "rejected_increased_overvoltage_count"

    if after["n_overloaded_lines"] > before["n_overloaded_lines"]:
        return False, "rejected_increased_line_overload_count"

    if after["n_overloaded_trafos"] > before["n_overloaded_trafos"]:
        return False, "rejected_increased_trafo_overload_count"

    if after["vm_max_pu"] > VMAX + 1e-4:
        return False, "rejected_voltage_above_vmax"

    return True, "accepted_safe"


def score_transition(before, after):
    """
    Higher score is better.

    Priority:
    1. reduce undervoltage count
    2. improve minimum voltage
    3. avoid too much overvoltage margin pressure
    """
    uv_reduction = before["n_undervoltage"] - after["n_undervoltage"]
    vm_gain = after["vm_min_pu"] - before["vm_min_pu"]
    vmax_margin_penalty = max(0.0, after["vm_max_pu"] - 1.03)

    return (1000.0 * uv_reduction) + (100.0 * vm_gain) - (10.0 * vmax_margin_penalty)


def test_shunt_action(current_net, bus, q_mvar):
    test_net = copy.deepcopy(current_net)
    pp.create_shunt(
        test_net,
        bus=int(bus),
        q_mvar=float(q_mvar),
        p_mw=0.0,
        name=f"phase2d_shunt_bus{bus}_q{q_mvar}",
    )

    converged, err = run_pf(test_net)
    if not converged:
        return None, "rejected_non_converged", err

    return test_net, "converged", None


def find_best_action_for_iteration(net, zones, taboo):
    before = grid_metrics(net)

    best = None
    rejected_records = []

    reports = {
        zone: zone_report(net, zone, buses)
        for zone, buses in zones.items()
    }

    # Focus on zones with undervoltage first, worst zone first.
    active_zones = sorted(
        [z for z, r in reports.items() if r["n_undervoltage"] > 0],
        key=lambda z: reports[z]["min_voltage_pu"]
    )

    for zone in active_zones:
        buses = zones[zone]
        report = reports[zone]
        cand_buses = candidate_buses_for_zone(report, buses, net)

        for bus in cand_buses:
            for q in Q_CANDIDATES_MVAR:
                action_key = (zone, int(bus), float(q))

                if action_key in taboo:
                    continue

                test_net, status, err = test_shunt_action(net, bus, q)

                if test_net is None:
                    rejected_records.append({
                        "zone": zone,
                        "bus": int(bus),
                        "q_mvar": float(q),
                        "accepted": False,
                        "reason": status,
                        "error": err,
                    })
                    taboo.add(action_key)
                    continue

                after = grid_metrics(test_net)
                safe, reason = is_safe_transition(before, after)

                if not safe:
                    rejected_records.append({
                        "zone": zone,
                        "bus": int(bus),
                        "q_mvar": float(q),
                        "accepted": False,
                        "reason": reason,
                        "before_vm_min_pu": before["vm_min_pu"],
                        "after_vm_min_pu": after["vm_min_pu"],
                        "before_n_undervoltage": before["n_undervoltage"],
                        "after_n_undervoltage": after["n_undervoltage"],
                    })
                    taboo.add(action_key)
                    continue

                score = score_transition(before, after)

                candidate = {
                    "zone": zone,
                    "bus": int(bus),
                    "q_mvar": float(q),
                    "score": float(score),
                    "before": before,
                    "after": after,
                    "net": test_net,
                    "reason": reason,
                }

                if best is None or candidate["score"] > best["score"]:
                    best = candidate

    return best, reports, rejected_records, taboo


def run_blackboard_controller_for_scenario(base_net, scenario, zones):
    scenario_id = scenario.get("scenario_id", scenario.get("id", "unknown_scenario"))

    net = copy.deepcopy(base_net)
    net = apply_scenario_to_net(net, scenario, zones)

    base_converged, base_err = run_pf(net)

    if not base_converged:
        return {
            "scenario_id": scenario_id,
            "base_converged": False,
            "error": base_err,
            "blackboard": [],
            "final_net": None,
        }

    base_metrics = grid_metrics(net)
    current_net = net

    blackboard = []
    taboo = set()
    termination_reason = None

    for iteration in range(MAX_ITERATIONS):
        current_metrics = grid_metrics(current_net)

        if current_metrics["n_undervoltage"] == 0:
            termination_reason = "success_all_voltages_above_vmin"
            break

        best, reports, rejected, taboo = find_best_action_for_iteration(
            current_net,
            zones,
            taboo,
        )

        if best is None:
            termination_reason = "stopped_no_safe_action_found"
            blackboard.append({
                "iteration": iteration,
                "current_metrics": current_metrics,
                "zone_reports": reports,
                "accepted_action": None,
                "rejected_candidates": rejected,
            })
            break

        accepted_action = {
            "zone": best["zone"],
            "bus": best["bus"],
            "q_mvar": best["q_mvar"],
            "score": best["score"],
            "reason": best["reason"],
            "before": best["before"],
            "after": best["after"],
        }

        blackboard.append({
            "iteration": iteration,
            "current_metrics": current_metrics,
            "zone_reports": reports,
            "accepted_action": accepted_action,
            "rejected_candidates": rejected,
        })

        current_net = best["net"]

    else:
        termination_reason = "stopped_max_iterations_reached"

    final_metrics = grid_metrics(current_net)

    return {
        "scenario_id": scenario_id,
        "base_converged": True,
        "base_metrics": base_metrics,
        "final_metrics": final_metrics,
        "termination_reason": termination_reason,
        "accepted_action_count": sum(
            1 for step in blackboard if step.get("accepted_action") is not None
        ),
        "blackboard": blackboard,
        "final_net": current_net,
    }


def main():
    assert FED_NET_PATH.exists(), f"Missing net: {FED_NET_PATH}"
    assert FED_META_PATH.exists(), f"Missing metadata: {FED_META_PATH}"

    scenario_dir = find_scenario_dir()
    scenario_files = sorted(scenario_dir.glob("*.json"))

    print("Using scenario dir:", scenario_dir)
    print("Scenario files:", len(scenario_files))

    meta, zones = load_metadata(FED_META_PATH)
    base_net = pp.from_json(str(FED_NET_PATH))

    scenario_rows = []
    action_rows = []
    raw_blackboards = []

    for i, sf in enumerate(scenario_files):
        with open(sf) as f:
            scenario = json.load(f)

        scenario_id = scenario.get("scenario_id", sf.stem)

        print(f"[{i+1}/{len(scenario_files)}] {scenario_id}")

        result = run_blackboard_controller_for_scenario(base_net, scenario, zones)

        if not result["base_converged"]:
            scenario_rows.append({
                "scenario_id": scenario_id,
                "base_converged": False,
                "error": result.get("error"),
            })
            continue

        b = result["base_metrics"]
        a = result["final_metrics"]

        scenario_rows.append({
            "scenario_id": scenario_id,
            "base_converged": True,

            "base_vm_min_pu": b["vm_min_pu"],
            "final_vm_min_pu": a["vm_min_pu"],
            "base_vm_max_pu": b["vm_max_pu"],
            "final_vm_max_pu": a["vm_max_pu"],

            "base_n_undervoltage": b["n_undervoltage"],
            "final_n_undervoltage": a["n_undervoltage"],
            "base_n_overvoltage": b["n_overvoltage"],
            "final_n_overvoltage": a["n_overvoltage"],

            "base_n_overloaded_lines": b["n_overloaded_lines"],
            "final_n_overloaded_lines": a["n_overloaded_lines"],
            "base_n_overloaded_trafos": b["n_overloaded_trafos"],
            "final_n_overloaded_trafos": a["n_overloaded_trafos"],

            "base_line_loading_max_pct": b["line_loading_max_pct"],
            "final_line_loading_max_pct": a["line_loading_max_pct"],
            "base_trafo_loading_max_pct": b["trafo_loading_max_pct"],
            "final_trafo_loading_max_pct": a["trafo_loading_max_pct"],

            "improved_vm_min": a["vm_min_pu"] > b["vm_min_pu"] + 1e-5,
            "reduced_undervoltage_count": a["n_undervoltage"] < b["n_undervoltage"],

            "accepted_action_count": result["accepted_action_count"],
            "termination_reason": result["termination_reason"],
        })

        for step in result["blackboard"]:
            action = step.get("accepted_action")
            if action is not None:
                action_rows.append({
                    "scenario_id": scenario_id,
                    "iteration": step["iteration"],
                    "zone": action["zone"],
                    "bus": action["bus"],
                    "q_mvar": action["q_mvar"],
                    "score": action["score"],
                    "reason": action["reason"],
                    "before_vm_min_pu": action["before"]["vm_min_pu"],
                    "after_vm_min_pu": action["after"]["vm_min_pu"],
                    "before_n_undervoltage": action["before"]["n_undervoltage"],
                    "after_n_undervoltage": action["after"]["n_undervoltage"],
                })

        raw_blackboards.append({
            "scenario_id": scenario_id,
            "termination_reason": result["termination_reason"],
            "accepted_action_count": result["accepted_action_count"],
            "blackboard": result["blackboard"],
        })

    scenario_df = pd.DataFrame(scenario_rows)
    action_df = pd.DataFrame(action_rows)

    scenario_df.to_csv(OUT_DIR / "phase2d_scenario_results.csv", index=False)
    action_df.to_csv(OUT_DIR / "phase2d_action_results.csv", index=False)

    with open(OUT_DIR / "phase2d_raw_blackboards.json", "w") as f:
        json.dump(raw_blackboards, f, indent=2, default=str)

    converged_df = scenario_df[scenario_df["base_converged"] == True].copy()

    summary = {
        "total_scenarios_seen": int(len(scenario_df)),
        "base_converged": int(converged_df.shape[0]),
        "base_failed": int((scenario_df["base_converged"] == False).sum()),

        "avg_base_vm_min_pu": float(converged_df["base_vm_min_pu"].mean()),
        "avg_final_vm_min_pu": float(converged_df["final_vm_min_pu"].mean()),
        "worst_base_vm_min_pu": float(converged_df["base_vm_min_pu"].min()),
        "worst_final_vm_min_pu": float(converged_df["final_vm_min_pu"].min()),

        "avg_base_undervoltage_count": float(converged_df["base_n_undervoltage"].mean()),
        "avg_final_undervoltage_count": float(converged_df["final_n_undervoltage"].mean()),

        "improved_vm_min_count": int(converged_df["improved_vm_min"].sum()),
        "improved_vm_min_rate": float(converged_df["improved_vm_min"].mean()),

        "reduced_undervoltage_count_cases": int(converged_df["reduced_undervoltage_count"].sum()),
        "reduced_undervoltage_rate": float(converged_df["reduced_undervoltage_count"].mean()),

        "total_accepted_actions": int(action_df.shape[0]),

        "success_all_voltages_above_vmin_count": int(
            (converged_df["termination_reason"] == "success_all_voltages_above_vmin").sum()
        ),
        "success_all_voltages_above_vmin_rate": float(
            (converged_df["termination_reason"] == "success_all_voltages_above_vmin").mean()
        ),
    }

    with open(OUT_DIR / "phase2d_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n================ PHASE 2D SUMMARY ================")
    print(json.dumps(summary, indent=2))
    print("Saved to:", OUT_DIR)


if __name__ == "__main__":
    main()
