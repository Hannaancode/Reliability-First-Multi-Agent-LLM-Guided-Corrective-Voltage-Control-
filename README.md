# HierGrid IEEE-118 Verified Voltage Recovery

This repository contains the reproducibility artifacts for the paper:

**Reliability-First Multi-Agent LLM-Guided Corrective Voltage Control with Embedded Power-Flow Verification**

## What this repository reproduces

- IEEE-118 four-zone federation setup
- Scenario scope tracking: 141 generated / 138 sanity-converged / 137 replay-aligned / 61 complete matched / 5 residual-failure cases
- Broad 137-case controller progression
- Complete 61-case matched statistical comparison
- Phase 2G accepted-action source audit
- Same-pipeline no-LLM fallback-first ablation
- Reflection-v4 residual-failure safety-envelope analysis

## Main folders

- `data/scenario_scopes/`: scenario identity lists and raw federation scenario files
- `results/broad_137_controller_progression/`: v2b, v2R, and verified-router broad comparison outputs
- `results/complete_case_61_statistics/`: matched 61-case Phase 2G and controller-comparison outputs
- `results/phase2g_action_source_audit/`: accepted-action source logs and summaries
- `results/reflection_v4_residual_cases/`: no-LLM, Reflection-v2, and Reflection-v4 residual-case files
- `scripts/`: reproduction and experiment scripts
- `docs/`: file manifests and reproducibility notes

## Core reproducibility principle

The LLM is used as a proposal generator only. Execution authority remains with deterministic validation, AC power-flow verification, deterministic routing, and fallback physics refinement.

## Suggested reproduction flow

1. Reproduce the 137-case broad controller progression.
2. Reproduce the 61-case complete matched statistics.
3. Reproduce the Phase 2G accepted-action source audit.
4. Reproduce the Reflection-v4 residual-failure safety-envelope table.
