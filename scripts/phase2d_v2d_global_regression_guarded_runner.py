
# ============================================================
# Phase 2D-v2D: Coordinated Global Regression-Guarded Controller
# ============================================================

import os
import sys
import json
import copy
import time
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pandapower as pp


# -----------------------------
# Config
# -----------------------------
MODE = os.environ.get("V2D_MODE", "hard").strip().lower()  # "hard" or "all"

V2_SCRIPT = Path("/content/phase2d_iterative_blackboard_v2_deficit_aware.py")
BASE_NET_PATH = Path("/content/hiergrid_phase1/testbeds/saved_nets/federation_4mg_ieee118.json")
METADATA_PATH = Path("/content/hiergrid_phase1/testbeds/metadata/federation_4mg_ieee118_metadata.json")
SCENARIO_DIR = Path("/content/hiergrid_phase1/scenarios/federation")

V2B_CSV = Path("/content/hiergrid_phase2/results/phase2d_iterative_blackboard_v2b_iter12/phase2d_v2b_scenario_results.csv")
V2R_COMP_CSV = Path("/content/hiergrid_phase2/results/phase2d_v2r_rag_taboo_all141/phase2d_v2r_vs_v2b_STRICT_VALIDATED.csv")
HARD_JSON = Path("/content/hiergrid_phase2/results/phase2d_v2r_rag_taboo_all141/v2r_hard_cases_for_v2d.json")

OUT_ROOT = Path("/content/hiergrid_phase2/results")
OUT_DIR = OUT_ROOT / ("phase2d_v2d_global_guard_hard" if MODE == "hard" else "phase2d_v2d_global_guard_all141")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIO_CSV = OUT_DIR / "phase2d_v2d_scenario_results.csv"
ACTION_CSV = OUT_DIR / "phase2d_v2d_action_results.csv"
SUMMARY_JSON = OUT_DIR / "phase2d_v2d_summary.json"

MAX_ITERATIONS = int(os.environ.get("V2D_MAX_ITERATIONS", "12"))
MAX_BUSES_PER_ITER = int(os.environ.get("V2D_MAX_BUSES_PER_ITER", "12"))

# Same spirit as v2R/v2b: capacitive shunt candidates are negative q_mvar.
Q_CANDIDATES = [
    -120.0, -100.0, -80.0, -60.0, -50.0, -40.0,
    -30.0, -20.0, -15.0, -10.0, -5.0, -2.5
]

VMIN = 0.95
VMAX = 1.05
LOAD_LIMIT = 100.0
BASE_TOL = 1e-8
RESUME = True


# -----------------------------
# Load trusted v2 exactly
# -----------------------------
assert V2_SCRIPT.exists(), f"Missing trusted v2 script: {V2_SCRIPT}"

spec = importlib.util.spec_from_file_location("trusted_v2_exact_v2d", str(V2_SCRIPT))
v2 = importlib.util.module_from_spec(spec)
sys.modules["trusted_v2_exact_v2d"] = v2
spec.loader.exec_module(v2)

assert hasattr(v2, "v0")
assert hasattr(v2.v0, "apply_scenario_to_net")
assert hasattr(v2.v0, "run_pf")

print("[v2D] Loaded trusted v2:", V2_SCRIPT)


# -----------------------------
# Helpers
# -----------------------------
def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def run_pf(net):
    return v2.v0.run_pf(net)


def get_zones(metadata):
    zones = (
        metadata.get("zones")
        or metadata.get("zone_map")
        or metadata.get("zone_definitions")
        or metadata.get("microgrid_zones")
    )
    if zones is None:
        raise KeyError(f"Could not find zones in metadata keys: {metadata.keys()}")
    return zones


def metrics(net):
    vm = net.res_bus.vm_pu.dropna().astype(float)

    if len(vm) == 0:
        return {
            "vm_min_pu": np.nan,
            "vm_max_pu": np.nan,
            "n_undervoltage": np.nan,
            "n_overvoltage": np.nan,
            "voltage_deficit_sum_pu": np.nan,
            "voltage_deficit_max_pu": np.nan,
            "line_loading_max_pct": np.nan,
            "trafo_loading_max_pct": np.nan,
            "n_overloaded_lines": np.nan,
            "n_overloaded_trafos": np.nan,
        }

    deficit = (VMIN - vm).clip(lower=0.0)

    if hasattr(net, "res_line") and len(net.res_line) > 0 and "loading_percent" in net.res_line:
        line_loading = pd.to_numeric(net.res_line.loading_percent, errors="coerce").dropna()
    else:
        line_loading = pd.Series(dtype=float)

    if hasattr(net, "res_trafo") and len(net.res_trafo) > 0 and "loading_percent" in net.res_trafo:
        trafo_loading = pd.to_numeric(net.res_trafo.loading_percent, errors="coerce").dropna()
    else:
        trafo_loading = pd.Series(dtype=float)

    return {
        "vm_min_pu": float(vm.min()),
        "vm_max_pu": float(vm.max()),
        "n_undervoltage": int((vm < VMIN).sum()),
        "n_overvoltage": int((vm > VMAX).sum()),
        "voltage_deficit_sum_pu": float(deficit.sum()),
        "voltage_deficit_max_pu": float(deficit.max()) if len(deficit) else 0.0,
        "line_loading_max_pct": float(line_loading.max()) if len(line_loading) else 0.0,
        "trafo_loading_max_pct": float(trafo_loading.max()) if len(trafo_loading) else 0.0,
        "n_overloaded_lines": int((line_loading > LOAD_LIMIT).sum()) if len(line_loading) else 0,
        "n_overloaded_trafos": int((trafo_loading > LOAD_LIMIT).sum()) if len(trafo_loading) else 0,
    }


def prefix_metrics(prefix, m):
    return {f"{prefix}_{k}": v for k, v in m.items()}


def safety_non_degrading(candidate, current):
    """
    Hard safety guard:
    no increase in discrete safety violations.
    Loading magnitudes are handled as tie-breakers in objective.
    """
    hard_keys = [
        "n_overvoltage",
        "n_overloaded_lines",
        "n_overloaded_trafos",
    ]
    for k in hard_keys:
        if candidate[k] > current[k]:
            return False
    return True


def objective_tuple(m):
    """
    Lower is better.
    Global lexicographic score:
    1. fewer undervoltage buses,
    2. lower voltage deficit,
    3. higher minimum voltage,
    4. lower max line loading,
    5. lower max transformer loading,
    6. lower max overvoltage,
    7. lower voltage deficit max.
    """
    return (
        int(m["n_undervoltage"]),
        float(m["voltage_deficit_sum_pu"]),
        -float(m["vm_min_pu"]),
        float(m["line_loading_max_pct"]),
        float(m["trafo_loading_max_pct"]),
        int(m["n_overvoltage"]),
        float(m["voltage_deficit_max_pu"]),
    )


def strictly_better(candidate, current, eps=1e-10):
    c = objective_tuple(candidate)
    b = objective_tuple(current)

    for x, y in zip(c, b):
        if x < y - eps:
            return True
        if x > y + eps:
            return False

    return False


def get_ext_grid_buses(net):
    buses = set()
    if hasattr(net, "ext_grid") and len(net.ext_grid) > 0 and "bus" in net.ext_grid:
        buses.update(int(x) for x in net.ext_grid.bus.dropna().astype(int).tolist())
    return buses


def get_neighbor_buses(net, seed_buses):
    seed = set(int(x) for x in seed_buses)
    neigh = set(seed)

    if hasattr(net, "line") and len(net.line) > 0:
        for _, row in net.line.iterrows():
            fb = int(row["from_bus"])
            tb = int(row["to_bus"])
            if fb in seed or tb in seed:
                neigh.add(fb)
                neigh.add(tb)

    return neigh


def candidate_buses(net, max_buses=12):
    vm = net.res_bus.vm_pu.dropna().astype(float)
    if len(vm) == 0:
        return []

    uv = vm[vm < VMIN].sort_values().index.astype(int).tolist()

    if len(uv) == 0:
        # If already restored, no need candidates.
        return []

    expanded = get_neighbor_buses(net, uv)
    slack = get_ext_grid_buses(net)

    allowed = []
    for b in expanded:
        if b in slack:
            continue
        if b not in net.bus.index:
            continue
        allowed.append(int(b))

    # Sort candidate buses by current voltage, lowest first.
    allowed = sorted(set(allowed), key=lambda b: float(vm.loc[b]) if b in vm.index else 999.0)

    return allowed[:max_buses]


def apply_shunt_candidate(net, bus, q_mvar, scenario_id, iteration):
    test = copy.deepcopy(net)

    pp.create_shunt(
        test,
        bus=int(bus),
        q_mvar=float(q_mvar),
        p_mw=0.0,
        name=f"v2d_{scenario_id}_iter{iteration}_bus{bus}_q{q_mvar}",
        in_service=True,
    )

    converged, err = run_pf(test)
    if not converged:
        return None, None, err

    return test, metrics(test), None


def load_v2b_lookup():
    assert V2B_CSV.exists(), f"Missing v2b CSV: {V2B_CSV}"
    df = pd.read_csv(V2B_CSV)
    return {
        str(row["scenario_id"]): row
        for _, row in df.iterrows()
    }


def check_base_match(scenario_id, base_metrics, v2b_lookup):
    sid = str(scenario_id)
    if sid not in v2b_lookup:
        raise RuntimeError(f"scenario_id missing in v2b lookup: {sid}")

    row = v2b_lookup[sid]

    v2b_vm = float(row["base_vm_min_pu"])
    v2b_uv = int(row["base_n_undervoltage"])

    my_vm = float(base_metrics["vm_min_pu"])
    my_uv = int(base_metrics["n_undervoltage"])

    vm_diff = abs(my_vm - v2b_vm)
    uv_diff = my_uv - v2b_uv

    if vm_diff > BASE_TOL or uv_diff != 0:
        raise RuntimeError(
            f"\n[v2D] BASE MISMATCH\n"
            f"scenario_id={sid}\n"
            f"v2D base vm={my_vm}, v2b base vm={v2b_vm}, diff={vm_diff}\n"
            f"v2D base uv={my_uv}, v2b base uv={v2b_uv}, diff={uv_diff}\n"
        )


def apply_scenario_exact(base_net, scenario, zones):
    net = copy.deepcopy(base_net)
    net = v2.v0.apply_scenario_to_net(net, scenario, zones)
    converged, err = run_pf(net)
    return net, converged, err


def run_one_scenario(sf, base_net, zones, v2b_lookup):
    scenario = load_json(sf)
    scenario_id = str(scenario.get("scenario_id", sf.stem))

    row = {
        "scenario_id": scenario_id,
        "scenario_file": str(sf),
        "mode": MODE,
        "base_converged": False,
        "base_error": None,
        "termination_reason": None,
        "accepted_actions": 0,
        "iterations": 0,
    }

    actions = []

    net, base_converged, base_err = apply_scenario_exact(base_net, scenario, zones)
    row["base_converged"] = bool(base_converged)
    row["base_error"] = str(base_err) if base_err is not None else None

    if not base_converged:
        row["termination_reason"] = "base_not_converged"
        return row, actions

    base_m = metrics(net)
    check_base_match(scenario_id, base_m, v2b_lookup)

    row.update(prefix_metrics("base", base_m))

    current_net = copy.deepcopy(net)
    current_m = dict(base_m)

    termination = None

    for it in range(1, MAX_ITERATIONS + 1):
        row["iterations"] = it

        if int(current_m["n_undervoltage"]) == 0:
            termination = "success_all_voltages_above_vmin"
            break

        buses = candidate_buses(current_net, MAX_BUSES_PER_ITER)

        if not buses:
            termination = "stopped_no_undervoltage_candidate_buses"
            break

        best = None

        for bus in buses:
            for q in Q_CANDIDATES:
                test_net, test_m, err = apply_shunt_candidate(current_net, bus, q, scenario_id, it)

                if test_net is None:
                    continue

                if not safety_non_degrading(test_m, current_m):
                    continue

                if not strictly_better(test_m, current_m):
                    continue

                if best is None or objective_tuple(test_m) < objective_tuple(best["metrics"]):
                    best = {
                        "bus": int(bus),
                        "q_mvar": float(q),
                        "net": test_net,
                        "metrics": test_m,
                    }

        if best is None:
            termination = "stopped_no_global_regression_guarded_action_found"
            break

        before_m = dict(current_m)

        current_net = best["net"]
        current_m = best["metrics"]

        actions.append({
            "scenario_id": scenario_id,
            "iteration": it,
            "bus": best["bus"],
            "q_mvar": best["q_mvar"],
            "before_vm_min_pu": before_m["vm_min_pu"],
            "after_vm_min_pu": current_m["vm_min_pu"],
            "before_n_undervoltage": before_m["n_undervoltage"],
            "after_n_undervoltage": current_m["n_undervoltage"],
            "before_voltage_deficit_sum_pu": before_m["voltage_deficit_sum_pu"],
            "after_voltage_deficit_sum_pu": current_m["voltage_deficit_sum_pu"],
            "before_line_loading_max_pct": before_m["line_loading_max_pct"],
            "after_line_loading_max_pct": current_m["line_loading_max_pct"],
            "before_trafo_loading_max_pct": before_m["trafo_loading_max_pct"],
            "after_trafo_loading_max_pct": current_m["trafo_loading_max_pct"],
        })

    else:
        termination = "stopped_max_iterations_reached"

    if termination is None:
        termination = "success_all_voltages_above_vmin" if current_m["n_undervoltage"] == 0 else "stopped_unknown"

    row["termination_reason"] = termination
    row["accepted_actions"] = len(actions)
    row.update(prefix_metrics("final", current_m))

    return row, actions


def summarize(scenario_rows):
    df = pd.DataFrame(scenario_rows)

    if len(df) == 0:
        return {}

    conv = df[df["base_converged"] == True].copy()

    numeric_cols = [
        "base_vm_min_pu", "base_n_undervoltage", "base_voltage_deficit_sum_pu",
        "final_vm_min_pu", "final_n_undervoltage", "final_voltage_deficit_sum_pu",
        "final_n_overvoltage", "final_n_overloaded_lines", "final_n_overloaded_trafos",
        "final_line_loading_max_pct", "final_trafo_loading_max_pct",
        "accepted_actions", "iterations"
    ]

    for c in numeric_cols:
        if c in conv.columns:
            conv[c] = pd.to_numeric(conv[c], errors="coerce")

    summary = {
        "mode": MODE,
        "total_rows": int(len(df)),
        "base_converged": int(len(conv)),
        "base_failed": int((df["base_converged"] != True).sum()) if "base_converged" in df else None,
        "avg_final_vm_min_pu": float(conv["final_vm_min_pu"].mean()) if "final_vm_min_pu" in conv else None,
        "worst_final_vm_min_pu": float(conv["final_vm_min_pu"].min()) if "final_vm_min_pu" in conv else None,
        "avg_final_undervoltage_count": float(conv["final_n_undervoltage"].mean()) if "final_n_undervoltage" in conv else None,
        "full_voltage_restoration_rate": float((conv["final_n_undervoltage"] == 0).mean()) if "final_n_undervoltage" in conv else None,
        "avg_final_voltage_deficit_sum_pu": float(conv["final_voltage_deficit_sum_pu"].mean()) if "final_voltage_deficit_sum_pu" in conv else None,
        "avg_accepted_actions": float(conv["accepted_actions"].mean()) if "accepted_actions" in conv else None,
        "termination_counts": conv["termination_reason"].value_counts(dropna=False).astype(str).to_dict() if "termination_reason" in conv else {},
    }

    return summary


def main():
    print("=" * 70)
    print("Phase 2D-v2D: Coordinated Global Regression-Guarded Controller")
    print("=" * 70)
    print("MODE:", MODE)
    print("OUT_DIR:", OUT_DIR)
    print("MAX_ITERATIONS:", MAX_ITERATIONS)
    print("MAX_BUSES_PER_ITER:", MAX_BUSES_PER_ITER)

    for p in [BASE_NET_PATH, METADATA_PATH, SCENARIO_DIR, V2B_CSV]:
        assert p.exists(), f"Missing required path: {p}"

    base_net = pp.from_json(str(BASE_NET_PATH))
    metadata = load_json(METADATA_PATH)
    zones = get_zones(metadata)

    v2b_lookup = load_v2b_lookup()

    scenario_files = sorted(SCENARIO_DIR.glob("*.json"))

    if MODE == "hard":
        assert HARD_JSON.exists(), f"Missing hard-case JSON: {HARD_JSON}"
        hard_ids = set(load_json(HARD_JSON)["scenario_ids"])
        scenario_files = [p for p in scenario_files if p.stem in hard_ids]
        print("Hard-case scenario files:", len(scenario_files))
    else:
        print("All scenario files:", len(scenario_files))

    scenario_rows = []
    action_rows = []
    completed = set()

    if RESUME and SCENARIO_CSV.exists():
        prev = pd.read_csv(SCENARIO_CSV)
        if "scenario_id" in prev.columns:
            scenario_rows = prev.to_dict("records")
            completed = set(prev["scenario_id"].astype(str))
            print("[RESUME] completed scenarios:", len(completed))

    if RESUME and ACTION_CSV.exists():
        prev_a = pd.read_csv(ACTION_CSV)
        action_rows = prev_a.to_dict("records")
        print("[RESUME] previous actions:", len(action_rows))

    t0 = time.time()

    for idx, sf in enumerate(scenario_files, start=1):
        sid = sf.stem

        if sid in completed:
            print(f"[{idx}/{len(scenario_files)}] SKIP {sid}")
            continue

        print(f"\n[{idx}/{len(scenario_files)}] RUN {sid}")

        try:
            row, actions = run_one_scenario(sf, base_net, zones, v2b_lookup)
            scenario_rows.append(row)
            action_rows.extend(actions)
            completed.add(str(row["scenario_id"]))

            pd.DataFrame(scenario_rows).drop_duplicates("scenario_id", keep="last").to_csv(SCENARIO_CSV, index=False)
            pd.DataFrame(action_rows).to_csv(ACTION_CSV, index=False)

            print(
                f"  term={row.get('termination_reason')} | "
                f"base_uv={row.get('base_n_undervoltage')} -> final_uv={row.get('final_n_undervoltage')} | "
                f"base_vm={row.get('base_vm_min_pu')} -> final_vm={row.get('final_vm_min_pu')} | "
                f"actions={row.get('accepted_actions')}"
            )

        except Exception as e:
            print("  ERROR:", repr(e))
            raise

    summary = summarize(scenario_rows)
    save_json(SUMMARY_JSON, summary)

    print("\n" + "=" * 70)
    print("v2D SUMMARY")
    print("=" * 70)
    print(json.dumps(summary, indent=2))
    print("Scenario CSV:", SCENARIO_CSV)
    print("Action CSV:", ACTION_CSV)
    print("Summary JSON:", SUMMARY_JSON)
    print("Elapsed minutes:", round((time.time() - t0) / 60.0, 2))


if __name__ == "__main__":
    main()
