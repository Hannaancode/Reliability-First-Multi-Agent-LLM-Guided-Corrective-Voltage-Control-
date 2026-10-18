"""Sole external paired-scale audit, zero model/PF/optimizer calls."""
import hashlib,json,os,sys,time
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'outputs/higher_matched_scale_20261015';PREP=BASE/'preparation';OUT=BASE/'audit'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text('utf8'))
def write(p,v):
    with p.open('x',encoding='utf8') as f:json.dump(v,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def strict(text,packet):
    def obj(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    try:
        v=json.loads(text,object_pairs_hook=obj,parse_constant=lambda t:(_ for _ in ()).throw(ValueError(t)))
        required={'state_summary','fault_detected','zone','min_voltage_pu','max_voltage_pu','n_undervoltage','n_overvoltage','proposed_action','requires_coordinator_review','autonomous_local_action_allowed','verification','confidence'}
        assert isinstance(v,dict) and required<=set(v) and set(v)<=required|{'candidate_action_for_coordinator'}
        assert isinstance(v['state_summary'],str) and v['zone']==packet['zone'] and isinstance(v['confidence'],str)
        assert all(isinstance(v[k],bool) for k in ['fault_detected','requires_coordinator_review','autonomous_local_action_allowed'])
        assert all(isinstance(v[k],(int,float)) and not isinstance(v[k],bool) for k in ['min_voltage_pu','max_voltage_pu'])
        assert all(isinstance(v[k],int) and not isinstance(v[k],bool) and v[k]>=0 for k in ['n_undervoltage','n_overvoltage'])
        assert isinstance(v['verification'],dict) and set(v['verification'])=={'verdict','reason'} and isinstance(v['verification']['reason'],str)
        a=v['proposed_action']
        if a is not None:
            assert isinstance(a,dict) and set(a)=={'add_shunts_q_mvar'};s=a['add_shunts_q_mvar']
            assert isinstance(s,dict) and s and all(b in packet['local_measurements']['bus_voltages'] and isinstance(q,(int,float)) and not isinstance(q,bool) and 0<q<=450 for b,q in s.items()) and sum(s.values())<=450
        return True,a,None
    except (ValueError,AssertionError,TypeError,KeyError):return False,None,'malformed_or_out_of_local_grammar'
def main():
    assert not OUT.exists(),'Never duplicate/restart a reader';OUT.mkdir();began=time.monotonic();proto=read(PREP/'protocol.json')
    write(OUT/'owner.claim',{'actual_pid':os.getpid(),'actual_parent_pid':os.getppid(),'command':sys.argv,'source_sha256':sha(Path(__file__))})
    repair=proto['prospective_forward_call_accounting'];assert sha(Path(__file__))==repair['reader_source_sha256']
    for n,h in proto['source_hashes'].items():assert sha(ROOT/n)==h
    fit=read(PREP/'fit.json');held=read(PREP/'held.json');results={};details={};costs={};audits={}
    for arm in proto['arms']:
        owner=BASE/arm;state=read(owner/'status.json');assert state['runtime_released'] and state['all_actual_artifacts_preserved'] and state['exit_code']==0
        assert read(owner/'Actual_Exit.json')['child_ended'];closed=read(owner/'Closed_Descriptor.json');study=owner/'staged/study'
        for n,m in closed['members'].items():assert (study/n).stat().st_size==m['bytes'] and sha(study/n)==m['sha256']
        identity=read(study/'Identity.json')['contract'];assert identity['arm']==arm and identity['protocol_sha256']==sha(PREP/'protocol.json') and identity['fit_sha256']==sha(PREP/'fit.json') and identity['held_sha256']==sha(PREP/'held.json')
        sourceproof=read(BASE/arm/'PEFT_Forward_Source_Proof.json');assert sourceproof['passed'] and sourceproof['source_sha256']==proto['prospective_forward_call_accounting']['actual_PEFT_source_sha256']
        complete=read(study/'Actual_Completion.json');assert complete['complete'] and complete['all96_fresh_reload_sequences_exact'] and complete['microsteps']==680 and complete['optimizer_steps']==170 and complete['generations']==192
        assert read(study/'Engineering_Integration.json')['passed']
        events=[json.loads(s) for s in (study/'events.jsonl').read_text('utf8').splitlines()]
        train=[e for e in events if e['event']=='backward_return' and e['phase']=='train'];opt=[e for e in events if e['event']=='optimizer_return' and e['phase']=='train']
        assert [(e['id'],e['weight']) for e in train]==[(r['id'],r['weight']) for r in fit*2]
        assert [e['step'] for e in opt]==list(range(1,171))
        forward=[e for e in events if e['event']=='forward_attempt'];returned=[e for e in events if e['event']=='forward_return']
        assert [e['sequence'] for e in forward]==[e['sequence'] for e in returned]==list(range(1,len(forward)+1))
        assert len(forward)==complete['actual_forward_attempts']==complete['actual_forward_returns']
        # PEFT BaseTuner.forward directly calls model.forward, bypassing inner nn.Module hooks in teacher forcing.
        # Complete actual caller/backward/moment journals establish each direct application call; no rerun.
        assert not [e for e in returned if e['phase'] in ['train','engineering_train','engineering_eval','engineering_cold_eval']]
        attempted_train=[e for e in events if e['event']=='training_microstep_attempt' and e['phase']=='train']
        attempted_engine=[e for e in events if e['event']=='training_microstep_attempt' and e['phase']=='engineering_train']
        returned_engine=[e for e in events if e['event']=='backward_return' and e['phase']=='engineering_train']
        assert len(attempted_engine)==len(returned_engine)==4
        assert [e['id'] for e in attempted_train]==[r['id'] for r in fit*2]
        integration=read(study/'Engineering_Integration.json')
        assert integration['passed'] and integration['loss_before_cold']==integration['loss_after_cold']
        assert integration['genuine_training_forwards']==4 and integration['genuine_eval_forwards']==2
        # Two eval losses are proven by the pinned loss() calls on the successful cold-integration path;
        # separate per-eval timing/root hooks were not recorded and remain unavailable.
        corrected_cost={'root_hook_attempts':len(forward),'root_hook_returns':len(returned),
          'source_bound_training_caller_attempts':len(attempted_train)+len(attempted_engine),
          'source_bound_training_returns_with_completed_backward':len(train)+len(returned_engine),
          'successful_cold_integration_eval_returns':2,
          'total_pretrained_application_forward_attempts':len(forward)+len(attempted_train)+len(attempted_engine)+2,
          'total_pretrained_application_forward_returns':len(returned)+len(train)+len(returned_engine)+2,
          'original_root_counter_preserved_not_total_model_calls':True,
          'direct_loss_call_individual_forward_latency':'UNKNOWN; workflow elapsed costs retained',
          'inner_gradient_checkpoint_recomputation_FLOPs':'UNKNOWN; included in workflow, no efficiency claim'}
        assert corrected_cost['total_pretrained_application_forward_attempts']==corrected_cost['total_pretrained_application_forward_returns']
        checkpoints=[e for e in events if e['event']=='checkpoint_return' and e['path'].startswith('checkpoints/')]
        assert [e['cursor']['optimizer_steps'] for e in checkpoints]==[0,20,40,60,80,85,100,120,140,160,170]
        certs=[]
        for folder in sorted((owner/'packages').iterdir()):
            cert=read(folder/'CPU_Verification.json');assert cert['all_passed'];certs.append(cert)
        assert sum(v['complete_states'] for v in certs)==12 and sum(v['outputs'] for v in certs)==192
        perworld=defaultdict(list);rows=[]
        for i,r in enumerate(held):
            f=read(study/'final'/f'{i:03d}.json');cold=read(study/'reload'/f'{i:03d}.json')
            assert f['id']==cold['id']==r['id'] and f['generated_ids']==cold['generated_ids']
            assert len(f['generated_ids'])==len(f['forward_records']) and f['generated_ids']==[v['argmax'] for v in f['forward_records']]
            valid,action,reason=strict(f['text'],r['packet']);hit=valid and action==r['action']
            item={'id':r['id'],'world_sha256':r['world_sha256'],'exact_action_hit':hit,'strict_schema_and_local_grammar':valid,'failure_reason':reason,'predicted_action':action,'target_action':r['action'],'nonnull_target':r['action'] is not None,'multiplicity':r['multiplicity']}
            rows.append(item);perworld[r['world_sha256']].append(item)
        worlds=[{'world_sha256':w,'pairs':len(v),'hits':sum(t['exact_action_hit'] for t in v),'exact_fraction':sum(t['exact_action_hit'] for t in v)/len(v),'legal_fraction':sum(t['strict_schema_and_local_grammar'] for t in v)/len(v)} for w,v in sorted(perworld.items())]
        results[arm]={'equal_world_exact_action':sum(v['exact_fraction'] for v in worlds)/len(worlds),'strict_schema_and_legal_fraction':sum(v['legal_fraction'] for v in worlds)/len(worlds),'hits':sum(t['exact_action_hit'] for t in rows),'pairs':96,'worlds':worlds,'row_weighted_exact':sum(t['multiplicity']*t['exact_action_hit'] for t in rows)/sum(t['multiplicity'] for t in rows)}
        details[arm]=rows;costs[arm]={'raw_completion':complete,'independent_corrected_call_costs':corrected_cost};audits[arm]={'all_source_member_identity_journal_counts_cold_sequences_passed':True,'checkpoints':11,'engineering_states':1,'new_model_PF_calls_in_reader':0}
    control=read(ROOT/proto['control']['source'])['arms']['extra_trees'];assert sha(ROOT/proto['control']['source'])==proto['control']['sha256']
    small=results['public_3B'];large=results['public_7B'];sw={r['world_sha256']:r for r in small['worlds']};cw={r['world_sha256']:r for r in control['worlds']}
    assert set(sw)==set(cw)=={r['world_sha256'] for r in large['worlds']}
    better_small=sum(r['exact_fraction']>sw[r['world_sha256']]['exact_fraction'] for r in large['worlds']);better_control=sum(r['exact_fraction']>cw[r['world_sha256']]['exact_fraction'] for r in large['worlds'])
    gate={'large_at_least5pp_over_small':large['equal_world_exact_action']>=small['equal_world_exact_action']+.05,
          'large_at_least5pp_over_completed_numeric':large['equal_world_exact_action']>=.7791666666666667,
          'positive_in2_worlds_vs_each':better_small>=2 and better_control>=2,
          'no_lower_legal_schema_fraction':large['strict_schema_and_legal_fraction']>=small['strict_schema_and_legal_fraction'],
          'better_worlds_vs_small':better_small,'better_worlds_vs_control':better_control}
    passed=all(gate[k] for k in ['large_at_least5pp_over_small','large_at_least5pp_over_completed_numeric','positive_in2_worlds_vs_each','no_lower_legal_schema_fraction'])
    write(OUT/'Independent_Audit.json',{'all_passed':True,'arms':audits,'seconds':time.monotonic()-began,'new_model_PF_optimizer_calls':0,'mechanical_cost_reader_repair':repair})
    write(OUT/'All_Results.json',{'arms':results,'completed_numeric_control':control,'all_case_results':details,'costs':costs,'development_not_confirmation':True})
    write(OUT/'Fixed_Gate_Decision.json',{'passed':passed,'gates':gate,'decision':'Only separately prospective physical/attribution planning permitted' if passed else 'STOP this fixed paired-scale intervention, no outcome-driven retunes','physical_DSE_superiority':'UNPROVED'})
    with (OUT/'Results.md').open('x',encoding='utf8') as f:f.write(f"Matched adapted-scale diagnostic COMPLETE; independent audit PASS.\n\n3B exact-action {small['equal_world_exact_action']:.6f};7B {large['equal_world_exact_action']:.6f};completed numerical control .729167. Fixed gate {'PASS' if passed else 'FAIL'}. All96 pairs/24 development worlds retained. Original private adapter untouched. No new physical trajectories or proof of D-SE superiority.\n")
    write(OUT/'Closed_Manifest.json',{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in OUT.iterdir() if p.is_file()})
    print(json.dumps({'audit_passed':True,'fixed_gate_passed':passed,'small':small['equal_world_exact_action'],'large':large['equal_world_exact_action']}))
if __name__=='__main__':main()
