
import sys
import json
import copy
import math
import inspect
from pathlib import Path
from collections import Counter, defaultdict

import pandas as pd
import pandapower as pp


import importlib.util as _v2_importlib_util
import sys as _v2_sys
import copy as _v2_copy

_TRUSTED_V2_SCRIPT = "/content/phase2d_iterative_blackboard_v2_deficit_aware.py"


for _k in list(_v2_sys.modules.keys()):
    if "phase2d" in _k or "iterative_blackboard" in _k:
        del _v2_sys.modules[_k]

_v2_spec = _v2_importlib_util.spec_from_file_location("trusted_v2_exact", _TRUSTED_V2_SCRIPT)
v2 = _v2_importlib_util.module_from_spec(_v2_spec)
_v2_sys.modules["trusted_v2_exact"] = v2
_v2_spec.loader.exec_module(v2)

assert hasattr(v2, "v0"), "trusted v2 module has no v0"
assert hasattr(v2.v0, "apply_scenario_to_net"), "trusted v2.v0 has no apply_scenario_to_net"
assert hasattr(v2.v0, "run_pf"), "trusted v2.v0 has no run_pf"

print("[PATCH CHECK] Loaded trusted v2 from:", _TRUSTED_V2_SCRIPT)


# ============================================================
# LIVE BASE-MATCH GATE AGAINST TRUSTED v2b - ADDED BY PATCH
# ============================================================

ENABLE_LIVE_BASE_GATE = True
BASE_VM_TOL = 1e-8

def _live_gate_pick_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(
        f"None of these columns found: {candidates}\n"
        f"Available columns: {df.columns.tolist()}"
    )

def _auto_find_v2b_csv():
    import glob
    import pandas as pd
    import os

    candidates = glob.glob("/content/hiergrid_phase2/results/**/*.csv", recursive=True)

    scored = []
    for path in candidates:
        lower = path.lower()

        # Prefer v2b files, but still inspect all CSVs
        score = 0
        if "v2b" in lower:
            score += 100
        if "extended" in lower:
            score += 25
        if "phase2d" in lower:
            score += 10
        if "comparison" in lower:
            score -= 50
        if "v2r" in lower:
            score -= 100

        try:
            df_head = pd.read_csv(path, nrows=5)
            cols = set(df_head.columns)

            has_sid = "scenario_id" in cols
            has_vm = ("base_vm_min" in cols) or ("base_vm_min_pu" in cols)
            has_uv = ("base_undervoltage_count" in cols) or ("base_n_undervoltage" in cols)

            if has_sid and has_vm and has_uv:
                scored.append((score, path))
        except Exception:
            pass

    if not scored:
        raise FileNotFoundError(
            "Could not auto-find a valid v2b CSV with scenario_id, base Vmin, and base UV columns.\n"
            "You must set V2B_CSV manually inside the runner."
        )

    scored.sort(reverse=True)
    return scored[0][1]

try:
    import pandas as _live_gate_pd

    V2B_CSV = "/content/hiergrid_phase2/results/phase2d_iterative_blackboard_v2b_iter12/phase2d_v2b_scenario_results.csv"
    _v2b_df_live_gate = _live_gate_pd.read_csv(V2B_CSV)

    _v2b_sid_col_live_gate = _live_gate_pick_col(_v2b_df_live_gate, ["scenario_id"])
    _v2b_base_vm_col_live_gate = _live_gate_pick_col(
        _v2b_df_live_gate,
        ["base_vm_min", "base_vm_min_pu"]
    )
    _v2b_base_uv_col_live_gate = _live_gate_pick_col(
        _v2b_df_live_gate,
        ["base_undervoltage_count", "base_n_undervoltage"]
    )

    _v2b_lookup_live_gate = {
        str(row[_v2b_sid_col_live_gate]): row
        for _, row in _v2b_df_live_gate.iterrows()
    }

    print("[LIVE BASE GATE] Loaded v2b CSV:", V2B_CSV)
    print("[LIVE BASE GATE] Loaded v2b rows:", len(_v2b_lookup_live_gate))
    print("[LIVE BASE GATE] v2b base Vmin column:", _v2b_base_vm_col_live_gate)
    print("[LIVE BASE GATE] v2b base UV column:", _v2b_base_uv_col_live_gate)

except Exception as _live_gate_init_error:
    print("[LIVE BASE GATE] Initialization failed:", repr(_live_gate_init_error))
    raise


def live_base_gate_check(scenario_id, base_vm_min, base_uv_count):
    """
    Stops v2R immediately if the reproduced base state does not match v2b.
    This prevents fake v2R improvements from wrong scenario paths or stale outputs.
    """
    if not ENABLE_LIVE_BASE_GATE:
        return

    scenario_id = str(scenario_id)

    if scenario_id not in _v2b_lookup_live_gate:
        raise RuntimeError(
            f"\nLIVE BASE GATE FAILED\n"
            f"scenario_id not found in v2b CSV: {scenario_id}\n"
            f"STOPPING because comparison would be invalid."
        )

    if base_vm_min is None or base_uv_count is None:
        raise RuntimeError(
            f"\nLIVE BASE GATE FAILED\n"
            f"scenario_id: {scenario_id}\n"
            f"Could not read base_vm_min/base_uv_count before actions.\n"
            f"base_vm_min={base_vm_min}, base_uv_count={base_uv_count}\n"
            f"STOPPING because comparison would be invalid."
        )

    row = _v2b_lookup_live_gate[scenario_id]

    v2b_base_vm = float(row[_v2b_base_vm_col_live_gate])
    v2b_base_uv = int(row[_v2b_base_uv_col_live_gate])

    v2r_base_vm = float(base_vm_min)
    v2r_base_uv = int(base_uv_count)

    vm_diff = abs(v2r_base_vm - v2b_base_vm)
    uv_diff = v2r_base_uv - v2b_base_uv

    if vm_diff > BASE_VM_TOL or uv_diff != 0:
        raise RuntimeError(
            f"\nLIVE BASE MISMATCH DETECTED\n"
            f"scenario_id: {scenario_id}\n"
            f"v2R base_vm_min: {v2r_base_vm}\n"
            f"v2b base_vm_min: {v2b_base_vm}\n"
            f"base_vm_min_diff: {vm_diff}\n"
            f"v2R base_uv_count: {v2r_base_uv}\n"
            f"v2b base_uv_count: {v2b_base_uv}\n"
            f"base_uv_diff: {uv_diff}\n"
            f"\nSTOPPING NOW. v2R comparison would be invalid."
        )

    print(
        f"[BASE OK] {scenario_id} | "
        f"base_vm={v2r_base_vm:.12f} | base_uv={v2r_base_uv}"
    )
# ============================================================



def apply_scenario_exact_v2_path(base_net, scenario, zones):
    """
    This must match v2/v2b exactly.
    No wrapper guessing.
    No alternate signatures.
    No fallback path.
    """
    net = _v2_copy.deepcopy(base_net)
    net = v2.v0.apply_scenario_to_net(net, scenario, zones)
    base_converged, base_err = v2.v0.run_pf(net)
    return net, base_converged, base_err

# ============================================================



sys.path.append("/content")

try:
    import phase2d_iterative_blackboard_v2_deficit_aware as v2_legacy_unused
    v2 = _v2_sys.modules.get('trusted_v2_exact', v2_legacy_unused) if '_v2_sys' in globals() else v2_legacy_unused
except Exception as e:
    raise RuntimeError(
        "Could not import /content/phase2d_iterative_blackboard_v2_deficit_aware.py. "
        "Restore that file first."
    ) from e


# ============================================================
# CONFIG
# ============================================================

VMIN = 0.95
VMAX = 1.05

MAX_ITERATIONS = 12
MAX_BUSES_PER_ZONE = 10

# Default: diagnostic only on worst v2b residual cases.
RUN_WORST_ONLY = False
WORST_N = 20

OUT_DIR = Path("/content/hiergrid_phase2/results/phase2d_v2r_rag_taboo_all141")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIO_CSV = OUT_DIR / "phase2d_v2r_scenario_results.csv"
ACTION_CSV = OUT_DIR / "phase2d_v2r_action_results.csv"
BLACKBOARD_JSONL = OUT_DIR / "phase2d_v2r_blackboards.jsonl"
SUMMARY_JSON = OUT_DIR / "phase2d_v2r_summary.json"
COMPARE_CSV = OUT_DIR / "phase2d_v2r_vs_v2b_same_cases.csv"
WORST_IDS_JSON = OUT_DIR / "selected_worst_scenario_ids.json"



base_q = list(getattr(v2, "Q_CANDIDATES_MVAR", [-5.0, -10.0, -20.0, -40.0, -60.0, -80.0, -100.0]))
if -50.0 not in base_q:
    base_q.append(-50.0)

# Bus-level order: try meaningful medium support first, then stronger/milder.
preferred_order = [-50.0, -60.0, -80.0, -100.0, -40.0, -20.0, -10.0, -5.0, -120.0]
Q_CANDIDATES = [q for q in preferred_order if q in set(base_q)]
for q in base_q:
    if q not in Q_CANDIDATES:
        Q_CANDIDATES.append(q)


# ============================================================
# BASIC UTILITIES
# ============================================================

def safe_float(x, default=None):
    try:
        if x is None:
            return default
        if isinstance(x, float) and math.isnan(x):
            return default
        return float(x)
    except Exception:
        return default


def json_dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def append_csv(path: Path, rows):
    if not rows:
        return
    df = pd.DataFrame(rows)
    header = not path.exists()
    df.to_csv(path, mode="a", header=header, index=False)


def write_jsonl(path: Path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj, default=str) + "\n")


def run_pf(net):
    """Forced exact v2/v2b run_pf path."""
    return v2.v0.run_pf(net)

def compute_metrics(net, converged=True, error=None):
    if not converged:
        return {
            "converged": False,
            "error": error,
            "vm_min_pu": None,
            "vm_max_pu": None,
            "n_undervoltage": None,
            "n_overvoltage": None,
            "n_overloaded_lines": None,
            "n_overloaded_trafos": None,
            "line_loading_max_pct": None,
            "trafo_loading_max_pct": None,
            "voltage_deficit_sum_pu": None,
            "voltage_deficit_max_pu": None,
            "voltage_deficit_sq_sum_pu": None,
        }

    vm = net.res_bus.vm_pu.dropna().astype(float)
    deficits = (VMIN - vm).clip(lower=0.0)

    if "res_line" in dir(net) and len(net.res_line):
        line_loading = net.res_line.loading_percent.dropna().astype(float)
    else:
        line_loading = pd.Series(dtype=float)

    if "res_trafo" in dir(net) and len(net.res_trafo):
        trafo_loading = net.res_trafo.loading_percent.dropna().astype(float)
    else:
        trafo_loading = pd.Series(dtype=float)

    return {
        "converged": True,
        "error": None,
        "vm_min_pu": float(vm.min()) if len(vm) else None,
        "vm_max_pu": float(vm.max()) if len(vm) else None,
        "n_undervoltage": int((vm < VMIN - 1e-9).sum()) if len(vm) else 0,
        "n_overvoltage": int((vm > VMAX + 1e-9).sum()) if len(vm) else 0,
        "n_overloaded_lines": int((line_loading > 100.0 + 1e-9).sum()) if len(line_loading) else 0,
        "n_overloaded_trafos": int((trafo_loading > 100.0 + 1e-9).sum()) if len(trafo_loading) else 0,
        "line_loading_max_pct": float(line_loading.max()) if len(line_loading) else 0.0,
        "trafo_loading_max_pct": float(trafo_loading.max()) if len(trafo_loading) else 0.0,
        "voltage_deficit_sum_pu": float(deficits.sum()) if len(deficits) else 0.0,
        "voltage_deficit_max_pu": float(deficits.max()) if len(deficits) else 0.0,
        "voltage_deficit_sq_sum_pu": float((deficits ** 2).sum()) if len(deficits) else 0.0,
    }





def apply_scenario_generic(base_net, scenario, meta=None, zones=None):
    """
    Exact scenario application path used by Phase 2D-v2/v2b.
    """
    import copy

    if zones is None:
        raise ValueError("zones must be provided.")

    net = copy.deepcopy(base_net)
    net = v2.v0.apply_scenario_to_net(net, scenario, zones)
    return net

def extract_zone_buses(zone_obj):
    if zone_obj is None:
        return []

    if isinstance(zone_obj, (list, tuple, set)):
        return list(zone_obj)

    if isinstance(zone_obj, dict):
        for key in [
            "buses",
            "bus_ids",
            "bus_indices",
            "zone_buses",
            "internal_buses",
            "all_buses",
        ]:
            if key in zone_obj and isinstance(zone_obj[key], (list, tuple, set)):
                return list(zone_obj[key])

        # Try nested dicts.
        for _, val in zone_obj.items():
            if isinstance(val, (list, tuple, set)) and len(val) > 0:
                if all(isinstance(x, (int, float, str)) for x in val):
                    return list(val)

    return []


def normalize_bus_id(net, b):
    """
    Try to convert metadata bus identifier into pandapower bus index.
    """
    try:
        bi = int(b)
        if bi in set(net.bus.index):
            return bi


        if (bi - 1) in set(net.bus.index):
            return bi - 1
    except Exception:
        pass


    try:
        matches = net.bus.index[net.bus["name"].astype(str) == str(b)].tolist()
        if matches:
            return int(matches[0])
    except Exception:
        pass

    return None


def candidate_buses_for_zone(net, zone_buses, max_buses=10):
    """
    Prefer v2's own deficit-aware candidate selector.
    Fallback: choose lowest-voltage buses inside the zone.
    """
    # First try existing v2 function.
    fn = getattr(v2, "candidate_buses_deficit_aware", None)
    if callable(fn):
        try:
            out = fn(net, zone_buses, max_buses=max_buses)
            out = [normalize_bus_id(net, b) for b in out]
            out = [b for b in out if b is not None]
            if out:
                return out[:max_buses]
        except Exception:
            pass

    norm = [normalize_bus_id(net, b) for b in zone_buses]
    norm = [b for b in norm if b is not None and b in set(net.res_bus.index)]

    if not norm:
        norm = list(net.res_bus.index)

    vm = net.res_bus.vm_pu.loc[norm].dropna().sort_values()
    return [int(x) for x in vm.index.tolist()[:max_buses]]


def zone_voltage_report(net, zones):
    reports = {}

    for zname, zobj in zones.items():
        raw_buses = extract_zone_buses(zobj)
        buses = [normalize_bus_id(net, b) for b in raw_buses]
        buses = [b for b in buses if b is not None and b in set(net.res_bus.index)]

        if not buses:
            continue

        vm = net.res_bus.vm_pu.loc[buses].dropna().astype(float)
        if len(vm) == 0:
            continue

        reports[zname] = {
            "n_buses": int(len(vm)),
            "min_voltage_pu": float(vm.min()),
            "max_voltage_pu": float(vm.max()),
            "n_undervoltage": int((vm < VMIN - 1e-9).sum()),
            "n_overvoltage": int((vm > VMAX + 1e-9).sum()),
            "worst_buses": [int(x) for x in vm.sort_values().index.tolist()[:10]],
        }

    return reports


def active_zones_from_reports(reports):
    active = []
    for z, r in reports.items():
        if r.get("n_undervoltage", 0) > 0 or r.get("min_voltage_pu", 9.0) < VMIN:
            active.append(z)
    return active


def add_shunt_and_run(net, bus, q_mvar, name):
    trial = copy.deepcopy(net)
    pp.create_shunt(
        trial,
        bus=int(bus),
        q_mvar=float(q_mvar),
        p_mw=0.0,
        name=name,
    )
    conv, err = run_pf(trial)
    metrics = compute_metrics(trial, converged=conv, error=err)
    return trial, metrics


# ============================================================
# RAG-STYLE SMART GATE
# ============================================================

def rag_smart_gate(before, after, eps_vm=0.001, allow_small_vm_worse=0.005):
    """
    RAG-style gate:
    - Reject non-convergence.
    - Reject new/worse overvoltage.
    - Reject new/worse line/trafo overload.
    - Reject increased undervoltage count.
    - Allow action if it reduces UV count OR improves Vmin OR reduces total deficit.
    """
    if not after.get("converged", False):
        return False, "non_converged"

    if after["n_overvoltage"] > before["n_overvoltage"]:
        return False, "increased_overvoltage"

    if after["n_overloaded_lines"] > before["n_overloaded_lines"]:
        return False, "increased_line_overload"

    if after["n_overloaded_trafos"] > before["n_overloaded_trafos"]:
        return False, "increased_trafo_overload"

    if after["n_undervoltage"] > before["n_undervoltage"]:
        return False, "increased_undervoltage_count"

    reduced_uv = after["n_undervoltage"] < before["n_undervoltage"]
    improved_vmin = after["vm_min_pu"] > before["vm_min_pu"] + eps_vm
    reduced_deficit = after["voltage_deficit_sum_pu"] < before["voltage_deficit_sum_pu"] - 1e-6

    # Reject clear Vmin damage unless it reduces UV count.
    if after["vm_min_pu"] < before["vm_min_pu"] - allow_small_vm_worse and not reduced_uv:
        return False, "worsened_vmin_without_uv_reduction"

    if reduced_uv or improved_vmin or reduced_deficit:
        return True, "accepted_rag_smart_gate"

    return False, "no_material_voltage_benefit"


def rag_action_score(before, after, q_mvar):
    delta_uv = before["n_undervoltage"] - after["n_undervoltage"]
    delta_vmin = after["vm_min_pu"] - before["vm_min_pu"]
    delta_deficit = before["voltage_deficit_sum_pu"] - after["voltage_deficit_sum_pu"]
    delta_deficit_max = before["voltage_deficit_max_pu"] - after["voltage_deficit_max_pu"]

    # Count-focused, RAG-style score.
    return (
        1000.0 * delta_uv
        + 250.0 * delta_vmin
        + 80.0 * delta_deficit
        + 50.0 * delta_deficit_max
        - 0.01 * abs(float(q_mvar))
    )


# ============================================================
# MAIN CONTROLLER
# ============================================================

def run_v2r_for_scenario(base_net, scenario, zones, meta=None):
    scenario_id = str(scenario.get("scenario_id", "unknown"))

    net = apply_scenario_generic(base_net, scenario, zones=zones)
    conv, err = run_pf(net)
    base_metrics = compute_metrics(net, converged=conv, error=err)

    if not conv:
        return {
            "scenario_id": scenario_id,
            "base_converged": False,
            "error": err,
            "base_metrics": base_metrics,
            "final_metrics": base_metrics,
            "accepted_action_count": 0,
            "termination_reason": "base_non_converged",
            "blackboard": [],
        }

    current_net = net
    current_metrics = base_metrics
    blackboard = []
    accepted_actions = []
    taboo_buses = set()
    taboo_events = []


    # ============================================================
    # LIVE BASE GATE CALL - ADDED BY PATCH
    # Must run before any v2R corrective action loop.
    # ============================================================
    _live_base_vm_value = locals().get("base_vm_min", locals().get("base_vm_min_pu", None))
    _live_base_uv_value = locals().get("base_uv_count", locals().get("base_n_undervoltage", None))

    if _live_base_vm_value is None and "base_metrics" in locals():
        if isinstance(base_metrics, dict):
            _live_base_vm_value = base_metrics.get("vm_min_pu", base_metrics.get("base_vm_min", None))
            _live_base_uv_value = base_metrics.get("n_undervoltage", base_metrics.get("base_uv_count", _live_base_uv_value))

    live_base_gate_check(
        scenario_id=scenario_id,
        base_vm_min=_live_base_vm_value,
        base_uv_count=_live_base_uv_value
    )
    # ============================================================

    for iteration in range(MAX_ITERATIONS):
        if current_metrics["n_undervoltage"] == 0:
            termination = "success_all_voltages_above_vmin"
            break

        reports = zone_voltage_report(current_net, zones)
        active_zones = active_zones_from_reports(reports)

        if not active_zones:
            termination = "stopped_no_active_undervoltage_zone"
            break

        step = {
            "iteration": iteration,
            "current_metrics": current_metrics,
            "zone_reports": reports,
            "active_zones": active_zones,
            "taboo_buses_at_start": sorted([int(x) for x in taboo_buses]),
            "trials": [],
            "accepted_action": None,
        }

        accepted_this_iter = None
        accepted_trial_net = None
        accepted_trial_score = None

        # Try worst zones first.
        active_zones = sorted(
            active_zones,
            key=lambda z: reports.get(z, {}).get("min_voltage_pu", 9.0)
        )

        for zname in active_zones:
            raw_zone_buses = extract_zone_buses(zones[zname])
            candidate_buses = candidate_buses_for_zone(current_net, raw_zone_buses, max_buses=MAX_BUSES_PER_ZONE)

            # Remove taboo buses.
            candidate_buses = [b for b in candidate_buses if int(b) not in taboo_buses]

            # Sort by current voltage, weakest first.
            try:
                candidate_buses = sorted(
                    candidate_buses,
                    key=lambda b: float(current_net.res_bus.vm_pu.loc[int(b)])
                )
            except Exception:
                pass

            for bus in candidate_buses:
                bus_best = None
                bus_best_net = None
                bus_best_score = None
                bus_rejections = []

                for q in Q_CANDIDATES:
                    trial_net, trial_metrics = add_shunt_and_run(
                        current_net,
                        bus=int(bus),
                        q_mvar=float(q),
                        name=f"v2R_iter{iteration}_{zname}_bus{bus}_q{q}",
                    )

                    accepted, reason = rag_smart_gate(current_metrics, trial_metrics)
                    score = None
                    if accepted:
                        score = rag_action_score(current_metrics, trial_metrics, q)

                    trial_record = {
                        "zone": zname,
                        "bus": int(bus),
                        "q_mvar": float(q),
                        "accepted_by_gate": bool(accepted),
                        "reason": reason,
                        "score": score,
                        "after_vm_min_pu": trial_metrics.get("vm_min_pu"),
                        "after_n_undervoltage": trial_metrics.get("n_undervoltage"),
                        "after_voltage_deficit_sum_pu": trial_metrics.get("voltage_deficit_sum_pu"),
                        "after_n_overvoltage": trial_metrics.get("n_overvoltage"),
                        "after_n_overloaded_lines": trial_metrics.get("n_overloaded_lines"),
                        "after_n_overloaded_trafos": trial_metrics.get("n_overloaded_trafos"),
                    }
                    step["trials"].append(trial_record)

                    if accepted:
                        if bus_best_score is None or score > bus_best_score:
                            bus_best = {
                                "zone": zname,
                                "bus": int(bus),
                                "q_mvar": float(q),
                                "reason": reason,
                                "score": float(score),
                                "before": current_metrics,
                                "after": trial_metrics,
                            }
                            bus_best_net = trial_net
                            bus_best_score = score
                    else:
                        bus_rejections.append(reason)

                # RAG-style: if every q for this bus failed, blacklist bus and pivot.
                if bus_best is None:
                    taboo_buses.add(int(bus))
                    taboo_events.append({
                        "iteration": iteration,
                        "zone": zname,
                        "bus": int(bus),
                        "reasons": dict(Counter(bus_rejections)),
                    })
                    continue

                # Accept first bus that has a valid action, using best q for that bus.
                accepted_this_iter = bus_best
                accepted_trial_net = bus_best_net
                accepted_trial_score = bus_best_score
                break

            if accepted_this_iter is not None:
                break

        if accepted_this_iter is None:
            step["accepted_action"] = None
            step["termination"] = "stopped_no_rag_smart_gate_action_found"
            blackboard.append(step)
            termination = "stopped_no_rag_smart_gate_action_found"
            break

        # Execute accepted action.
        current_net = accepted_trial_net
        current_metrics = accepted_this_iter["after"]

        # RAG-style memory reset: clear taboo after successful accepted action.
        taboo_buses.clear()

        accepted_actions.append(accepted_this_iter)
        step["accepted_action"] = accepted_this_iter
        step["termination"] = "accepted_and_continue"
        blackboard.append(step)

    else:
        termination = "stopped_max_iterations_reached"

    return {
        "scenario_id": scenario_id,
        "base_converged": True,
        "error": None,
        "base_metrics": base_metrics,
        "final_metrics": current_metrics,
        "accepted_action_count": len(accepted_actions),
        "termination_reason": termination,
        "blackboard": blackboard,
        "taboo_events": taboo_events,
    }


# ============================================================
# OUTPUT ROWS
# ============================================================

def scenario_row(result):
    scenario_id = result["scenario_id"]

    if not result.get("base_converged", False):
        return {
            "scenario_id": scenario_id,
            "base_converged": False,
            "error": result.get("error"),
            "termination_reason": result.get("termination_reason"),
        }

    b = result["base_metrics"]
    f = result["final_metrics"]

    return {
        "scenario_id": scenario_id,
        "base_converged": True,

        "base_vm_min_pu": b["vm_min_pu"],
        "final_vm_min_pu": f["vm_min_pu"],
        "base_vm_max_pu": b["vm_max_pu"],
        "final_vm_max_pu": f["vm_max_pu"],

        "base_n_undervoltage": b["n_undervoltage"],
        "final_n_undervoltage": f["n_undervoltage"],
        "base_n_overvoltage": b["n_overvoltage"],
        "final_n_overvoltage": f["n_overvoltage"],

        "base_n_overloaded_lines": b["n_overloaded_lines"],
        "final_n_overloaded_lines": f["n_overloaded_lines"],
        "base_n_overloaded_trafos": b["n_overloaded_trafos"],
        "final_n_overloaded_trafos": f["n_overloaded_trafos"],

        "base_line_loading_max_pct": b["line_loading_max_pct"],
        "final_line_loading_max_pct": f["line_loading_max_pct"],
        "base_trafo_loading_max_pct": b["trafo_loading_max_pct"],
        "final_trafo_loading_max_pct": f["trafo_loading_max_pct"],

        "base_voltage_deficit_sum_pu": b["voltage_deficit_sum_pu"],
        "final_voltage_deficit_sum_pu": f["voltage_deficit_sum_pu"],
        "base_voltage_deficit_max_pu": b["voltage_deficit_max_pu"],
        "final_voltage_deficit_max_pu": f["voltage_deficit_max_pu"],
        "base_voltage_deficit_sq_sum_pu": b["voltage_deficit_sq_sum_pu"],
        "final_voltage_deficit_sq_sum_pu": f["voltage_deficit_sq_sum_pu"],

        "improved_vm_min": f["vm_min_pu"] > b["vm_min_pu"] + 1e-5,
        "reduced_undervoltage_count": f["n_undervoltage"] < b["n_undervoltage"],
        "reduced_voltage_deficit_sum": f["voltage_deficit_sum_pu"] < b["voltage_deficit_sum_pu"] - 1e-7,

        "accepted_action_count": result["accepted_action_count"],
        "termination_reason": result["termination_reason"],
        "taboo_event_count": len(result.get("taboo_events", [])),
        "error": None,
    }


def action_rows(result):
    rows = []
    for step in result.get("blackboard", []):
        action = step.get("accepted_action")
        if action is None:
            continue

        rows.append({
            "scenario_id": result["scenario_id"],
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

            "before_voltage_deficit_sum_pu": action["before"]["voltage_deficit_sum_pu"],
            "after_voltage_deficit_sum_pu": action["after"]["voltage_deficit_sum_pu"],
        })
    return rows


# ============================================================
# WORST-CASE SELECTION + COMPARISON
# ============================================================

def find_v2b_scenario_csv():
    candidates = []

    search_roots = [
        Path("/content/hiergrid_phase2/results"),
        Path("/content"),
    ]

    for root in search_roots:
        if root.exists():
            candidates.extend(root.rglob("*v2b*scenario_results*.csv"))


    candidates = sorted(set(candidates), key=lambda p: (("fast" in str(p).lower()), len(str(p))))

    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        "Could not find v2b scenario results CSV. Expected something like "
        "/content/hiergrid_phase2/results/phase2d_iterative_blackboard_v2b_iter12/phase2d_v2b_scenario_results.csv"
    )


def select_worst_scenario_ids():
    v2b_csv = find_v2b_scenario_csv()
    df = pd.read_csv(v2b_csv)

    conv = df[df["base_converged"] == True].copy()
    if "final_n_undervoltage" in conv.columns:
        conv = conv[conv["final_n_undervoltage"] > 0]

    worst = (
        conv.sort_values(["final_vm_min_pu", "final_n_undervoltage"], ascending=[True, False])
        .head(WORST_N)
        .copy()
    )

    ids = worst["scenario_id"].astype(str).tolist()

    json_dump(WORST_IDS_JSON, {
        "source_v2b_csv": str(v2b_csv),
        "worst_n": WORST_N,
        "scenario_ids": ids,
    })

    print("Using v2b source:", v2b_csv)
    print("Selected worst scenario IDs:")
    for x in ids:
        print(" -", x)

    return set(ids), v2b_csv


def update_summary(v2b_csv=None):
    if not SCENARIO_CSV.exists():
        return

    df = pd.read_csv(SCENARIO_CSV)
    conv = df[df["base_converged"] == True].copy()



    _numeric_cols = [
        "base_vm_min_pu", "base_vm_max_pu", "base_n_undervoltage",
        "base_voltage_deficit_sum_pu", "base_voltage_deficit_max_pu",
        "base_line_loading_max_pct", "base_trafo_loading_max_pct",
        "base_n_overvoltage", "base_n_overloaded_lines", "base_n_overloaded_trafos",
        "final_vm_min_pu", "final_vm_max_pu", "final_n_undervoltage",
        "final_voltage_deficit_sum_pu", "final_voltage_deficit_max_pu",
        "final_line_loading_max_pct", "final_trafo_loading_max_pct",
        "final_n_overvoltage", "final_n_overloaded_lines", "final_n_overloaded_trafos",
        "accepted_actions", "iterations", "total_actions", "n_actions",
    ]

    for _c in _numeric_cols:
        if _c in df.columns:
            df[_c] = pd.to_numeric(df[_c], errors="coerce")
        if _c in conv.columns:
            conv[_c] = pd.to_numeric(conv[_c], errors="coerce")
    # ============================================================
    if len(conv) == 0:
        summary = {
            "controller_version": "phase2d_v2r_rag_taboo",
            "processed_scenarios": int(len(df)),
            "base_converged": 0,
        }
    else:
        summary = {
            "controller_version": "phase2d_v2r_rag_taboo",
            "run_worst_only": RUN_WORST_ONLY,
            "worst_n": WORST_N,
            "max_iterations": MAX_ITERATIONS,
            "max_buses_per_zone": MAX_BUSES_PER_ZONE,
            "q_candidates_mvar": Q_CANDIDATES,
            "processed_scenarios": int(len(df)),
            "base_converged": int(len(conv)),
            "base_failed": int((df["base_converged"] == False).sum()),

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

            "improved_vm_min_rate": float(conv["improved_vm_min"].mean()),
            "reduced_undervoltage_rate": float(conv["reduced_undervoltage_count"].mean()),
            "reduced_voltage_deficit_sum_rate": float(conv["reduced_voltage_deficit_sum"].mean()),

            "total_accepted_actions": int(conv["accepted_action_count"].sum()),
            "avg_accepted_actions_per_scenario": float(conv["accepted_action_count"].mean()),

            "success_all_voltages_above_vmin_count": int(
                (conv["termination_reason"] == "success_all_voltages_above_vmin").sum()
            ),
            "success_all_voltages_above_vmin_rate": float(
                (conv["termination_reason"] == "success_all_voltages_above_vmin").mean()
            ),
            "termination_reason_counts": conv["termination_reason"].value_counts().to_dict(),

            "safety_audit": {
                "increased_overvoltage_cases": int((conv["final_n_overvoltage"] > conv["base_n_overvoltage"]).sum()),
                "increased_line_overload_cases": int((conv["final_n_overloaded_lines"] > conv["base_n_overloaded_lines"]).sum()),
                "increased_trafo_overload_cases": int((conv["final_n_overloaded_trafos"] > conv["base_n_overloaded_trafos"]).sum()),
                "worsened_vm_min_cases": int((conv["final_vm_min_pu"] < conv["base_vm_min_pu"] - 1e-5).sum()),
                "increased_voltage_deficit_sum_cases": int((conv["final_voltage_deficit_sum_pu"] > conv["base_voltage_deficit_sum_pu"] + 1e-7).sum()),
            },
        }

    if v2b_csv is not None:
        summary["v2b_comparison_source"] = str(v2b_csv)

    json_dump(SUMMARY_JSON, summary)


def compare_against_v2b(v2b_csv):
    if not SCENARIO_CSV.exists():
        return

    v2r = pd.read_csv(SCENARIO_CSV)
    v2b = pd.read_csv(v2b_csv)

    common = sorted(set(v2r["scenario_id"].astype(str)) & set(v2b["scenario_id"].astype(str)))

    a = v2b[v2b["scenario_id"].astype(str).isin(common)].copy()
    b = v2r[v2r["scenario_id"].astype(str).isin(common)].copy()

    a = a.set_index("scenario_id")
    b = b.set_index("scenario_id")

    rows = []
    for sid in common:
        if sid not in a.index or sid not in b.index:
            continue

        ar = a.loc[sid]
        br = b.loc[sid]

        rows.append({
            "scenario_id": sid,

            "v2b_final_vm_min_pu": ar.get("final_vm_min_pu"),
            "v2r_final_vm_min_pu": br.get("final_vm_min_pu"),
            "delta_vm_min_v2r_minus_v2b": safe_float(br.get("final_vm_min_pu"), 0) - safe_float(ar.get("final_vm_min_pu"), 0),

            "v2b_final_n_undervoltage": ar.get("final_n_undervoltage"),
            "v2r_final_n_undervoltage": br.get("final_n_undervoltage"),
            "delta_uv_v2r_minus_v2b": safe_float(br.get("final_n_undervoltage"), 0) - safe_float(ar.get("final_n_undervoltage"), 0),

            "v2b_final_voltage_deficit_sum_pu": ar.get("final_voltage_deficit_sum_pu"),
            "v2r_final_voltage_deficit_sum_pu": br.get("final_voltage_deficit_sum_pu"),
            "delta_deficit_sum_v2r_minus_v2b": safe_float(br.get("final_voltage_deficit_sum_pu"), 0) - safe_float(ar.get("final_voltage_deficit_sum_pu"), 0),

            "v2b_actions": ar.get("accepted_action_count"),
            "v2r_actions": br.get("accepted_action_count"),
            "v2b_termination": ar.get("termination_reason"),
            "v2r_termination": br.get("termination_reason"),
        })

    comp = pd.DataFrame(rows)
    comp.to_csv(COMPARE_CSV, index=False)

    print("\nSaved same-case comparison:", COMPARE_CSV)
    if len(comp):
        print("\nSame-case comparison summary:")
        print({
            "n_common": len(comp),
            "avg_delta_vm_min_v2r_minus_v2b": float(comp["delta_vm_min_v2r_minus_v2b"].mean()),
            "avg_delta_uv_v2r_minus_v2b": float(comp["delta_uv_v2r_minus_v2b"].mean()),
            "avg_delta_deficit_sum_v2r_minus_v2b": float(comp["delta_deficit_sum_v2r_minus_v2b"].mean()),
            "v2r_better_vm_min_cases": int((comp["delta_vm_min_v2r_minus_v2b"] > 1e-5).sum()),
            "v2r_better_uv_cases": int((comp["delta_uv_v2r_minus_v2b"] < 0).sum()),
            "v2r_better_deficit_cases": int((comp["delta_deficit_sum_v2r_minus_v2b"] < -1e-7).sum()),
        })


# ============================================================
# MAIN
# ============================================================

def main():
    assert hasattr(v2, "v0"), "v2 module does not expose v0. Restore the correct v2 script."
    assert v2.v0.FED_NET_PATH.exists(), f"Missing net: {v2.v0.FED_NET_PATH}"
    assert v2.v0.FED_META_PATH.exists(), f"Missing metadata: {v2.v0.FED_META_PATH}"

    scenario_dir = v2.v0.find_scenario_dir()
    scenario_files = sorted(scenario_dir.glob("*.json"))

    print("==============================================")
    print("Phase 2D-v2R: RAG-style Smart-Gate Taboo Test")
    print("==============================================")
    print("Scenario dir:", scenario_dir)
    print("Scenario files:", len(scenario_files))
    print("Output dir:", OUT_DIR)
    print("RUN_WORST_ONLY:", RUN_WORST_ONLY)
    print("WORST_N:", WORST_N)
    print("MAX_ITERATIONS:", MAX_ITERATIONS)
    print("MAX_BUSES_PER_ZONE:", MAX_BUSES_PER_ZONE)
    print("Q_CANDIDATES:", Q_CANDIDATES)

    meta, zones = v2.v0.load_metadata(v2.v0.FED_META_PATH)
    base_net = pp.from_json(str(v2.v0.FED_NET_PATH))

    if RUN_WORST_ONLY:
        selected_ids, v2b_csv = select_worst_scenario_ids()
        scenario_files = [
            sf for sf in scenario_files
            if json.load(open(sf)).get("scenario_id", sf.stem) in selected_ids
        ]
    else:
        selected_ids = None
        v2b_csv = None

    print("Running selected scenario files:", len(scenario_files))


    for p in [SCENARIO_CSV, ACTION_CSV, BLACKBOARD_JSONL, SUMMARY_JSON, COMPARE_CSV]:
        if p.exists():
            p.unlink()

    for i, sf in enumerate(scenario_files):
        with open(sf) as f:
            scenario = json.load(f)

        scenario_id = str(scenario.get("scenario_id", sf.stem))
        print(f"\n[{i+1}/{len(scenario_files)}] RUN {scenario_id}")

        try:
            result = run_v2r_for_scenario(base_net, scenario, zones, meta=meta)

            srow = scenario_row(result)
            arows = action_rows(result)

            append_csv(SCENARIO_CSV, [srow])
            append_csv(ACTION_CSV, arows)

            write_jsonl(BLACKBOARD_JSONL, {
                "scenario_id": scenario_id,
                "termination_reason": result.get("termination_reason"),
                "accepted_action_count": result.get("accepted_action_count"),
                "taboo_events": result.get("taboo_events", []),
                "blackboard": result.get("blackboard", []),
            })

            update_summary(v2b_csv=v2b_csv)

            print(
                "  final_vm_min:",
                srow.get("final_vm_min_pu"),
                "| final_uv:",
                srow.get("final_n_undervoltage"),
                "| actions:",
                srow.get("accepted_action_count"),
                "| termination:",
                srow.get("termination_reason"),
            )

        except Exception as e:
            print("  ERROR:", repr(e))
            append_csv(SCENARIO_CSV, [{
                "scenario_id": scenario_id,
                "base_converged": False,
                "error": repr(e),
                "termination_reason": "runner_exception",
            }])
            update_summary(v2b_csv=v2b_csv)

    if v2b_csv is not None:
        compare_against_v2b(v2b_csv)

    print("\nDONE.")
    print("Scenario CSV:", SCENARIO_CSV)
    print("Action CSV:", ACTION_CSV)
    print("Summary JSON:", SUMMARY_JSON)
    print("Comparison CSV:", COMPARE_CSV)

    if SUMMARY_JSON.exists():
        print("\nSummary:")
        print(json.dumps(json.load(open(SUMMARY_JSON)), indent=2))


if __name__ == "__main__":
    main()
