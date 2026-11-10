"""One bounded CPU engineering owner and one first saved-only reader."""
import hashlib,json,os,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];P=R/'outputs/g5_disabled_frontier_20261109';O=P/'handoff'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())
def main():
    assert not O.exists() and not (P/'owner').exists() and not (P/'reader').exists()
    p=read(P/'Protocol.json');g=read(P/'FINAL_Gate.json');assert g['status']=='PASS_G5_PAID_DISABLED_FRONTIER_SOURCE' and g['protocol_sha256']==sha(P/'Protocol.json')
    for path,h in p['source_input_sha256'].items():assert sha(R/path)==h
    O.mkdir();put(O/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'source_sha256':sha(__file__)})
    roles={}
    for role in ('owner','reader'):
        if role=='reader':
            if not all((P/x).exists() for x in ('owner/Result.json','owner/Closed_Manifest.json','owner_coordination/End_ACK.json')):roles[role]={'status':'UNENTERED_NO_CLOSED_OWNER'};break
            assert read(P/'owner_coordination/End_ACK.json')['actual_owned_chain_ended']
        with (O/(role+'.log')).open('x',encoding='utf-8') as log:
            code=subprocess.call([str(R/'work/vcsa_module_env/Scripts/python.exe'),'-X','utf8',str(R/'work/coordinate_single_source_bound_owner_20261020.py'),'--protocol',str((P/(role+'_Protocol.json')).relative_to(R))],cwd=R,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        roles[role]={'exit_code':code}
    put(O/'Completion.json',{'roles':roles,'status':'TERMINAL_REVIEW_ACTUAL_EVIDENCE','no_model_allocation_PF_calls_by_coordinator':True})
    if roles.get('reader',{}).get('exit_code')!=0:raise SystemExit(1)
if __name__=='__main__':main()
