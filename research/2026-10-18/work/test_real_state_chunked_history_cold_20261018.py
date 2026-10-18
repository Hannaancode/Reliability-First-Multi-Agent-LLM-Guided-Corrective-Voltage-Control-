"""Saved real118-bus state transport + oversized record, software only, expired bound."""
import copy,hashlib,json,os,pickle,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np,pandapower as pp
import paid_receding_commit_and_history_v1 as old
import paid_receding_chunked_history_v2_20261018 as new
from bounded_chunk_evidence_store_v1_20261015 import restore as restore_chunks
R=Path(__file__).resolve().parents[1];B=R/'outputs/real_state_chunked_history_cold_engineering_20261018'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def main():
    started=time.perf_counter();B.mkdir(exist_ok=False)
    request= json.loads((R/'outputs/full_receding_paid_campaign_20261015/actual_cold_request/Request.json').read_text())
    protocol={'role':'SOFTWARE_ONLY_SAVED_STATE_TRANSPORT_NOT_EXECUTABLE_SCIENCE',
        'source':'Existing exact cold checkpoint1, preserved actual35MB history record50; no future physical outcome selection.',
        'original_absolute_deadline_not_extended':request['original_deadline_utc'],
        'test_changes':'Only fixture commit_mode namespace/protocol label/next_phase and transport history anchor. Preserve actual118NET, all operations/cap/ownedbank/receipts, RNG, costs and already expired deadline.',
        'no_scientific_queries_commits_model_optimizer_or_solve':True,'original_commit_ASTs':new.SOURCE_CERTIFICATE,
        'new_adapter_sha256':sha(R/'work/paid_receding_chunked_history_v2_20261018.py')}
    put(B/'Protocol.json',protocol)
    called=[]
    def forbidden(*a,**k):called.append('FORBIDDEN');raise AssertionError('No new physical or numerical solve permitted')
    pp.runpp=forbidden;pp.runopp=forbidden;np.linalg.solve=forbidden
    state=old.restore(R/request['checkpoint'],request['receipt'])
    assert state['absolute_deadline_utc']==request['original_deadline_utc']
    assert datetime.now(timezone.utc)>datetime.fromisoformat(state['absolute_deadline_utc'])
    expected_fields=old.fields(state['net']);expected_cursor=copy.deepcopy(state['cursor']);expected_costs=copy.deepcopy(state['costs'])
    expected_python=pickle.dumps(state['python_rng'],protocol=5);expected_numpy=pickle.dumps(state['numpy_rng'],protocol=5)
    prior_registry=set(state['paid_query_registry'])
    actual_record=json.loads((R/'outputs/bounded_chunk_actual_history_engineering_20261015/Results.json').read_text())
    raw=restore_chunks(actual_record['source_and_input_anchor'])[0]['payload'];assert len(raw)==35228332
    # Fixture namespace changes are explicit; original scientific state/files are never rewritten.
    state['cursor']['commit_mode']=new.MODE
    state['protocol_sha256']=sha(B/'Protocol.json');state['next_phase']='SOFTWARE_FIXTURE_NO_EXECUTION_ALLOWED'
    history=new.History(B/'history',source_anchor=protocol['new_adapter_sha256'],input_anchor=hashlib.sha256(raw).hexdigest(),max_bytes=2*1024**3)
    history.append('SOFTWARE_FIXTURE_ARCHIVED_LARGE_RECORD',{'original_raw_record':raw.decode('utf-8'),'not_a_new_scientific_event':True})
    state['paid_query_registry'][new.HISTORY_KEY]=history.anchor()
    anchors={'source':protocol['new_adapter_sha256'],'input':request['receipt']['raw_sha256'],'paid_receipt':request['receipt']['manifest_sha256'],'predecessor':request['receipt']['state_fingerprint']}
    receipt=new.save_complete(B/'checkpoint1',state,anchors)
    recovered,events=new.restore_complete(B/'checkpoint1',receipt)
    controls={'all118_vm_angle_P_Q_fields_exact':new.fields(recovered['net'])==expected_fields,
        'all_operation_cap_stock_and_prior_commit_cursor_preserved_except_explicit_namespace':{k:v for k,v in recovered['cursor'].items() if k!='commit_mode'}=={k:v for k,v in expected_cursor.items() if k!='commit_mode'},
        'costs_exact':recovered['costs']==expected_costs,'python_RNG_exact':pickle.dumps(recovered['python_rng'],protocol=5)==expected_python,
        'numpy_RNG_exact':pickle.dumps(recovered['numpy_rng'],protocol=5)==expected_numpy,
        'paid_registry_identity_set_exact':set(recovered['paid_query_registry'])==prior_registry,
        '35MB_record_exact_after_full_state_cold_restore':events[0]['payload']['original_raw_record'].encode()==raw,
        'original_absolute_bound_preserved_and_expired':recovered['absolute_deadline_utc']==request['original_deadline_utc'],
        'fixture_cannot_claim_live_scientific_next_phase':recovered['next_phase']=='SOFTWARE_FIXTURE_NO_EXECUTION_ALLOWED'}
    try:new.restore_complete(R/request['checkpoint'],request['receipt'])
    except AssertionError:controls['old_study_receipt_rejected_by_new_mode']=True
    else:raise AssertionError('Old mode silently admitted')
    history.append('SECOND_SOFTWARE_EVENT',{'no_science':True})
    try:new.restore_complete(B/'checkpoint1',receipt)
    except ValueError:controls['stale_checkpoint_after_new_event_rejected_no_rollback']=True
    else:raise AssertionError('Stale cursor admitted')
    state['paid_query_registry'][new.HISTORY_KEY]=history.anchor();receipt2=new.save_complete(B/'checkpoint2',state,anchors)
    recovered2,events2=new.restore_complete(B/'checkpoint2',receipt2);history.close()
    controls['latest_complete_cold_history_has_both_events']=len(events2)==2
    assert all(controls.values()) and not called
    put(B/'Results.json',{'status':'PASS_SAVED_REAL_NET_CURSOR_RNG_COST_COMPLETE_STATE_CHUNKED_HISTORY_COLD_TRANSPORT',
        'controls':controls,'actual_large_record_bytes':len(raw),'source_checkpoint':request['checkpoint'],'source_receipt':request['receipt'],
        'new_checkpoint_receipt':receipt2,'all_original_deadlines_costs_actions_preserved':True,'new_model_PF_optimizer_derivative_forecast_solve_calls':0,
        'workflow_seconds':time.perf_counter()-started,'original_experiment_resumed_or_modified':False,
        'limits':'Saved-state transport software engineering only, not actual following-query/controller factory integration or a new physical trajectory. Expired old budget stays expired; oldmissing26th state not recovered.'})
    print(json.dumps({'real_state_chunked_cold_transport':'PASS','controls':len(controls),'new_science_calls':0}))
if __name__=='__main__':main()
