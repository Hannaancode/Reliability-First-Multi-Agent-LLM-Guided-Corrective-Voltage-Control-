"""Prospective new adapted3B/7B comparison; stopped smaller/unadapted arms untouched."""
import ast,copy,hashlib,json,os,shutil,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
import requests
R=Path(__file__).resolve().parents[1];OLD=R/'outputs/matched_scale_20261011/preparation';B=R/'outputs/higher_matched_scale_20261015';P=B/'preparation'
PEFT_SHA='d14719d5813e5409411f924a52d34f973d192ca000107bf4cccd5feae6417a1e'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def put(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def main():
    started=time.perf_counter();P.mkdir(parents=True,exist_ok=False)
    old=json.loads((OLD/'protocol.json').read_text());proto=copy.deepcopy(old)
    meta=json.loads((R/'outputs/hybrid_scale_screen_20261012/preparation/Public_Model_Metadata.json').read_text())
    selected=[m for m in meta if m['repo'] in ['Qwen/Qwen2.5-3B-Instruct','Qwen/Qwen2.5-7B-Instruct']];assert len(selected)==2
    rows=[];params={};tokenizer_proof=[];smallfiles=['config.json','generation_config.json','model.safetensors.index.json']
    for m,arm in zip(selected,['public_3B','public_7B']):
        assert m['repo']==('Qwen/Qwen2.5-3B-Instruct' if arm=='public_3B' else 'Qwen/Qwen2.5-7B-Instruct')
        folder=P/'tokenizers'/arm;folder.mkdir(parents=True)
        cache=R/'outputs/hybrid_scale_screen_20261012/preparation/tokenizers'/arm
        for n in ['tokenizer.json','tokenizer_config.json']:
            assert sha(cache/n)==sha(OLD/'tokenizers/public_1_5B'/n),'No assumed tokenizer compatibility'
            shutil.copyfile(cache/n,folder/n)
        tokenizer_proof.append({'arm':arm,'both_actual_tokenizer_files_byte_identical_to_audited_1_5B':True,
            'cached436_prefix_and_continuation_ID_sequences_reused_without_reencoding':True})
        files={n:{'sha256':d['lfs_sha256'],'bytes':d['bytes']} for n,d in m['files'].items() if n.endswith('.safetensors')}
        download=P/'public_model_metadata'/arm;download.mkdir(parents=True)
        for n in smallfiles:
            response=requests.get(f'https://huggingface.co/{m["repo"]}/resolve/{m["revision"]}/{n}',timeout=(10,40));response.raise_for_status();raw=response.content
            decl=m['files'][n];assert len(raw)==decl['bytes']
            assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==decl['git_blob_id']
            (download/n).write_bytes(raw);files[n]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
        config=json.loads((download/'config.json').read_text());assert config==m['config']
        h=config['hidden_size'];kv=config['hidden_size']//config['num_attention_heads']*config['num_key_value_heads'];intermediate=config['intermediate_size']
        params[arm]=16*config['num_hidden_layers']*(9*h+2*kv+3*intermediate)
        rows.append({'arm':arm,'repo':m['repo'],'revision':m['revision'],'files':files,'public_safetensors_parameters':m['safetensors_parameter_metadata']['total'],
            'config':config,'lora_parameter_formula':'16 * layers * (9*hidden + 2*KV_dimension + 3*intermediate)'})
    for name in ['fit.json','held.json']:shutil.copyfile(OLD/name,P/name)
    fit=json.loads((P/'fit.json').read_text());held=json.loads((P/'held.json').read_text());assert len(fit)==340 and len(held)==96
    assert len({r['world_sha256'] for r in fit})==85 and len({r['world_sha256'] for r in held})==24
    assert not {r['world_sha256'] for r in fit}&{r['world_sha256'] for r in held}
    owner_name='run_higher_matched_scale_colab_20261015.py';audit_name='audit_higher_matched_scale_20261015.py';handoff_name='continue_higher_matched_scale_audit_20261015.py'
    base='outputs/higher_matched_scale_20261015'
    owner=(R/'work/run_matched_scale_colab.py').read_text().replace('outputs/matched_scale_20261011',base).replace("arm=='public_0_5B'","arm=='public_3B'").replace('work/run_matched_scale_colab.py','work/'+owner_name)
    source_check="import hashlib,inspect,json\nfrom pathlib import Path\nfrom peft.tuners.tuners_utils import BaseTuner\nf=Path(inspect.getsourcefile(BaseTuner))\nh=hashlib.sha256(f.read_bytes()).hexdigest()\nassert h=="+repr(PEFT_SHA)+"\ns=inspect.getsource(BaseTuner.forward)\nassert 'self.model.forward' in s\nPath('outputs/PEFT_Forward_Source_Proof.json').write_text(json.dumps({'passed':True,'source_sha256':h,'direct_forward':s,'new_model_calls':0}))\n"
    injection="    execute(\"import subprocess\\nsubprocess.run(['env/bin/python','-c',\"+repr("+repr(source_check)+")+\"],cwd='/content/hiergrid_execution',check=True)\\n\")\n    preserve(OUT/'PEFT_Forward_Source_Proof.json',raw(REMOTE+'/PEFT_Forward_Source_Proof.json'))\n"
    anchor="    safe_release=False;state.update(stage='engineering_then_fixed_training',science_started=True);save()"
    assert owner.count(anchor)==1;owner=owner.replace(anchor,injection+anchor)
    (R/'work'/owner_name).write_text(owner,encoding='utf-8')
    audit=(R/'work/audit_matched_scale_forward_cost_v2.py').read_text().replace('outputs/matched_scale_20261011',base).replace("OUT=BASE/'audit_forward_cost_v2'","OUT=BASE/'audit'").replace('public_0_5B','public_3B').replace('public_1_5B','public_7B')
    oldline=next(line for line in audit.splitlines() if "repair=read(BASE/'forward_cost_reader_v2_preparation/Protocol.json')" in line)
    audit=audit.replace(oldline,"    repair=proto['prospective_forward_call_accounting'];assert sha(Path(__file__))==repair['reader_source_sha256']")
    anchor="        complete=read(study/'Actual_Completion.json');"
    assert audit.count(anchor)==1
    audit=audit.replace(anchor,"        sourceproof=read(BASE/arm/'PEFT_Forward_Source_Proof.json');assert sourceproof['passed'] and sourceproof['source_sha256']==proto['prospective_forward_call_accounting']['actual_PEFT_source_sha256']\n"+anchor)
    audit=audit.replace('0.5B exact-action','3B exact-action').replace('1.5B {large','7B {large')
    (R/'work'/audit_name).write_text(audit,encoding='utf-8')
    handoff=(R/'work/continue_matched_scale_audit.py').read_text().replace('outputs/matched_scale_20261011',base).replace('run_matched_scale_colab.py',owner_name).replace('public_0_5B','public_3B').replace('public_1_5B','public_7B').replace('work/audit_matched_scale_results.py','work/'+audit_name)
    # Launcher waits are supplemented by actual-owner identity/command checks before any reader.
    anchor="states=[json.loads((BASE/arm/'status.json').read_text()) for arm in ['public_3B','public_7B']]"
    extra="\nfor arm,state in zip(['public_3B','public_7B'],states):\n    claim=json.loads((BASE/arm/'owner.claim').read_text());assert claim['actual_pid']==state['actual_pid'] and claim['actual_parent_pid']==state['actual_parent_pid']\n    assert not alive(state['actual_pid']), 'Actual owner still live; no simultaneous reader'\n"
    assert handoff.count(anchor)==1;handoff=handoff.replace(anchor,anchor+extra)
    (R/'work'/handoff_name).write_text(handoff,encoding='utf-8')
    for n in [owner_name,audit_name,handoff_name]:ast.parse((R/'work'/n).read_text())
    proto.update(study_id='matched_full_current_original_local_higher_scale_20261015',declared_at_utc=datetime.now(timezone.utc).isoformat(),
        human_priority='Human requested experiments and higher adapted SLM comparisons; these new3B/7B trained arms were never run. Stopped smaller/unadapted arms remain untouched.',
        question='Does identically adapted7B improve over3B and the fixed strongest same-information numerical reference? All four model sizes are reported with their architecture/precision/training costs.',
        models=rows,arms=['public_3B','public_7B'],profiles={'public_3B':'abdulhannaan2002@gmail.com','public_7B':'sheenahammed@gmail.com'},trainable_parameters=params,
        collector_seconds=18600,
        primary_gate='7B equal-world exact action >=3B+0.05 AND >=.7791666666666667; improvement in>=2 exact worlds against each; no lower legal/schema fraction. Fixed final2 only, all96 cases; no hyperparameter/seed/checkpoint/prompt sweeps. 3B/7B outcomes both retained even if nonmonotonic. No automatic physical rollout.',
        old_reference_results={'adapted_0_5B':.4166666666666667,'adapted_1_5B':.53125,'numerical_extra_trees':.7291666666666666,'reuse_no_reruns':True},
        prospective_forward_call_accounting={'reader_source_sha256':sha(R/'work'/audit_name),'actual_PEFT_source_sha256':PEFT_SHA,
            'method':'Verify actual pinned BaseTuner source BEFORE engineering, then bind successful actual teacher-loss caller/backward pairs plus2 cold evals and generation root hooks. Preserve hook subset, unknown per-direct-call latency/recomputation FLOPs.'},
        execution_readiness='Input/token/source preparation only; still require source/import/static closure, bundle verification and fresh exact authenticated assignment ownership before allocation. Actual full-context/cold gradient/memory gates precede scientific initialization. No fit/lifetime guarantee.',
        resource_fairness='Same2epochs680microsteps170updates/seed/LoRA/optimizer/data/order/decoder, different architectures/adapter counts/FLOPs/actual costs disclosed. Collector18600seconds is a prospective preservation allowance; science14400/process14700/setup1800 unchanged.',
        three_GPU_resources='Human-reported separately authenticated resources; only two preselected allocations needed, third not a fallback; no pooled VRAM/no rotation after denial.')
    # Remote scientific implementation and complete-state verifier are reused byte-for-byte.
    keep=['work/matched_scale_remote.py','work/matched_scale_state.py','work/candidate_complete_state_and_transfer_v2.py','work/relational_delta_transfer.py','work/matched_scale_setup.py','work/matched_scale_guardian.py',
          'work/verify_matched_scale_package.py','work/google_account_profile.py','work/candidate_process_runtime.py']
    proto['source_hashes']={n:sha(R/n) for n in keep+['work/'+owner_name,'work/'+audit_name,'work/'+handoff_name]}
    proto['source_pins'].update({str((P/n).relative_to(R)).replace('\\','/'):sha(P/n) for n in ['fit.json','held.json']})
    put(P/'protocol.json',proto)
    payload={}
    oldpayload=json.loads((OLD/'Payload.json').read_text())
    with zipfile.ZipFile(R/oldpayload['path']) as z:
        for name in z.namelist():
            if name.startswith('work/'):payload[name]=z.read(name)
    for n in ['protocol.json','fit.json','held.json']:payload['prep/'+n]=(P/n).read_bytes()
    for arm in proto['arms']:
        for n in ['tokenizer.json','tokenizer_config.json']:payload[f'prep/tokenizers/{arm}/{n}']=(P/'tokenizers'/arm/n).read_bytes()
    im={n:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for n,v in payload.items()}
    path=P/'Higher_Matched_Scale_Inputs.zip'
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for n,v in payload.items():z.writestr(n,v)
        z.writestr('INPUT_MANIFEST.json',json.dumps(im,indent=2))
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
        assert set(z.namelist())==set(im)|{'INPUT_MANIFEST.json'}
        for n,v in im.items():assert hashlib.sha256(z.read(n)).hexdigest()==v['sha256']
    put(P/'Payload.json',{'path':str(path.relative_to(R)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':sha(path),'members':len(im)+1,'CRC_all_hashes_passed':True,'private_adapter_credentials_network_not_exported':True})
    put(P/'Input_And_Source_Readiness.json',{'status':'PREPARED_NOT_ALLOCATED_PENDING_FINAL_CLOSURE','tokenizer_equivalence':tokenizer_proof,
        'trainable_parameters':params,'all436_rows_and_actual_token_IDs_reused_exactly':True,'no_old_model_training_inference_repeated':True,
        'remote_scientific_trainer_and_full_state_verifier_byte_unchanged':True,'new_model_PF_GPU_allocation_calls':0,'workflow_seconds':time.perf_counter()-started})
    print(json.dumps({'status':'higher_adapted_inputs_prepared','trainable_parameters':params,'new_GPU_model_calls':0}))
if __name__=='__main__':main()
