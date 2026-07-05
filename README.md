# HierGrid

**Reliability-first multi-agent AI for physics-verified corrective voltage control.**

HierGrid is an applied AI project that uses multiple zone-conditioned large language model agents to propose corrective actions for stressed power-grid states. The system does not allow the LLM to directly control the grid. Every proposed action is validated, tested through AC power-flow simulation, and accepted only when it improves the verified operating state.

## AI Problem

Corrective voltage control is a high-risk decision problem. LLM outputs may be syntactically valid but physically unsafe, numerically weak, or inconsistent with grid constraints.

HierGrid addresses this by separating:

- **AI proposal generation**
- **deterministic validation**
- **physics-based verification**
- **safe action selection**

## Core AI Components

### Multi-Agent LLM System

Four zone-conditioned agents, MG1-MG4, observe local voltage states and generate structured JSON corrective-action proposals.

The agents use a shared **Qwen2.5-0.5B model with LoRA adaptation**, allowing lightweight domain specialization while keeping inference efficient.

### Structured AI Outputs

Each agent produces a constrained action proposal containing:

- control zone
- candidate bus
- action type
- reactive-power value
- diagnostic reasoning

Malformed, cross-zone, or out-of-range outputs are rejected before simulation.

### Physics-Verified Decision Making

Every admissible proposal is applied to a copied IEEE-118 network and evaluated through AC power-flow simulation.

The verifier checks:

- power-flow convergence
- undervoltage reduction
- minimum-voltage improvement
- voltage-deficit reduction
- loading constraints
- absence of new safety violations

### Deterministic Router and Safety Fallback

A deterministic router ranks only verified candidates. When the LLM route fails, a physics-based fallback search generates and tests alternative actions.

This keeps the LLM in an **auditable proposal role**, while deterministic logic retains execution authority.

## AI Workflow

```text
Stressed IEEE-118 grid state
            |
            v
  Zone-state extraction
     MG1 | MG2 | MG3 | MG4
            |
            v
 Multi-agent LLM proposals
      structured JSON
            |
            v
 Schema + zone + limit validation
            |
            v
 AC power-flow verification
            |
            v
 MVAr refinement and candidate scoring
            |
            v
 Deterministic verified router
            |
            v
 Safe action execution or physics fallback
```

## Reported Results

On 61 matched evaluation scenarios, the final controller achieved:

- **93.44% full-restoration rate**
- **97.04% reduction** in total undervoltage burden
- mean final undervoltage count of **0.459**
- **63.20% of accepted actions** involving the LLM branch
- zero acceptance of an LLM-reflection trajectory worse than the deterministic fallback in the tested residual-case safety envelope

These results apply only to the reported simulation setup and do not imply production-grid readiness.

## Applied AI Skills Demonstrated

- Multi-agent AI systems
- Large language model adaptation
- LoRA fine-tuning
- Structured generation
- Prompt and schema design
- Tool-augmented LLM workflows
- Safety gating
- AI-agent orchestration
- Deterministic routing
- Physics-informed AI
- Simulation-based validation
- Ablation and statistical evaluation

## Technology Stack

- Python
- PyTorch
- Hugging Face Transformers
- Qwen2.5
- LoRA / PEFT
- Pandapower
- NumPy
- Pandas
- JSON-based agent interfaces

## System Design

The project includes:

- four zone-conditioned LLM proposer agents
- shared-model multi-context prompting
- blackboard-style coordination
- JSON schema validation
- zone-ownership checks
- candidate-bus validation
- reactive-power limit enforcement
- AC power-flow verification
- MVAr refinement
- deterministic action routing
- physics-based fallback control
- action-source logging
- no-LLM and safety-envelope ablations

## Evaluation Setup

- IEEE-118 test system
- four control zones
- stressed AC power-flow scenarios
- 141 generated scenarios
- 137 replay-aligned cases
- 61 complete matched scenarios for final statistical comparison
- corrective reactive-power support actions
- iterative closed-loop verification

## Key Metrics

The project evaluates:

- full-restoration rate
- minimum bus voltage
- undervoltage count
- voltage-deficit severity
- power-flow convergence
- action-source contribution
- regression against deterministic baselines
- LLM-direct versus LLM-guided versus fallback actions

## Important Limitation

HierGrid is a research prototype. It is not production grid-control software.

The LLM does not receive execution authority. All actions must pass deterministic constraints and AC power-flow verification before being applied.


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
