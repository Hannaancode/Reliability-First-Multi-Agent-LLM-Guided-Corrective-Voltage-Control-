"""Launch exactly two prospectively selected NEW adapted-model owners and one handoff."""
import hashlib,json,os,subprocess
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R/'outputs/higher_matched_scale_20261015';P=B/'preparation'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    ready=json.loads((P/'Final_Preallocation_Readiness.json').read_text());assert ready['status'].startswith('PASS_')
    assert sha(P/'protocol.json')==ready['protocol_sha256']
    p=json.loads((P/'protocol.json').read_text())
    for n,h in p['source_hashes'].items():assert sha(R/n)==h
    assert not any((B/arm).exists() for arm in p['arms']) and not (B/'handoff').exists()
    with (B/'Launch_Claim.json').open('x',encoding='utf-8') as f:json.dump({'actual_pid':os.getpid(),'parent_pid':os.getppid(),'at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(__file__)},f)
    owners=[]
    for arm in p['arms']:
        with (B/(arm+'_owner_console.log')).open('xb') as f:
            command=[str(R/'work/colab_access_env/Scripts/python.exe'),'-X','utf8','work/run_higher_matched_scale_colab_20261015.py','--arm',arm]
            child=subprocess.Popen(command,cwd=R,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            owners.append({'arm':arm,'launcher_pid':child.pid,'command':command})
    with (B/'handoff_console.log').open('xb') as f:
        command=[str(R/'work/physics_env/Scripts/python.exe'),'-X','utf8','work/continue_higher_matched_scale_audit_20261015.py','--small-pid',str(owners[0]['launcher_pid']),'--large-pid',str(owners[1]['launcher_pid'])]
        handoff=subprocess.Popen(command,cwd=R,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    result={'at_utc':datetime.now(timezone.utc).isoformat(),'owners':owners,'sole_handoff_launcher_pid':handoff.pid,'handoff_command':command,
        'protocol_sha256':sha(P/'protocol.json'),'third_profile_not_used_or_fallback':True,'no_automatic_retries':True}
    with (B/'Launcher.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.flush();os.fsync(f.fileno())
    print(json.dumps(result))
if __name__=='__main__':main()
