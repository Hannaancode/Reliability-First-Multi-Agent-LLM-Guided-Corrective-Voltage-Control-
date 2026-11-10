"""Once-only saved metadata preparation; no imports of native/model/controller."""
import ast,hashlib,importlib.util,json,os,tempfile,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];W=R/'work/g5_disabled_frontier_20261109';P=R/'outputs/g5_disabled_frontier_20261109'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
def put(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
def main():
    start=time.perf_counter();assert not P.exists();P.mkdir()
    ep=R/'outputs/g5_original118_adapter_ablation_20261109/execution_preparation';exe=R/'outputs/g5_original118_adapter_ablation_execution_20261109/staged/study'
    auditpath=R/'outputs/g5_original118_adapter_ablation_independent_20261109/Independent_Audit.json';audit=read(auditpath)
    assert audit['complete_engineering'] and audit['checks']==1381 and audit['complete_receipt_count']==5
    frozen=read(ep/'Frozen_Engineering_Protocol.json');inputs=read(ep/'All4_Original_Inputs.json')
    if isinstance(inputs,dict):inputs=inputs['inputs']
    rows=[]
    for i,item in enumerate(inputs):
        path=exe/f'primary_Original_{i:02d}.json';receipt=read(path);assert receipt['ordinal']==i and receipt['case_id']==item['case_id'] and receipt['replica']=='primary'
        assert receipt['input_token_ids']==item['input_token_ids'] and receipt['adapter_mode']==frozen['adapter_mode'] and receipt['adapter_disabled_during_every_forward']
        rows.append({'case_id':item['case_id'],'messages':item['messages'],'input_token_ids':item['input_token_ids'],'receipt':receipt,'receipt_ref':ref(path)})
    bundle={'status':'VERIFIED_PAID_FIRST_RESPONSES_FOR_NEW_TREATMENT_PREFIX_ONLY','adapter_mode':frozen['adapter_mode'],'immutable_inference_contract':frozen['immutable_inference_contract'],'rows':rows,'independent_closed_source_ref':ref(auditpath),'cold_replica_is_not_primary':True,'all_raw_responses_retained_without_quality_selection':True}
    put(P/'Paid_First_Response_Bundle.json',bundle)
    # New bridge-only boundary checks; no old successful suite or source controller is executed.
    spec=importlib.util.spec_from_file_location('g5_frontier_bridge_checks',W/'paid_prefix.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);checks=[]
    with tempfile.TemporaryDirectory(dir=P) as tmp:
        d=Path(tmp)
        for i,row in enumerate(rows):
            b=m.PaidFirstReply(bundle,i,d/f'{i}.jsonl');assert b(row['messages'])==row['receipt']['raw_text'];checks.append('exact_raw_primary_'+str(i))
            cold=m.PaidFirstReply(bundle,i,d/f'{i}.jsonl');assert cold.snapshot()==b.snapshot();checks.append('cold_paid_cursor_'+str(i))
            nextmsg=[{'role':'user','content':'SYNTHETIC_UNMEASURED_TEST_ONLY'}]
            try:cold(nextmsg)
            except m.Frontier as e:assert e.kind=='MISSING_DISABLED_GENERATION' and not e.payload['measured'];checks.append('unmeasured_stops_'+str(i))
            else:raise AssertionError('Unexpected generation')
        bad=json.loads(json.dumps(bundle));bad['adapter_mode']='ENABLED'
        try:m.PaidFirstReply(bad,0,d/'badmode.jsonl')
        except AssertionError:checks.append('enabled_treatment_rejected')
        else:raise AssertionError('Wrong mode admitted')
        b=m.PaidFirstReply(bundle,0,d/'wrongmsg.jsonl')
        try:b([{'role':'user','content':'WRONG'}])
        except AssertionError:checks.append('changed_causal_message_rejected')
        else:raise AssertionError('Wrong input admitted')
    put(P/'Bridge_Software_Checks.json',{'status':'PASS','checks':checks,'count':len(checks),'new_native_controller_model_PF_tokenizer_calls':0,'scope':'New paid-response bridge only; no old audits rerun'})
    initial='outputs/r118chrono_20261022/local_controller/fed_combined_load_1p5_line_35_MG1/reflection_v2/pf_000000.json'
    rec=read(R/initial);old=read(R/'outputs/reflection118_chronological_preparation_20261022/Frozen_Engineering_Protocol.json')
    sourcepaths=[x for x in old['local_source_hashes'] if x.startswith('work/e/')]+['work/frozen_physics_loader.py','work/native13_candidate_reconstruction_v10_label_graph_20261101.py','work/security_scientific_state_profile_20261102.py','work/coordinate_single_source_bound_owner_20261020.py','work/coordinate_native_inverter_linear_reference_20261020.py']
    paths=[W/x for x in ('owner.py','reader.py','coordinate.py','paid_prefix.py','prepare.py')]+[R/x for x in sourcepaths]
    paths += [P/'Paid_First_Response_Bundle.json',auditpath,ep/'Frozen_Engineering_Protocol.json',ep/'Original_Enabled_Runtime_Binding.json',ep/'Finite_Treatment_History_Disposition.json']
    for row in rows:paths.append(R/row['receipt_ref']['path'])
    paths += [R/initial]+[(R/initial).parent/rec[k]['path'] for k in ('before','after')]
    for path in W.glob('*.py'):ast.parse(path.read_text(encoding='utf-8'))
    base='work/e/pack/testbeds/federation_4mg_ieee118.json';zones='work/e/pack/testbeds/federation_4mg_ieee118_metadata.json';recipe='work/e/pack/scenarios/federation/fed_combined_load_1p5_line_35_MG1.json';paths += [R/x for x in (base,zones,recipe)]
    cost={'engineering_receipt':ref(exe/'Results.json'),'engineering_costs':audit['actual_costs'],'first_source_PF_record':ref(R/initial),'all_old_model_training_setup_PF_verification_failure_costs_remain_paid':True,'unknown_historical_costs_not_zero':True,'repeated_logical_reuse_is_not_new_model_or_new_physics':True,'counts_not_additive_across_original_and_derived_receipts':True}
    put(P/'Historical_Cost_Bindings.json',cost);paths.append(P/'Historical_Cost_Bindings.json')
    protocol={'status':'FROZEN_PROSPECTIVE_CPU_PAID_DISABLED_FRONTIER_REQUIRES_INDEPENDENT_GATE','case_index':0,'case_id':rows[0]['case_id'],'source_input_sha256':{p.relative_to(R).as_posix():sha(p) for p in paths},'base_net':base,'zones':zones,'recipe':recipe,'initial_record':initial,'seed':20261022,'codec_source':'work/native13_candidate_reconstruction_v10_label_graph_20261101.py','profile_source':'work/security_scientific_state_profile_20261102.py','owner_science_seconds':300,'closure_seconds':30,'reader_seconds':120,'storage_bound_bytes':268435456,'historical_costs_ref':ref(P/'Historical_Cost_Bindings.json'),'model_mode':frozen['adapter_mode'],'source_controller':'UNCHANGED_ORIGINAL_REFLECTION_V4','native_scope':'Two saved before/after decodes plus one base JSON decode; original read-only metrics/parser and hypothetical candidate preparation; zero native conversions/PF/model. Reuse initial result only after full typed input and exact kwargs equality.','stop':'Before second generation or first subsequent native PP call, whichever is reached first. Native frontier is unbound, not necessarily unexecuted.','cold_scope':'Persistent paid reply journal only; full warm-cold controller continuation remains unproved.','no_full_trajectory_or_G5_completion':True,'no_external_method_or_same_information_claim':True,'original_enabled_results_untouched':True}
    g3=read(R/'outputs/g3_first_packet_engineering_20261109/Protocol_v2.json') if (R/'outputs/g3_first_packet_engineering_20261109/Protocol_v2.json').exists() else read(R/'outputs/g3_first_packet_engineering_20261109/Protocol.json')
    protocol['runtime_versions']=g3['runtime_versions'];protocol['runtime_image_sha256']=g3['runtime_image_sha256']
    protocol['runtime_admission_scope']='Exact same pinned physics environment; no model import, tokenizer or native solve admitted.'
    put(P/'Protocol.json',protocol)
    for role,python,bound in [('owner','work/physics_env/Scripts/python.exe',330),('reader','work/vcsa_module_env/Scripts/python.exe',150)]:
        put(P/(role+'_Protocol.json'),{'single_owner':{'source':(W/(role+'.py')).relative_to(R).as_posix(),'sha256':sha(W/(role+'.py')),'output':(P/role).relative_to(R).as_posix(),'coordination':(P/(role+'_coordination')).relative_to(R).as_posix(),'python':python,'bound_seconds':bound},'require_ended_claims':[]})
    route={'status':'ENGINEERING_COMPLETE_NEXT_FINITE_CAUSAL_FRONTIER_PREPARED_NOT_LAUNCHED','new_engineering_audit':ref(auditpath),'four_full_disabled_episodes_ready':False,'first_response_adverse_evidence':'All four raw outputs preserved unchanged; no validity rescue. Exact original parser, including conditional reprompt, determines continuation.','ready_next_scope':protocol['native_scope'],'next_launch_command':'work/vcsa_module_env/Scripts/python.exe -X utf8 work/g5_disabled_frontier_20261109/coordinate.py','required_before_launch':['Independent owner/reader source gate bound to this Protocol','Fresh exact all-owner/PID/parent/source/claim absence and one fixed CPU assignment','Protocol storage/runtime/bounds/source checks admitted; no GPU'], 'after_actual_frontier':['Bind exact pending model message+tokens+adapter mode, or find exact paid pending native input; never infer missing means unexecuted.','Adapt frozen disabled remote generation to causal service, reuse returned tokens on failure and this paid first reply; do not use enabled answers or repeat cold generation.','Complete exact full controller checkpoint/RNG/paid-history restoration at first actual disabled commit; current prefix journal alone is insufficient.','Freeze all4 full trajectories, future newly executed first-only independent physical verification, partial handling, same source metrics and total costs before performance.'],'strong_controls':'Original DFF and literal DFF+DFFALT/FULLBOTH remain strong system references; message-only fitted numerical proposal control is not ready and hidden NET/Ybus baselines are not same information.','scope_limits':['Four fixed inspected development roots, no unused confirmation','Adapter ablation isolates only current serving treatment; historical paper SFT base revision remains unknown','No guarantee adapter-enabled improves system outcome; original adverse enabled-vs-DFF gate remains failed','All six main tasks retain their existing status']}
    put(P/'Updated_Full_Trajectory_Route.json',route)
    put(P/'Preparation_Result.json',{'status':'PREPARED_ONLY','protocol_ref':ref(P/'Protocol.json'),'bridge_checks':len(checks),'new_native_model_PF_controller_calls':0,'workflow_seconds':time.perf_counter()-start,'independent_source_gate_needed':True})
    print(json.dumps({'protocol':ref(P/'Protocol.json'),'bridge_checks':len(checks),'native_model_PF':0}))
if __name__=='__main__':main()
