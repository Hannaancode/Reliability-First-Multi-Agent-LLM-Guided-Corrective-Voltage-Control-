"""First saved-only review of new paid disabled prefix; no original replay."""
import hashlib,json,os,sys,time
from pathlib import Path
from paid_prefix import PaidFirstReply,put
R=Path(__file__).resolve().parents[2];P=R/'outputs/g5_disabled_frontier_20261109';O=P/'reader';E=P/'owner'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    begun=time.monotonic();O.mkdir(exist_ok=False);put(O/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'source_sha256':sha(__file__)})
    while not (O/'Launcher_ACK.json').exists():assert time.monotonic()-begun<45;time.sleep(.05)
    ack=read(O/'Launcher_ACK.json');assert ack['actual_pid']==os.getpid() and ack['actual_parent_pid']==os.getppid() and ack['fresh_exact_source_PID_parent_command']
    p=read(P/'Protocol_v2.json');gate=read(P/'FINAL_Gate.json');assert gate['status']=='PASS_G5_PAID_DISABLED_FRONTIER_SOURCE' and gate['protocol_sha256']==sha(P/'Protocol_v2.json')
    for path,h in p['source_input_sha256'].items():assert sha(R/path)==h
    sys.path.insert(0,str(R/'work'));from coordinate_native_inverter_linear_reference_20261020 import process
    end=read(P/'owner_coordination/End_ACK.json');assert end['actual_owned_chain_ended']
    for pid in (end['actual_pid'],end['launcher_pid']):
        live=process(pid);assert live is None or 'g5_disabled_frontier_20261109' not in (live.get('CommandLine') or '')
    checks=[]
    def check(ok,label):assert ok,label;checks.append(label)
    for name,ref in read(E/'Closed_Manifest.json')['members'].items():
        path=E/name;check(path.stat().st_size==ref['bytes'] and sha(path)==ref['sha256'],'new closed '+name)
    result=read(E/'Result.json');counts=result['counts'];complete=result['status']=='COMPLETE_PAID_DISABLED_CAUSAL_FRONTIER' and end['exit_code']==0
    for key in ('new_model_calls','new_PF_calls','native_input_conversions','native_algorithm_calls','actual_commits'):check(counts[key]==0,key+' zero')
    if complete:
        check(counts['initial_paid_PF_reuses']==1 and counts['paid_reply_uses']==1,'one paid physical root and disabled reply used')
        check(counts['saved_NET_decode_returns']==2 and counts['base_json_decode_returns']==1,'explicit new input decoding costs')
        check(read(E/'Actual_Initial_Input.json')==read(E/'Saved_Initial_Before.json'),'full typed paid initial input exact')
        bridge=PaidFirstReply(read(P/'Paid_First_Response_Bundle.json'),0,E/'Model_Paid_Use.jsonl')
        check(bridge.snapshot()==read(E/'Paid_Model_Checkpoint.json'),'new journal cold metadata reconstruction exact')
        check(bridge.cursor==1,'exact first paid reply consumed; exposure caveat retained')
        frame=read(E/'Boundary_Source_Frame.json')
        check(set(('net','result','failed_sigs','failed_actions','feedback_state','it','zone','zs','global_uv'))<=set(frame['typed_locals']),'critical causal fields represented')
        kind=result['frontier']['kind']
        if kind=='MISSING_DISABLED_GENERATION':check(bridge.pending==result['frontier']['payload'] and bridge.pending['measured'] is False,'missing model request preserved before inference')
        elif kind=='NATIVE_IDENTITY_NOT_YET_BOUND':
            inp=read(E/'Pending_Native_Input.json');check(inp['new_public_or_backend_call'] is False,'pending native input preserved before call')
            check(inp['classification']=='UNBOUND_NATIVE_IDENTITY_NOT_CLAIMED_UNEXECUTED','no false no-history claim')
        else:raise AssertionError('Unadmitted boundary kind')
    put(O/'Independent_Audit.json',{'status':'PASS_COMPLETE_PAID_DISABLED_CAUSAL_FRONTIER_ENGINEERING' if complete else 'PASS_PRESERVED_PARTIAL_FRONTIER_UNKNOWN','checks':len(checks),'check_labels':checks,'counts':counts,'frontier':result['frontier'],'complete':complete,'new_model_native_PF_conversion_controller_calls_by_reader':0,'cold_scope':'Saved provider journal only; no full process or suspended-controller restart claim','full_trajectory_or_adapter_superiority':False,'workflow_seconds':time.monotonic()-begun})
    put(O/'Closed_Manifest.json',{'members':{f.relative_to(O).as_posix():{'bytes':f.stat().st_size,'sha256':sha(f)} for f in O.rglob('*') if f.is_file()}})
if __name__=='__main__':main()
