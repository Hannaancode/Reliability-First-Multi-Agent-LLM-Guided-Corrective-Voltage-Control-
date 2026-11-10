"""Independent saved-only first actual-input comparison, no normalization."""
import hashlib,json,os,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];P=R/'outputs/g5_initializer_observation_20261109';E=P/'owner';O=P/'reader'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
def value_sha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def differences(a,b,path=()):
    if type(a) is not type(b):yield list(path),'TYPE';return
    if isinstance(a,dict):
        for k in sorted(set(a)|set(b)):
            if k not in a or k not in b:yield list(path+(k,)),'MISSING_FIELD'
            else:yield from differences(a[k],b[k],path+(k,))
    elif isinstance(a,list):
        if len(a)!=len(b):yield list(path),'LIST_LENGTH'
        for i in range(min(len(a),len(b))):yield from differences(a[i],b[i],path+(i,))
    elif a!=b:yield list(path),'VALUE'
def main():
    began=time.monotonic();O.mkdir(exist_ok=False);put(O/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'source_sha256':sha(__file__)})
    while not (O/'Launcher_ACK.json').exists():assert time.monotonic()-began<45;time.sleep(.05)
    ack=read(O/'Launcher_ACK.json');assert ack['actual_pid']==os.getpid() and ack['actual_parent_pid']==os.getppid() and ack['fresh_exact_source_PID_parent_command']
    p=read(P/'Protocol.json');g=read(P/'FINAL_Gate.json');assert g['status']=='PASS_G5_INITIALIZER_INPUT_OBSERVATION_SOURCE' and g['protocol_sha256']==sha(P/'Protocol.json')
    for path,h in p['source_input_sha256'].items():assert sha(R/path)==h,path
    sys.path.insert(0,str(R/'work'));from coordinate_native_inverter_linear_reference_20261020 import process
    end=read(P/'owner_coordination/End_ACK.json');assert end['actual_owned_chain_ended']
    for pid in (end['actual_pid'],end['launcher_pid']):
        live=process(pid);assert live is None or 'g5_initializer_observation_20261109' not in (live.get('CommandLine') or '')
    checks=[]
    def check(ok,label):assert ok,label;checks.append(label)
    for name,d in read(E/'Closed_Manifest.json')['members'].items():check((E/name).stat().st_size==d['bytes'] and sha(E/name)==d['sha256'],'new closed '+name)
    result=read(E/'Result.json');complete=result['status']=='COMPLETE_DISTINCT_ACTUAL_INITIAL_INPUT_OBSERVATION' and end['exit_code']==0;comparison=None
    counts=result['counts'];check(counts['old_NET_decodes']==counts['native_public_body_calls']==counts['native_conversion_PF_model_controller_metric_commit_calls']==0,'no old native decode or scientific body')
    if complete:
        check(counts['new_base_JSON_decode_returns']==counts['source_apply_scenario_entries']==counts['source_run_pf_wrapper_entries']==counts['intercepted_public_call_intents']==counts['actual_input_snapshot_returns']==1,'exact finite observation counts')
        actual=read(E/'Actual_Initial_Input_Before_Admission.json');saved=read(R/p['saved_input_snapshot']);kw=read(E/'Initial_Kwargs_And_Provenance.json');proof=read(E/'Initial_Admission_Comparison.json')
        all_diffs=list(differences(actual,saved));comparison={'supported_full_typed_input_equal':actual==saved,'exact_kwargs_equal':kw['actual_kwargs']==kw['expected_kwargs'],'different_leaf_or_structure_count':len(all_diffs),'first100_difference_paths':all_diffs[:100],'all_differences_retained_in_full_input_pair':True,'actual_sha256':value_sha(actual),'saved_sha256':value_sha(saved),'no_projection_relaxation_or_cache_cause_assumption':True}
        check(proof['supported_typed_snapshot_equal']==comparison['supported_full_typed_input_equal'] and proof['exact_kwargs_equal']==comparison['exact_kwargs_equal'],'independent saved equality checks')
        check(proof['actual_snapshot_sha256']==comparison['actual_sha256'] and proof['saved_snapshot_sha256']==comparison['saved_sha256'],'independent exact source pair hashes')
        check(kw['expected_kwargs']==read(R/p['paid_initial_record'])['kwargs'],'original paid solver kwargs')
        put(O/'Exact_Actual_Input_Differences.json',comparison)
    put(O/'Independent_Audit.json',{'status':'PASS_COMPLETE_DISTINCT_INITIAL_INPUT_OBSERVATION' if complete else 'PASS_PRESERVED_PARTIAL_INPUT_OBSERVATION_UNKNOWN','complete':complete,'checks':len(checks),'check_labels':checks,'comparison':comparison,'counts':counts,'native_controller_PF_model_calls_by_reader':0,'input_reuse_admission_or_scientific_performance':False,'workflow_seconds':time.monotonic()-began})
    put(O/'Closed_Manifest.json',{'members':{x.relative_to(O).as_posix():{'bytes':x.stat().st_size,'sha256':sha(x)} for x in O.rglob('*') if x.is_file()}})
if __name__=='__main__':main()
