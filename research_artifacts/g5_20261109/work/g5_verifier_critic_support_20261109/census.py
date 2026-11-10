"""Once-only saved-JSON support census. No model/native/controller imports or calls."""
from pathlib import Path
import collections
import hashlib
import json
import math
import os
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/g5_verifier_critic_support_20261109'
LEDGER = 'outputs/original118_component_ledger_20261030/QA_LOCAL_ONLY/Verifier_Ledger.json'
FAMILIES = (
    'fed_combined_load_1p5_line_35_MG1',
    'fed_combined_load_1p5_line_36_MG1',
    'fed_combined_load_1p5_line_84_MG2',
    'fed_combined_load_1p5_line_127_MG3',
)
PROTOCOL = {
    'kind': 'PROSPECTIVE_SAVED_METADATA_SUPPORT_CENSUS_NOT_TRAINING',
    'population': 'All direct_HGVF_records in the existing four-root component ledger, in original ledger order. No outcome filtering.',
    'fixed_worlds': list(FAMILIES),
    'causal_input_fields': ['zone_state', 'global_uv', 'candidate_buses', 'action'],
    'target': 'Original native verifier accepted boolean for a non-null proposal with an explicitly converged returned candidate result. Rejection is not necessarily unsafe: all original reason strings retained.',
    'no_action_rule': 'Null and pretest records remain in population but are not negative physical labels or avoided-PF opportunities.',
    'unresolved_rule': 'Nonconvergence, missing before/after/converged/accepted, or source mismatch cannot fabricate a binary physical label.',
    'leakage_rule': 'No verifier/before/after/score/response/commit outcome or future history enters the feature packet. Source zone/global/candidate/action fields are copied only.',
    'context_limit': 'This is a NEW named action-conditioned critic packet, not the exact historical generation prompt: feedback memory and token IDs are not recovered here.',
    'split_rule': 'No random row split. Four outage worlds share the same registered base and all are inspected development. No unused confirmation or disconnected split is asserted.',
    'work_bound_seconds': 60,
    'read_bound_bytes': 16777216,
    'cost_scope': 'One metadata census, source JSON reads, hashes and serialization only. Prior model/PF/preparation/training/failure costs retained by reference, not zeroed.',
    'not_authorized': ['training', 'GPU allocation', 'inference', 'PF', 'native decode', 'controller calls', 'old audit rerun', 'policy or guard modification'],
}


def canonical(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(b):
    return hashlib.sha256(b).hexdigest()


def main():
    start = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'Protocol.json').write_text(json.dumps(PROTOCOL, indent=2), encoding='utf-8')
    (OUT / 'owner.claim').write_text(json.dumps({'pid': os.getpid(), 'source_sha256': digest(Path(__file__).read_bytes()), 'scope': 'saved JSON only'}), encoding='utf-8')
    read_bytes = 0
    refs = []

    def read(path):
        nonlocal read_bytes
        assert time.perf_counter() - start <= 60
        b = (ROOT / path).read_bytes()
        read_bytes += len(b)
        assert read_bytes <= 16777216
        ref = {'path': path, 'bytes': len(b), 'sha256': digest(b)}
        refs.append(ref)
        return json.loads(b), ref

    ledger, ledger_ref = read(LEDGER)
    population = ledger['direct_HGVF_records']
    assert len(population) == 308
    cache = {}
    for row in population:
        r = row['source_ref']
        if r['path'] not in cache:
            d, actual = read(r['path'])
            assert actual == {k: r[k] for k in ('path', 'bytes', 'sha256')}
            cache[r['path']] = d
    assert len(cache) == 4
    assert set(r['case_id'] for r in population) == set(FAMILIES)
    rows = []
    counts = collections.Counter()
    by_world = {k: collections.Counter() for k in FAMILIES}
    by_reason = collections.Counter()
    feature_labels = collections.defaultdict(set)
    for ordinal, r in enumerate(population):
        pointer = r['source_ref']['json_pointer'].split('/')
        assert len(pointer) == 4 and pointer[1] == 'logs' and pointer[3] == 'verif'
        log = cache[r['source_ref']['path']]['logs'][int(pointer[2])]
        assert log['source'] == 'llm_zone_agent_direct'
        assert log['zone'] == r['zone'] and log['iteration'] == r['iteration']
        v = log['verif']
        assert v['reason'] == r['reason'] and v.get('accepted', False) == r['accepted']
        inputs = {k: log[k] for k in ('zone_state', 'global_uv', 'action')}
        inputs['candidate_buses'] = log['llm_info']['candidate_buses']
        assert isinstance(inputs['zone_state'], dict) and isinstance(inputs['global_uv'], dict)
        assert isinstance(inputs['candidate_buses'], list)
        key = digest(canonical(inputs))
        label = None
        if log['action'] is None or r['status'] == 'pretest_rejected':
            status = 'PRETEST_OR_NULL_NOT_PHYSICAL_NEGATIVE'
        elif v.get('converged') is True and isinstance(v.get('accepted'), bool) and isinstance(v.get('before'), dict) and isinstance(v.get('after'), dict):
            values = [x for m in (v['before'], v['after']) for x in m.values() if isinstance(x, (float, int))]
            assert all(math.isfinite(x) for x in values)
            label = v['accepted']
            status = 'OBSERVED_NATIVE_ACCEPTED' if label else 'OBSERVED_NATIVE_REJECTED'
            feature_labels[key].add(label)
        else:
            status = 'UNKNOWN_PHYSICAL_TARGET'
        counts[status] += 1
        by_world[r['case_id']][status] += 1
        by_reason[v['reason']] += 1
        rows.append({
            'original_ledger_ordinal': ordinal, 'world': r['case_id'],
            'iteration': r['iteration'], 'zone': r['zone'],
            'causal_inputs': inputs, 'causal_inputs_sha256': key,
            'target_status': status, 'native_acceptance_target': label,
            'original_reason': v['reason'], 'original_committed': r['committed'],
            'source_ref': r['source_ref'],
            'exact_native_state_identity': 'NOT_JOINED_BY_THIS_CENSUS',
            'target_cost': 'ALREADY_PAID_AND_INDEPENDENTLY_REVIEWED_SOURCE_RESULT; no new physical measurement',
        })
    assert len(rows) == len(population)
    support_bytes = canonical({'rows': rows})
    (OUT / 'Causal_Support_Rows.json').write_bytes(support_bytes)
    result = {
        'status': 'COMPLETE_SAVED_CAUSAL_FIELD_SUPPORT_CENSUS_TRAINING_NOT_READY',
        'population_rows': len(rows), 'counts': dict(counts),
        'world_counts': {k: dict(v) for k, v in by_world.items()},
        'reason_counts': dict(by_reason),
        'unique_labeled_feature_packets': len(feature_labels),
        'feature_packets_with_conflicting_observed_labels': sum(len(v) > 1 for v in feature_labels.values()),
        'worlds': 4, 'all_inspected_development': True,
        'disconnected_training_confirmation_split_certified': False,
        'exact_prompt_token_and_memory_join': 'NOT_DONE; this is a restricted new critic interface',
        'same_state_alternative_preferences': 'NOT_CERTIFIED; scalar before metrics and iteration are not native state equality',
        'accepted_is_optimal': False,
        'unsafe_means_any_rejection': False,
        'full_hidden_feedback_reconstruction_claim': False,
        'new_model_PF_optimizer_training_native_calls': 0,
        'new_scientific_labels': 0,
        'old_audit_reruns': 0,
        'read_bytes': read_bytes, 'workflow_seconds': time.perf_counter() - start,
        'original_ledger_ref': ledger_ref, 'source_refs': refs,
        'support_ref': {'path': str((OUT / 'Causal_Support_Rows.json').relative_to(ROOT)).replace('\\', '/'), 'bytes': len(support_bytes), 'sha256': digest(support_bytes)},
        'independent_census_review': 'PENDING; prior physical audits are inherited, not rerun',
        'training_blockers': [
            'Only four related inspected development worlds; no disconnected unused confirmation.',
            'Exact frozen tokenizer/loader and whole-context label mask for the NEW critic interface are not implemented or tested.',
            'Same-input numerical and architecture/reference controls and prospective improvement/budget gates are not frozen.',
            'No validated query policy, full-menu preservation, false-veto prevention or fresh protected complete trajectory comparison.',
            'Existing component timings do not prove new critic inference plus training cost is less than saved PF cost.',
        ],
    }
    (OUT / 'Support_Census_Result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'population_rows', 'counts', 'unique_labeled_feature_packets', 'feature_packets_with_conflicting_observed_labels', 'read_bytes', 'workflow_seconds')}))


if __name__ == '__main__':
    main()
