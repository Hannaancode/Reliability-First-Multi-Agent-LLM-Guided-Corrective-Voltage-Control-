# ============================================================
# Phase 2G verified safety-envelope experiment
# Targeted Reflection-v4 verification on no-LLM failure cases
# Method:
#   Run frozen no-LLM fallback-first branch and Reflection-v2 branch.
#   Select the better fully verified final trajectory.
#   This is a trajectory-level safety envelope, not a prompt-only method.

# ============================================================

from pathlib import Path
import sys, json, copy, datetime, zipfile
from collections import Counter, deque
import pandas as pd
import pandapower as pp


sys.path.insert(0, "/content")

import phase2g_llm_guided_rescue_runner as runner

runner.MAX_ITERATIONS = 25

SEVERE_CASES = [
    "fed_combined_load_1p5_line_101_MG1",
    "fed_combined_load_1p5_line_127_MG3",
    "fed_combined_load_1p5_line_128_MG3",
    "fed_combined_load_1p5_line_129_MG3",
    "fed_combined_load_1p5_line_135_MG3",
]


NO_LLM_BASELINE_FINAL_UV = {
    "fed_combined_load_1p5_line_101_MG1": 11,
    "fed_combined_load_1p5_line_127_MG3": 7,
    "fed_combined_load_1p5_line_128_MG3": 7,
    "fed_combined_load_1p5_line_129_MG3": 7,
    "fed_combined_load_1p5_line_135_MG3": 8,
}

ALLOWED_Q = [25, 50, 75, 100, 125, 150, 200, 250, 300]

# ============================================================
# Compact feedback memory helpers
# ============================================================

def _safe_bus_q(action):
    """Return (bus, q) from a normalized {'add_shunts_q_mvar': {...}} action."""
    if not action or not isinstance(action, dict):
        return None, None
    payload = action.get("add_shunts_q_mvar")
    if not isinstance(payload, dict) or not payload:
        return None, None
    bus = str(list(payload.keys())[0])
    try:
        q = float(list(payload.values())[0])
    except Exception:
        q = None
    return bus, q


def _uv_delta(verif):
    """Return before_uv, after_uv, delta if available."""
    try:
        before = int(verif["before"]["uv_count"])
        after = int(verif["after"]["uv_count"])
        return before, after, before - after
    except Exception:
        return None, None, None


def init_feedback_state():
    return {
        "accepted_recent": deque(maxlen=5),
        "rejected_hard_ov": deque(maxlen=8),
        "rejected_other": deque(maxlen=6),
        "weak_or_stalled": deque(maxlen=8),
        "strong_fallback": deque(maxlen=5),
    }


def record_candidate_feedback(feedback_state, source, zone, action, verif):
    """
    Store only compact causal facts. No raw LLM text.
    This prevents context explosion and avoids the 4096-token truncation issue.
    """
    bus, q = _safe_bus_q(action)
    if bus is None:
        return

    reason = str(verif.get("reason", "unknown")) if isinstance(verif, dict) else "unknown"
    accepted = bool(verif.get("accepted", False)) if isinstance(verif, dict) else False
    before, after, delta = _uv_delta(verif)

    item = {
        "bus": bus,
        "q": q,
        "source": source,
        "zone": zone,
        "reason": reason,
        "before_uv": before,
        "after_uv": after,
        "delta_uv": delta,
    }

    if accepted:
        feedback_state["accepted_recent"].append(item)
        if delta is not None and delta < 2:
            feedback_state["weak_or_stalled"].append(item)
        if source == "safety_fallback_physics_refinement" and delta is not None and delta >= 5:
            feedback_state["strong_fallback"].append(item)
    else:
        if "hard" in reason.lower() or "ov" in reason.lower() or "overvoltage" in reason.lower():
            feedback_state["rejected_hard_ov"].append(item)
        else:
            feedback_state["rejected_other"].append(item)


def build_compact_feedback_text(feedback_state, candidate_buses=None, max_chars=1200):
    """
    Candidate-filtered compact memory.
    Only include facts that are relevant to current candidate buses when possible.
    """
    cand = set(str(x) for x in (candidate_buses or []))

    def filt(items):
        out = []
        for it in list(items):
            if not cand or str(it.get("bus")) in cand:
                out.append(it)
        return out

    accepted = filt(feedback_state["accepted_recent"])[-4:]
    hard_ov = filt(feedback_state["rejected_hard_ov"])[-5:]
    weak = filt(feedback_state["weak_or_stalled"])[-5:]
    strong_fb = filt(feedback_state["strong_fallback"])[-4:]

    lines = []

    if accepted:
        lines.append("accepted_recent:")
        for it in accepted:
            effect = "unknown" if it["before_uv"] is None else f"UV {it['before_uv']}->{it['after_uv']}"
            lines.append(f"- bus={it['bus']} q={int(it['q'])} source={it['source']} effect={effect}")

    if hard_ov:
        lines.append("rejected_hard_overvoltage_avoid:")
        for it in hard_ov:
            lines.append(f"- bus={it['bus']} q={int(it['q'])} reason={it['reason']}")

    if weak:
        lines.append("weak_or_stalled_avoid_if_possible:")
        for it in weak:
            effect = "unknown" if it["before_uv"] is None else f"UV {it['before_uv']}->{it['after_uv']}"
            lines.append(f"- bus={it['bus']} q={int(it['q'])} effect={effect}")

    if strong_fb:
        lines.append("strong_fallback_examples_current_run:")
        for it in strong_fb:
            effect = "unknown" if it["before_uv"] is None else f"UV {it['before_uv']}->{it['after_uv']}"
            lines.append(f"- bus={it['bus']} q={int(it['q'])} effect={effect}")

    if not lines:
        return "None"

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[-max_chars:]
    return text


# ============================================================
# Improved prompt builder
# ============================================================

def severity_stage(global_uv_count):
    if global_uv_count > 40:
        return "CRITICAL", "Prefer 150-300 MVAr on unused safe candidate buses. Prioritize global UV-count reduction. Avoid timid 25-50 MVAr unless higher actions are risky."
    if global_uv_count > 15:
        return "HIGH", "Prefer 100-250 MVAr. Avoid buses/actions that caused hard overvoltage. Prefer a different bus if prior action reduced UV by fewer than 2 buses."
    return "FINISHING", "Prefer 25-125 MVAr. Be conservative enough to avoid overvoltage. Prioritize clearing remaining UV without creating hard overvoltage."


def build_two_best_prompt_v2(mode, zone_state, global_uv, candidate_buses, failed_actions, feedback_state):
    """
    mode:
      - emergency_v2: severity-staged emergency operator instruction + compact current-run effects
      - reflection_v2: compact verifier-feedback reflection + candidate-filtered memory
    """
    assert mode in {"emergency_v2", "reflection_v2"}, f"Unsupported mode: {mode}"

    global_uv_count = len(global_uv)
    stage, stage_rule = severity_stage(global_uv_count)

    candidate_text = ", ".join(str(x) for x in candidate_buses) if candidate_buses else "None"

    # Keep failed actions tiny. Do not include raw output.
    failed_short = []
    for fa in (failed_actions or [])[-5:]:
        act = fa.get("action") if isinstance(fa, dict) else None
        b, q = _safe_bus_q(act)
        if b is not None:
            failed_short.append({"bus": b, "q": q, "reason": fa.get("reason", "unknown")})

    # Candidate-filtered compact memory, never raw logs.
    feedback_text = build_compact_feedback_text(
        feedback_state=feedback_state,
        candidate_buses=candidate_buses,
        max_chars=900 if mode == "emergency_v2" else 1200,
    )

    if mode == "emergency_v2":
        mode_instruction = f"""
EMERGENCY_OPERATOR_INSTRUCTION:
This is a severe undervoltage recovery task. Use severity-staged control.
SEVERITY_STAGE: {stage}
STAGE_RULE: {stage_rule}
Do not repeat a bus-q pair that caused hard overvoltage.
Do not keep using a weak/stalled bus when another candidate bus exists.
Prefer high-impact corrective actions across different zones early, but avoid hard overvoltage.
""".strip()
    else:
        mode_instruction = f"""
COMPACT_VERIFIER_REFLECTION_INSTRUCTION:
Use the verifier feedback memory below to revise your next proposal.
Avoid rejected_hard_overvoltage actions.
Avoid weak_or_stalled actions unless no better candidate exists.
Prefer candidate buses related to strong_fallback_examples_current_run when they are available.
For high-severity cases, prioritize global UV-count reduction over tiny local deficit changes.
SEVERITY_STAGE: {stage}
STAGE_RULE: {stage_rule}
""".strip()


    user_text = f"""
You are a microgrid zone agent inside a physics-verified multi-agent grid controller.
The deterministic verifier will reject unsafe actions, so your job is only to propose one valid candidate action.

GLOBAL_STATE:
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
ALLOWED_Q_MVAR_VALUES: {ALLOWED_Q}
FAILED_ACTIONS_TO_AVOID_SHORT: {json.dumps(failed_short)}

VERIFIER_FEEDBACK_MEMORY:
{feedback_text}

{mode_instruction}

TASK:
If GLOBAL_UNDERVOLTAGE_COUNT > 0, choose exactly one bus from CANDIDATE_BUSES_YOU_MAY_USE and one q_mvar from ALLOWED_Q_MVAR_VALUES.
Do not return null.
Do not use a bus outside the candidate list.
Return ONLY this compact JSON schema and nothing else:
{{"bus":"BUS_ID","q_mvar":Q_MVAR}}

Example:
{{"bus":"52","q_mvar":150}}
""".strip()

    return [
        {"role": "system", "content": "Return only valid JSON. No markdown. No prose. Use exactly the requested compact JSON schema."},
        {"role": "user", "content": user_text},
    ]


# ============================================================
# Simple parser for compact schema
# ============================================================

def normalize_compact_or_nested_action(parsed):
    """Accept compact {'bus':'52','q_mvar':100} or original nested schema."""

    act = runner.rescue.normalize_action(parsed)
    return act


def get_llm_action_required_two_best_v2(model, tokenizer, net, zone, zones, zone_state, global_uv, failed_actions, feedback_state, mode):
    candidate_buses = runner.get_zone_candidate_buses(net, zone, zones, zone_state)

    if len(global_uv) == 0:
        return None, {
            "mode": mode,
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
            "mode": mode,
            "candidate_buses": candidate_buses,
            "raw": None,
            "parsed": None,
            "parse_valid": False,
            "parse_error": "no_candidate_buses",
            "valid_action": False,
            "valid_reason": "no_candidate_buses",
        }

    # Attempt 1
    msgs = build_two_best_prompt_v2(mode, zone_state, global_uv, candidate_buses, failed_actions, feedback_state)
    raw = runner.base_runner.generate_response(model, tokenizer, msgs)
    parsed, parse_valid, parse_error = runner.base_runner.extract_json(raw)
    action = normalize_compact_or_nested_action(parsed)
    valid_action, valid_reason = runner.validate_action_against_candidates(action, candidate_buses)

    if valid_action:
        return action, {
            "mode": mode,
            "candidate_buses": candidate_buses,
            "raw": raw,
            "parsed": parsed,
            "parse_valid": parse_valid,
            "parse_error": parse_error,
            "valid_action": True,
            "valid_reason": valid_reason,
            "reprompted": False,
        }

    # Attempt 2: error-specific short reprompt.
    # Keep this tiny to avoid context truncation.
    candidate_text = ", ".join(str(x) for x in candidate_buses)
    msgs2 = [
        {"role": "system", "content": "Return only valid JSON. No prose."},
        {"role": "user", "content": f"""
Your previous answer was invalid.
Failure reason: {valid_reason}
You must choose exactly one bus from this list: [{candidate_text}]
You must choose one q_mvar from this list: {ALLOWED_Q}
Return exactly this JSON schema only:
{{"bus":"BUS_ID","q_mvar":Q_MVAR}}
Example: {{"bus":"{candidate_buses[0]}","q_mvar":100}}
""".strip()},
    ]

    raw2 = runner.base_runner.generate_response(model, tokenizer, msgs2)
    parsed2, parse_valid2, parse_error2 = runner.base_runner.extract_json(raw2)
    action2 = normalize_compact_or_nested_action(parsed2)
    valid_action2, valid_reason2 = runner.validate_action_against_candidates(action2, candidate_buses)

    return action2 if valid_action2 else None, {
        "mode": mode,
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
# LLM-guided severe-case run loop using the two improved methods
# ============================================================

def run_one_scenario_two_best_v2(scenario, base_net, zones, v2, model, tokenizer, mode):
    assert mode in {"emergency_v2", "reflection_v2"}
    scenario_id = scenario.get("scenario_id", scenario.get("id", "unknown"))

    net = copy.deepcopy(base_net)
    net = v2.v0.apply_scenario_to_net(net, scenario, zones)
    conv, err = v2.v0.run_pf(net)

    if not conv:
        return {
            "method": mode,
            "scenario_id": scenario_id,
            "base_converged": False,
            "stop_reason": "base_fail",
            "base_metrics": None,
            "final_metrics": None,
            "logs": [],
            "executed_actions": [],
        }

    base_metrics = runner.rescue.grid_metrics(net)

    result = {
        "method": mode,
        "scenario_id": scenario_id,
        "base_converged": True,
        "base_metrics": base_metrics,
        "final_metrics": None,
        "logs": [],
        "executed_actions": [],
        "stop_reason": None,
        "counters": Counter(),
    }

    failed_sigs = set()
    failed_actions = []
    feedback_state = init_feedback_state()

    for it in range(runner.MAX_ITERATIONS):
        current = runner.rescue.grid_metrics(net)
        print(f"    [Iteration {it+1}] Mode={mode} | Global UV: {current['uv_count']} | Vmin={current['vmin']:.4f} | Def={current['deficit_sum']:.5f}")

        if current["uv_count"] == 0:
            result["stop_reason"] = "full_restoration"
            break

        global_uv = runner.rescue.global_uv_buses(net)
        zone_reports = {}
        llm_actions = []
        cands = []


        for zone in sorted(zones.keys()):
            zs = runner.rescue.extract_zone_state_full(net, zone, zones)
            zone_reports[zone] = zs

            act, llm_info = get_llm_action_required_two_best_v2(
                model=model,
                tokenizer=tokenizer,
                net=net,
                zone=zone,
                zones=zones,
                zone_state=zs,
                global_uv=global_uv,
                failed_actions=failed_actions,
                feedback_state=feedback_state,
                mode=mode,
            )

            verif = runner.rescue.verify_action(net, act)

            if act:
                bus_id = runner.action_bus(act)
                llm_actions.append(act)
                result["counters"]["llm_direct_tests"] += 1
                if verif.get("accepted"):
                    result["counters"]["llm_direct_accepted_tests"] += 1
                print(f"      🔹 LLM {zone}: bus={bus_id}, action={act}, verdict={verif['reason']}")
            else:
                print(f"      🔹 LLM {zone}: no valid proposal, reason={llm_info.get('valid_reason')}")

            record_candidate_feedback(feedback_state, "llm_direct", zone, act, verif)

            log_row = {
                "iteration": it + 1,
                "source": "llm_zone_agent_direct",
                "mode": mode,
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
                "bus": str(runner.action_bus(act)) if act else None,
                "q_abs": list(act["add_shunts_q_mvar"].values())[0] if act else None,
                "verif": verif,
                "raw": llm_info.get("raw"),
            })

            if act and not verif["accepted"]:
                sig = runner.action_signature(act)
                failed_sigs.add(sig)
                failed_actions.append({
                    "source": "llm_direct",
                    "zone": zone,
                    "action": act,
                    "reason": verif["reason"],
                })

        # Original priority 1: direct LLM actions
        accepted_direct = [c for c in cands if c["source"] == "llm_direct" and c["verif"]["accepted"]]

        # Original priority 2: physics refinement around LLM-proposed buses only
        guided = runner.llm_guided_refinement_candidates(net, llm_actions, failed_sigs)
        accepted_guided = [c for c in guided if c["verif"]["accepted"]]
        result["counters"]["guided_tests"] += len(guided)
        print(f"      🔧 LLM-guided refinement tested {len(guided)} candidates; accepted {len(accepted_guided)}")

        for c in guided:
            record_candidate_feedback(feedback_state, c.get("source", "llm_guided_refinement"), c.get("zone"), c.get("action"), c.get("verif", {}))

        cands.extend(guided)

        # Original priority 3: safety fallback only if LLM layer gives no accepted candidate
        fallback = []
        if not accepted_direct and not accepted_guided:
            fallback = runner.fallback_physics_candidates(net, zones, zone_reports, llm_actions, failed_sigs)
            accepted_fallback = [c for c in fallback if c["verif"]["accepted"]]
            result["counters"]["fallback_tests"] += len(fallback)
            print(f"      🛟 Safety fallback tested {len(fallback)} candidates; accepted {len(accepted_fallback)}")

            for c in fallback:
                record_candidate_feedback(feedback_state, c.get("source", "safety_fallback_physics_refinement"), c.get("zone"), c.get("action"), c.get("verif", {}))

            cands.extend(fallback)

        accepted = [c for c in cands if c["verif"]["accepted"]]

        if not accepted:
            result["stop_reason"] = "no_accepted_action"
            break


        priority = {
            "llm_direct": 3,
            "llm_guided_refinement": 2,
            "safety_fallback_physics_refinement": 1,
        }

        def score_with_source_priority(c):
            base_score = runner.rescue.score_candidate(c)
            return (priority.get(c["source"], 0),) + tuple(base_score)

        best = max(accepted, key=score_with_source_priority)
        print(f"      ✅ Executing {best['source']} | zone={best['zone']} | action={best['action']} | score={score_with_source_priority(best)}")

        runner.rescue.apply_action(net, best["action"])
        conv, err = runner.rescue.r.run_pf(net)

        if not conv:
            result["stop_reason"] = f"execution_pf_failed: {err}"
            break

        post = runner.rescue.grid_metrics(net)

        result["executed_actions"].append({
            "iteration": it + 1,
            "source": best["source"],
            "zone": best["zone"],
            "action": best["action"],
            "post_metrics": post,
        })

    final_metrics = runner.rescue.grid_metrics(net)
    result["final_metrics"] = final_metrics

    if result["stop_reason"] is None:
        result["stop_reason"] = "max_iterations_reached"

    result["uv_reduced"] = bool(final_metrics["uv_count"] < base_metrics["uv_count"])
    result["full_restoration"] = bool(final_metrics["uv_count"] == 0)
    result["vmin_improved"] = bool(final_metrics["vmin"] > base_metrics["vmin"] + 1e-9)
    result["deficit_reduced"] = bool(final_metrics["deficit_sum"] < base_metrics["deficit_sum"] - 1e-9)

    return result



# ============================================================
# Safety-envelope driver
# ============================================================

def run_one_scenario_no_llm_fallback_first(scenario, base_net, zones, v2):
    """
    Frozen no-LLM fallback-first branch.
    This does not call the LLM. It uses the same existing fallback candidate generator,
    verifier, scoring, action application, and PF execution from the runner.
    """
    scenario_id = scenario.get("scenario_id", scenario.get("id", "unknown"))

    net = copy.deepcopy(base_net)
    net = v2.v0.apply_scenario_to_net(net, scenario, zones)
    conv, err = v2.v0.run_pf(net)

    if not conv:
        return {
            "method": "no_llm_fallback_first",
            "scenario_id": scenario_id,
            "base_converged": False,
            "stop_reason": "base_fail",
            "base_metrics": None,
            "final_metrics": None,
            "logs": [],
            "executed_actions": [],
            "counters": Counter(),
        }

    base_metrics = runner.rescue.grid_metrics(net)
    result = {
        "method": "no_llm_fallback_first",
        "scenario_id": scenario_id,
        "base_converged": True,
        "base_metrics": base_metrics,
        "final_metrics": None,
        "logs": [],
        "executed_actions": [],
        "stop_reason": None,
        "counters": Counter(),
    }

    failed_sigs = set()

    for it in range(runner.MAX_ITERATIONS):
        current = runner.rescue.grid_metrics(net)
        print(f"    [No-LLM Iteration {it+1}] Global UV: {current['uv_count']} | Vmin={current['vmin']:.4f} | Def={current['deficit_sum']:.5f}")

        if current["uv_count"] == 0:
            result["stop_reason"] = "full_restoration"
            break

        zone_reports = {}
        for zone in sorted(zones.keys()):
            zone_reports[zone] = runner.rescue.extract_zone_state_full(net, zone, zones)


        fallback = runner.fallback_physics_candidates(
            net=net,
            zones=zones,
            zone_reports=zone_reports,
            llm_actions=[],
            failed_sigs=failed_sigs,
        )
        result["counters"]["fallback_tests"] += len(fallback)
        accepted = [c for c in fallback if c["verif"]["accepted"]]
        print(f"      🛟 No-LLM fallback tested {len(fallback)} candidates; accepted {len(accepted)}")

        result["logs"].append({
            "iteration": it + 1,
            "source": "no_llm_fallback_first",
            "current_metrics": current,
            "fallback_tests": len(fallback),
            "accepted_fallback": len(accepted),
        })

        if not accepted:
            result["stop_reason"] = "no_accepted_action"
            break

        best = max(accepted, key=runner.rescue.score_candidate)
        print(f"      ✅ Executing no_llm_fallback | action={best['action']} | score={runner.rescue.score_candidate(best)}")

        runner.rescue.apply_action(net, best["action"])
        conv, err = runner.rescue.r.run_pf(net)
        if not conv:
            result["stop_reason"] = f"execution_pf_failed: {err}"
            break

        post = runner.rescue.grid_metrics(net)
        result["executed_actions"].append({
            "iteration": it + 1,
            "source": "safety_fallback_physics_refinement",
            "zone": best.get("zone"),
            "action": best["action"],
            "post_metrics": post,
        })

    final_metrics = runner.rescue.grid_metrics(net)
    result["final_metrics"] = final_metrics
    if result["stop_reason"] is None:
        result["stop_reason"] = "max_iterations_reached"

    result["uv_reduced"] = bool(final_metrics["uv_count"] < base_metrics["uv_count"])
    result["full_restoration"] = bool(final_metrics["uv_count"] == 0)
    result["vmin_improved"] = bool(final_metrics["vmin"] > base_metrics["vmin"] + 1e-9)
    result["deficit_reduced"] = bool(final_metrics["deficit_sum"] < base_metrics["deficit_sum"] - 1e-9)
    return result


def summarize_result(res):
    src = Counter([a["source"] for a in res.get("executed_actions", [])])
    counters = Counter(res.get("counters", {}))
    fm = res.get("final_metrics") or {}
    bm = res.get("base_metrics") or {}

    return {
        "method": res.get("method"),
        "scenario_id": res.get("scenario_id"),
        "base_uv": bm.get("uv_count"),
        "final_uv": fm.get("uv_count"),
        "final_vmin": fm.get("vmin"),
        "final_deficit": fm.get("deficit_sum"),
        "full_restoration": res.get("full_restoration"),
        "accepted_actions": len(res.get("executed_actions", [])),
        "llm_direct": src.get("llm_direct", 0),
        "llm_guided": src.get("llm_guided_refinement", 0),
        "fallback": src.get("safety_fallback_physics_refinement", 0),
        "guided_tests": counters.get("guided_tests", 0),
        "fallback_tests": counters.get("fallback_tests", 0),
        "llm_direct_tests": counters.get("llm_direct_tests", 0),
        "llm_direct_accepted_tests": counters.get("llm_direct_accepted_tests", 0),
        "stop_reason": res.get("stop_reason"),
    }


def choose_safety_envelope(no_llm_row, llm_row):
    """
    Verified trajectory-level selector.
    Select lower final UV. Tie-break by lower final deficit. Tie-break by fewer actions.
    """
    n_uv = int(no_llm_row["final_uv"])
    l_uv = int(llm_row["final_uv"])

    if l_uv < n_uv:
        return "reflection_v2"
    if l_uv > n_uv:
        return "no_llm_fallback_first"

    n_def = float(no_llm_row.get("final_deficit") or 1e99)
    l_def = float(llm_row.get("final_deficit") or 1e99)
    if l_def < n_def - 1e-12:
        return "reflection_v2"
    if n_def < l_def - 1e-12:
        return "no_llm_fallback_first"

    n_actions = int(no_llm_row.get("accepted_actions") or 0)
    l_actions = int(llm_row.get("accepted_actions") or 0)
    if l_actions < n_actions:
        return "reflection_v2"
    return "no_llm_fallback_first"


def run_reflection_v4_safety_envelope():
    run_id = datetime.datetime.now().strftime("reflection_v4_safety_envelope_%Y%m%d_%H%M%S")
    out_dir = Path("/content/hiergrid_phase2/results/reflection_v4_safety_envelope") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print("Output folder:", out_dir)

    v2 = runner.base_runner.load_v2()
    model, tokenizer = runner.base_runner.load_llm()

    base_net = pp.from_json(str(runner.base_runner.FED_NET))
    meta = json.load(open(runner.base_runner.FED_META))
    zones = {k: [int(x) for x in v] for k, v in meta["zones"].items()}

    all_results = []
    rows = []
    selected_rows = []

    for sid in SEVERE_CASES:
        matches = sorted(runner.base_runner.SCENARIO_DIRS[0].glob(f"{sid}.json"))
        if not matches:
            raise FileNotFoundError(f"Could not find scenario JSON for {sid} in {runner.base_runner.SCENARIO_DIRS[0]}")
        sf = matches[0]
        scenario = json.load(open(sf))
        scenario.setdefault("scenario_id", sf.stem)

        print("\n" + "=" * 110)
        print("SCENARIO:", sid)
        print("=" * 110)

        print("\n--- Branch A: frozen no-LLM fallback-first ---")
        no_res = run_one_scenario_no_llm_fallback_first(
            scenario=scenario,
            base_net=base_net,
            zones=zones,
            v2=v2,
        )
        no_row = summarize_result(no_res)
        no_row["branch"] = "candidate_branch"
        rows.append(no_row)
        all_results.append({"branch": "no_llm_fallback_first", "result": no_res})
        print("NO-LLM FINAL:", no_row)

        print("\n--- Branch B: Reflection-v2 LLM proposal branch ---")
        llm_res = run_one_scenario_two_best_v2(
            scenario=scenario,
            base_net=base_net,
            zones=zones,
            v2=v2,
            model=model,
            tokenizer=tokenizer,
            mode="reflection_v2",
        )
        llm_row = summarize_result(llm_res)
        llm_row["branch"] = "candidate_branch"
        rows.append(llm_row)
        all_results.append({"branch": "reflection_v2", "result": llm_res})
        print("REFLECTION-V2 FINAL:", llm_row)

        selected = choose_safety_envelope(no_row, llm_row)
        selected_source_row = llm_row if selected == "reflection_v2" else no_row

        no_llm_reference_uv = NO_LLM_BASELINE_FINAL_UV.get(sid, no_row.get("final_uv"))
        selected_row = dict(selected_source_row)
        selected_row["method"] = "reflection_v4_safety_envelope"
        selected_row["selected_branch"] = selected
        selected_row["scenario_id"] = sid
        selected_row["no_llm_reference_final_uv_from_log"] = no_llm_reference_uv
        selected_row["fresh_no_llm_branch_final_uv"] = no_row["final_uv"]
        selected_row["reflection_v2_branch_final_uv"] = llm_row["final_uv"]
        selected_row["uv_gain_vs_fresh_no_llm"] = int(no_row["final_uv"]) - int(selected_row["final_uv"])
        selected_row["uv_gain_vs_pasted_no_llm_log"] = int(no_llm_reference_uv) - int(selected_row["final_uv"])
        selected_row["better_than_fresh_no_llm"] = int(selected_row["final_uv"]) < int(no_row["final_uv"])
        selected_row["equal_to_fresh_no_llm"] = int(selected_row["final_uv"]) == int(no_row["final_uv"])
        selected_rows.append(selected_row)

        print("\nSELECTED BY SAFETY ENVELOPE:", selected_row)


        pd.DataFrame(rows).to_csv(out_dir / "reflection_v4_candidate_branches.csv", index=False)
        pd.DataFrame(selected_rows).to_csv(out_dir / "reflection_v4_safety_envelope_per_scenario_results.csv", index=False)
        with open(out_dir / "reflection_v4_safety_envelope_all_results.json", "w") as f:
            json.dump(all_results, f, indent=2, default=str)

    branch_df = pd.DataFrame(rows)
    selected_df = pd.DataFrame(selected_rows)

    agg = selected_df.groupby("method").agg(
        fresh_no_llm_total_final_uv=("fresh_no_llm_branch_final_uv", "sum"),
        pasted_no_llm_log_total_final_uv=("no_llm_reference_final_uv_from_log", "sum"),
        reflection_v2_branch_total_final_uv=("reflection_v2_branch_final_uv", "sum"),
        selected_total_final_uv=("final_uv", "sum"),
        total_gain_vs_fresh_no_llm=("uv_gain_vs_fresh_no_llm", "sum"),
        total_gain_vs_pasted_no_llm_log=("uv_gain_vs_pasted_no_llm_log", "sum"),
        cases_selected_reflection=("selected_branch", lambda s: int((s == "reflection_v2").sum())),
        cases_selected_no_llm=("selected_branch", lambda s: int((s == "no_llm_fallback_first").sum())),
        cases_better_than_fresh_no_llm=("better_than_fresh_no_llm", "sum"),
        cases_equal_to_fresh_no_llm=("equal_to_fresh_no_llm", "sum"),
        full_restoration_count=("full_restoration", "sum"),
        avg_accepted_actions=("accepted_actions", "mean"),
        llm_direct_total=("llm_direct", "sum"),
        llm_guided_total=("llm_guided", "sum"),
        fallback_total=("fallback", "sum"),
        fallback_tests_total=("fallback_tests", "sum"),
    ).reset_index()

    branch_df.to_csv(out_dir / "reflection_v4_candidate_branches.csv", index=False)
    selected_df.to_csv(out_dir / "reflection_v4_safety_envelope_per_scenario_results.csv", index=False)
    agg.to_csv(out_dir / "reflection_v4_safety_envelope_aggregate_comparison.csv", index=False)

    print("\n" + "=" * 110)
    print("CANDIDATE BRANCH RESULTS")
    print("=" * 110)
    print(branch_df.to_string(index=False))

    print("\n" + "=" * 110)
    print("SAFETY ENVELOPE SELECTED RESULTS")
    print("=" * 110)
    print(selected_df.to_string(index=False))

    print("\n" + "=" * 110)
    print("AGGREGATE COMPARISON")
    print("=" * 110)
    print(agg.to_string(index=False))

    zip_path = out_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in out_dir.rglob("*"):
            z.write(p, p.relative_to(out_dir.parent))

    print("\nSaved results:", out_dir)
    print("ZIP:", zip_path)
    return selected_df, agg, out_dir, zip_path


if __name__ == "__main__" or True:
    df_reflection_v4, agg_reflection_v4, out_dir_reflection_v4, zip_reflection_v4 = run_reflection_v4_safety_envelope()
