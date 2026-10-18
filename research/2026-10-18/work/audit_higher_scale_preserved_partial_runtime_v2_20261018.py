"""New explicit partial reader: all declared identities and logical missing bounds.

No model, optimizer, PF or scientific replay. Never invokes complete-only reader.
"""
import candidate_process_runtime
import hashlib,json,os,struct,time
from collections import Counter,defaultdict
from pathlib import Path
from audit_higher_matched_scale_20261015 import strict
R=Path(__file__).resolve().parents[1];B=R/'outputs/higher_matched_scale_20261015';O=B/'partial_evidence_audit_runtime_v2_20261018'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def put(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def main():
    started=time.perf_counter();protocol=read(O/'Protocol.json');p=read(B/'preparation/protocol.json')
    put(O/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'source_sha256':sha(Path(__file__)),'protocol_sha256':sha(O/'Protocol.json')})
    for name,h in p['source_hashes'].items():assert sha(R/name)==h,name
    fit=read(B/'preparation/fit.json');held=read(B/'preparation/held.json');assert len(fit)==340 and len(held)==96
    world_counts=Counter(r['world_sha256'] for r in held);assert len(world_counts)==24
    summaries={};all_rows=[]
    for arm in p['arms']:
        base=B/arm;state=read(base/'status.json');assert state['runtime_released'] and state['all_actual_artifacts_preserved'] and state['exit_code']==1
        assert read(base/'Actual_Exit.json')['child_ended']
        study=base/'staged/study';closed=read(base/'Closed_Descriptor.json');descriptor=closed['members']
        # This partial reader checks exactly the identity, journals and output subset it uses;
        # final3B tensor state separately checked below. It is not an all-member/full-study audit.
        selected=[x for x in study.rglob('*') if x.is_file() and (x.suffix in ['.json','.jsonl'] or x.name=='science.log')]
        for path in selected:
            name=path.relative_to(study).as_posix()
            if name in descriptor:assert path.stat().st_size==descriptor[name]['bytes'] and sha(path)==descriptor[name]['sha256'],name
        contract=read(study/'Identity.json')['contract'];assert contract['protocol_sha256']==sha(B/'preparation/protocol.json') and contract['arm']==arm
        assert contract['fit_sha256']==sha(B/'preparation/fit.json') and contract['held_sha256']==sha(B/'preparation/held.json')
        events=[json.loads(line) for line in (study/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        train=[e for e in events if e['event']=='backward_return' and e['phase']=='train']
        optimizer=[e for e in events if e['event']=='optimizer_return' and e['phase']=='train']
        assert [(e['id'],e['weight']) for e in train]==[(r['id'],r['weight']) for r in (fit*2)[:len(train)]]
        assert [e['step'] for e in optimizer]==list(range(1,len(optimizer)+1))
        completed={};primary_attempts=[e['id'] for e in events if e['event']=='generation_attempt' and e['phase']=='final']
        assert primary_attempts==[r['id'] for r in held[:len(primary_attempts)]]
        for i,row in enumerate(held):
            path=study/'final'/f'{i:03d}.json'
            if not path.exists():continue
            value=read(path);assert value['id']==row['id'] and value['world_sha256']==row['world_sha256'] and value['input_sha256']==row['input_sha256']
            prompt_hash=hashlib.sha256(struct.pack('<'+'q'*len(row['prefix_ids']),*row['prefix_ids'])).hexdigest()
            assert value['prompt_ids_sha256']==prompt_hash
            assert value['generated_ids']==[v['argmax'] for v in value['forward_records']] and 0<len(value['generated_ids'])<=384
            valid,action,error=strict(value['text'],row['packet']);hit=bool(valid and action==row['action'])
            item={'arm':arm,'id':row['id'],'world_sha256':row['world_sha256'],'strict_schema_and_local_grammar':valid,'exact_action_hit':hit,'invalid_reason':error,'original_teacher_target_is_not_physical_oracle':True}
            completed[row['id']]=item;all_rows.append(item)
        perworld=[]
        for world,n in sorted(world_counts.items()):
            observed=[v for v in completed.values() if v['world_sha256']==world];hits=sum(v['exact_action_hit'] for v in observed);missing=n-len(observed)
            perworld.append({'world_sha256':world,'declared':n,'observed':len(observed),'hits':hits,'missing':missing,'lower':hits/n,'upper':(hits+missing)/n})
        lower=sum(w['lower'] for w in perworld)/24;upper=sum(w['upper'] for w in perworld)/24
        failure=read(study/'Failure.json');raw_attempts=sum(e['event']=='forward_attempt' for e in events);raw_returns=sum(e['event']=='forward_return' for e in events)
        assert failure['actual_forward_attempts']==raw_attempts and failure['actual_forward_returns']==raw_returns
        engineering_backward=[e for e in events if e['event']=='backward_return' and e['phase']=='engineering_train']
        engineering_optimizer=[e for e in events if e['event']=='optimizer_return' and e['phase']=='engineering_train']
        summary={'scientific_backward_returns':len(train),'scientific_optimizer_returns':len(optimizer),'engineering_backward_returns':len(engineering_backward),'engineering_optimizer_returns':len(engineering_optimizer),
            'observed_primary_outputs':len(completed),'primary_attempts':len(primary_attempts),'unknown_primary_identities':[r['id'] for r in held if r['id'] not in completed],
            'unattempted_primary_identities':[r['id'] for r in held[len(primary_attempts):]],'fresh_reload_outputs':len(list((study/'reload').glob('*.json'))),
            'exact_action_missing_evidence_lower':lower,'exact_action_missing_evidence_upper':upper,
            'fixed_required_primary_threshold':protocol['threshold'],'necessary_primary_threshold_mathematically_excluded':upper<protocol['threshold'],
            'all_worlds':perworld,'raw_root_hook_attempts':raw_attempts,'raw_root_hook_returns':raw_returns,'raw_root_hooks_are_not_total_model_calls':True,
            'failure':failure,'complete_end_to_end_matched_gate':'UNKNOWN_PARTIAL_NO_COMPLETE_RELOAD_OR_BOTH_ARM_COMPARISON'}
        if arm=='public_3B':
            assert len(train)==680 and len(optimizer)==170 and len(completed)==81 and len(primary_attempts)==82
            assert len(engineering_backward)==4 and len(engineering_optimizer)==1
            integration=read(study/'Engineering_Integration.json');assert integration['passed'] and integration['loss_before_cold']==integration['loss_after_cold']
            # Verify preserved FINAL checkpoint bytes and complete CPU AdamW/RNG/cursor state.
            path=study/'checkpoints/step_170.pt';m=descriptor['checkpoints/step_170.pt'];assert path.stat().st_size==m['bytes'] and sha(path)==m['sha256']
            import torch
            from matched_scale_state import verify
            checkpoint=torch.load(path,map_location='cpu',weights_only=False);assert verify(checkpoint,contract)
            assert checkpoint['cursor']['microsteps']==680 and checkpoint['cursor']['optimizer_steps']==170
            assert sum(v.numel() for v in checkpoint['parameters'].values())==p['trainable_parameters'][arm]
            summary['final_complete_state_CPU_verified']=True;summary['final_checkpoint_sha256']=m['sha256']
            summary['source_bound_application_attempts']=raw_attempts+684+2;summary['source_bound_application_returns']=raw_returns+684+2
            del checkpoint
        else:
            assert not train and not optimizer and not completed and failure['type']=='OutOfMemoryError'
            log=(study/'control/science.log').read_text(encoding='utf-8');assert 'torch.OutOfMemoryError' in log and 'backward' in log
            summary['source_bound_loss_forward_returns_lower_bound']=1
            summary['reason']='First longest-input engineering loss returned; backward then ran out of VRAM. Root hooks0 are a known subset, not zero actual model work. No trained7B result.'
        summaries[arm]=summary
    put(O/'All_Preserved_Primary_Output_Checks.json',all_rows)
    put(O/'Independent_Partial_Audit.json',{'status':'PASS_EXPLICIT_PRESERVED_OUTPUT_IDENTITIES_TRAIN_JOURNALS_AND_FINAL3B_STATE_PARTIAL_AUDIT',
        'arms':summaries,'all96_original_denominators_retained':True,'bounds_are_logical_missing_evidence_not_CI':True,
        'full_scientific_study_and_pair_gate':'UNKNOWN_TERMINAL_PARTIAL','new_model_PF_optimizer_calls':0,'workflow_seconds':time.perf_counter()-started,
        'limits':'Not an all-member/checkpoint replay/full-source or cold96 completion certificate. No fresh inference, no measured physical outcomes, no LLM superiority, no subset/generalization claim.'})
    put(O/'Closed_Manifest.json',{'members':{x.name:{'bytes':x.stat().st_size,'sha256':sha(x)} for x in O.iterdir() if x.is_file()}})
    print(json.dumps({'partial_audit':'PASS','observed3B':summaries['public_3B']['observed_primary_outputs'],'lower':summaries['public_3B']['exact_action_missing_evidence_lower'],'upper':summaries['public_3B']['exact_action_missing_evidence_upper'],'threshold_excluded':summaries['public_3B']['necessary_primary_threshold_mathematically_excluded'],'new_science_calls':0}))
if __name__=='__main__':main()
