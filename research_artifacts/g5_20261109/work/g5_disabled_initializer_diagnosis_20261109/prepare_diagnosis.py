"""Saved JSON/source diagnosis plus NEW pure guard negatives; no old owner call."""
import ast,hashlib,importlib.util,json,os,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];W=R/'work/g5_disabled_initializer_diagnosis_20261109';O=R/'outputs/g5_disabled_initializer_diagnosis_20261109'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return {'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
def put(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())
def main():
    begun=time.perf_counter();O.mkdir(exist_ok=False)
    E=R/'outputs/g5_disabled_frontier_20261109/owner';result=read(E/'Result.json');auditpath=R/'outputs/g5_disabled_frontier_20261109/reader/Independent_Audit.json';audit=read(auditpath)
    assert result['status']=='PARTIAL_FRONTIER_UNKNOWN' and audit['status']=='PASS_PRESERVED_PARTIAL_FRONTIER_UNKNOWN'
    assert result['counts']['logical_PF_calls']==1 and result['counts']['initial_paid_PF_reuses']==0 and result['counts']['paid_reply_uses']==0
    assert result['counts']['new_PF_calls']==result['counts']['new_model_calls']==0
    source=R/'work/e/pack/scripts/phase2d_iterative_blackboard_v0.py';tree=ast.parse(source.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_pf')
    call=next(n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='runpp')
    source_kw={n.arg:ast.literal_eval(n.value) for n in call.keywords}
    oldrecord=R/'outputs/r118chrono_20261022/local_controller/fed_combined_load_1p5_line_35_MG1/reflection_v2/pf_000000.json';saved_kw=read(oldrecord)['kwargs'];assert source_kw==saved_kw
    handlers=[ast.unparse(h.type) if h.type else 'BARE' for n in ast.walk(fn) if isinstance(n,ast.Try) for h in n.handlers]
    assert 'Exception' in handlers
    d={'status':'SOURCE_SAVED_ONLY_DIAGNOSIS_COMPLETE_ACTUAL_MISMATCH_DETAIL_UNKNOWN','actual_closed_result_ref':ref(E/'Result.json'),'partial_independent_review_ref':ref(auditpath),'source_ref':ref(source),'paid_record_ref':ref(oldrecord),'source_kwargs':source_kw,'saved_kwargs':saved_kw,'kwargs_mismatch_excluded_by_exact_source':True,'exact_initial_failure_unknown':True,'observation_gap':'Actual input snapshot/exception was not durably saved before admission. Either snapshot capture or typed equality could have failed. Do not assert cache-only or other exact cause.','source_mechanism':'Original run_pf catches Exception. Provider AssertionError/ValueError could become conv=False; outer owner discarded natural controller base_fail result and raised generic unexpected end.','old_source_and_artifacts_unchanged':True,'no_controller_decodes_native_model_PF_or_old_audit_rerun':True,'mandatory_future_changes':['Durably preserve actual kwargs/provenance before admission','Durably preserve actual full supported typed snapshot before equality','Retain comparison or capture failure details','Wrap entire provider operational boundary so assertions/time/storage/serialization failures become BaseException, not physical solver failure','Preserve any original natural controller return including base_fail','Use separately justified unentered integration namespace/protocol; no old restart, old-clock extension or relaxed projection'],'remaining_question':'Which actual full typed input field or capture precondition differs; existing saved evidence cannot recover it.','future_physical_or_model_entry_authorized':False}
    put(O/'Diagnosis.json',d)
    spec=importlib.util.spec_from_file_location('g5_new_initializer_guard_checks',W/'admission_capture.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    checks=[];writes={}
    def save(path,value):assert str(path) not in writes;writes[str(path)]=value
    actual={'full_fingerprint':{'alias':['a','b']},'full_typed_mapping':['dict',[['x',['int',1]]]]}
    def fresh():writes.clear()
    fresh();v=m.compare_and_preserve(None,source_kw,actual,source_kw,{'paid':True},lambda _:actual,save,Path('fixture'));assert v['supported_typed_snapshot_equal'];checks.append('exact_supported_input_admitted_without_restore')
    for label,changed,kw in [('typed_value',{'full_fingerprint':actual['full_fingerprint'],'full_typed_mapping':['different']},source_kw),('alias',{'full_fingerprint':{'alias':[]},'full_typed_mapping':actual['full_typed_mapping']},source_kw),('kwargs',actual,{**source_kw,'max_iteration':80})]:
        fresh()
        try:m.compare_and_preserve(None,kw,actual,source_kw,{},lambda _:changed,save,Path('fixture'))
        except m.InitialAdmissionStop as e:assert e.kind=='INITIAL_PAID_INPUT_NOT_EXACT';assert 'fixture/Actual_Initial_Input_Before_Admission.json'.replace('/',os.sep) in writes;checks.append(label+'_preserved_then_stop')
        else:raise AssertionError('Mismatch admitted')
    fresh()
    def failed_capture(_):raise ValueError('labelled mocked unsupported value')
    try:m.compare_and_preserve(None,source_kw,actual,source_kw,{},failed_capture,save,Path('fixture'))
    except m.InitialAdmissionStop as e:assert e.kind=='INITIAL_ADMISSION_CAPTURE_INCOMPLETE';checks.append('capture_failure_retained_no_PF_translation')
    else:raise AssertionError('Capture failure admitted')
    for kind in (AssertionError,TimeoutError,OSError):
        fresh()
        def failed(*a,**k):raise kind('labelled mocked operational failure')
        wrapped=m.prevent_solver_translation(failed,save,Path('fixture'))
        def original_exception_shape():
            try:wrapped();return True
            except Exception:return False
        try:original_exception_shape()
        except m.InitialAdmissionStop as e:assert e.kind=='OPERATIONAL_PROVIDER_FAILURE';checks.append(kind.__name__+'_escapes_original_Exception_handler')
        else:raise AssertionError('Operational failure swallowed')
    put(O/'New_Guard_Software_Checks.json',{'status':'PASS','checks':checks,'count':len(checks),'new_native_controller_model_PF_calls':0,'fixture_only_no_old_suite_rerun':True,'source_ref':ref(W/'admission_capture.py')})
    put(O/'Exact_Next.json',{'status':'FUTURE_INTEGRATION_SOURCE_HELPER_PREPARED_NO_OWNER_OR_LAUNCH_PROTOCOL','helper_ref':ref(W/'admission_capture.py'),'diagnosis_ref':ref(O/'Diagnosis.json'),'next':'Bind exact current failing initializer observation in a new prospective zero-science boundary owner, preserve complete actual input first; no weaker comparison. Root decides admission.','costs':{'workflow_seconds':time.perf_counter()-begun,'actual_saved_NET_decodes':0,'actual_source_controller_calls':0,'actual_native_conversions_PF_model_calls':0}})
    print(json.dumps({'diagnosis':ref(O/'Diagnosis.json'),'new_checks':len(checks),'native_calls':0}))
if __name__=='__main__':main()
