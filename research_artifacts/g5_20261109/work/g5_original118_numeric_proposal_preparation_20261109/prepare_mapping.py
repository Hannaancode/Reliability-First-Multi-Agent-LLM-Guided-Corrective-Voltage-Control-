"""Source/metadata mapping and new synthetic slot checks only; no estimator fit."""
import hashlib
import importlib.util
import json
from pathlib import Path

R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent
O=R/'outputs/g5_original118_numeric_proposal_preparation_20261109'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def ref(rel):
    p=R/rel;return {'path':rel,'sha256':sha(p),'bytes':p.stat().st_size}

def main():
    spec=importlib.util.spec_from_file_location('new_pure_proposal_slot',W/'direct_slot_contract.py');slot=importlib.util.module_from_spec(spec);spec.loader.exec_module(slot)
    rows=json.loads((R/'outputs/g5_original118_adapter_ablation_20261109/All4_Original_Inputs.json').read_text('utf-8'))
    inputs=[]
    for row in rows:
        contract=slot.request_contract(row['messages'])
        inputs.append({'case_id':row['case_id'],'messages_sha256':contract['messages_sha256'],'kind':contract['kind'],
            'candidate_bus_count':len(contract['candidate_buses']),'candidate_action_count':len(contract['candidate_catalog']),
            'candidate_catalog_sha256':contract['candidate_catalog_sha256'],'new_predictions':0})
    assert len(inputs)==4 and all(x['kind']=='PRIMARY' for x in inputs)
    msgs=[{'role':'system','content':'SYNTHETIC_ONLY'},{'role':'user','content':'CANDIDATE_BUSES_YOU_MAY_USE: [0, 2]\nALLOWED_Q_MVAR_VALUES: [25, 50, 75, 100, 125, 150, 200, 250, 300]'}]
    c=slot.request_contract(msgs);receipt={'status':'COMPLETE_SOURCE_BOUND_NUMERIC_PREDICTION','messages_sha256':c['messages_sha256'],
      'candidate_catalog_sha256':c['candidate_catalog_sha256'],'estimator_sha256':'a'*64,'training_manifest_sha256':'b'*64,
      'scores':[0.0]*18,'numeric_prediction_calls':1,'extra_PF_queries':0,'extra_observed_fields':0,
      'prediction_cost_ref':{'path':'SYNTHETIC_COST_ONLY','bytes':1,'sha256':'c'*64}}
    def run(value):return slot.decode_admitted_scores(msgs,value,expected_estimator_sha256='a'*64,expected_training_manifest_sha256='b'*64)
    checks=[];assert json.loads(run(receipt)['raw'])=={'bus':'0','q_mvar':25};checks.append('fixed_first_tie_in_full_original_catalog')
    v=dict(receipt,scores=[0.0]*17+[1.0]);assert json.loads(run(v)['raw'])=={'bus':'2','q_mvar':300};checks.append('single_max_single_legal_compact_proposal')
    for name,delta in [('foreign_input',{'messages_sha256':'d'*64}),('wrong_estimator',{'estimator_sha256':'d'*64}),
         ('hidden_extra_query',{'extra_PF_queries':1}),('missing_candidate_class',{'scores':[0.0]*17}),
         ('hidden_current_field',{'extra_observed_fields':1}),('nonfinite_score',{'scores':[float('nan')]*18})]:
        try:run(dict(receipt,**delta))
        except ValueError:checks.append(name+'_rejected')
        else:raise AssertionError(name)
    O.mkdir(exist_ok=False)
    source_paths=['work/e/audit/run_reflection_v4_safety_envelope.py','work/e/audit/phase2g_llm_guided_rescue_runner.py',
      'work/reflection118_chronological_core_20261022.py','work/run_original_role_numeric_gate_20261011.py',
      'work/candidate_process_numerical_predictor.py','work/actual_mask_jacobian_engineering_20261014.py',
      'work/g5_original118_numeric_proposal_preparation_20261109/direct_slot_contract.py',
      'outputs/g3_common118_protocol_20261109/Source_Bound_Admission_Protocol.json']
    value={'status':'SOURCE_BOUND_NUMERIC_DIRECT_ROLE_MAPPING_COMPLETE_NO_TRAINED_PROVIDER_ADMITTED',
      'scientific_recommendation':'Reuse the verified ExtraTrees algorithm/conditioning recipe as a separately named exact-original-message proposal adaptation; do not reuse its incompatible saved estimator or restart its stopped study.',
      'original_hook':'work/reflection118_chronological_core_20261022.py controller replaces only runner.base_runner.generate_response with model_provider(messages). Return exactly one compact JSON per source request; original parser/repair/verify/refinement/fallback/priority/commit remain untouched.',
      'same_information':['Exact ordered original messages only, including candidate list, global UV map, local extrema/lowest entries, failed-short list and the actually truncated feedback text.','No NET, full Ybus, voltage angles, full omitted non-UV voltages, active set, current unqueried outcomes or offline teacher ranking.','Format-repair requests contain only their own actual source messages; no undeclared retained first-prompt memory.'],
      'allowance':{'proposal_slot':'One numerical prediction and one returned direct proposal per original primary request; second request only if unchanged original parser triggers it.','additional_candidate_PF_queries':0,'direct_verifier_calls':'Exactly unchanged source call at the direct slot; cap/invalid rejection semantics remain original.','query_economics':'Full guided/fallback menus remain governed by unchanged original source and fully paid. Different proposed buses may legitimately change realized guided queries. This is not identical realized cost; freeze a common declared allowance and report all realized costs, failures and bound censoring. Never prune DFF to match a weak budget.'},
      'control_admission_map':[
        {'control':'Original DFF/DFF-ALT/literal D-SE','use':'Unchanged strong full-system reference with both branches/full BOTH costs.','exact_direct_slot_same_information':False,'reason':'It evaluates physical menus using simulator state and queries unavailable to a single original prompt proposal.'},
        {'control':'Correct-mask current Jacobian/LP and numeric lookahead','use':'Strong physics-informed system/control reference only.','exact_direct_slot_same_information':False,'reason':'Requires Ybus, complex state, solver active set and paid derivatives/solves beyond prompt information. Giving those to all actors defines a different named task.'},
        {'control':'Completed original-role ExtraTrees','use':'Reuse algorithm, typed-feature masks, FIT-only conditioning, world weighting and closed-reload discipline.','old_evidence':'72.9167% held equal-world exact teacher action on96pairs/24worlds; teacher imitation, not physical advantage.','exact_saved_estimator_direct_admission':False,'reason':'Old input is zone plus ALL local_measurements, old decoder permits null and multi-bus actions up to450; original Reflection-v4 message is different and demands one candidate bus and one originalQ. Missing fields cannot be filled silently.'},
        {'control':'Completed nearest-current/weighted-prior controls','use':'Additional same-encoding diagnostics after new data admission, not strongest numerical substitute by themselves.','exact_saved_estimator_direct_admission':False,'reason':'Same old feature/action-support mismatch.'},
        {'control':'TableGraphProcessControl','use':'Potential richer same-resource learned reference only in a separately admitted shared-information task.','exact_direct_slot_same_information':False,'reason':'Its full table/graph input contains information absent from original messages; old process studies remain stopped.'}],
      'proposed_unchanged_tree_recipe':{'n_estimators':512,'criterion':'gini','max_depth':None,'min_samples_split':2,'min_samples_leaf':1,'max_features':1.0,'bootstrap':False,'n_jobs':2,'random_state':20261011,'class_weight':None},
      'minimal_next_changes_in_order':[
        'Bind exact causal ORIGINAL prompt/label records by world and chronological state; confirm which training labels and resources are shared with the original trained LoRA. Do not turn these four inspected engineering roots or archived evaluation outputs into unused holdout.',
        'Declare a numerical encoder consuming all actually exposed feedback/current information with missingness and precision explicitly retained. The new slot contract preserves full messages but is NOT that feature encoder.',
        'Resolve complete current candidate-action score support. The old24-class learned catalog does not cover the whole variable original menu. A candidate-conditioned ExtraTrees ranker is a new methodological adaptation requiring declared labels/objective before fit; no zero-filled unseen classes or fallback heuristic.',
        'Freeze dataset split, one-fit/no-outcome-sweep recipe, paired training/inference budgets, full costs and checkpoint/cold reader. Only then fit the new named control and produce source-bound predictions.',
        'Use the pure one-slot decoder at the existing messages-only provider boundary; prove original parser/validator compatibility on admitted outputs before any physical continuation. Freeze protected trajectory/receipt-reuse/ownership/independent reader protocol before comparing outcomes.'],
      'critical_methodological_choice_not_silently_resolved':'New numerical action support/learning target: direct joint-class imitation versus candidate-conditioned ranking. Ranking is implementable and avoids unseen-class omission, but requires complete causally valid labels/objective; no new fit or claim is admitted by this design.',
      'four_initial_inputs_contract_only':inputs,'new_bridge_source':ref(source_paths[6]),'synthetic_checks':checks,
      'genuinely_new_calls':{'PF':0,'model':0,'trained_numeric_predictions':0,'native_decode':0,'optimizer_or_fit':0,'old_audits':0},
      'remaining_blockers':['Exact shared causal training-data/label join and world split','Full original-message numeric encoder','Declared full legal-action scoring support','Actual new fitted estimator plus source/cold/source-compatible parser evidence','Matched complete protected trajectories/fullcost/unused confirmation'],
      'strong_numeric_baseline_ready':False,'benchmark_or_G5_complete':False,'no_controller_source_edits':True,
      'source_refs':[ref(path) for path in source_paths],
      'old_control_result_ref':ref('outputs/critical_research_reset_20261010/original_role_numeric_gate_20261011/execution/Results.json')}
    out=O/'Admissibility_And_Minimal_Change.json'
    with out.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    print(json.dumps({'status':value['status'],'checks':len(checks),'four_inputs_parsed':len(inputs),'sha256':sha(out),'bytes':out.stat().st_size}))

if __name__=='__main__':main()
