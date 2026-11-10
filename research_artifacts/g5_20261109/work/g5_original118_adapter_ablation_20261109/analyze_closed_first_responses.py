"""Once-only descriptive parsing of all four closed first responses; no inference."""
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[2]
O = R / 'outputs/g5_original118_first_response_description_20261109'
P = R / 'outputs/g5_original118_adapter_ablation_20261109/execution_preparation'
E = R / 'outputs/g5_original118_adapter_ablation_execution_20261109'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text('utf-8'))


def save(name, value):
    with (O / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)


def main():
    start = time.perf_counter()
    assert not O.exists()
    audit = read(R / 'outputs/g5_original118_adapter_ablation_independent_20261109/Independent_Audit.json')
    assert audit['complete_engineering'] and audit['status'] == 'PASS_COMPLETE_ORIGINAL118_DISABLED_ENGINEERING_ONLY'
    status = read(E / 'status.json')
    assert status['runtime_released'] and status['all_actual_closed_artifacts_preserved']
    completion = read(R / 'outputs/g5_original118_adapter_ablation_handoff_20261109/Completion.json')
    assert all(v['exit_code'] == 0 for v in completion['roles'].values())
    protocol = read(P / 'Frozen_Engineering_Protocol.json')
    for name, h in protocol['original_serving_sources'].items():
        assert sha(R / name) == h
    source = R / 'work/original_reflection_serving_pure_20261022.py'
    bridge = R / 'work/g5_original118_numeric_proposal_preparation_20261109/direct_slot_contract.py'
    O.mkdir()
    save('Protocol.json', {'scope': 'ALL4 fixed first responses, enabled inherited and disabled newly closed; cold replica excluded from denominator',
        'parser': 'Unchanged original extract_json -> normalize_action -> validate_action_against_candidates; no repair or reprompt',
        'outcomes': ['raw_text', 'parsed', 'normalized_action', 'parse_valid', 'parse_error', 'valid_action', 'valid_reason'],
        'no_performance_gate_or_physical_claim': True, 'source_hashes': {str(source.relative_to(R)): sha(source), str(bridge.relative_to(R)): sha(bridge)},
        'audit_sha256': sha(R / 'outputs/g5_original118_adapter_ablation_independent_20261109/Independent_Audit.json')})
    sys.path.insert(0, str(R / 'work'))
    from original_reflection_serving_pure_20261022 import definitions
    spec = importlib.util.spec_from_file_location('g5_first_response_request_contract', bridge)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = definitions('base'); rescue = definitions('rescue'); runner = definitions('runner')
    results = []
    for item in read(P / 'All4_Original_Inputs.json'):
        candidates = module.request_contract(item['messages'])['candidate_buses']
        enabled_ref = item['enabled_input_source_ref']; enabled_path = R / enabled_ref['path']
        assert sha(enabled_path) == enabled_ref['sha256'] and enabled_path.stat().st_size == enabled_ref['bytes']
        paths = {'enabled_saved': enabled_path, 'disabled_new': E / f'staged/study/primary_Original_{item["ordinal"]:02d}.json'}
        row = {'ordinal': item['ordinal'], 'case_id': item['case_id'], 'candidate_buses': candidates}
        for mode, path in paths.items():
            response = read(path)
            assert response['input_token_ids'] == item['input_token_ids']
            raw = response['raw_text']; parsed, valid, error = base['extract_json'](raw)
            action = rescue['normalize_action'](parsed)
            accepted, reason = runner['validate_action_against_candidates'](action, candidates)
            row[mode] = {'response_ref': {'path': path.relative_to(R).as_posix(), 'sha256': sha(path)},
                'raw_text': raw, 'parsed': parsed, 'normalized_action': action, 'parse_valid': valid,
                'parse_error': error, 'valid_action': accepted, 'valid_reason': reason,
                'conditional_reprompt_needed': not accepted,
                'physical_acceptance_and_following_trajectory': 'NOT_ASSESSED_BY_THIS_ANALYSIS'}
        results.append(row)
    assert [x['ordinal'] for x in results] == [0, 1, 2, 3]
    summary = {'status': 'COMPLETE_DESCRIPTIVE_ORIGINAL_FIRST_RESPONSE_PARSE_ONLY', 'case_count': 4,
        'source_valid_first_responses': {mode: sum(x[mode]['valid_action'] for x in results) for mode in paths},
        'same_normalized_action_count': sum(x['enabled_saved']['normalized_action'] == x['disabled_new']['normalized_action'] for x in results),
        'new_model_PF_training_or_reprompt_calls': 0, 'LLM_or_adapter_physical_advantage': 'UNPROVEN',
        'all_inspected_development': True, 'whole_seconds': time.perf_counter() - start, 'rows': results}
    save('All4_First_Response_Description.json', summary)
    print(json.dumps({k: summary[k] for k in ('status', 'source_valid_first_responses', 'same_normalized_action_count')}))


if __name__ == '__main__':
    main()
