"""Close saved-only registry gates, then lock THREE unentered case protocols.

Neither stage allocates a GPU or runs model/physics. Actual host owners may be
started once only after these new saved-source/input/ownership gates pass.
"""
import ast,subprocess,zipfile
from datetime import datetime,timezone
from reflection118_remaining_cases_core_20261023 import *
from finalize_r118_dff_prelaunch_and_task_snapshot_20261023 import replace_json
TOP=R/'outputs/reflection118_remaining_cases_preparation_20261023'

def registry_stage():
    assert read(R/'outputs/r118_dff_missing_continuation_handoff_20261023/Completion.json')['independent_audit_status'].startswith('PASS_')
    source=R/'work/build_and_audit_closed_dff_registry_20261023.py'
    for phase,mode,out,coord in [('Producer','build','closed_registry','registry_coordination'),('Reader','audit','closed_registry_independent','registry_reader_coordination')]:
        protocol=TOP/(phase+'_Registry_Owner_Protocol.json')
        put(protocol,dict(single_owner=dict(source=source.relative_to(R).as_posix(),sha256=sha(source),python='work/vcsa_module_env/Scripts/python.exe',output=(TOP/out).relative_to(R).as_posix(),coordination=(TOP/coord).relative_to(R).as_posix(),bound_seconds=1900,arguments=['--mode',mode])))
        with (TOP/(phase+'_Registry.log')).open('x',encoding='utf-8') as log:
            child=subprocess.Popen([sys.executable,'-X','utf8',str(R/'work/coordinate_single_owner_arguments_v2_20261022.py'),'--protocol',str(protocol.relative_to(R))],cwd=R,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            put(TOP/(phase+'_Registry_Launch.json'),dict(pid=child.pid,parent=os.getpid(),source_sha256=sha(source)));code=child.wait(timeout=1950)
        put(TOP/(phase+'_Registry_End.json'),dict(pid=child.pid,exit_code=code));assert code==0,'Keep initial failure, no repeated index or scientific stage'
    assert read(TOP/'closed_registry_independent/Independent_Audit.json')['status'].startswith('PASS_')

def freeze_stage():
    integration=read(TOP/'integration/New_Integration_Readiness.json');assert integration['status'].startswith('PASS_NEW_ALL3')
    index=TOP/'closed_registry/Closed_Physical_Receipt_Registry.json';audit=read(TOP/'closed_registry_independent/Independent_Audit.json');assert audit['index_sha256']==sha(index)
    assert read(R/'outputs/r118_dff_missing_continuation_handoff_20261023/Completion.json')['independent_audit_status'].startswith('PASS_')
    remote_names=['run_reflection118_remaining_model_remote_20261023.py','reflection118_remaining_model_service_guardian_20261023.py','original_reflection_serving_pure_20261022.py','original_reflection_tokenizer_tensor_view_v2_20261022.py','native13_lora_setup_remote_v2_20261020.py','native13_lora_environment_check_v2_20261020.py','candidate_process_pretrained_loader_native13_v2_20261020.py','public_size_u61_preservation.py','frozen_gpu_requirements.txt','frozen_dependency_closure.txt','uv_bootstrap_version.txt']
    source_names=['reflection118_remaining_cases_core_20261023.py','run_reflection118_remaining_local_20261023.py','audit_reflection118_remaining_case_20261023.py','run_reflection118_remaining_colab_20261023.py','coordinate_reflection118_remaining_cases_20261023.py','build_and_audit_closed_dff_registry_20261023.py','check_remaining_reflection118_new_integration_20261023.py','r118_dff_missing_continuation_core_20261023.py','reflection118_chronological_core_20261022.py','frozen_physics_loader.py','run_reflection118_chronological_local_20261022.py','prior_physical_query_footprints_20261018.py','candidate_process_evidence_utils.py','public_size_local_preservation_v2.py','google_account_profile.py','coordinate_single_owner_arguments_v2_20261022.py','finalize_reflection118_three_case_gates_20261023.py']
    pins={}
    for name in set(source_names+remote_names):
        path=R/'work'/name
        if path.suffix=='.py':ast.parse(path.read_text('utf-8'))
        pins[path.relative_to(R).as_posix()]=sha(path)
    (R/'outputs/reflection118_remaining_cases_execution_20261023').mkdir(exist_ok=False)
    (R/'outputs/reflection118_remaining_cases_independent_20261023').mkdir(exist_ok=False)
    completed=[]
    for number in [1,2,3]:
        prep=TOP/f'case_{number:02d}';protocol=prep/'Frozen_Engineering_Protocol.json';p=read(protocol)
        assert p['old_model_calls_for_this_case']==0 and p['source_case_index']==number
        (prep/'Initial_Design_Protocol.json').write_bytes(protocol.read_bytes())
        p['status']='FROZEN_REMAINING_ORIGINAL_CASE_REQUIRE_FRESH_ONE_ASSIGNMENT_OWNER'
        p['closed_paid_registry']=index.relative_to(R).as_posix()
        p['local_source_hashes']={k:v for k,v in pins.items() if k.endswith('.py')}|p['original_serving_sources']
        p['closed_DFF_result_sha256']=sha(E/'Result.json');p['closed_DFF_independent_audit_sha256']=sha(A/'Independent_Audit.json')
        binding=read(R/p['bindings'])[number]
        p['input_hashes']={x.relative_to(R).as_posix():sha(x) for x in [index,TOP/'closed_registry_independent/Independent_Audit.json',TOP/'integration/New_Integration_Readiness.json',R/p['bindings'],R/p['base_net'],R/p['metadata'],R/binding['solved_payload'],R/binding['registration']['recipe']]}
        replace_json(protocol,p)
        authority=prep/'Direct_Human_Authority.json'
        payload={'work/'+n:R/'work'/n for n in remote_names};payload.update({n:R/n for n in p['original_serving_sources']})
        adapter=R/'work/e/pack/models/zone_agent_shared_lora_qwen05b_ultra_v1'
        for n,h in p['private_adapter_tokenizer_unchanged'].items():assert sha(adapter/n)==h;payload[adapter.relative_to(R).as_posix()+'/'+n]=adapter/n
        payload['prep/protocol.json']=protocol
        manifest={n:dict(bytes=x.stat().st_size,sha256=sha(x)) for n,x in payload.items()}
        archive=prep/'Unchanged_Private_Adapter_And_Causal_Service.zip'
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
            for n,x in payload.items():z.write(x,n)
            z.writestr('PUBLIC_SIZE_INPUT_MANIFEST.json',json.dumps(manifest,indent=2))
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None and len(z.namelist())==len(manifest)+1
            for n,m in manifest.items():raw=z.read(n);assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
        put(prep/'Cloud_Payload_Manifest.json',dict(archive=archive.relative_to(R).as_posix(),bytes=archive.stat().st_size,sha256=sha(archive),members=len(manifest)+1,human_authority_source=authority.relative_to(R).as_posix(),human_authority_sha256=sha(authority),private_adapter_tokenizer_authorized=True,credentials_NET_bank_teacher_labels_uploaded=False))
        for kind,source,python,output,coord,bound in [('Primary','run_reflection118_remaining_colab_20261023.py','work/colab_access_env/Scripts/python.exe','reflection118_remaining_cases_execution_20261023','reflection118_remaining_cases_coordination_20261023',13500),('Reader','audit_reflection118_remaining_case_20261023.py','work/vcsa_module_env/Scripts/python.exe','reflection118_remaining_cases_independent_20261023','reflection118_remaining_cases_reader_coordination_20261023',7500)]:
            path=R/'work'/source
            put(prep/(kind+'_Owner_Protocol.json'),dict(single_owner=dict(source=path.relative_to(R).as_posix(),sha256=sha(path),python=python,output=f'outputs/{output}/case_{number:02d}',coordination=f'outputs/{coord}/case_{number:02d}',bound_seconds=bound,arguments=['--case-index',str(number)])))
            (R/'outputs'/coord).mkdir(exist_ok=True)
        (R/'outputs/reflection118_remaining_cases_coordination_20261023').mkdir(exist_ok=True)
        hashes=pins|p['original_serving_sources']|p['input_hashes']
        for x in [protocol,prep/'Direct_Human_Authority.json',prep/'Cloud_Payload_Manifest.json']:
            hashes[x.relative_to(R).as_posix()]=sha(x)
        put(prep/'Launch_Readiness_Audit.json',dict(passed=True,source_hashes=hashes,actual_new_model_PF_calls_before_freeze=0,only_this_previously_unentered_case=True,partial_unknowns_preserved=True))
        put(prep/'Final_Allocation_Readiness.json',dict(passed=True,exact_original_policy_context_cold_preservation_and_closed_history_gates=True,protocol_sha256=sha(protocol),source_case_index=number,one_fixed_profile_no_fallback=True,not_a_performance_result=True))
        completed.append(dict(case_index=number,case_id=p['case_order'][0],protocol_sha256=sha(protocol),payload_bytes=archive.stat().st_size))
    checks=frozen_checks();put(TOP/'Final_All3_Readiness.json',dict(passed=True,status='ALL3_PROSPECTIVE_ORIGINAL_CASE_PROTOCOLS_LOCKED_NOT_YET_ALLOCATED',cases=completed,source_hashes=pins,closed_registry_independent_audit=audit,original_frozen_checks=checks,current_GPU_assignments=0,no_science_in_freeze=True,all6_final_goals='OPEN'))
    print(json.dumps(dict(status='THREE_ORIGINAL_CASES_READY_NO_ALLOCATIONS_YET',cases=completed)))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['registry','freeze'],required=True);args=ap.parse_args()
    registry_stage() if args.stage=='registry' else freeze_stage()
