"""Saved-only first review of declared common archived-state entry."""
import hashlib,json,os,sys,time
from pathlib import Path
from paid_prefix import PaidFirstReply,put
R=Path(__file__).resolve().parents[2];P=R/'outputs/g5_conditional_archived_start_20261109';E=P/'owner';O=P/'reader'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    began=time.monotonic();O.mkdir(exist_ok=False);put(O/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'source_sha256':sha(__file__)})
    while not (O/'Launcher_ACK.json').exists():assert time.monotonic()-began<45;time.sleep(.05)
    ack=read(O/'Launcher_ACK.json');assert ack['actual_pid']==os.getpid() and ack['actual_parent_pid']==os.getppid() and ack['fresh_exact_source_PID_parent_command']
    p=read(P/'Protocol.json');g=read(P/'FINAL_Gate.json');assert g['status']=='PASS_G5_CONDITIONAL_ARCHIVED_START_SOURCE' and g['protocol_sha256']==sha(P/'Protocol.json')
    for path,h in p['source_input_sha256'].items():assert sha(R/path)==h,path
    sys.path.insert(0,str(R/'work'));from coordinate_native_inverter_linear_reference_20261020 import process
    end=read(P/'owner_coordination/End_ACK.json');assert end['actual_owned_chain_ended']
    for pid in (end['actual_pid'],end['launcher_pid']):
        live=process(pid);assert live is None or 'g5_conditional_archived_start_20261109' not in (live.get('CommandLine') or '')
    checks=[]
    def check(ok,label):assert ok,label;checks.append(label)
    for name,ref in read(E/'Closed_Manifest.json')['members'].items():check((E/name).stat().st_size==ref['bytes'] and sha(E/name)==ref['sha256'],'new closed '+name)
    result=read(E/'Result.json');c=result['counts'];complete=result['status']=='COMPLETE_CONDITIONAL_ARCHIVED_START_FRONTIER' and end['exit_code']==0
    for key in ('new_initializer_calls','new_model_calls','new_PF_calls','native_input_conversions','actual_commits'):check(c[key]==0,key+' zero')
    if complete:
        check(c['archived_after_decode_returns']==c['paid_disabled_reply_uses']==1,'one charged archived-state load and one exact paid reply')
        check(read(E/'Archived_Common_Start.json')==read(E/'Actual_First_Decision_Start.json'),'full supported archived-start fingerprint/value equality')
        source=read(E/'Conditional_Source_Binding.json');check(source['all_post_initializer_ASTs_unchanged'] and source['changed_input_contract']=='CONDITIONAL_ARCHIVED_SOLVED_INITIAL_STATE','explicit conditional input and unchanged tail')
        bundle=read(R/p['paid_reply_bundle']);check(read(E/'Exact_First_Messages.json')==bundle['rows'][0]['messages'],'exact original causal first message')
        bridge=PaidFirstReply(bundle,0,E/'Paid_Model_Uses.jsonl');check(bridge.snapshot()==read(E/'Paid_Model_Checkpoint.json') and bridge.cursor==1,'paid mode/token/raw reply and persistent cursor')
        frame=read(E/'Pending_Causal_Frame.json');check(set(('net','result','failed_sigs','failed_actions','feedback_state','it','zone','zs','global_uv'))<=set(frame['typed_locals']),'critical pending source state retained')
        if result['frontier']['kind']=='MISSING_DISABLED_GENERATION':check(bridge.pending==result['frontier']['payload'] and bridge.pending['measured'] is False,'unmeasured model boundary preserved')
        elif result['frontier']['kind']=='NATIVE_IDENTITY_NOT_YET_BOUND':check(read(E/'Pending_Native_Input.json')['public_body_called'] is False,'native request stopped before body')
        else:raise AssertionError('Unexpected frontier')
    put(O/'Independent_Audit.json',{'status':'PASS_COMPLETE_CONDITIONAL_ARCHIVED_START_FRONTIER' if complete else 'PASS_PRESERVED_PARTIAL_CONDITIONAL_FRONTIER_UNKNOWN','complete':complete,'checks':len(checks),'check_labels':checks,'counts':c,'frontier':result['frontier'],'conditional_initial_state_contract':'Common archived paid initial state; original pre-initializer physical-call identity is not asserted.','new_native_controller_model_PF_calls_by_reader':0,'same_information_control_or_full_trajectory_superiority':False,'workflow_seconds':time.monotonic()-began})
    put(O/'Closed_Manifest.json',{'members':{f.relative_to(O).as_posix():{'bytes':f.stat().st_size,'sha256':sha(f)} for f in O.rglob('*') if f.is_file()}})
if __name__=='__main__':main()
