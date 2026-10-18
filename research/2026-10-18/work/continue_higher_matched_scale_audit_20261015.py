"""One handoff bound to exact two owners; complete-only reader never on partials."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'outputs/higher_matched_scale_20261015'
p=argparse.ArgumentParser();p.add_argument('--small-pid',type=int,required=True);p.add_argument('--large-pid',type=int,required=True);a=p.parse_args()
OUT=BASE/'handoff';OUT.mkdir(exist_ok=False);(OUT/'owner.claim').write_text(json.dumps({'actual_pid':os.getpid(),'actual_parent_pid':os.getppid(),'command':sys.argv,'bound_small_pid':a.small_pid,'bound_large_pid':a.large_pid}))
def alive(pid):
    result=subprocess.run(['powershell','-NoProfile','-Command',f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; if($p){{$p.CommandLine}}"],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.stdout.strip():assert 'run_higher_matched_scale_colab_20261015.py' in result.stdout,'PID reused by another process';return True
    return False
def save(v):
    tmp=OUT/'status.tmp';tmp.write_text(json.dumps(v,indent=2));tmp.replace(OUT/'status.json')
while alive(a.small_pid) or alive(a.large_pid):
    save({'stage':'waiting_exact_owners','reader_started':False});time.sleep(30)
states=[json.loads((BASE/arm/'status.json').read_text()) for arm in ['public_3B','public_7B']]
for arm,state in zip(['public_3B','public_7B'],states):
    claim=json.loads((BASE/arm/'owner.claim').read_text());assert claim['actual_pid']==state['actual_pid'] and claim['actual_parent_pid']==state['actual_parent_pid']
    assert not alive(state['actual_pid']), 'Actual owner still live; no simultaneous reader'

if not all(s.get('exit_code')==0 and s['runtime_released'] and s.get('all_actual_artifacts_preserved') for s in states):
    save({'stage':'terminal_partial_no_complete_reader','reader_started':False,'states':states});raise SystemExit(1)
save({'stage':'sole_external_reader','reader_started':True})
with (OUT/'reader_stdout.log').open('x') as so,(OUT/'reader_stderr.log').open('x') as se:
    result=subprocess.run([str(ROOT/'work/physics_env/Scripts/python.exe'),'-X','utf8','work/audit_higher_matched_scale_20261015.py'],cwd=ROOT,stdout=so,stderr=se,creationflags=subprocess.CREATE_NO_WINDOW,timeout=900)
save({'stage':'complete' if result.returncode==0 else 'reader_failed_preserve_no_science_rerun','reader_started':True,'reader_exit_code':result.returncode})
