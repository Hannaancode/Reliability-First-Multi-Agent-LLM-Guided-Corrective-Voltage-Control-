"""One fixed original-profile T4 owner, hashed preservation, no fallback."""
import argparse,ast,base64,hashlib,json,logging,os,time,uuid,zipfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'work'))
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession,Request
from colab_cli.client import Client,Prod,Variant,Accelerator
from colab_cli.runtime import ColabRuntime
from google_account_profile import verify_account
from public_size_local_preservation_v2 import preserve as safe_preserve,extended

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/'outputs'
PREP=R/'g5_original118_adapter_ablation_20261109/execution_preparation'
arm='public_0_5B'
OUT=extended(R/'g5_original118_adapter_ablation_execution_20261109')
logging.disable(logging.CRITICAL)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def preserve(path,raw):safe_preserve(path,raw,digest(raw))
class BoundedSession(AuthorizedSession):
    def request(self,*a,**kw):kw.setdefault('timeout',(10,30));return super().request(*a,**kw)

def allocation_recovery_disposition(error, stage, allocation_requests, runtime_allocated):
    status=getattr(getattr(error,'response',None),'status_code',None)
    denied=status in (401,403,429)
    uncertain=(stage=='allocating_one_selected_T4' and allocation_requests==1 and not runtime_allocated
      and not denied and (isinstance(error,(requests.exceptions.Timeout,requests.exceptions.ConnectionError))
      or (isinstance(error,requests.exceptions.HTTPError) and isinstance(status,int) and status>=500)))
    return {'failure_http_status':status,'definite_denial':denied,'allocation_outcome_uncertain':uncertain}

def main():
    os.chdir(ROOT);assert not OUT.exists(),'Preserve all old claims and attempts';OUT.mkdir()
    preserve(OUT/'owner.claim',json.dumps({'actual_pid':os.getpid(),'parent_pid':os.getppid(),'source_sha256':digest(Path(__file__).read_bytes()),'command':str(Path(__file__).resolve()),'started_at_utc':datetime.now(timezone.utc).isoformat()}).encode())
    began=time.monotonic()
    while not (OUT/'Launcher_ACK.json').exists():assert time.monotonic()-began<60;time.sleep(.1)
    ack=read(OUT/'Launcher_ACK.json');assert ack['actual_pid']==os.getpid() and ack['actual_parent_pid']==os.getppid() and ack['fresh_exact_source_PID_parent_command']
    protocol=read(PREP/'Frozen_Engineering_Protocol.json');payload=read(PREP/'Cloud_Payload_Manifest.json');ready=read(PREP/'Launch_Readiness_Audit.json')
    profile=dict(protocol['profiles'][arm])
    profile['credential_path']={'public_0_5B':r'C:\Users\HOME\AppData\Roaming\gcloud\application_default_credentials.json',
      'public_1_5B':r'C:\Users\HOME\AppData\Roaming\gcloud-hiergrid-sheenah\application_default_credentials.json'}[arm]
    state={'started_at_utc':datetime.now(timezone.utc).isoformat(),'stage':'preconditions','expected_account':profile['account'],
      'runtime_allocated':False,'runtime_released':False,'allocation_requests':0,'science_started':False,'actual_preserved_packages':0}
    client=runtime=session=assignment=None;safe_release=True;refreshed=0;acknowledged=[];transfers=[]
    def save():
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat()
        p=OUT/'status.tmp';p.write_text(json.dumps(state,indent=2));p.replace(OUT/'status.json')
        p=OUT/'Transfer_Costs.tmp';p.write_text(json.dumps(transfers,indent=2));p.replace(OUT/'Transfer_Costs.json')
    def fresh():
        nonlocal assignment,refreshed
        a=client._get_assignment(nbh,variant=Variant.GPU,accelerator=Accelerator.T4)
        if getattr(a,'endpoint',None)!=state['endpoint'] or getattr(a,'runtime_proxy_info',None) is None:
            state['same_exact_assignment_unavailable']=True;save();raise RuntimeError('Exact assignment unavailable; no replacement')
        assignment=a;refreshed=time.monotonic()
    def content(method,path,payload=None,file=False):
        for attempt in range(3):
            if time.monotonic()-refreshed>100:fresh()
            began=time.perf_counter();entry={'method':method,'artifact':path,'attempt':attempt+1,'returned':False}
            try:
                response=requests.request(method,assignment.runtime_proxy_info.url.rstrip('/')+'/api/contents/'+quote(path.strip('/'),safe='/'),
                  params={'authuser':'0','colab-runtime-proxy-token':assignment.runtime_proxy_info.token,'content':'1',
                          **({'format':'base64'} if file and method=='GET' else {})},json=payload,timeout=(10,30))
                entry['http_status']=response.status_code
                if response.status_code==404:raise FileNotFoundError('Artifact not published yet')
                response.raise_for_status();value=response.json();entry['returned']=True;entry['response_bytes']=len(response.content);return value
            except (requests.exceptions.Timeout,requests.exceptions.ConnectionError,requests.exceptions.HTTPError) as transport_error:
                if getattr(getattr(transport_error,'response',None),'status_code',None) in (401,403,429):raise
                if attempt==2:raise
                time.sleep(2);fresh()
            finally:entry['seconds']=time.perf_counter()-began;transfers.append(entry)
    def raw_file(path):
        v=content('GET',path,file=True)
        return base64.b64decode(v['content']) if v.get('format')=='base64' else str(v['content']).encode()
    def execute(code,seconds=60):
        ast.parse(code);out=runtime.execute_code(code,allow_stdin=False,timeout=seconds)
        assert not any(x.get('output_type')=='error' for x in out),'Remote control stage failed'
        return out
    transfer_root='content/hiergrid_execution/outputs/public_size_transfer'
    science_root='content/hiergrid_execution/outputs/public_size_science'
    def package(name):
        descriptor=json.loads(raw_file(transfer_root+'/'+name+'/descriptor.json'))
        number=descriptor['number'];assert number==len(acknowledged) and name==f'package_{number:03d}'
        local=OUT/'packages'/name;local.mkdir(parents=True,exist_ok=True)
        preserve(local/'descriptor.json',json.dumps(descriptor,indent=2).encode())
        blocks=[]
        for part in descriptor['parts']:
            assert '/' not in part['name'] and '\\' not in part['name'] and part['bytes']<=2*1024*1024
            path=local/part['name']
            if not path.exists():preserve(path,raw_file(transfer_root+'/'+name+'/'+part['name']))
            raw=path.read_bytes();assert len(raw)==part['bytes'] and digest(raw)==part['sha256'];blocks.append(raw)
        raw=b''.join(blocks);assert len(raw)==descriptor['archive_bytes'] and digest(raw)==descriptor['archive_sha256']
        archive=local/'package.zip';preserve(archive,raw)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
            assert set(z.namelist())==set(descriptor['members'])|{'journal_delta.jsonl'}
            for name,m in descriptor['members'].items():
                p=Path(name);assert not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name
                b=z.read(name);assert len(b)==m['bytes'] and digest(b)==m['sha256'];preserve(OUT/'staged/study'/p,b)
            delta=z.read('journal_delta.jsonl');assert len(delta)==descriptor['journal_delta_bytes'] and digest(delta)==descriptor['journal_delta_sha256']
        journal_path=OUT/'live/events.jsonl';prior=journal_path.read_bytes() if journal_path.exists() else b''
        if len(prior)==descriptor['journal_prefix_bytes']:
            assert digest(prior)==descriptor['journal_prefix_sha256'];prior=prior[:descriptor['journal_offset']]
        assert len(prior)==descriptor['journal_offset'] and digest(prior)==descriptor['journal_previous_sha256']
        combined=prior+delta;assert len(combined)==descriptor['journal_prefix_bytes'] and digest(combined)==descriptor['journal_prefix_sha256']
        if not journal_path.exists() or journal_path.stat().st_size==len(prior):
            journal_path.parent.mkdir(parents=True,exist_ok=True)
            with journal_path.open('ab') as f:f.write(delta);f.flush();os.fsync(f.fileno())
        ack={'number':number,'archive_sha256':descriptor['archive_sha256'],'journal_prefix_sha256':descriptor['journal_prefix_sha256'],'all_bytes_preserved_locally':True}
        content('PUT',transfer_root+'/'+f'package_{number:03d}'+'/ack.json',{'type':'file','format':'text','content':json.dumps(ack)})
        preserve(local/'Sent_Acknowledgement.json',json.dumps(ack,indent=2).encode());acknowledged.append(ack)
        state['actual_preserved_packages']=len(acknowledged);save()
    def observe():
        try:state['remote_progress']=json.loads(raw_file(science_root+'/progress.json'))
        except FileNotFoundError:pass
        try:listing=content('GET',transfer_root)
        except FileNotFoundError:save();return
        for item in sorted(listing.get('content',[]),key=lambda x:x['name']):
            if item['type']=='directory' and item['name']==f'package_{len(acknowledged):03d}':
                try:package(item['name'])
                except FileNotFoundError:break
        save()
    def closed():
        desc=json.loads(raw_file('content/hiergrid_execution/outputs/public_size_closed_descriptor.json'))
        assert desc['scientific_process_ended']
        for name,m in desc['members'].items():
            p=Path(name);assert not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name
            path=OUT/'staged/study'/p
            if path.is_file() and path.stat().st_size==m['bytes'] and digest(path.read_bytes())==m['sha256']:continue
            blocks=[]
            for part in m['parts']:
                assert '/' not in part['name'] and part['bytes']<=2*1024*1024
                raw=raw_file('content/hiergrid_execution/outputs/public_size_closed_parts/'+part['name'])
                assert len(raw)==part['bytes'] and digest(raw)==part['sha256'];blocks.append(raw)
            raw=b''.join(blocks);assert len(raw)==m['bytes'] and digest(raw)==m['sha256']
            if name=='events.jsonl' and (OUT/'live/events.jsonl').exists():assert raw.startswith((OUT/'live/events.jsonl').read_bytes())
            preserve(path,raw)
        preserve(OUT/'remote_closed_descriptor.json',json.dumps(desc,indent=2).encode())
        for name in ['public_size_science.log','public_size_exit.json','public_size_guardian_End.json']:
            preserve(OUT/'staged'/name,raw_file('content/hiergrid_execution/outputs/'+name))
        guardian_end=read(OUT/'staged/public_size_guardian_End.json')
        assert guardian_end['actual_pid']==desc['guardian_claim']['actual_pid']
        assert guardian_end['source_sha256']==protocol['remote_source_hashes']['work/g5_original118_ablation_guardian.py']
        gid=int(guardian_end['actual_pid']);start_identity=desc['guardian_claim']['proc_start_identity']
        probe="from pathlib import Path\nimport json,time\np=Path('/proc/"+str(gid)+"/stat')\nend=time.monotonic()+10\nwhile p.exists() and p.read_text().split()[2]!='Z' and time.monotonic()<end: time.sleep(.1)\nstate=p.read_text().split() if p.exists() else None\nassert state is None or (state[2]=='Z' and state[21]=="+repr(start_identity)+")\nprint(json.dumps({'actual_guardian_pid':"+str(gid)+",'ended_or_reaped_zombie':True,'original_start_identity':"+repr(start_identity)+"}))\n"
        observed=execute(probe,seconds=20)
        preserve(OUT/'Remote_Guardian_Terminal_Observation.json',json.dumps({'identity':desc['guardian_claim'],'returned_remote_observation':observed,'fresh_remote_probe_passed':True},indent=2).encode())
        state.update(remote_exit_code=desc['exit_code'],scientific_process_ended=True,guardian_ended=True,all_actual_closed_artifacts_preserved=True)
        archive=OUT/'preserved_remote_science.zip'
        if not archive.exists():
            with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
                for name in desc['members']:z.write(OUT/'staged/study'/name,name)
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None and len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(desc['members'])
            for name,m in desc['members'].items():b=z.read(name);assert len(b)==m['bytes'] and digest(b)==m['sha256']
        state['preserved_archive']={'bytes':archive.stat().st_size,'sha256':digest(archive.read_bytes())};save()
    save()
    try:
        assert ready['passed'] and ready['independent_source_review_status']=='PASS_ORIGINAL118_DISABLED_ENGINEERING_SOURCE'
        for path,h in ready['source_hashes'].items():assert digest((ROOT/path).read_bytes())==h
        archive=ROOT/payload['archive'];assert archive.stat().st_size==payload['bytes'] and digest(archive.read_bytes())==payload['sha256']
        assert digest((ROOT/payload['human_authority_source']).read_bytes())==payload['human_authority_sha256']
        os.environ['HIERGRID_EXPECTED_GOOGLE_ACCOUNT']=profile['account']
        credentials=Credentials.from_authorized_user_file(profile['credential_path'])
        transport=Request()
        def refresh(*a,**kw):kw.setdefault('timeout',25);return transport(*a,**kw)
        credentials.refresh(refresh);session=BoundedSession(credentials,refresh_timeout=30)
        assert verify_account(session)==profile['account'];client=Client(Prod(),session)
        assert not client.list_assignments(),'Current assignment ownership must not be duplicated'
        response=session.get('https://colab.research.google.com/tun/m/ccu-info',params={'authuser':'0'},headers={'X-Colab-Client-Agent':'colab-cli','Accept':'application/json'})
        response.raise_for_status();usage=json.loads(response.text.removeprefix(")]}'\n"));assert 'T4' in usage.get('eligibleGpus',[])
        preserve(OUT/'Preallocation_Identity_And_Eligibility.json',json.dumps({'actual_account':profile['account'],'assignment_count':0,
          'eligible_gpus':usage['eligibleGpus'],'remaining_free_hours_not_exposed':True},indent=2).encode())
        nbh=uuid.uuid4();state.update(stage='allocating_one_selected_T4',notebook_hash=str(nbh),allocation_requests=1);save()
        assignment=client.assign(nbh,variant=Variant.GPU,accelerator=Accelerator.T4)
        state.update(runtime_allocated=True,endpoint=assignment.endpoint);refreshed=time.monotonic();save()
        assert assignment.accelerator==Accelerator.T4
        runtime=ColabRuntime(url=assignment.runtime_proxy_info.url,token=assignment.runtime_proxy_info.token,session_name='hiergrid-original118-adapter-off-first-inputs')
        execute("print('PUBLIC_SIZE_OWNER_READY')")
        raw=archive.read_bytes();paths=[]
        for i,offset in enumerate(range(0,len(raw),2*1024*1024)):
            name=f'public_size_input_{i:03d}.bin';path='content/'+name
            content('PUT',path,{'type':'file','format':'base64','content':base64.b64encode(raw[offset:offset+2*1024*1024]).decode()});paths.append('/'+path)
        code="from pathlib import Path\nimport hashlib,zipfile,json\nraw=b''.join(Path(p).read_bytes() for p in "+repr(paths)+")\nassert hashlib.sha256(raw).hexdigest()=="+repr(payload['sha256'])+"\nPath('/content/public_size_input.zip').write_bytes(raw)\nwith zipfile.ZipFile('/content/public_size_input.zip') as z:\n assert z.testzip() is None\n for n,m in json.loads(z.read('PUBLIC_SIZE_INPUT_MANIFEST.json')).items():assert len(z.read(n))==m['bytes'] and hashlib.sha256(z.read(n)).hexdigest()==m['sha256']\n"
        execute(code)
        setup=(ROOT/'work/native13_lora_setup_remote_v2_20261020.py').read_text();ast.parse(setup)
        safe_release=False;state['stage']='one_async_bounded_framework_setup';save()
        execute("import subprocess,sys\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,'-c',"+repr(setup)+","+repr(arm)+"])\nPath('/content/public_size_setup_pid.json').write_text(str(p.pid))\n")
        began=time.monotonic()
        while time.monotonic()-began<protocol['setup_seconds']:
            try:setup_exit=json.loads(raw_file('content/hiergrid_execution/outputs/public_size_setup_exit.json'));break
            except FileNotFoundError:save();time.sleep(3)
        else:raise TimeoutError('Setup state unknown; no repeat launch')
        for name in ['public_size_setup.log','public_size_setup_exit.json']:
            preserve(OUT/'staged'/name,raw_file('content/hiergrid_execution/outputs/'+name))
        assert setup_exit['setup_process_ended'];safe_release=True
        assert setup_exit['exit_code']==0,'Setup failure preserved; no retry'
        preserve(OUT/'staged/public_size_environment.json',raw_file('content/hiergrid_execution/outputs/public_size_environment.json'))
        guardian="import os,subprocess\nos.chdir('/content/hiergrid_execution')\np=subprocess.Popen(['env/bin/python','work/g5_original118_ablation_guardian.py'])\nprint('ONE_PUBLIC_SIZE_GUARDIAN',p.pid)\n"
        safe_release=False;state.update(stage='fixed_pair_with_acknowledged_preservation',science_started=True);save();execute(guardian)
        began=time.monotonic()
        while time.monotonic()-began<protocol['collector_seconds']:
            observe()
            try:exit_info=json.loads(raw_file('content/hiergrid_execution/outputs/public_size_exit.json'))
            except FileNotFoundError:time.sleep(2);continue
            assert exit_info['scientific_process_ended'];closed();safe_release=True
            state['stage']='closed_complete_or_partial_science_preserved';save();break
        else:raise TimeoutError('Collector bound reached; no science repeat or replacement allocation')
    except BaseException as error:
        state.update(allocation_recovery_disposition(error,state['stage'],state['allocation_requests'],state['runtime_allocated']))
        state.update(stage='failed_or_uncertain_preserved_attempt',failure_type=type(error).__name__);save()
        if state['science_started'] and not state.get('definite_denial'):
            try:closed();safe_release=True
            except BaseException as preservation_error:state['preservation_failure_type']=type(preservation_error).__name__;save()
    finally:
        if runtime:
            try:runtime.stop()
            except Exception:pass
        if client and state.get('allocation_outcome_uncertain') and not state.get('definite_denial') and state['allocation_requests']==1 and not state['runtime_allocated']:
            try:
                recovered=client._get_assignment(nbh,variant=Variant.GPU,accelerator=Accelerator.T4)
                if getattr(recovered,'runtime_proxy_info',None) is not None:
                    state.update(runtime_allocated=True,endpoint=recovered.endpoint,assignment_recovered_by_exact_GET=True)
            except Exception as error:state['post_allocation_GET_failure_type']=type(error).__name__
        if client and state['runtime_allocated'] and safe_release:
            try:
                client.unassign(state['endpoint']);state['runtime_released']=not any(a.endpoint==state['endpoint'] for a in client.list_assignments())
            except Exception as error:state['release_failure_type']=type(error).__name__
        if session:session.close()
        state['finished_at_utc']=datetime.now(timezone.utc).isoformat();save()
    if not state.get('all_actual_closed_artifacts_preserved') or not state['runtime_released']:raise SystemExit(1)
if __name__=='__main__':main()
