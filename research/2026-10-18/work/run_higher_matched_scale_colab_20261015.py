"""Exclusive prospectively assigned T4 owner/collector; never fallback or science retry."""
import argparse,ast,base64,hashlib,json,logging,os,subprocess,time,uuid,zipfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession,Request
from colab_cli.client import Client,Prod,Variant,Accelerator
from colab_cli.runtime import ColabRuntime
from google_account_profile import verify_account
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT);logging.disable(logging.CRITICAL)
PREP=ROOT/'outputs/higher_matched_scale_20261015/preparation';proto=json.loads((PREP/'protocol.json').read_text())
p=argparse.ArgumentParser();p.add_argument('--arm',required=True,choices=proto['arms']);arm=p.parse_args().arm
OUT=ROOT/'outputs/higher_matched_scale_20261015'/arm;assert not OUT.exists(),'No restart';OUT.mkdir()
expected=proto['profiles'][arm];adc=Path(r'C:\Users\HOME\AppData\Roaming')/('gcloud' if arm=='public_3B' else 'gcloud-hiergrid-sheenah')/'application_default_credentials.json'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
state={'stage':'preconditions','arm':arm,'account':expected,'actual_pid':os.getpid(),'actual_parent_pid':os.getppid(),'command':__import__('sys').argv,
       'started_at_utc':now(),'allocation_requests':0,'runtime_allocated':False,'runtime_released':False,'science_started':False}
def save():
    state['updated_at_utc']=now();tmp=OUT/'status.tmp';tmp.write_text(json.dumps(state,indent=2));tmp.replace(OUT/'status.json')
with (OUT/'owner.claim').open('x') as f:json.dump({**state,'source_sha256':sha(Path(__file__)),'protocol_sha256':sha(PREP/'protocol.json')},f)
def preserve(path,b):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():assert path.read_bytes()==b;return
    tmp=path.with_name('.transfer_'+uuid.uuid4().hex)
    with tmp.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
class BoundedSession(AuthorizedSession):
    def request(self,*a,**kw):kw.setdefault('timeout',(10,30));return super().request(*a,**kw)
session=client=runtime=assignment=None;safe_release=True;refreshed=0;acks=[]
def fresh():
    global assignment,refreshed
    value=client._get_assignment(nbh,variant=Variant.GPU,accelerator=Accelerator.T4)
    assert getattr(value,'endpoint',None)==state['endpoint'] and getattr(value,'runtime_proxy_info',None) is not None,'Exact runtime unavailable; no replacement'
    assignment=value;refreshed=time.monotonic()
def content(method,path,payload=None,file=False):
    for attempt in range(3):
        if time.monotonic()-refreshed>100:fresh()
        try:
            r=requests.request(method,assignment.runtime_proxy_info.url.rstrip('/')+'/api/contents/'+quote(path,safe='/'),params={'authuser':'0','colab-runtime-proxy-token':assignment.runtime_proxy_info.token,'content':'1',**({'format':'base64'} if file and method=='GET' else {})},json=payload,timeout=(10,30))
            if r.status_code==404:raise FileNotFoundError(path)
            r.raise_for_status();return r.json()
        except (requests.exceptions.Timeout,requests.exceptions.ConnectionError,requests.exceptions.HTTPError):
            if attempt==2:raise
            time.sleep(3);fresh()
def raw(path):
    v=content('GET',path,file=True);return base64.b64decode(v['content']) if v.get('format')=='base64' else v['content'].encode()
def execute(code,seconds=60):
    ast.parse(code);out=runtime.execute_code(code,allow_stdin=False,timeout=seconds);assert not any(v.get('output_type')=='error' for v in out),'Remote control failure';return out
REMOTE='content/hiergrid_execution/outputs'
def collect_package(number):
    name=f'package_{number:03d}';path=REMOTE+'/transfer/'+name;desc=json.loads(raw(path+'/descriptor.json'));assert desc['number']==number
    local=OUT/'packages'/name;local.mkdir(parents=True,exist_ok=True);preserve(local/'descriptor.json',json.dumps(desc,indent=2).encode())
    for part in desc['parts']:
        assert '/' not in part['name'] and '\\' not in part['name'] and part['bytes']<=2*1024*1024
        file=local/part['name']
        if not file.exists():preserve(file,raw(path+'/'+part['name']))
        assert file.stat().st_size==part['bytes'] and sha(file)==part['sha256']
    archive=local/'package.zip'
    if not archive.exists():
        tmp=local/'package.tmp'
        with tmp.open('wb') as f:
            for part in desc['parts']:f.write((local/part['name']).read_bytes())
            f.flush();os.fsync(f.fileno())
        assert tmp.stat().st_size==desc['archive_bytes'] and sha(tmp)==desc['archive_sha256'];tmp.replace(archive)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(desc['members'])|{'journal_delta.jsonl'}
        for n,v in desc['members'].items():
            assert not n.startswith('/') and '..' not in Path(n).parts and ':' not in n and '\\' not in n
            b=z.read(n);assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256'];preserve(OUT/'staged/study'/n,b)
        delta=z.read('journal_delta.jsonl');assert hashlib.sha256(delta).hexdigest()==desc['journal_delta_sha256']
        previous=(OUT/'events.jsonl').read_bytes() if (OUT/'events.jsonl').exists() else b''
        if len(previous)==desc['journal_prefix_bytes']:previous=previous[:desc['journal_offset']]
        assert len(previous)==desc['journal_offset'] and hashlib.sha256(previous).hexdigest()==desc['journal_previous_sha256']
        prefix=previous+delta;assert len(prefix)==desc['journal_prefix_bytes'] and hashlib.sha256(prefix).hexdigest()==desc['journal_prefix_sha256']
        if not (OUT/'events.jsonl').exists() or (OUT/'events.jsonl').stat().st_size==len(previous):
            with (OUT/'events.jsonl').open('ab') as f:f.write(delta);f.flush();os.fsync(f.fileno())
    cert=local/'CPU_Verification.json'
    with (local/'verify_stdout.log').open('x') as so,(local/'verify_stderr.log').open('x') as se:
        r=subprocess.run([str(ROOT/'work/vcsa_module_env/Scripts/python.exe'),'-X','utf8','work/verify_matched_scale_package.py','--package',str(archive),'--descriptor',str(local/'descriptor.json'),'--prep',str(PREP),'--prefix',str(OUT/'events.jsonl'),'--certificate',str(cert)],stdout=so,stderr=se,cwd=ROOT,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    assert r.returncode==0 and json.loads(cert.read_text())['all_passed'],'CPU full-state proof failed, no ACK'
    ack={'number':number,'archive_sha256':desc['archive_sha256'],'journal_prefix_sha256':desc['journal_prefix_sha256'],'full_state_and_bytes_verified':True}
    content('PUT',path+'/ack.json',{'type':'file','format':'text','content':json.dumps(ack)});preserve(local/'ACK.json',json.dumps(ack).encode());acks.append(ack)
    state['verified_ACK_packages']=len(acks);save()
def observe():
    try:state['remote_progress']=json.loads(raw(REMOTE+'/science/progress.json'));save()
    except FileNotFoundError:pass
    try:collect_package(len(acks))
    except FileNotFoundError:pass
def closed():
    desc=json.loads(raw(REMOTE+'/closed_descriptor.json'))
    for n,v in desc['members'].items():
        assert not n.startswith('/') and '..' not in Path(n).parts and ':' not in n and '\\' not in n
        path=OUT/'staged/study'/n
        if path.exists() and path.stat().st_size==v['bytes'] and sha(path)==v['sha256']:continue
        pieces=[]
        for part in v['parts']:
            b=raw(REMOTE+'/closed_parts/'+part['name']);assert len(b)==part['bytes'] and hashlib.sha256(b).hexdigest()==part['sha256'];pieces.append(b)
        b=b''.join(pieces);assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256']
        if n=='events.jsonl':
            old=(OUT/'events.jsonl').read_bytes();assert b.startswith(old)
        preserve(path,b)
    preserve(OUT/'Closed_Descriptor.json',json.dumps(desc,indent=2).encode());preserve(OUT/'Actual_Exit.json',raw(REMOTE+'/exit.json'))
    state['exit_code']=desc['exit_code'];state['all_actual_artifacts_preserved']=True;save()
save()
try:
    assert sha(Path(__file__))==proto['source_hashes']['work/run_higher_matched_scale_colab_20261015.py']
    for n,h in proto['source_hashes'].items():assert sha(ROOT/n)==h
    payload=json.loads((PREP/'Payload.json').read_text());archive=ROOT/payload['path'];assert archive.stat().st_size==payload['bytes'] and sha(archive)==payload['sha256']
    os.environ['HIERGRID_EXPECTED_GOOGLE_ACCOUNT']=expected;credentials=Credentials.from_authorized_user_file(str(adc));transport=Request()
    def refresh(*a,**kw):kw.setdefault('timeout',25);return transport(*a,**kw)
    credentials.refresh(refresh);session=BoundedSession(credentials,refresh_timeout=30);assert verify_account(session)==expected;client=Client(Prod(),session)
    assert not client.list_assignments(),'Prospectively selected profile already owns a runtime'
    r=session.get('https://colab.research.google.com/tun/m/ccu-info',params={'authuser':'0'},headers={'X-Colab-Client-Agent':'colab-cli','Accept':'application/json'});r.raise_for_status();usage=json.loads(r.text.removeprefix(")]}'\n"))
    preserve(OUT/'Actual_Eligibility.json',json.dumps({k:usage.get(k) for k in ['eligibleGpus','ineligibleGpus','assignmentsCount','currentBalance']}).encode());assert 'T4' in usage.get('eligibleGpus',[]),'No T4 eligibility; no fallback'
    nbh=uuid.uuid4();state.update(stage='allocating_T4',notebook_hash=str(nbh),allocation_requests=1);save();assignment=client.assign(nbh,variant=Variant.GPU,accelerator=Accelerator.T4)
    assert assignment.accelerator==Accelerator.T4;state.update(runtime_allocated=True,endpoint=assignment.endpoint,stage='uploading');refreshed=time.monotonic();save()
    runtime=ColabRuntime(url=assignment.runtime_proxy_info.url,token=assignment.runtime_proxy_info.token,session_name='hiergrid-matched-adapted-scale')
    execute("print('READY_FOR_ONE_MATCHED_SCALE_ARM')");b=archive.read_bytes();parts=[]
    for i,off in enumerate(range(0,len(b),2*1024*1024)):
        path=f'content/scale_input_{i:03d}.bin';content('PUT',path,{'type':'file','format':'base64','content':base64.b64encode(b[off:off+2*1024*1024]).decode(),'chunk':1});parts.append('/'+path)
    execute("from pathlib import Path\nimport hashlib\nb=b''.join(Path(n).read_bytes() for n in "+repr(parts)+")\nassert hashlib.sha256(b).hexdigest()=="+repr(payload['sha256'])+"\nPath('/content/hiergrid_execution_bundle.zip').write_bytes(b)\n")
    source=(ROOT/'work/matched_scale_setup.py').read_text()
    execute("from pathlib import Path\nimport subprocess\nPath('/content/matched_scale_setup.py').write_text("+repr(source)+")\nf=open('/content/matched_scale_setup_control.log','w')\np=subprocess.Popen(['python','/content/matched_scale_setup.py',"+repr(arm)+"],stdout=f,stderr=subprocess.STDOUT)\nprint('SETUP_PID',p.pid)\n")
    state['stage']='pinned_setup';save();start=time.monotonic()
    while time.monotonic()-start<proto['setup_seconds']:
        try:setup=json.loads(raw(REMOTE+'/setup_exit.json'));break
        except FileNotFoundError:time.sleep(5)
    else:raise TimeoutError('Setup bound; no repeated setup')
    for n in ['setup_exit.json','setup.log']:preserve(OUT/'staged'/n,raw(REMOTE+'/'+n))
    assert setup['exit_code']==0,'Pinned setup failed'
    preserve(OUT/'staged/environment.json',raw(REMOTE+'/environment.json'))
    execute("import subprocess\nsubprocess.run(['env/bin/python','-c',"+repr("import hashlib,inspect,json\nfrom pathlib import Path\nfrom peft.tuners.tuners_utils import BaseTuner\nf=Path(inspect.getsourcefile(BaseTuner))\nh=hashlib.sha256(f.read_bytes()).hexdigest()\nassert h=='d14719d5813e5409411f924a52d34f973d192ca000107bf4cccd5feae6417a1e'\ns=inspect.getsource(BaseTuner.forward)\nassert 'self.model.forward' in s\nPath('outputs/PEFT_Forward_Source_Proof.json').write_text(json.dumps({'passed':True,'source_sha256':h,'direct_forward':s,'new_model_calls':0}))\n")+"],cwd='/content/hiergrid_execution',check=True)\n")
    preserve(OUT/'PEFT_Forward_Source_Proof.json',raw(REMOTE+'/PEFT_Forward_Source_Proof.json'))
    safe_release=False;state.update(stage='engineering_then_fixed_training',science_started=True);save()
    execute("import subprocess,os\nos.chdir('/content/hiergrid_execution')\nf=open('outputs/guardian.log','w')\np=subprocess.Popen(['env/bin/python','work/matched_scale_guardian.py',"+repr(arm)+"],stdout=f,stderr=subprocess.STDOUT)\nprint('SOLE_GUARDIAN_PID',p.pid)\n")
    start=time.monotonic()
    while time.monotonic()-start<proto['collector_seconds']:
        observe()
        try:ended=json.loads(raw(REMOTE+'/exit.json'))
        except FileNotFoundError:time.sleep(5);continue
        closed();safe_release=True;assert ended['exit_code']==0,'Actual partial preserved; never rerun science';state['stage']='complete_science_preserved';save();break
    else:raise TimeoutError('Collector bound; no replacement/no science retry')
except BaseException as e:
    state.update(stage='failed_or_partial',failure_type=type(e).__name__);save()
    if state['science_started']:
        try:closed();safe_release=True
        except BaseException as repair:state['preservation_failure_type']=type(repair).__name__;save()
    # No raw API error or proxy/credential text is printed.
finally:
    if runtime:
        try:runtime.stop()
        except Exception:pass
    if client and state['runtime_allocated'] and safe_release:
        try:client.unassign(state['endpoint']);state['runtime_released']=not any(a.endpoint==state['endpoint'] for a in client.list_assignments())
        except Exception as e:state['release_failure_type']=type(e).__name__
    if session:session.close()
    state['finished_at_utc']=now();save()
if state.get('exit_code')!=0 or not state['runtime_released']:raise SystemExit(1)
