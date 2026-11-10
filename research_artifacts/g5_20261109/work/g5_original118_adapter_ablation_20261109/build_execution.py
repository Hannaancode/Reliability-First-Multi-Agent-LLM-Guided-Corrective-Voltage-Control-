"""Prepare the new bounded package/host/reader bindings; NEVER allocate or run it."""
import ast
import hashlib
import json
import time
import zipfile
from pathlib import Path

R = Path(__file__).resolve().parents[2]
W = Path(__file__).resolve().parent
BASE = R / 'outputs/g5_original118_adapter_ablation_20261109'
P = BASE / 'execution_preparation'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ref(p):
    p = Path(p)
    return {'path': p.relative_to(R).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}


def put(p, value):
    with Path(p).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)


def main():
    began = time.perf_counter()
    assert not P.exists()
    P.mkdir()
    source = R / 'work/run_native13_adapter_disabled_colab_20261021.py'
    assert sha(source) == '1c67d8704f3de17f2d99ae4d2c1569ba0da3e4eac27831f581fb446ceab60377'
    text = source.read_text(encoding='utf-8')
    replacements = {
        "from urllib.parse import quote": "from urllib.parse import quote\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parents[2]/'work'))",
        "ROOT=Path(__file__).resolve().parents[1]": "ROOT=Path(__file__).resolve().parents[2]",
        "PREP=R/'native13_adapter_disabled_diagnostic_preparation_20261021'": "PREP=R/'g5_original118_adapter_ablation_20261109/execution_preparation'",
        "native13_adapter_disabled_diagnostic_execution_20261021": "g5_original118_adapter_ablation_execution_20261109",
        "work/native13_adapter_disabled_guardian_20261021.py": "work/g5_original118_ablation_guardian.py",
        "session_name='hiergrid-public-size-screen'": "session_name='hiergrid-original118-adapter-off-first-inputs'",
        "except (requests.exceptions.Timeout,requests.exceptions.ConnectionError,requests.exceptions.HTTPError):": "except (requests.exceptions.Timeout,requests.exceptions.ConnectionError,requests.exceptions.HTTPError) as transport_error:\n                if getattr(getattr(transport_error,'response',None),'status_code',None) in (401,403,429):raise",
        "        ast.parse(code);out=runtime.execute_code(code,allow_stdin=False,timeout=seconds)\n        assert not any(x.get('output_type')=='error' for x in out),'Remote control stage failed'": "        ast.parse(code);out=runtime.execute_code(code,allow_stdin=False,timeout=seconds)\n        assert not any(x.get('output_type')=='error' for x in out),'Remote control stage failed'\n        return out",
        "        assert ready['passed']": "        assert ready['passed'] and ready['independent_source_review_status']=='PASS_ORIGINAL118_DISABLED_ENGINEERING_SOURCE'",
        "        for name in ['public_size_science.log','public_size_exit.json']:": "        for name in ['public_size_science.log','public_size_exit.json','public_size_guardian_End.json']:",
    }
    for old, new in replacements.items():
        assert old in text, old
        text = text.replace(old, new)
    marker = "        state.update(remote_exit_code=desc['exit_code'],scientific_process_ended=True,all_actual_closed_artifacts_preserved=True)"
    assert marker in text
    text = text.replace(marker, """        guardian_end=read(OUT/'staged/public_size_guardian_End.json')
        assert guardian_end['actual_pid']==desc['guardian_claim']['actual_pid']
        assert guardian_end['source_sha256']==protocol['remote_source_hashes']['work/g5_original118_ablation_guardian.py']
        gid=int(guardian_end['actual_pid']);start_identity=desc['guardian_claim']['proc_start_identity']
        probe="from pathlib import Path\\nimport json,time\\np=Path('/proc/"+str(gid)+"/stat')\\nend=time.monotonic()+10\\nwhile p.exists() and p.read_text().split()[2]!='Z' and time.monotonic()<end: time.sleep(.1)\\nstate=p.read_text().split() if p.exists() else None\\nassert state is None or (state[2]=='Z' and state[21]=="+repr(start_identity)+")\\nprint(json.dumps({'actual_guardian_pid':"+str(gid)+",'ended_or_reaped_zombie':True,'original_start_identity':"+repr(start_identity)+"}))\\n"
        observed=execute(probe,seconds=20)
        preserve(OUT/'Remote_Guardian_Terminal_Observation.json',json.dumps({'identity':desc['guardian_claim'],'returned_remote_observation':observed,'fresh_remote_probe_passed':True},indent=2).encode())
        state.update(remote_exit_code=desc['exit_code'],scientific_process_ended=True,guardian_ended=True,all_actual_closed_artifacts_preserved=True)""")
    ast.parse(text)
    assert text.count('client.assign(') == 1 and "arm='public_0_5B'" in text
    with (W / 'host.py').open('x', encoding='utf-8') as f:
        f.write(text)
    put(P / 'Host_Reuse_Delta.json', {'status': 'ADDITIVE_SOURCE_PREPARATION_NO_HOST_INVOCATION',
        'original_host_ref': ref(source), 'new_host_ref': ref(W / 'host.py'),
        'changes': list(replacements), 'guardian_terminal_observation_added': True,
        'one_fixed_profile_one_assign_no_fallback': True,
        'explicit_HTTP401_403_429_no_retry': True, 'new_network_or_allocation_calls': 0})
    # Bind actual six enabled-serving runtimes, including both missing suffixes.
    history = read(R / 'outputs/original118_finite_model_history_query_20261102/execution/Finite_Original118_Request_History_LOCAL_ONLY.json')
    hosts = []
    common = None
    canonical_inventory = None
    for host in history['hosts']:
        folder = (R / host['descriptor_ref']['path']).parent
        desc = read(R / host['descriptor_ref']['path'])
        assert ref(R / host['descriptor_ref']['path']) == host['descriptor_ref']
        paths = {'environment': folder / 'staged/public_size_environment.json',
                 'loader': folder / 'staged/study/primary_Loader_Proof.json',
                 'immutable': folder / 'staged/study/primary_Immutable_Before.json',
                 'enabled': folder / 'staged/study/primary_Actual_Enabled_Adapter_State.json'}
        for key in ('loader', 'immutable', 'enabled'):
            m = desc['members'][paths[key].name]
            assert paths[key].stat().st_size == m['bytes'] and sha(paths[key]) == m['sha256']
        env = read(paths['environment']); loader = read(paths['loader']); flags = read(paths['enabled'])
        actual = {k: env[k] for k in ['base_revision', 'base_weight_sha256', 'config_sha256',
                                     'versions', 'exact_dependency_count', 'dependency_differences']}
        if common is None:
            common = actual; canonical_inventory = ref(paths['immutable'])
        assert actual == common
        assert sha(paths['immutable']) == canonical_inventory['sha256'] == '25eb42ee7db8aacb96ffc15db881af8c4188b9d47a34bc4a9bd6e2fa5a0c3194'
        assert flags and not any(flags.values())
        assert loader['trainable_body_parameters'] == 0 and loader['source_tensor_values_identical']
        assert loader['enabled_disabled_restored_unmerged'] and loader['four_bit_base']
        hosts.append({'id': host['id'], 'artifact_refs': {k: ref(v) for k, v in paths.items()},
                      'inherited_closed_descriptor_ref': host['descriptor_ref'], 'inherited_audit_ref': host['audit_ref']})
    binding = {'status': 'SAVED_ACTUAL_SIX_ENABLED_SERVING_RUNTIMES_AND_IMMUTABLE_BASE_MATCH',
        'hosts': hosts, 'common_actual_environment': common,
        'canonical_immutable_inventory_ref': canonical_inventory,
        'scope': 'Exact current2026 original118 serving runtimes and preserved quantized/base parameter-buffer inventories, with source-copied private adapter. NOT recovery of the historical paper SFT base revision.',
        'historical_paper_base_revision': 'UNRECOVERED', 'new_model_tokenizer_PF_calls': 0}
    put(P / 'Original_Enabled_Runtime_Binding.json', binding)
    protocol = read(BASE / 'Engineering_Protocol.json')
    protocol['status'] = 'FROZEN_ENGINEERING_PACKAGE_AWAITING_INDEPENDENT_SOURCE_GATE_NO_ALLOCATION'
    protocol['profiles'] = protocol['fixed_profile']
    protocol['historical_actual_environment'] = common
    protocol['historical_immutable_inventory_sha256'] = canonical_inventory['sha256']
    protocol['runtime_binding_ref'] = ref(P / 'Original_Enabled_Runtime_Binding.json')
    protocol['immutable_inference_contract']['actual_environment'] = common
    protocol['immutable_inference_contract']['actual_base_immutable_inventory_sha256'] = canonical_inventory['sha256']
    protocol['request_key_scope'] = 'Transport/case provenance identity; no universal prior-input-disjointness claim. All4 exact token inputs are pairwise distinct. Future global inference reuse must also bind actual token/model/adapter-mode/decode/RNG identity.'
    protocol['returned_output_preservation'] = 'Observed generation return marker, full raw token sequence saved before postchecks, decoded text saved before RNG/footer; closure writes within fixed1020sec process envelope. Unpreserved return stays UNKNOWN.'
    remote_map = protocol['remote_file_mapping']
    remote_map['work/g5_original118_ablation_guardian.py'] = 'work/g5_original118_adapter_ablation_20261109/guardian.py'
    for name in ['native13_lora_setup_remote_v2_20261020.py', 'native13_lora_environment_check_v2_20261020.py',
                 'frozen_gpu_requirements.txt', 'frozen_dependency_closure.txt', 'uv_bootstrap_version.txt']:
        remote_map['work/' + name] = 'work/' + name
    for name in protocol['original_serving_sources']:
        remote_map[name] = name
    protocol['remote_source_hashes'] = {dest: sha(R / src) for dest, src in remote_map.items()}
    for dest, src in remote_map.items():
        if src.endswith('.py'):
            ast.parse((R / src).read_bytes())
    put(P / 'Frozen_Engineering_Protocol.json', protocol)
    inputs_bytes = (BASE / 'All4_Original_Inputs.json').read_bytes()
    (P / 'All4_Original_Inputs.json').write_bytes(inputs_bytes)
    authority = {'scope': 'User explicitly requested original-model/G5 contribution work; original full authority to serve original private weights and causal inputs on the fixed own profile persists. Parent explicitly requested this new bounded adapter-off package, no allocation by this preparation.',
        'export_allowlist': 'Only original private adapter/tokenizer, four causal message/token inputs, exact source/dependency metadata. No credentials, NETs, training corpus, original outputs or outcome labels.',
        'fixed_profile': protocol['profiles'], 'no_purchases_fallback_or_denial_bypass': True}
    put(P / 'Direct_Human_Authority.json', authority)
    files = {dest: R / src for dest, src in remote_map.items()}
    for name, h in protocol['private_adapter_tokenizer_unchanged'].items():
        f = R / 'work/e/pack/models/zone_agent_shared_lora_qwen05b_ultra_v1' / name
        assert sha(f) == h
        files['work/e/pack/models/zone_agent_shared_lora_qwen05b_ultra_v1/' + name] = f
    files['prep/protocol.json'] = P / 'Frozen_Engineering_Protocol.json'
    files['prep/All4_Original_Inputs.json'] = P / 'All4_Original_Inputs.json'
    assert not any(any(t in name.lower() for t in ('credential', 'network.json', 'train.jsonl', 'result.json')) for name in files)
    manifest = {name: {'bytes': f.stat().st_size, 'sha256': sha(f)} for name, f in files.items()}
    archive = P / 'Original118_Disabled_Four_Causal_Inputs_Only.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for name, f in files.items():
            z.write(f, name)
        z.writestr('PUBLIC_SIZE_INPUT_MANIFEST.json', json.dumps(manifest, indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist()) == len(set(z.namelist()))
        for name, m in manifest.items():
            b = z.read(name)
            assert len(b) == m['bytes'] and hashlib.sha256(b).hexdigest() == m['sha256']
    put(P / 'Cloud_Payload_Manifest.json', {'archive': archive.relative_to(R).as_posix(),
        'bytes': archive.stat().st_size, 'sha256': sha(archive), 'members': len(manifest) + 1,
        'human_authority_source': (P / 'Direct_Human_Authority.json').relative_to(R).as_posix(),
        'human_authority_sha256': sha(P / 'Direct_Human_Authority.json')})
    for role, source_name, output, coordination, python, bound in [
        ('Primary', 'host.py', 'g5_original118_adapter_ablation_execution_20261109',
         'g5_original118_adapter_ablation_coordination_20261109', 'colab_access_env', 4200),
        ('Reader', 'saved_reader.py', 'g5_original118_adapter_ablation_independent_20261109',
         'g5_original118_adapter_ablation_reader_coordination_20261109', 'vcsa_module_env', 600)]:
        put(P / (role + '_Owner_Protocol.json'), {'single_owner': {
            'source': (W / source_name).relative_to(R).as_posix(), 'sha256': sha(W / source_name),
            'output': 'outputs/' + output, 'coordination': 'outputs/' + coordination,
            'python': 'work/' + python + '/Scripts/python.exe', 'bound_seconds': bound},
            'require_ended_claims': []})
    own_sources = [W / x for x in ('host.py', 'remote_owner.py', 'guardian.py', 'saved_reader.py', 'contract.py', 'coordinator.py', 'build_execution.py')]
    for path in own_sources:
        ast.parse(path.read_bytes())
    additional = [R / 'work' / x for x in ('google_account_profile.py', 'public_size_local_preservation_v2.py',
                    'coordinate_single_source_bound_owner_20261020.py', 'coordinate_native_inverter_linear_reference_20261020.py')]
    hashes = {x.relative_to(R).as_posix(): sha(x) for x in own_sources + additional}
    hashes.update({f.relative_to(R).as_posix(): sha(f) for f in P.iterdir() if f.is_file() and f.suffix == '.json'})
    put(P / 'Prepared_Launch_Bindings.json', {'passed': False,
        'status': 'PREPARED_ONLY_REQUIRES_ROOT_INDEPENDENT_SOURCE_REVIEW_AND_FRESH_OWNERSHIP',
        'expected_independent_source_review_status': 'PASS_ORIGINAL118_DISABLED_ENGINEERING_SOURCE',
        'source_hashes': hashes, 'protocol_ref': ref(P / 'Frozen_Engineering_Protocol.json'),
        'all_private_files_verified_during_new_allowlisted_packaging': True,
        'old_archives_or_scientific_audits_rerun': False,
        'actual_software_owner_model_GPU_PF_network_calls': 0,
        'workflow_seconds': time.perf_counter() - began})
    print(json.dumps({'status': 'PREPARED_AWAITING_INDEPENDENT_GATE_NO_ALLOCATION',
                      'payload': ref(archive), 'source_count': len(hashes),
                      'actual_prior_hosts_bound': len(hosts), 'new_science': 0}))


if __name__ == '__main__':
    main()
