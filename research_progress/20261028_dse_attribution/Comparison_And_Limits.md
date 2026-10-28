# Saved D-SE and original Reflection-v4 comparison

All four current DFF result objects exactly match the earlier DFF records, including every action and log. Scenario hashes and shared source hashes match. The existing DFF-ALT branch is reused with its original committed-state audit; no science was repeated.

| Severe root | Initial UV | DFF UV/OV | DFF-ALT UV/OV | Numerical D-SE UV/OV | HG-VF UV/OV | Offline HG-SE UV/OV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fed_combined_load_1p5_line_35_MG1 | 56 | 11/3 | 9/3 | 9/3 | 7/2 | 7/2 |
| fed_combined_load_1p5_line_36_MG1 | 58 | 15/2 | 9/2 | 9/2 | 1/3 | 1/3 |
| fed_combined_load_1p5_line_84_MG2 | 57 | 18/2 | 10/4 | 10/4 | 5/3 | 5/3 |
| fed_combined_load_1p5_line_127_MG3 | 55 | 7/4 | 7/3 | 7/3 | 13/3 | 7/4 |

HG-VF has 26 residual UV versus numerical D-SE 35: three UV wins and one loss. Offline HG-SE has 20 residual UV: three wins and one tie. HG-VF has one case with more strict OV than numerical D-SE; offline HG-SE has two such cases. These are descriptive development findings; they do not pass a no-loss/no-extra-OV claim.

- This is a retrospective source/recipe/complete-DFF-output join over all four previously fixed inspected roots, not unused confirmation or a new prospective success gate.
- Historical ALT has independently replayed initial and committed-state metrics. Its old record does not certify every candidate query full field, cold runtime, KCL or exact native solver-input bytes to the newer audit standard.
- Strict UV below 0.95 and OV above 1.05 are unchanged. Native verifier upper guard remains 1.06. No zero-UV case or whole-band restoration in these four endpoints.
- The LLM branch includes numerical normalization, guarded selection, guided and fallback search. Offline HG-SE selects DFF or HG-VF and pays both; numerical D-SE selects DFF or DFF-ALT and pays both.
- Raw costs remain in distinct historical source blocks. Shared paid receipts, setup, training, failed stages and missing old timing are not free; no equal-cost or deployment-speed claim.
- No inference, physics, optimizer, derivative, replay or old-reader call was made. No general external-method or causal LLM superiority follows.
