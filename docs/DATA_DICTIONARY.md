# Data Dictionary

## Scenario fields

- `scenario_id`: unique scenario identifier.
- `base_uv`: number of undervoltage buses before control.
- `final_uv`: number of undervoltage buses after control.
- `base_vmin`: minimum voltage before control.
- `final_vmin`: minimum voltage after control.
- `final_deficit`: final voltage-deficit sum.
- `restored`: whether final undervoltage count is zero.

## Controller/action fields

- `controller`: controller branch or method.
- `action_source`: source of accepted action.
- `llm_direct`: accepted action directly from validated LLM proposal.
- `llm_guided_refinement`: LLM-guided bus/direction with deterministic MVAr refinement.
- `safety_fallback_physics_refinement`: deterministic fallback action after failed LLM route.

## Main scenario scopes

- 141 generated federation scenarios.
- 138 sanity-converged federation cases.
- 137 replay-aligned controller-comparison cases.
- 61 complete matched statistical cases.
- 5 residual-failure safety-envelope cases.
