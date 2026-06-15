
import sys
import json
import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pandapower as pp

sys.path.append("/content")
import phase2d_iterative_blackboard_v0 as v0


PHASE2_ROOT = Path("/content/hiergrid_phase2")
OUT_DIR = PHASE2_ROOT / "results/phase2d_iterative_blackboard_v2_deficit_aware"
OUT_DIR.mkdir(parents=True, exist_ok=True)

VMIN = 0.95
VMAX = 1.05


MAX_ITERATIONS = 8


Q_CANDIDATES_MVAR = [
    -2.5, -5.0, -10.0, -15.0, -20.0, -30.0,
    -40.0, -50.0, -60.0, -80.0, -100.0,
    -120.0, -150.0
]

MIN_DEFICIT_REDUCTION = 1e-5
MIN_VM_GAIN = 1e-5


def grid_metrics_ext(net):
    base = v0.grid_metrics(net)

    vm = net.res_bus["vm_pu"].astype(float)
    deficit = np.maximum(0.0, VMIN - vm.values)

    base["voltage_deficit_sum_pu"] = float(deficit.sum())
    base["voltage_deficit_max_pu"] = float(deficit.max()) if len(deficit) else 0.0
    base["voltage_deficit_sq_sum_pu"] = float((deficit ** 2).sum())

    if len(vm):
        base["worst_bus"] = int(vm.idxmin())
    else:
        base["worst_bus"] = -1

    return base


def zone_report_ext(net, zone, zone_buses):
    r = v0.zone_report(net, zone, zone_buses)

    vm = net.res_bus.loc[zone_buses, "vm_pu"].astype(float)
    deficit = np.maximum(0.0, VMIN - vm.values)

    r["voltage_deficit_sum_pu"] = float(deficit.sum())
    r["voltage_deficit_max_pu"] = float(deficit.max()) if len(deficit) else 0.0
    r["voltage_deficit_sq_sum_pu"] = float((deficit ** 2).sum())

    return r


def candidate_buses_deficit_aware(net, zone_buses, max_buses=14):
    """
    Use the lowest-voltage buses in the active zone.
    This protects the worst buses directly.
    """
    vm = net.res_bus.loc[zone_buses, "vm_pu"].astype(float).sort_values()
    return [int(b) for b in vm.index[:max_buses]]


def strict_safety_check(before, after):
    """
    Absolute safety:
    - do not increase overvoltage count
    - do not increase line overload count
    - do not increase transformer overload count
    - do not violate hard VMAX
    - do not reduce global minimum voltage
    - do not increase total voltage deficit
    - do not increase worst voltage deficit
    """

    if after["n_overvoltage"] > before["n_overvoltage"]:
        return False, "rejected_increased_overvoltage_count"

    if after["n_overloaded_lines"] > before["n_overloaded_lines"]:
        return False, "rejected_increased_line_overload_count"

    if after["n_overloaded_trafos"] > before["n_overloaded_trafos"]:
        return False, "rejected_increased_trafo_overload_count"

    if after["vm_max_pu"] > VMAX + 1e-4:
        return False, "rejected_voltage_above_vmax"

    if after["vm_min_pu"] < before["vm_min_pu"] - 1e-6:
        return False, "rejected_worsened_min_voltage"

    if after["voltage_deficit_sum_pu"] > before["voltage_deficit_sum_pu"] + 1e-7:
        return False, "rejected_increased_total_voltage_deficit"

    if after["voltage_deficit_max_pu"] > before["voltage_deficit_max_pu"] + 1e-7:
        return False, "rejected_increased_worst_voltage_deficit"

    return True, "passed_safety"


def helpfulness_check(before, after):
    uv_reduction = before["n_undervoltage"] - after["n_undervoltage"]
    vm_gain = after["vm_min_pu"] - before["vm_min_pu"]
    deficit_reduction = before["voltage_deficit_sum_pu"] - after["voltage_deficit_sum_pu"]
    worst_deficit_reduction = before["voltage_deficit_max_pu"] - after["voltage_deficit_max_pu"]

    if uv_reduction > 0:
        return True, "accepted_reduced_undervoltage_count"

    if vm_gain > MIN_VM_GAIN:
        return True, "accepted_improved_min_voltage"

    if deficit_reduction > MIN_DEFICIT_REDUCTION:
        return True, "accepted_reduced_total_voltage_deficit"

    if worst_deficit_reduction > MIN_DEFICIT_REDUCTION:
        return True, "accepted_reduced_worst_voltage_deficit"

    return False, "rejected_no_voltage_deficit_benefit"


def candidate_rank_key(before, after, q_mvar):
    """
    Lexicographic selection:
    1. full restoration
    2. highest final minimum voltage
    3. lowest total voltage deficit
    4. lowest worst voltage deficit
    5. lowest remaining undervoltage count
    6. largest deficit reduction
    7. smaller control magnitude
    """

    full_restoration = 1 if after["n_undervoltage"] == 0 else 0

    deficit_reduction = before["voltage_deficit_sum_pu"] - after["voltage_deficit_sum_pu"]
    worst_deficit_reduction = before["voltage_deficit_max_pu"] - after["voltage_deficit_max_pu"]
    uv_reduction = before["n_undervoltage"] - after["n_undervoltage"]
    vm_gain = after["vm_min_pu"] - before["vm_min_pu"]

    return (
        full_restoration,
        after["vm_min_pu"],
        -after["voltage_deficit_sum_pu"],
        -after["voltage_deficit_max_pu"],
        -after["n_undervoltage"],
        deficit_reduction,
        worst_deficit_reduction,
        uv_reduction,
        vm_gain,
        -abs(float(q_mvar)),
    )


def find_best_action_for_iteration_v2(current_net, zones, taboo):
    before = grid_metrics_ext(current_net)

    reports = {
        zone: zone_report_ext(current_net, zone, buses)
        for zone, buses in zones.items()
    }

    # Active zones sorted by worst voltage first, then total deficit.
    active_zones = sorted(
        [z for z, r in reports.items() if r["n_undervoltage"] > 0],
        key=lambda z: (
            reports[z]["min_voltage_pu"],
            -reports[z]["voltage_deficit_sum_pu"]
        )
    )

    best = None
    rejected_records = []

    for zone in active_zones:
        zone_buses = zones[zone]
        candidate_buses = candidate_buses_deficit_aware(
            current_net,
            zone_buses,
            max_buses=14,
        )

        for bus in candidate_buses:
            for q_mvar in Q_CANDIDATES_MVAR:
                action_key = (zone, int(bus), float(q_mvar))

                if action_key in taboo:
                    continue

                test_net, status, err = v0.test_shunt_action(
                    current_net,
                    bus,
                    q_mvar,
                )

                if test_net is None:
                    rejected_records.append({
                        "zone": zone,
                        "bus": int(bus),
                        "q_mvar": float(q_mvar),
                        "accepted": False,
                        "reason": status,
                        "error": err,
                    })
                    taboo.add(action_key)
                    continue

                after = grid_metrics_ext(test_net)

                safe, safety_reason = strict_safety_check(before, after)
                if not safe:
                    rejected_records.append({
                        "zone": zone,
                        "bus": int(bus),
                        "q_mvar": float(q_mvar),
                        "accepted": False,
                        "reason": safety_reason,
                        "before_vm_min_pu": before["vm_min_pu"],
                        "after_vm_min_pu": after["vm_min_pu"],
                        "before_deficit_sum": before["voltage_deficit_sum_pu"],
                        "after_deficit_sum": after["voltage_deficit_sum_pu"],
                        "before_n_undervoltage": before["n_undervoltage"],
                        "after_n_undervoltage": after["n_undervoltage"],
                    })
                    taboo.add(action_key)
                    continue

                helpful, helpful_reason = helpfulness_check(before, after)
                if not helpful:
                    rejected_records.append({
                        "zone": zone,
                        "bus": int(bus),
                        "q_mvar": float(q_mvar),
                        "accepted": False,
                        "reason": helpful_reason,
                        "before_vm_min_pu": before["vm_min_pu"],
                        "after_vm_min_pu": after["vm_min_pu"],
                        "before_deficit_sum": before["voltage_deficit_sum_pu"],
                        "after_deficit_sum": after["voltage_deficit_sum_pu"],
                        "before_n_undervoltage": before["n_undervoltage"],
                        "after_n_undervoltage": after["n_undervoltage"],
                    })
                    taboo.add(action_key)
                    continue

                rank_key = candidate_rank_key(before, after, q_mvar)

                candidate = {
                    "zone": zone,
                    "bus": int(bus),
                    "q_mvar": float(q_mvar),
                    "rank_key": rank_key,
                    "before": before,
                    "after": after,
                    "net": test_net,
                    "reason": helpful_reason,
                }

                if best is None or candidate["rank_key"] > best["rank_key"]:
                    best = candidate

    return best, reports, rejected_records, taboo


def run_blackboard_controller_for_scenario_v2(base_net, scenario, zones):
    scenario_id = scenario.get("scenario_id", scenario.get("id", "unknown_scenario"))

    net = copy.deepcopy(base_net)
    net = v0.apply_scenario_to_net(net, scenario, zones)

    base_converged, base_err = v0.run_pf(net)

    if not base_converged:
        return {
            "scenario_id": scenario_id,
            "base_converged": False,
            "error": base_err,
            "blackboard": [],
            "final_net": None,
        }

    base_metrics = grid_metrics_ext(net)
    current_net = net

    blackboard = []
    taboo = set()
    termination_reason = None

    for iteration in range(MAX_ITERATIONS):
        current_metrics = grid_metrics_ext(current_net)

        if current_metrics["n_undervoltage"] == 0:
            termination_reason = "success_all_voltages_above_vmin"
            break

        best, reports, rejected, taboo = find_best_action_for_iteration_v2(
            current_net,
            zones,
            taboo,
        )

        if best is None:
            termination_reason = "stopped_no_deficit_reducing_safe_action_found"
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
            "rank_key": list(best["rank_key"]),
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

        taboo.add((best["zone"], int(best["bus"]), float(best["q_mvar"])))
        current_net = best["net"]

    else:
        termination_reason = "stopped_max_iterations_reached"

    final_metrics = grid_metrics_ext(current_net)

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
    assert v0.FED_NET_PATH.exists(), f"Missing net: {v0.FED_NET_PATH}"
    assert v0.FED_META_PATH.exists(), f"Missing metadata: {v0.FED_META_PATH}"

    scenario_dir = v0.find_scenario_dir()
    scenario_files = sorted(scenario_dir.glob("*.json"))

    print("Using scenario dir:", scenario_dir)
    print("Scenario files:", len(scenario_files))

    meta, zones = v0.load_metadata(v0.FED_META_PATH)
    base_net = pp.from_json(str(v0.FED_NET_PATH))

    scenario_rows = []
    action_rows = []
    raw_blackboards = []

    for i, sf in enumerate(scenario_files):
        with open(sf) as f:
            scenario = json.load(f)

        scenario_id = scenario.get("scenario_id", sf.stem)

        print(f"[{i+1}/{len(scenario_files)}] {scenario_id}")

        result = run_blackboard_controller_for_scenario_v2(
            base_net,
            scenario,
            zones,
        )

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

            "base_voltage_deficit_sum_pu": b["voltage_deficit_sum_pu"],
            "final_voltage_deficit_sum_pu": a["voltage_deficit_sum_pu"],
            "base_voltage_deficit_max_pu": b["voltage_deficit_max_pu"],
            "final_voltage_deficit_max_pu": a["voltage_deficit_max_pu"],
            "base_voltage_deficit_sq_sum_pu": b["voltage_deficit_sq_sum_pu"],
            "final_voltage_deficit_sq_sum_pu": a["voltage_deficit_sq_sum_pu"],

            "improved_vm_min": a["vm_min_pu"] > b["vm_min_pu"] + 1e-5,
            "reduced_undervoltage_count": a["n_undervoltage"] < b["n_undervoltage"],
            "reduced_voltage_deficit_sum": a["voltage_deficit_sum_pu"] < b["voltage_deficit_sum_pu"] - 1e-7,

            "accepted_action_count": result["accepted_action_count"],
            "termination_reason": result["termination_reason"],
            "error": None,
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
                    "reason": action["reason"],

                    "before_vm_min_pu": action["before"]["vm_min_pu"],
                    "after_vm_min_pu": action["after"]["vm_min_pu"],

                    "before_n_undervoltage": action["before"]["n_undervoltage"],
                    "after_n_undervoltage": action["after"]["n_undervoltage"],

                    "before_voltage_deficit_sum_pu": action["before"]["voltage_deficit_sum_pu"],
                    "after_voltage_deficit_sum_pu": action["after"]["voltage_deficit_sum_pu"],

                    "before_voltage_deficit_max_pu": action["before"]["voltage_deficit_max_pu"],
                    "after_voltage_deficit_max_pu": action["after"]["voltage_deficit_max_pu"],
                })

        raw_blackboards.append({
            "scenario_id": scenario_id,
            "termination_reason": result["termination_reason"],
            "accepted_action_count": result["accepted_action_count"],
            "blackboard": result["blackboard"],
        })

    scenario_df = pd.DataFrame(scenario_rows)
    action_df = pd.DataFrame(action_rows)

    scenario_df.to_csv(OUT_DIR / "phase2d_v2_scenario_results.csv", index=False)
    action_df.to_csv(OUT_DIR / "phase2d_v2_action_results.csv", index=False)

    with open(OUT_DIR / "phase2d_v2_raw_blackboards.json", "w") as f:
        json.dump(raw_blackboards, f, indent=2, default=str)

    conv = scenario_df[scenario_df["base_converged"] == True].copy()

    summary = {
        "controller_version": "phase2d_iterative_blackboard_v2_deficit_aware",
        "total_scenarios_seen": int(len(scenario_df)),
        "base_converged": int(conv.shape[0]),
        "base_failed": int((scenario_df["base_converged"] == False).sum()),

        "avg_base_vm_min_pu": float(conv["base_vm_min_pu"].mean()),
        "avg_final_vm_min_pu": float(conv["final_vm_min_pu"].mean()),
        "worst_base_vm_min_pu": float(conv["base_vm_min_pu"].min()),
        "worst_final_vm_min_pu": float(conv["final_vm_min_pu"].min()),

        "avg_base_undervoltage_count": float(conv["base_n_undervoltage"].mean()),
        "avg_final_undervoltage_count": float(conv["final_n_undervoltage"].mean()),

        "avg_base_voltage_deficit_sum_pu": float(conv["base_voltage_deficit_sum_pu"].mean()),
        "avg_final_voltage_deficit_sum_pu": float(conv["final_voltage_deficit_sum_pu"].mean()),
        "worst_base_voltage_deficit_max_pu": float(conv["base_voltage_deficit_max_pu"].max()),
        "worst_final_voltage_deficit_max_pu": float(conv["final_voltage_deficit_max_pu"].max()),

        "improved_vm_min_count": int(conv["improved_vm_min"].sum()),
        "improved_vm_min_rate": float(conv["improved_vm_min"].mean()),

        "reduced_undervoltage_count_cases": int(conv["reduced_undervoltage_count"].sum()),
        "reduced_undervoltage_rate": float(conv["reduced_undervoltage_count"].mean()),

        "reduced_voltage_deficit_sum_cases": int(conv["reduced_voltage_deficit_sum"].sum()),
        "reduced_voltage_deficit_sum_rate": float(conv["reduced_voltage_deficit_sum"].mean()),

        "total_accepted_actions": int(action_df.shape[0]),

        "success_all_voltages_above_vmin_count": int(
            (conv["termination_reason"] == "success_all_voltages_above_vmin").sum()
        ),
        "success_all_voltages_above_vmin_rate": float(
            (conv["termination_reason"] == "success_all_voltages_above_vmin").mean()
        ),
    }

    with open(OUT_DIR / "phase2d_v2_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n================ PHASE 2D-v2 SUMMARY ================")
    print(json.dumps(summary, indent=2))
    print("Saved to:", OUT_DIR)


if __name__ == "__main__":
    main()
