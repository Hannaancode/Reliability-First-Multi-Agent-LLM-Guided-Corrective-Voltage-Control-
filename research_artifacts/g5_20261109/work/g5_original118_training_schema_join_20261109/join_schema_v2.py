"""New saved-metadata causal-schema join; no tokenizer/native/model/fit imports."""
import ast
import collections
import gzip
import hashlib
import json
import math
import time
from pathlib import Path

R=Path(__file__).resolve().parents[2]
B=R/'outputs/critical_research_reset_20261010/original_role_numeric_gate_20261011/execution'
O=R/'outputs/g5_original118_training_schema_join_20261109'
RAW=R/'work/e/training_provenance/zone_agent_train.jsonl'
def dump(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(x): return hashlib.sha256(x).hexdigest()
def canonical(v):
    if v is None:return ['null']
    if isinstance(v,bool):return ['bool',v]
    if isinstance(v,(int,float)):
        assert math.isfinite(v);n,d=v.as_integer_ratio();return ['number',str(n),str(d)]
    if isinstance(v,str):return ['string',v]
    if isinstance(v,list):return ['list',[canonical(x) for x in v]]
    assert isinstance(v,dict);return ['object',[[k,canonical(v[k])] for k in sorted(v)]]
def identity(x):return sha(dump(canonical(x)).encode())
def ref(path):
    p=R/path;v=p.read_bytes();return {'path':path,'bytes':len(v),'sha256':sha(v)}
def literal_assignment(path,name):
    t=ast.parse((R/path).read_text('utf-8'))
    return next(ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and any(isinstance(a,ast.Name) and a.id==name for a in n.targets))
def write(name,value):
    with (O/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def main():
    started=time.perf_counter();oldids=json.loads((B/'All_Row_Identities.json').read_text('utf-8'))
    support=json.loads((B/'Support_And_Partition.json').read_text('utf-8'))
    components=json.loads((B/'World_Components.json').read_text('utf-8'))
    rows=[]
    for part in ['FIT','HELD']:
        for row in json.loads(gzip.decompress((B/f'{part}_Current_Packets_And_Targets.json.gz').read_bytes())):
            row['saved_partition']=part;rows.append(row)
    raw_bytes=RAW.read_bytes();lines=raw_bytes.splitlines();assert len(lines)==len(oldids)
    signatures=collections.Counter();aliases=collections.defaultdict(set);original_message_ids=set();system_ids=set()
    assistant_fields=collections.Counter();verification_fields=collections.Counter();history_fields=set();joins=0
    for i,line in enumerate(lines):
        d=json.loads(line);u=json.loads(next(m['content'] for m in d['messages'] if m['role']=='user'));a=json.loads(d['messages'][-1]['content'])
        observed={'row_index':i,'world_sha256':sha(str(u['scenario_id']).encode()),'input_sha256':identity({'zone':u['zone'],'local_measurements':u['local_measurements']}),'action_sha256':identity(a['proposed_action'])}
        assert all(oldids[i][k]==v for k,v in observed.items()),('new_schema_join_identity_mismatch',i)
        joins+=1;aliases[observed['world_sha256']].add(u['scenario_id']);signatures[(tuple(sorted(u)),tuple(sorted(u['local_measurements'])))]+=1
        original_message_ids.add(sha(dump(d['messages'][:-1]).encode()));system_ids.add(sha(next(m['content'] for m in d['messages'] if m['role']=='system').encode()))
        assistant_fields.update(a.keys());verification_fields.update(a.get('verification',{}).keys())
        history_fields.update(k for k in u if any(t in k.lower() for t in ['feedback','history','failed','iteration','cursor','step','timestamp']))
    zones=json.loads((R/'work/e/pack/testbeds/federation_4mg_ieee118_metadata.json').read_text('utf-8'))['zones']
    anchors=literal_assignment('work/e/audit/phase2g_llm_guided_rescue_runner.py','ZONE_ANCHORS')
    qgrid=literal_assignment('work/e/audit/run_reflection_v4_safety_envelope.py','ALLOWED_Q')
    world=collections.defaultdict(list)
    for row in rows:world[row['world_sha256']].append(row)
    details=[];counts=collections.Counter();qcounts=collections.Counter();allcandidate=0;firstscope_cases=[];coverage=[]
    for wh, rr in sorted(world.items()):
        assert len(rr)==4 and {r['packet']['zone'] for r in rr}==set(zones)
        vv={}
        for row in rr:
            z=row['packet']['zone'];v=row['packet']['local_measurements']['bus_voltages'];assert set(map(int,v))<=set(zones[z]);assert not(set(vv)&set(map(int,v)))
            vv.update({int(k):val for k,val in v.items()})
        coverage.append({'world_sha256':wh,'missing_bus_fields':sorted(set(range(118))-set(vv))});guv={str(k):vv[k] for k in sorted(vv) if vv[k]<.95}
        for row in sorted(rr,key=lambda r:r['packet']['zone']):
            z=row['packet']['zone'];v=row['packet']['local_measurements']['bus_voltages'];ordered=sorted((float(value),int(k)) for k,value in v.items())
            cutoff_tie=len(ordered)>8 and ordered[7][0]==ordered[8][0];minimum_tie=len(ordered)>1 and ordered[0][0]==ordered[1][0]
            # No tie-order substitution: source pandas ordering is UNKNOWN if its boundary ties.
            candidate=None if cutoff_tie else sorted({int(b) for b,val in v.items() if val<.95}|{b for _,b in ordered[:8]}|set(anchors.get(z,[])))
            action=row['action'];kind='NULL' if action is None else 'SINGLE' if len(action['add_shunts_q_mvar'])==1 else 'MULTI'
            label='NULL_WITH_GLOBAL_UV' if kind=='NULL' and guv else 'SOURCE_SKIPPED_GLOBAL_ZERO' if not guv else 'NOT_SINGLE_DIRECT_LABEL' if kind!='SINGLE' else 'UNKNOWN_CANDIDATE_CUTOFF_TIE' if candidate is None else 'OUTSIDE_ORIGINAL_MENU'
            if kind=='SINGLE':
                b,q=next(iter(action['add_shunts_q_mvar'].items()));qcounts[str(q)]+=1
                if candidate is not None and int(b) in candidate and q in qgrid:label='LEGAL_OBSERVED_SINGLE_TEACHER_CHOICE'
            counts[label]+=1;counts[label+'_multiplicity']+=row['multiplicity'];allcandidate+=0 if candidate is None else len(candidate)*len(qgrid)
            details.append({'world_sha256':wh,'input_sha256':row['input_sha256'],'saved_partition':row['saved_partition'],'zone':z,'multiplicity':row['multiplicity'],'source_action_sha256':row['action_sha256'],'label_admission':label,'observed_uv_count_from_all_four_saved_packets':len(guv),'global_uv_map_complete':len(vv)==118,'candidate_buses_current_only':candidate,'candidate_action_count':None if candidate is None else len(candidate)*len(qgrid),'lowest8_boundary_tie':cutoff_tie,'worst_bus_minimum_tie':minimum_tie,'history_and_feedback':'ABSENT_NOT_EMPTY_PROVED','chronological_state_binding':'UNRECOVERED_FROM_THIS_STATIC_RECORD'})
    current=json.loads((R/'outputs/g5_original118_adapter_ablation_20261109/All4_Original_Inputs.json').read_text('utf-8'))
    for r in current:
        w=sha(r['case_id'].encode());found=[x for x in rows if x['world_sha256']==w]
        firstscope_cases.append({'case_id':r['case_id'],'training_world_name_match':bool(found),'saved_partition':found[0]['saved_partition'] if found else None,'claim':'Name membership only; not same native state or unused confirmation.'})
    alias_components=[{'component_sha256':c['component_sha256'],'worlds':[{'world_sha256':w,'scenario_ids':sorted(aliases[w])} for w in c['world_sha256']]} for c in components if len(c['world_sha256'])>1]
    assert (O/'Preserved_First_Metadata_Failure.json').exists()
    write('All436_Schema_And_Label_Dispositions.json',details)
    result={'status':'COMPLETE_NEW_CAUSAL_SCHEMA_JOIN_NO_FIT_NO_EXACT_CHRONOLOGICAL_DATA_ADMISSION',
      'scope':'All saved original TRAIN records joined to prior audited identities; old population counts, world split, tokenization and performance audits reused, never rerun.',
      'original_population_reused':support,'materialized_raw_ref':{'path':str(RAW.relative_to(R)),'bytes':len(raw_bytes),'sha256':sha(raw_bytes)},
      'new_join_identity_matches':joins,'user_schema_signatures':[{'user_fields':list(k[0]),'local_fields':list(k[1]),'multiplicity':n} for k,n in signatures.items()],
      'distinct_original_input_message_hashes':len(original_message_ids),'distinct_system_message_hashes':len(system_ids),'history_feedback_step_fields_found':sorted(history_fields),
      'assistant_only_fields':dict(assistant_fields),'assistant_only_verification_fields':dict(verification_fields),
      'current_voltage_schema':{'all_worlds_have_four_nonoverlap_zone_packets':True,'worlds_with_all118_saved_bus_voltages':sum(not x['missing_bus_fields'] for x in coverage),'incomplete_worlds':[x for x in coverage if x['missing_bus_fields']],'current_only_projection_admission':'Conditional source projection only; missingbus neverzeroimputed, native/simultaneous history binding remainsunknown','lowest8_cutoff_tie_pairs':sum(x['lowest8_boundary_tie'] for x in details),'minimum_tie_pairs':sum(x['worst_bus_minimum_tie'] for x in details),'precision':'Use recorded numbers exactly; this does not prove identity to the unrecorded full-precision NET or a simultaneous chronological state.'},
      'label_dispositions_all_pairs_and_multiplicities':dict(counts),'observed_positive_Q_pair_counts':dict(qcounts),'original_Q_grid':qgrid,'Q_without_positive_teacher_example':[q for q in qgrid if str(float(q)) not in qcounts],
      'all_current_catalog_candidate_pairs':allcandidate,'aliases_existing_connected_components':alias_components,'four_current_engineering_root_membership':firstscope_cases,
      'causal_field_join':[
       {'field':'zone, local min/max/counts/UV map/lowest8 and candidate domain','admission':'Reconstructible from saved local voltages and source zone/anchor constants; existing source tie rules remain, no native call needed.'},
       {'field':'global current UV map/count and severity instruction','admission':'Four saved zone packets can supply a static world union. This is extra training context compared with original zone-only SFT; do not call it byte-identical shared training information. Simultaneous state/source binding remains required.'},
       {'field':'failed-short and candidate-filtered chronological verifier feedback, prior operations/stock','admission':'Absent from all original user records. Absence is not proof that a historical prefix is empty; cannot synthesize later Reflection states or outcomes.'},
       {'field':'format-repair request error and attempted malformed answer','admission':'Not supplied by static SFT records. Exact first-prompt data cannot silently become repair-prompt training.'},
       {'field':'assistant verification/summary/confidence/coordinator fields','admission':'Teacher-side labels, not causal actor input; no global observations or physical rewards may be extracted from these as if observed at the input.'},
       {'field':'scenario id/type/severity','admission':'Grouping/provenance only for the new direct control. The source Reflection messages omit these administrative fields; do not feed them to the predictor.'}],
      'candidate_conditioned_tree_verdict':{
       'exact_original_chronological_imitation_dataset_ready':False,
       'pure_demonstration_indicator_possible':'For each preserved record and source-legal candidate, selected-by-this-teacher is a defined categorical fact; a nonselection indicator is not a measured unsafe action, bad reward, or inferior physical action.',
       'genuine_method_choice':'A named demonstration-agreement ranker could preserve every record and an explicit NULL teacher class, with class/multiplicity/world weighting declared before fit. At source-forced-positive inference it could condition on the legal positive catalog, just as the original prompt forces the old SFT model. This is a new constrained-decoding adaptation, not exact historical prompt reproduction or proven strong control.',
       'no_silent_rescue':'Do not drop null-with-globalUV rows, invent their best positive action, fill missing histories with empty, or label unqueried actions as physical failures/rewards. No positive examples exist for all nine Q classes; scoreability is not learned support.',
       'complete_population_preserved':True},
      'preserved_first_metadata_failure':ref('outputs/g5_original118_training_schema_join_20261109/Preserved_First_Metadata_Failure.json'),'smallest_next_data_operation':'Before any fit, bind the original TRAIN generator snapshot construction/zone-message provenance to the existing109 four-zone records. Then, as one metadata-only operation, materialize all436 static-current projections including all missingbus/chronology/null dispositions with explicit unavailable-history flags and original teacher/null classes, retaining16000 multiplicities and old107 connected-component grouping. Freeze whether this named static demonstration-agreement target is the intended numeric control; do not claim those projections are exact chronological Reflection messages. If exact chronological training is required, an already-paid complete source-bound prefix/feedback join is necessary and must keep evaluation roots out of unused confirmation.',
      'new_calls':{'native':0,'PF':0,'model':0,'tokenizer':0,'fit':0,'old_audit_or_scoring_rerun':0},
      'source_refs':[ref('work/e/audit/run_reflection_v4_safety_envelope.py'),ref('work/e/audit/phase2g_llm_guided_rescue_runner.py'),ref('work/e/audit/phase2g_rescue_runner.py'),ref('work/e/pack/testbeds/federation_4mg_ieee118_metadata.json'),ref('work/run_original_role_numeric_gate_20261011.py'),ref('outputs/critical_research_reset_20261010/original_role_numeric_gate_20261011/execution/All_Row_Identities.json'),ref('outputs/critical_research_reset_20261010/original_role_numeric_gate_20261011/execution/World_Components.json')],
      'elapsed_metadata_seconds':time.perf_counter()-started,'G5_or_benchmark_complete':False}
    write('Causal_Schema_Join_And_Next.json',result)
    print(dump({'status':result['status'],'label_dispositions':dict(counts),'missing_positive_Q':result['Q_without_positive_teacher_example'],'result_ref':ref(str((O/'Causal_Schema_Join_And_Next.json').relative_to(R)))}))
if __name__=='__main__':main()
