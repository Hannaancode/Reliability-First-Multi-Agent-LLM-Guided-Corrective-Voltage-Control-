"""New static source + one representative per already-audited pair; zero science."""
import ast
import collections
import gzip
import hashlib
import json
import time
import zipfile
from pathlib import Path

R=Path(__file__).resolve().parents[2]
O=R/'outputs/g5_original118_generator_binding_20261109'
B=R/'outputs/critical_research_reset_20261010/original_role_numeric_gate_20261011/execution'
D=Path(r'C:\Users\HOME\Desktop\multi agentic llm  power systesm')
GEN=D/'phase2a_extract_zone_data_corrected.py'
NB=Path(r'C:\Users\HOME\Downloads\phase_2A_Lora_traininf_1ipynb.ipynb')
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def ref(p):
    b=p.read_bytes();return {'path':str(p.relative_to(R)) if p.is_relative_to(R) else str(p),'bytes':len(b),'sha256':sha(b)}
def write(name,x):
    with (O/name).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def main():
    started=time.perf_counter();rawsource=GEN.read_bytes();source=rawsource.decode('utf-8');tree=ast.parse(source)
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    wanted=['run_extraction','extract_zone_state','generate_corrective_action','candidate_buses','build_training_record','run_pf']
    spans={n:{'start_line':functions[n].lineno,'end_line':functions[n].end_lineno,'AST_sha256':sha(ast.dump(functions[n],include_attributes=False).encode())} for n in wanted}
    with zipfile.ZipFile(D/'multi agentic llm.zip') as z:
        zi=z.getinfo('phase2a_extract_zone_data_corrected.py');bundle_meta={'member_size':zi.file_size,'compression_type':zi.compress_type,'CRC_from_directory_only':zi.CRC}
    ids=json.loads((B/'All_Row_Identities.json').read_text('utf-8'));first={}
    for x in ids:first.setdefault((x['world_sha256'],x['input_sha256']),x['row_index'])
    selected={i:k for k,i in first.items()};rows={}
    for part in ['FIT','HELD']:
        for x in json.loads(gzip.decompress((B/f'{part}_Current_Packets_And_Targets.json.gz').read_bytes())):rows[x['world_sha256'],x['input_sha256']]=x
    assert set(selected.values())==set(rows)
    bindings=[];counts=collections.Counter();globals_byworld=collections.defaultdict(dict);ties=collections.defaultdict(dict);ties_conflicts=[];metrics_mismatch=[];rawbytes=0;seen=0
    with (R/'work/e/training_provenance/zone_agent_train.jsonl').open('rb') as f:
        for i,line in enumerate(f):
            rawbytes+=len(line)
            if i not in selected:continue
            seen+=1;key=selected[i];old=rows[key];d=json.loads(line);u=json.loads(d['messages'][1]['content']);a=json.loads(d['messages'][-1]['content']);v=a.get('verification',{})
            # The previous schema stage certified exact16,000-row identities; this new join adds label-reason and source ancestry only.
            assert u['zone']==old['packet']['zone'] and u['local_measurements']==old['packet']['local_measurements'] and a['proposed_action']==old['action']
            vm=list(old['packet']['local_measurements']['bus_voltages'].values());nu=sum(x<.95 for x in vm);no=sum(x>1.05 for x in vm)
            assert (a['n_undervoltage'],a['n_overvoltage'],a['min_voltage_pu'],a['max_voltage_pu'])==(nu,no,min(vm),max(vm))
            if old['action'] is not None:category='POSITIVE_TEACHER_ACTION'
            elif nu==0:category='NO_LOCAL_UV'
            elif no>0:category='LOCAL_UV_AND_OV'
            else:category='LOCAL_UV_ONLY_GLOBAL_POLICY_WITHHELD'
            counts[category]+=1;counts[category+'_multiplicity']+=old['multiplicity']
            b={'world_sha256':key[0],'input_sha256':key[1],'scenario_id':u['scenario_id'],'zone':u['zone'],'first_source_row':i,'raw_line_sha256':sha(line),'multiplicity_preserved':old['multiplicity'],'classification_from_current_local_fields':category,'actual_verdict':v.get('verdict'),'actual_original_verdict':v.get('original_verdict'),'actual_reason':v.get('reason'),'coordinator_candidate':a.get('candidate_action_for_coordinator'),'actual_requires_coordinator_review':a.get('requires_coordinator_review'),'actual_autonomous_local_action_allowed':a.get('autonomous_local_action_allowed'),'selected_or_best_local_trial':v.get('best_local_candidate_trial') if old['action'] is None else None}
            bindings.append(b)
            if v.get('old_global') is not None:globals_byworld[key[0]][canonical(v['old_global'])]=v['old_global']
            for idx,t in u['local_measurements']['tie_line_flows'].items():
                if idx in ties[key[0]] and ties[key[0]][idx]!=t:ties_conflicts.append([key[0],idx])
                ties[key[0]][idx]=t
    assert seen==len(rows)
    worlds=collections.defaultdict(list)
    for (w,_),r in rows.items():worlds[w].append(r)
    for w,rr in worlds.items():
        vm=[v for r in rr for v in r['packet']['local_measurements']['bus_voltages'].values()]
        for gm in globals_byworld[w].values():
            expected={'vm_min_pu':min(vm),'vm_max_pu':max(vm),'n_undervoltage':sum(v<.95 for v in vm),'n_overvoltage':sum(v>1.05 for v in vm)}
            if any(gm.get(k)!=val for k,val in expected.items()):metrics_mismatch.append(w)
    nulls=[b for b in bindings if b['classification_from_current_local_fields']!='POSITIVE_TEACHER_ACTION']
    assert all(b['actual_verdict']=='NO_ACTION_NEEDED' for b in nulls if b['classification_from_current_local_fields']=='NO_LOCAL_UV')
    assert all(b['actual_verdict']=='NO_AUTOMATIC_ACTION' for b in nulls if b['classification_from_current_local_fields']!='NO_LOCAL_UV')
    withheld=[b for b in nulls if b['classification_from_current_local_fields']=='LOCAL_UV_ONLY_GLOBAL_POLICY_WITHHELD']
    assert all(b['actual_original_verdict']=='NO_VERIFIED_ACTION_FOUND' and b['coordinator_candidate'] is not None and b['selected_or_best_local_trial']['accepted_by_policy'] is False for b in withheld)
    nb=json.loads(NB.read_text('utf-8'));cellrefs=[]
    for i in [14,21,36,39]:
        s=''.join(nb['cells'][i]['source']);cellrefs.append({'cell_index_zero_based':i,'source_sha256':sha(s.encode()),'lines':len(s.splitlines()),'role':{14:'Preserve old proposed_action/null and coordinator flags while compacting assistant',21:'Build ultra-compact actor input from assistant zone/extrema/counts/state_summary',36:'Same ultra-compact reconstruction directly from original grouped-split labels',39:'Original ultra model training/loading recipe; inspected source only, not executed'}[i]})
    assert (O/'Preserved_Archive_Read_Limitation.json').exists();write('All436_Source_Reason_Bindings.json',bindings)
    result={
      'status':'COMPLETE_SCOPED_GENERATOR_AND_TEACHER_ROLE_BINDING_NO_WEIGHT_INTERVENTION',
      'generator_source_ref':ref(GEN),'named_bundled_member':{'archive_path':str(D/'multi agentic llm.zip'),'member':'phase2a_extract_zone_data_corrected.py','directory_only':bundle_meta,'member_byte_equality':'UNKNOWN_UNSUPPORTED_COMPRESSION; no alternate extraction performed','archive_rehash_performed':False},'function_source_spans':spans,
      'simultaneous_state_source_argument':{
       'source_semantics':'run_extraction creates one scenario NET, solves it once, then extracts all four zones from that same variable. generate_corrective_action computes old_global on that NET and runs every candidate on copy.deepcopy(solved_net); no selected candidate is committed to the source NET. Thus the recovered generator defines simultaneous pre-action zone snapshots, not a four-zone chronological rollout.',
       'observed_support':{'all436_current_fields_match_their_previously_audited_pair':'PASS','all436_assistant_local_counts_extrema_match_saved_current_fields':'PASS','worlds_with_old_global_in_representative_labels':sum(bool(x) for x in globals_byworld.values()),'worlds_with_multiple_distinct_old_global_records':sum(len(x)>1 for x in globals_byworld.values()),'old_global_observed_minmax_UV_OV_mismatches':metrics_mismatch,'shared_tie_flow_field_conflicts':ties_conflicts},
       'exact_lineage_limit':'No saved native full-state hash or original execution/source receipt joins every four-zone TRAIN packet to this exact generator execution. The augmentation/relabel source that added coordinator candidates is not recovered by the narrow named-source inspection. The source and saved cross-zone fields support a common static snapshot, but exact simultaneous native-state provenance remains CONDITIONAL, not certified.',
       'bus116':'The generator omits a bus voltage if res_bus lacks its row or pandas.isna(value). Four saved worlds omit116. The precise historical missing-row versus NaN cause is UNKNOWN; no voltage is filled in and no complete global map is claimed for them.'},
      'teacher_policy':{'local_decision_not_global_forced_proposal':True,'positive_Q_source_grid':[25,50,75,100,150],'candidate_scope':'Worst bus plus next-lowest UV bus, at most two; not the Reflection candidate union.',
       'null_rules':'NO_ACTION_NEEDED when local UV=0; NO_AUTOMATIC_ACTION when local UV and OV coexist; otherwise no globally accepted candidate returns NO_VERIFIED_ACTION_FOUND before the later coordinator-label transformation.',
       'acceptance':'Local minimum must improve >1e-5; global minimum may not worsen >1e-5; global maximum<=1.06; overloaded line and transformer counts may not increase.',
       'score':'(local UV count decreases [Boolean], local minimum improvement, -Q). This is not Reflection global UV-count ordering.',
       'solver_source':'NR/init auto/Qlimits/checkconnectivity/tolerance1e-6/max_iteration120/numbaFalse; source only, no replay.'},
      'all_pair_local_null_reasons_and_multiplicities':dict(counts),
      'coordinator_candidate_limit':{'pairs':len(withheld),'original_nulls_preserved':True,'all23_actual_best_local_trial_accepted_by_policy_false':True,'example_observed_maximum':withheld[0]['selected_or_best_local_trial']['new_global_max_v'],'meaning':'A local improvement is already recorded, but its global acceptance failed. These are unapproved proposals, never safe winners or replacement positive reward labels.'},
      'serving_role_difference':{'source_ref':ref(R/'work/e/audit/run_reflection_v4_safety_envelope.py'),'required':'When globalUV>0, propose one legal bus and one of nine Qs; do not return null. Direct response is a proposal; unchanged verifier decides safety. All four zones are asked even when a zone is locally healthy or already overvoltage.',
       'not_a_causal_model_failure_explanation':'The source-role mismatch is verified; no claim is made that it caused a given generation, null response, bus error, benchmark result, or all old failures. The original labels are coherent with their original local-action policy.'},
      'original_model_input_recipe':{'notebook_ref':ref(NB),'source_cell_refs':cellrefs,'finding':'Recovered ultra-compact recipe retains nullable local-action targets and coordinator flags and constructs input using teacher zone statistics/state_summary. Reflection instead supplies globalUV, explicit candidate/Q menus and chronological feedback. Source inspection does not recertify exact historical runtime/training token bytes or rerun old audits.'},
      'all_record_target_options':[
       {'option':'Preserve original local diagnosis/permission target for all436 records','admitted_semantics':'No relabeling; all16000 multiplicities and old107 connected-component grouping stay. Useful faithful numerical imitation reference, but not an exact direct forced-proposal task.'},
       {'option':'Named role-alignment adaptation separating proposal from permission','admitted_semantics':'The331 existing teacher actions and23 explicit coordinator candidates can be transcribed with their original approval distinction. Remaining82 null records have no recorded positive proposal; retain their null/UNKNOWN target disposition, never invent a bus/Q or call exclusion a balanced complete target. The same prepared corpus and loss masks must be shared with numerical controls and declared before fit. Four Q values still lack positive teacher examples.',
        'blocker':'An all-record forced-positive response target is not supplied by the existing data; objective/data construction is a prospective methodological decision, not an automatic fit gate.'},
       {'option':'Exact chronological proposal supervision from already-paid source-bound histories','admitted_semantics':'Join exact original messages, menus, feedback, current state and saved query receipts. Keep returned, unsafe, failed and unentered labels separate; use only observed actions/outcomes, retain development exposure. This can support a genuinely different weight intervention without reopening old stopped scale work.',
        'blocker':'Requires its own complete causal data join and split/weight/query-cost contract; the static TRAIN file cannot supply absent chronology.'}],
      'recommended_smallest_next_operation':'A saved-only label-availability manifest for the proposed role-alignment corpus: all436 original pairs with331 verified local actions,23 explicitly unapproved coordinator proposals and82 unavailable positive proposals. Bind exact source prompt/target roles and old multiplicities/components, then freeze one declared objective shared with a strong numerical learner before any fit. Do not automatically promote rejected candidates, drop null worlds or synthesize all-nine-Q rewards.',
      'new_cost_scope':{'raw_input_bytes_read_for_selected_row_scan':rawbytes,'raw_input_rows_parsed':seen,'metadata_elapsed_seconds':time.perf_counter()-started,'native_model_tokenizer_PF_fit_calls':0,'old_token_count_split_performance_audit_reruns':0},
      'prior_schema_ref':ref(R/'outputs/g5_original118_training_schema_join_20261109/Causal_Schema_Join_And_Next.json'),'pair_evidence_ref':ref(O/'All436_Source_Reason_Bindings.json'),'G5_complete':False}
    write('Generator_Source_And_Target_Options.json',result)
    print(canonical({'status':result['status'],'result_ref':ref(O/'Generator_Source_And_Target_Options.json'),'observed_support':result['simultaneous_state_source_argument']['observed_support'],'null_counts':dict(counts)}))
if __name__=='__main__':main()
