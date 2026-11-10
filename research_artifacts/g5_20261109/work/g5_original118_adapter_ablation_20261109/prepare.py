"""Once-only saved JSON/source preparation. Never imports a model/native module."""
import ast
import copy
import hashlib
import importlib.util
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'outputs/g5_original118_adapter_ablation_20261109'
HISTORY = 'outputs/original118_finite_model_history_query_20261102/execution/Finite_Original118_Request_History_LOCAL_ONLY.json'
OLD13 = 'outputs/native13_adapter_disabled_diagnostic_preparation_20261021/All6_Messages_And_Token_IDs.json'
ORIGINAL = 'outputs/reflection118_chronological_preparation_20261022/Frozen_Engineering_Protocol.json'
ANALYSIS = 'outputs/original118_matched_analysis_preparation_20261023/Protocol.json'


def main():
    began = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    read_bytes = 0
    refs = []

    def read(path):
        nonlocal read_bytes
        raw = (ROOT / path).read_bytes(); read_bytes += len(raw)
        r = {'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        refs.append(r)
        return json.loads(raw), r

    def source_ref(path):
        raw = (ROOT / path).read_bytes()
        ast.parse(raw)
        return {'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    spec = importlib.util.spec_from_file_location('g5_ablation_contract_preparation', HERE / 'contract.py')
    c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
    history, hr = read(HISTORY)
    assert hr['sha256'] == '766a88530a911041068779f490addf14486fd1c22fc93c03475518d45130e97d'
    old13, r13 = read(OLD13)
    old, oldref = read(ORIGINAL)
    analysis, ar = read(ANALYSIS)
    assert tuple(analysis['case_order']) == c.CASE_ORDER
    assert len(history['rows']) == 465 and len(history['hosts']) == 6
    inputs = []
    for i, host in enumerate(('case0', 'old_case1', 'old_case2', 'old_case3')):
        found = [r for r in history['rows'] if r['host'] == host and
                 r['logical_number'] == 0 and r['replica'] == 'primary']
        assert len(found) == 1
        row = found[0]
        contract, contract_ref = read(row['source_contract_ref']['path'])
        assert contract_ref == row['source_contract_ref']
        for key in ('base_for_new_experiment', 'private_adapter_tokenizer_unchanged',
                    'original_serving_sources', 'seed'):
            assert contract[key] == old[key], (host, key)
        response, actual = read(row['receipt_ref']['path'])
        assert actual == row['receipt_ref']
        assert response['request']['active'] == {'case_id': c.CASE_ORDER[i], 'arm': 'reflection_v2'}
        assert response['number'] == response['request']['number'] == 0
        assert response['input_token_ids'] == row['input_token_ids']
        messages = response['request']['messages']
        assert c.sha(messages) == row['canonical_message_sha256']
        assert c.sha(row['input_token_ids']) == row['input_token_ids_sha256']
        inputs.append({'ordinal': i, 'case_id': c.CASE_ORDER[i], 'adapter_mode': c.MODE,
            'messages': messages, 'input_token_ids': row['input_token_ids'],
            'input_token_ids_sha256': row['input_token_ids_sha256'],
            'canonical_message_sha256': row['canonical_message_sha256'],
            'enabled_input_source_ref': row['receipt_ref']})
    c.validate_inputs(inputs)
    matches = [{'original_case': row['case_id'], 'old_native13_item': j}
               for row in inputs for j, other in enumerate(old13)
               if row['input_token_ids'] == other['token_ids']]
    assert not matches
    # Exact call identity includes adapter treatment even if all input tokens match.
    immutable = {'adapter_mode': c.MODE,
        'base_for_new_experiment': old['base_for_new_experiment'],
        'private_adapter_tokenizer_unchanged': old['private_adapter_tokenizer_unchanged'],
        'generation_source_sha256': old['original_serving_sources']['work/e/audit/phase2g_multiagent_llm_runner.py'],
        'do_sample': False, 'num_beams': 1, 'max_new_tokens': 384, 'use_cache': True,
        'seed': old['seed'], 'attention_backend': 'sdpa', 'base_quantization': 'original pinned NF4'}
    checks = []
    def reject(label, function):
        try:
            function()
        except (AssertionError, KeyError):
            checks.append({'label': label, 'pass': True}); return
        raise AssertionError(label)
    checks.append({'label': 'all4_exact_original_messages_and_token_ids', 'pass': c.validate_inputs(inputs)})
    mutated = copy.deepcopy(inputs); mutated[0]['adapter_mode'] = 'ORIGINAL118_PRIVATE_LORA_ENABLED'
    reject('enabled_treatment_refused_as_disabled_input', lambda: c.validate_inputs(mutated))
    mutated = copy.deepcopy(inputs); mutated[0], mutated[1] = mutated[1], mutated[0]
    reject('world_order_substitution_refused', lambda: c.validate_inputs(mutated))
    mutated = copy.deepcopy(inputs); mutated[0]['input_token_ids'] = mutated[0]['input_token_ids'][:-1]
    reject('truncated_original_tokens_refused', lambda: c.validate_inputs(mutated))
    mutated = copy.deepcopy(inputs); mutated[0]['raw_text'] = 'old enabled output must not enter input'
    reject('enabled_response_output_field_refused', lambda: c.validate_inputs(mutated))
    enabled_contract = copy.deepcopy(immutable); enabled_contract['adapter_mode'] = 'ENABLED'
    reject('enabled_model_contract_key_refused', lambda: c.request_key(inputs[0], enabled_contract))
    receipt = {'adapter_mode': c.MODE, 'request_key': c.request_key(inputs[0], immutable),
               'input_token_ids': inputs[0]['input_token_ids'], 'case_id': inputs[0]['case_id'],
               'adapter_disabled_during_every_forward': True}
    checks.append({'label': 'correct_disabled_receipt_identity_accepted_software_only',
                   'pass': c.validate_returned_identity(receipt, inputs[0], immutable)})
    wrong = copy.deepcopy(receipt); wrong['adapter_mode'] = 'ENABLED'
    reject('enabled_return_never_reused_for_disabled', lambda: c.validate_returned_identity(wrong, inputs[0], immutable))
    checks.append({'label': 'all4_exact_token_inputs_disjoint_from_old_native13_disabled_six', 'pass': not matches})
    remote_mapping = {
        'work/g5_original118_ablation_contract.py': 'work/g5_original118_adapter_ablation_20261109/contract.py',
        'work/run_g5_original118_adapter_disabled_remote_20261109.py': 'work/g5_original118_adapter_ablation_20261109/remote_owner.py',
        **{x: x for x in [
            'work/candidate_process_pretrained_loader_native13_v2_20261020.py',
            'work/original_reflection_serving_pure_20261022.py',
            'work/original_reflection_tokenizer_tensor_view_v2_20261022.py',
            'work/public_size_u61_preservation.py']}}
    source_refs = [source_ref(x) for x in remote_mapping.values()]
    enabled_owner_sources = []
    for name in ('work/run_reflection118_model_service_remote_20261022.py',
                 'work/run_reflection118_remaining_model_remote_20261023.py'):
        content = (ROOT / name).read_text(encoding='utf-8')
        assert 'assert flags and not any(flags.values())' in content
        assert 'with model.disable_adapter()' not in content
        enabled_owner_sources.append(source_ref(name))
    protocol = {
        'status': 'PREPARED_ENGINEERING_SOURCE_AND_INPUT_ONLY_NO_ALLOCATION_ADMISSION',
        'question': 'Can the pinned original model with its private adapter disabled serve the exact original118 causal role without changing messages, parser or generation settings?',
        'adapter_mode': c.MODE, 'case_order': list(c.CASE_ORDER),
        'root_hashes': analysis['root_hashes'],
        'planned_generations': {'primary': 4, 'cold_first_only': 1},
        'planned_model_loads': 2, 'science_process_seconds': 900,
        'science_process_closure_allowance_seconds': 120,
        'setup_seconds': 1800, 'collector_seconds': 2100,
        'storage_bound_bytes': 1073741824,
        'seed': old['seed'], 'base_for_new_experiment': old['base_for_new_experiment'],
        'private_adapter_tokenizer_unchanged': old['private_adapter_tokenizer_unchanged'],
        'original_serving_sources': old['original_serving_sources'],
        'immutable_inference_contract': immutable,
        'remote_source_hashes': {dest: source_ref(src)['sha256'] for dest, src in remote_mapping.items()},
        'remote_file_mapping': remote_mapping,
        'fixed_profile': old['profiles'],
        'engineering_acceptance': [
            'Actual exact base/private tensor/tokenizer identity and 168 unmerged layer states disabled during EVERY actual forward; zero trainable parameters.',
            'All4 full causal token sequences equal existing receipts, no truncation, no message or source-generation changes.',
            'Actual raw token/text outcomes all retained even if malformed, null or no legal action; no success-based case or prompt choice.',
            'A genuinely fresh second model load repeats only first disabled context as the predeclared separately charged cold replica, exact tokens/text and immutable quantized/private tensor inventories.',
            'Every actual attempt/return/failure/cost plus checkpoint/RNG and owner/assignment/transport/preservation closure independently bound.'
        ],
        'technical_failure_rule': 'Preserve all artifacts and stop; no retry, other-account fallback, old budget extension or scientific call replacement.',
        'no_performance_gate': 'Invalid/null outputs do not fail engineering and do not authorize output repair; full controller decides their consequences later under original parser/fallback.',
        'old_science': 'All enabled trajectories/requests and the native13 disabled study stay closed and are not rerun.',
        'future_receipt_reuse': 'Keep four new primary disabled outputs under exact model-mode/input keys for later original controller invocation; never serve an enabled response in the disabled arm or repeat these primary calls.',
        'native_and_training_calls_admitted': 0,
        'ready_gpu': False,
        'remaining_before_allocation': [
            'Independent current source/input review and saved-only partial-aware reader implementation/source lock.',
            'One exact original-profile host/coordinator/remote-child ownership and assignment protocol, setup/dependency lock, bounded process/collector/release/preservation implementation.',
            'Scoped original118 disabled-arm prior-history review; finite known six enabled hosts and old native13 input exclusion are not a universal absence certificate.',
            'Packaging/privacy/source manifest bound to the actual original same account; no allocation merely because a profile is eligible.'
        ]}
    for name, value in [('All4_Original_Inputs.json', inputs), ('Engineering_Protocol.json', protocol),
                        ('Software_Boundary_Checks.json', {'status': 'PASS_SOFTWARE_ONLY', 'checks': checks}),
                        ('Input_History_And_Source_Findings.json', {
                            'status': 'FINITE_METADATA_AND_SOURCE_PREPARATION_COMPLETE',
                            'original_enabled_hosts': [x['id'] for x in history['hosts']],
                            'logical_requests': 459, 'separately_paid_cold_replicas': 6,
                            'all465_share_adapter_tokenizer_contract': len({r['adapter_tokenizer_contract_sha256'] for r in history['rows']}) == 1,
                            'all465_share_actual_model_inventory': len({r['immutable_model_inventory_sha256'] for r in history['rows']}) == 1,
                            'old_native13_disabled_exact_token_matches_to_four_original_inputs': matches,
                            'disabled_original118_arm_found_in_named_original_six_host_roster': False,
                            'universal_original_disabled_history_absence': False,
                            'earlier_unjoined_scope': history['uncovered_domains'],
                            'initial_prefix_lengths': [len(x['input_token_ids']) for x in inputs],
                            'new_model_tokenizer_native_PF_training_calls': 0,
                            'old_audit_reruns': 0, 'source_refs': source_refs, 'input_refs': refs,
                            'known_enabled_owner_sources': enabled_owner_sources,
                            'actual_read_bytes': read_bytes, 'workflow_seconds': time.perf_counter() - began})]:
        (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'status': protocol['status'], 'software_checks': len(checks),
                      'original_prefix_lengths': [len(x['input_token_ids']) for x in inputs],
                      'old_native13_exact_input_matches': len(matches), 'new_science': 0}))


if __name__ == '__main__':
    main()
