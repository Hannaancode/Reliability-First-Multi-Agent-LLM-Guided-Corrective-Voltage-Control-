"""Freeze only the previously missing actual initializer observation."""
import ast,hashlib,json,os,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];W=R/'work/g5_initializer_observation_20261109';P=R/'outputs/g5_initializer_observation_20261109';OLD=R/'outputs/g5_disabled_frontier_20261109'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return {'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
def put(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(v if isinstance(v,str) else json.dumps(v,indent=2)+'\n');f.flush();os.fsync(f.fileno())
def main():
    begun=time.perf_counter();assert not P.exists();P.mkdir()
    old=read(OLD/'Protocol_v2.json');result=read(OLD/'owner/Result.json');audit=read(OLD/'reader/Independent_Audit.json')
    assert result['status']=='PARTIAL_FRONTIER_UNKNOWN' and audit['status']=='PASS_PRESERVED_PARTIAL_FRONTIER_UNKNOWN'
    assert result['counts']['new_PF_calls']==result['counts']['new_model_calls']==result['counts']['initial_paid_PF_reuses']==result['counts']['paid_reply_uses']==0
    for role in ('owner','reader'):assert read(OLD/(role+'_coordination/End_ACK.json'))['actual_owned_chain_ended']
    coordinate=(R/'work/g5_disabled_frontier_20261109/coordinate_v2.py').read_text().replace('g5_disabled_frontier_20261109','g5_initializer_observation_20261109').replace('PASS_G5_PAID_DISABLED_FRONTIER_SOURCE','PASS_G5_INITIALIZER_INPUT_OBSERVATION_SOURCE').replace('Protocol_v2.json','Protocol.json')
    ast.parse(coordinate);put(W/'coordinate.py',coordinate)
    v0='work/e/pack/scripts/phase2d_iterative_blackboard_v0.py';reflection='work/e/audit/run_reflection_v4_safety_envelope.py'
    tree=ast.parse((R/reflection).read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_one_scenario_two_best_v2')
    statements=[ast.unparse(n) for n in fn.body[2:5]];assert statements==['net = copy.deepcopy(base_net)','net = v2.v0.apply_scenario_to_net(net, scenario, zones)','conv, err = v2.v0.run_pf(net)']
    snapshots=OLD/'owner/Saved_Initial_Before.json';snap=read(snapshots);assert set(snap)=={'full_fingerprint','full_typed_mapping'}
    p={'status':'PROSPECTIVE_DISTINCT_UNRECORDED_INITIAL_INPUT_OBSERVATION_NOT_FAILED_OWNER_RESTART','source_v0':v0,'source_reflection':reflection,'exact_initializer_statements':statements,'base_net':old['base_net'],'zones':old['zones'],'recipe':old['recipe'],'codec_source':old['codec_source'],'profile_source':old['profile_source'],'admission_source':'work/g5_disabled_initializer_diagnosis_20261109/admission_capture.py','saved_input_snapshot':snapshots.relative_to(R).as_posix(),'paid_initial_record':old['initial_record'],'science_seconds':300,'closure_seconds':30,'reader_seconds':120,'storage_bound_bytes':268435456,'runtime_versions':old['runtime_versions'],'runtime_image_sha256':old['runtime_image_sha256'],'old_failure_ref':ref(OLD/'owner/Result.json'),'old_partial_audit_ref':ref(OLD/'reader/Independent_Audit.json'),'old_clocks_ended_not_extended':True,'new_observable':'Actual initializer NET typed snapshot and exact kwargs that previous failed owner computed or attempted but did not durably preserve.','scope':'One base JSON decode, original deepcopy/apply_scenario/run_pf prefix; intercept BEFORE public runpp body. Full controller, metrics, prompt, model, physical conversion/solver, restoration and commits are forbidden.','old_NET_redecode':False,'mismatch_is_observation_not_failure_or_entry_permission':True,'stronger_trajectory_or_native_mapping_still_unknown':True,'no_relaxed_projection':True,'snapshot_scope':old['snapshot_scope']}
    paths=[W/n for n in ('owner.py','reader.py','coordinate.py','prepare.py')]+[R/p[k] for k in ('source_v0','source_reflection','base_net','zones','recipe','codec_source','profile_source','admission_source','saved_input_snapshot','paid_initial_record')]+[OLD/'owner/Result.json',OLD/'reader/Independent_Audit.json',OLD/'owner_coordination/End_ACK.json',OLD/'reader_coordination/End_ACK.json',R/'work/coordinate_single_source_bound_owner_20261020.py',R/'work/coordinate_native_inverter_linear_reference_20261020.py']
    for role,python,bound in [('owner','work/physics_env/Scripts/python.exe',330),('reader','work/vcsa_module_env/Scripts/python.exe',150)]:
        spec={'single_owner':{'source':(W/(role+'.py')).relative_to(R).as_posix(),'sha256':sha(W/(role+'.py')),'output':(P/role).relative_to(R).as_posix(),'coordination':(P/(role+'_coordination')).relative_to(R).as_posix(),'python':python,'bound_seconds':bound},'require_ended_claims':[]}
        put(P/(role+'_Protocol.json'),spec);paths.append(P/(role+'_Protocol.json'))
    p['source_input_sha256']={x.relative_to(R).as_posix():sha(x) for x in paths}
    for path in W.glob('*.py'):ast.parse(path.read_text(encoding='utf-8'))
    put(P/'Protocol.json',p)
    put(P/'Preparation_Result.json',{'status':'PREPARED_ONLY_INDEPENDENT_REVIEW_AND_FRESH_OWNERSHIP_REQUIRED','protocol_ref':ref(P/'Protocol.json'),'new_native_JSON_decode_controller_model_PF_calls':0,'previous_owner_and_successful_checks_rerun':False,'source_only_statement_gate':True,'workflow_seconds':time.perf_counter()-begun,'command':'work/vcsa_module_env/Scripts/python.exe -X utf8 work/g5_initializer_observation_20261109/coordinate.py'})
    print(json.dumps({'protocol_ref':ref(P/'Protocol.json'),'new_native_calls':0}))
if __name__=='__main__':main()
