"""One event-bound completion save; no timer, scientific call, retry or allocation."""
import ctypes,hashlib,json,os
from ctypes import wintypes
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R/'outputs/higher_matched_scale_20261015';OUT=B/'completion_save'
def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def put(p,d):
    tmp=p.with_name(p.name+'.completion_tmp');tmp.write_text(json.dumps(d,indent=2),encoding='utf-8');tmp.replace(p)
def main():
    OUT.mkdir(exist_ok=False)
    with (OUT/'owner.claim').open('x',encoding='utf-8') as f:json.dump({'actual_pid':os.getpid(),'parent_pid':os.getppid(),'at_utc':now(),'role':'exit-triggered save only, no timer'},f)
    proto=read(B/'preparation/protocol.json');launch=read(B/'Launcher.json');handoff=read(B/'handoff/owner.claim')
    pids=[handoff['actual_pid'],handoff['actual_parent_pid']]
    for row in launch['owners']:
        claim=read(B/row['arm']/'owner.claim');pids.extend([claim['actual_pid'],claim['actual_parent_pid']])
    pids=list(dict.fromkeys(pids));kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForMultipleObjects.argtypes=[wintypes.DWORD,ctypes.POINTER(wintypes.HANDLE),wintypes.BOOL,wintypes.DWORD];kernel.WaitForMultipleObjects.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handles=[]
    for pid in pids:
        handle=kernel.OpenProcess(0x00100000,False,pid)
        if handle:handles.append(handle)
        else:assert ctypes.get_last_error()==87,'Cannot bind original process chain'
    put(OUT/'Ready.json',{'at_utc':now(),'bound_existing_process_ids':pids,'handles':len(handles),'timers':0,'new_scientific_calls':0})
    if handles:
        array=(wintypes.HANDLE*len(handles))(*handles);assert kernel.WaitForMultipleObjects(len(handles),array,True,0xFFFFFFFF)==0
        for handle in handles:kernel.CloseHandle(handle)
    states={arm:read(B/arm/'status.json') for arm in proto['arms']}
    actual_handoff=read(B/'handoff/status.json');complete=(B/'audit/All_Results.json').exists() and (B/'audit/Fixed_Gate_Decision.json').exists() and actual_handoff.get('reader_exit_code')==0
    pending_remote=[{'arm':a,'account':s.get('account'),'notebook_hash':s.get('notebook_hash'),'role':'exact remote release/preservation UNKNOWN; no retry or replacement'} for a,s in states.items() if s.get('runtime_allocated') and not s.get('runtime_released')]
    result={'at_utc':now(),'status':'COMPLETE_INDEPENDENTLY_AUDITED' if complete else 'TERMINAL_PARTIAL_OR_ANALYSIS_FAILURE_PRESERVED',
        'all_local_owner_handoff_chains_ended':True,'owner_states':states,'handoff':actual_handoff,'remote_release_or_preservation_pending':pending_remote,
        'no_new_scientific_calls':True,'timers_created':0,'physical_LLM_DSE_superiority':'NOT_TESTED','historical_development_not_unused_confirmation':True}
    if complete:
        results=read(B/'audit/All_Results.json');result['metrics']={arm:{k:v for k,v in item.items() if k in ['equal_world_exact_action','strict_schema_and_legal_fraction','hits','pairs']} for arm,item in results['arms'].items()}
        result['gate']=read(B/'audit/Fixed_Gate_Decision.json')
    put(OUT/'Verified_Terminal_Result.json',result)
    for name in ['outputs/critical_research_reset_20261010/Research_Resume_20261012.json','outputs/llm_value_relational_adaptation_research_20261009/latest_execution_status.json']:
        path=R/name;d=read(path);d.update({'latest_higher_matched_scale_terminal':result,'latest_owned_jobs':pending_remote,'latest_verified_at_utc':now()});put(path,d)
    header=f'HIGHER MATCHED SCALE TERMINAL {now()}\n\nRead outputs/higher_matched_scale_20261015/completion_save/Verified_Terminal_Result.json. Both actual owner/launcher chains and sole handoff ended; status {result["status"]}. Never rerun or retune either fixed arm, restart a reader, or select checkpoints. Missing evidence remains UNKNOWN. No automatic physical rollout/GPU/allocation/timer follows this result. Preserve complete actual artifacts/costs and failures. Native public OPF3attempts remain terminal compatibility exceptions; oldfullrecedinggate UNKNOWN. Overall six goals remain unachieved.\n\n'
    for name in ['outputs/Unattended_Execution_Runbook.md','outputs/llm_value_development/Next_Phase_Plan.md','RESEARCH_INDEX.md']:
        path=R/name;path.write_text(header+path.read_text(encoding='utf-8'),encoding='utf-8')
    with (R/'reseacrh progress.txt').open('a',encoding='utf-8') as f:f.write('\n'+header+json.dumps(result,indent=2)+'\n')
    put(OUT/'Completion_Saved.json',{'at_utc':now(),'all_available_results_saved':True,'new_scientific_calls':0,'timers_created':0})
if __name__=='__main__':main()
