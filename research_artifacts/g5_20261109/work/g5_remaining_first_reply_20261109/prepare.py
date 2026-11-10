"""Prospective remaining first-reply source/metadata only; no observation rerun."""
import ast,hashlib,json,os,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];W=Path(__file__).resolve().parent
P=R/'outputs/g5_remaining_first_reply_20261109'
OLD=R/'outputs/g5_conditional_archived_start_20261109'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):
    p=Path(p);return {'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
def put(p,v):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def main():
    begun=time.perf_counter();P.mkdir(exist_ok=False)
    proposal_path=R/'outputs/g5_copy_cache_source_resolution_20261109/Source_Proposal.json'
    assert sha(proposal_path)=='536ee7ee29f64329dc608da3aa2fd0202fa85558e721a65f2938a0ce72985597'
    proposal=read(proposal_path);p=read(OLD/'Protocol.json')
    old_result=read(OLD/'owner/Result.json');old_audit=read(OLD/'reader/Independent_Audit.json')
    assert old_result['status']=='PARTIAL_CONDITIONAL_FRONTIER_UNKNOWN'
    assert old_result['frontier']['kind']=='COMMON_ARCHIVED_STATE_COPY_DIFFERS'
    assert all(old_result['counts'][k]==0 for k in ('paid_disabled_reply_uses','new_model_calls','new_PF_calls','actual_commits'))
    assert old_audit['status']=='PASS_PRESERVED_PARTIAL_CONDITIONAL_FRONTIER_UNKNOWN' and old_audit['complete'] is False
    assert all(read(OLD/(role+'_coordination')/'End_ACK.json')['actual_owned_chain_ended'] for role in ('owner','reader'))
    p['status']='PROSPECTIVE_REMAINING_FIRST_PAID_REPLY_REQUIRE_REVIEW'
    p['source_resolution_proposal_ref']=ref(proposal_path)
    p['first_decision_reference']=proposal['source_refs']['actual_source_produced_first_decision']
    assert p['first_decision_reference']['sha256']=='33143abbc527f8f145e927c5c22421ad5304c7068d25bf0286c908efea05c8a3'
    p['prior_pre_copy_snapshot_ref']=proposal['source_refs']['raw_archived_before_copy']
    p['prior_partial_result_ref']=ref(OLD/'owner/Result.json')
    p['prior_partial_audit_ref']=ref(OLD/'reader/Independent_Audit.json')
    p['prior_partial_protocol_ref']=ref(OLD/'Protocol.json')
    p['first_decision_reference_contract']='Compare complete supported actual first-decision snapshot to the preserved ORIGINAL source-produced snapshot at that same boundary, after original deepcopy and original observations. Never compare it to the pre-copy cache layout; never strip or materialize caches. Mismatch remains a stopped partial.'
    p['conditional_start_definition']='Same exact archived solved NET and original source-required copy/post-initializer statements. Necessary new-process prefix reconstruction is charged; original snapshots/costs and prior failed comparison remain preserved. New work is first paid disabled reply consumption and the following previously unentered source frontier only.'
    p['new_first_entry_scope']='One fixed first root, previously unconsumed disabled paidreply0; stop before the next missing generation or any native input body. All4 fixed roots remain eventual scope, no case/outcome selection.'
    p['prior_observation_owner_rerun']=False
    p['old_partial_reclassified_as_pass']=False
    costs={'prior_historical_costs_ref':p['historical_costs_ref'],
        'prior_partial_owner_result_ref':p['prior_partial_result_ref'],'prior_partial_audit_ref':p['prior_partial_audit_ref'],
        'prior_owner_workflow_seconds':old_result['workflow_seconds'],'prior_reader_workflow_seconds':old_audit['workflow_seconds'],
        'prior_owner_counts':old_result['counts'],'all_prior_training_model_physics_preparation_failure_costs_remain_paid':True,
        'new_setup':'One necessary saved after-NET decode and source-prefix reconstruction, separately charged; no new initializer/model/PF.',
        'reference_reuse':'Prior actual first-decision JSON/source proof reused without rerunning its observation owner.'}
    put(P/'Historical_Cost_Bindings.json',costs);p['historical_costs_ref']=ref(P/'Historical_Cost_Bindings.json')
    p['source_input_sha256']=dict(p['source_input_sha256'])
    # Pin the actual pandas/pandapower copy/getter definitions, observer and both
    # saved snapshots from the reviewed finite source explanation.
    for item in proposal['source_refs'].values():
        path=R/item['path'];assert sha(path)==item['sha256']
        p['source_input_sha256'][item['path']]=item['sha256']
    for path in sorted(W.glob('*.py')):
        ast.parse(path.read_text(encoding='utf-8'));r=ref(path);p['source_input_sha256'][r['path']]=r['sha256']
    assert sha(W/'continuation.py')==sha(R/'work/g5_conditional_archived_start_20261109/continuation.py')
    assert sha(W/'paid_prefix.py')==sha(R/'work/g5_conditional_archived_start_20261109/paid_prefix.py')
    for role,python,bound in [('owner','work/physics_env/Scripts/python.exe',330),('reader','work/vcsa_module_env/Scripts/python.exe',150)]:
        put(P/(role+'_Protocol.json'),{'single_owner':{'source':(W/(role+'.py')).relative_to(R).as_posix(),
            'sha256':sha(W/(role+'.py')),'output':(P/role).relative_to(R).as_posix(),
            'coordination':(P/(role+'_coordination')).relative_to(R).as_posix(),'python':python,'bound_seconds':bound},'require_ended_claims':[]})
        r=ref(P/(role+'_Protocol.json'));p['source_input_sha256'][r['path']]=r['sha256']
    for path in [proposal_path,P/'Historical_Cost_Bindings.json',OLD/'owner/Result.json',OLD/'owner/Closed_Manifest.json',
                 OLD/'reader/Independent_Audit.json',OLD/'reader/Closed_Manifest.json',OLD/'owner_coordination/End_ACK.json',
                 OLD/'reader_coordination/End_ACK.json',OLD/'handoff/Completion.json',OLD/'Protocol.json']:
        r=ref(path);p['source_input_sha256'][r['path']]=r['sha256']
    put(P/'Protocol.json',p)
    put(P/'Preparation_Result.json',{'status':'PREPARED_UNENTERED_FIRST_PAID_REPLY_REQUIRES_INDEPENDENT_SOURCE_REVIEW',
        'protocol_ref':ref(P/'Protocol.json'),'first_decision_reference':p['first_decision_reference'],
        'source_ast_tail_and_paid_reply_helper_unchanged':True,'full_supported_snapshot_equality_not_relaxed':True,
        'new_native_controller_parser_model_PF_calls':0,'old_observation_owners_readers_or_fixtures_rerun':False,
        'workflow_seconds':time.perf_counter()-begun,'launch_allowed_by_preparation':False,
        'command':'work/vcsa_module_env/Scripts/python.exe -X utf8 work/g5_remaining_first_reply_20261109/coordinate.py'})
    print(json.dumps(ref(P/'Protocol.json')))
if __name__=='__main__':main()
