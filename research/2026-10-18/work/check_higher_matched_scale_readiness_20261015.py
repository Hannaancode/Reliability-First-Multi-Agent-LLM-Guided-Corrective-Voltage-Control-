"""Read-only preallocation closure of the two new adapted arms, no model calls."""
import ast,hashlib,json,os,shutil,zipfile
from datetime import datetime,timezone
from pathlib import Path
from candidate_process_evidence_utils import frozen_checks
R=Path(__file__).resolve().parents[1];B=R/'outputs/higher_matched_scale_20261015';P=B/'preparation'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def constant_expression(n):
    if isinstance(n,ast.Constant):return n.value
    if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add):return constant_expression(n.left)+constant_expression(n.right)
    if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='repr' and len(n.args)==1:return repr(constant_expression(n.args[0]))
    raise ValueError('Not a constant-only expression')
def main():
    p=json.loads((P/'protocol.json').read_text());payload=json.loads((P/'Payload.json').read_text())
    assert not any((B/arm).exists() for arm in p['arms']) and not (B/'handoff').exists(),'No repeat/duplicate launch'
    assert p['arms']==['public_3B','public_7B'] and p['epochs']==2 and p['seed']==20261011
    assert p['microsteps_per_arm']==680 and p['optimizer_steps_per_arm']==170
    assert p['trainable_parameters']=={'public_3B':29933568,'public_7B':40370176}
    assert p['context']==4096 and p['max_new_tokens']==384
    assert p['science_seconds']==14400 and p['process_seconds']==14700
    for n,h in p['source_hashes'].items():assert sha(R/n)==h,n
    archive=R/payload['path'];assert sha(archive)==payload['sha256'] and archive.stat().st_size==payload['bytes']
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
        manifest=json.loads(z.read('INPUT_MANIFEST.json'))
        for n,v in manifest.items():
            raw=z.read(n);assert len(raw)==v['bytes'] and hashlib.sha256(raw).hexdigest()==v['sha256']
            if n.startswith('work/') and n.endswith('.py'):
                assert sha(R/n)==v['sha256'],'Remote source must equal previously verified local implementation';ast.parse(raw)
        assert not any('adapter_model' in n or 'credential' in n or 'testbeds/' in n for n in z.namelist())
    old=json.loads((R/'outputs/matched_scale_20261011/preparation/protocol.json').read_text())
    remote=['matched_scale_remote.py','matched_scale_state.py','candidate_complete_state_and_transfer_v2.py','relational_delta_transfer.py','matched_scale_setup.py','matched_scale_guardian.py']
    assert all(p['source_hashes']['work/'+n]==old['source_hashes']['work/'+n] for n in remote)
    proof_calls=0
    for node in ast.walk(ast.parse((R/'work/run_higher_matched_scale_colab_20261015.py').read_text())):
        if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name) or node.func.id!='execute':continue
        try:control=constant_expression(node.args[0])
        except ValueError:continue
        if 'PEFT_Forward_Source_Proof' not in control:continue
        tree=ast.parse(control);call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='run')
        argv=ast.literal_eval(call.args[0]);assert argv[:2]==['env/bin/python','-c'];ast.parse(argv[2]);proof_calls+=1
    assert proof_calls==1,'Generated remote control/proof code must actually parse'
    fit=json.loads((P/'fit.json').read_text());held=json.loads((P/'held.json').read_text())
    assert len(fit)==340 and len(held)==96 and sum(r['multiplicity'] for r in fit+held)==16000
    longest=max(len(r['prefix_ids'])+len(r['answer_ids']) for r in fit+held)
    assert longest==3461 and max(len(r['prefix_ids'])+384 for r in fit+held)<=4096
    for arm in p['arms']:
        for n in ['tokenizer.json','tokenizer_config.json']:
            assert sha(P/'tokenizers'/arm/n)==sha(R/'outputs/matched_scale_20261011/preparation/tokenizers/public_1_5B'/n)
    assert shutil.disk_usage(R).free>=30*1024**3,'Need complete checkpoints and transfer preservation space'
    result={'at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_PREALLOCATION_SOURCE_INPUT_TOKEN_PACKAGE_AND_CONTROL_CLOSURE',
        'protocol_sha256':sha(P/'protocol.json'),'payload_sha256':payload['sha256'],'remote_scientific_implementation_byte_identical':True,
        'local_owner_new_PEFT_source_guard_before_scientific_launch':True,'full436_token_arrays_and_masks_reused':True,'longest_full_tokens':longest,
        'all16k_multiplicities_retained':True,'fresh_nine_frozen_checks':frozen_checks(),'actual_GPU_memory_loader_training_cold_gates':'MUST_PASS_ON_EACH_ASSIGNED_GPU_BEFORE_FRESH_SCIENTIFIC_INITIALIZATION',
        'new_GPU_model_PF_optimizer_calls':0,'no_fit_or_runtime_lifetime_guarantee':True}
    with (P/'Final_Preallocation_Readiness.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.flush();os.fsync(f.fileno())
    print(json.dumps({'preallocation_closure':'PASS','new_science_calls':0}))
if __name__=='__main__':main()
