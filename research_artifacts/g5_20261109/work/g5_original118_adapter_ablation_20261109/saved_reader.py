"""First saved-only reader of the NEW original118 adapter-off engineering.

No model, tokenizer, native, training, controller or allocation invocation.
Partial raw returns are retained and cannot become a complete engineering PASS.
"""
import hashlib
import importlib.util
import json
import os
import time
from collections import Counter
from pathlib import Path

R = Path(__file__).resolve().parents[2]
P = R / 'outputs/g5_original118_adapter_ablation_20261109/execution_preparation'
E = R / 'outputs/g5_original118_adapter_ablation_execution_20261109'
O = R / 'outputs/g5_original118_adapter_ablation_independent_20261109'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.flush(); os.fsync(f.fileno())


def main():
    started = time.monotonic()
    O.mkdir(exist_ok=False)
    put(O / 'owner.claim', {'actual_pid': os.getpid(), 'parent_pid': os.getppid(),
                           'source_sha256': sha(__file__), 'scope': 'saved JSON only'})
    while not (O / 'Launcher_ACK.json').exists():
        assert time.monotonic() - started < 60
        time.sleep(.1)
    ack = read(O / 'Launcher_ACK.json')
    assert ack['actual_pid'] == os.getpid() and ack['actual_parent_pid'] == os.getppid()
    assert ack['fresh_exact_source_PID_parent_command']
    checks = []
    unknown = []
    def check(label, value):
        assert value, label
        checks.append(label)
    protocol = read(P / 'Frozen_Engineering_Protocol.json')
    ready = read(P / 'Launch_Readiness_Audit.json')
    check('exact current sources', all(sha(R / name) == h for name, h in ready['source_hashes'].items()))
    end = read(R / 'outputs/g5_original118_adapter_ablation_coordination_20261109/End_ACK.json')
    check('actual host chain ended', end['actual_owned_chain_ended'])
    # The reader accepts a closed partial remote result, not a still-live host.
    import sys
    sys.path.insert(0, str(R / 'work'))
    from coordinate_native_inverter_linear_reference_20261020 import process
    claim = read(E / 'owner.claim')
    host_spec = read(P / 'Primary_Owner_Protocol.json')['single_owner']
    host_source = str((R / host_spec['source']).resolve()).lower()
    check('exact ended host source', claim['source_sha256'] == host_spec['sha256'])
    for pid in (claim['actual_pid'], claim['parent_pid']):
        actor = process(pid)
        check('ended exact host or launcher ' + str(pid), actor is None or
              host_source not in (actor.get('CommandLine') or '').lower())
    state = read(E / 'status.json')
    check('actual selected runtime released', state['runtime_released'])
    check('all actual closed artifacts preserved', state['all_actual_closed_artifacts_preserved'])
    check('actual scientific child ended', state['scientific_process_ended'])
    descriptor = read(E / 'remote_closed_descriptor.json')
    check('descriptor scientific child ended', descriptor['scientific_process_ended'])
    study = E / 'staged/study'
    for name, record in descriptor['members'].items():
        part = Path(name)
        check('safe member ' + name, not part.is_absolute() and '..' not in part.parts and ':' not in name and '\\' not in name)
        path = study / part
        check('closed bytes ' + name, path.stat().st_size == record['bytes'] and sha(path) == record['sha256'])
    remote_claim = read(study / 'owner.claim')
    check('remote source identity', remote_claim['source_sha256'] == protocol['remote_source_hashes']['work/run_g5_original118_adapter_disabled_remote_20261109.py'])
    check('remote actual protocol', remote_claim['protocol_sha256'] == sha(P / 'Frozen_Engineering_Protocol.json'))
    check('remote treatment', remote_claim['adapter_mode'] == protocol['adapter_mode'])
    items = read(P / 'All4_Original_Inputs.json')
    contract_path = R / 'work/g5_original118_adapter_ablation_20261109/contract.py'
    check('contract source pin', sha(contract_path) == protocol['remote_source_hashes']['work/g5_original118_ablation_contract.py'])
    spec = importlib.util.spec_from_file_location('g5_ablation_reader_contract', contract_path)
    contract = importlib.util.module_from_spec(spec); spec.loader.exec_module(contract)
    contract.validate_inputs(items)
    prior = '0' * 64
    events = []
    for line in (study / 'events.jsonl').read_text(encoding='utf-8').splitlines():
        record = json.loads(line); event = record['event']
        check('journal chain ' + str(len(events)), event['previous'] == prior)
        h = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        check('journal hash ' + str(len(events)), h == record['sha256'])
        prior = h; events.append(event)
    counts = Counter(x['kind'] for x in events)
    for i, event in enumerate(events):
        if event['kind'] == 'pretrained_forward_attempt':
            check('every forward disabled ' + str(i), event['disabled_layer_count'] == 168 and
                  event['enabled_layer_count'] == event['merged_layer_count'] == 0)
            check('forward entered before scientific bound ' + str(i), event['elapsed_seconds'] < 900)
        if event['kind'] in ('generation_attempt', 'model_load_attempt'):
            check('science entry bound ' + str(i), event['elapsed_seconds'] < 900)
        check('fixed closure bound ' + str(i), event['elapsed_seconds'] < 1020)
    returned = []
    complete_receipts = {}
    token_sum = 0
    for replica, indices in [('primary', range(4)), ('cold', range(1))]:
        for i in indices:
            row = items[i]
            stem = f'{replica}_Original_{i:02d}'
            raw_path = study / (stem + '_Returned_Tokens.json')
            final_path = study / (stem + '.json')
            if not raw_path.exists():
                unknown.append({'replica': replica, 'ordinal': i, 'status': 'NO_CLOSED_RETURNED_TOKEN_ARTIFACT',
                                'actual_attempt_may_exist': any(x['kind'] == 'generation_attempt' and x.get('replica') == replica and x.get('ordinal') == i for x in events)})
                continue
            raw = read(raw_path)
            check('raw treatment ' + stem, raw['adapter_mode'] == contract.MODE)
            check('raw exact request ' + stem, raw['request_key'] == contract.request_key(row, protocol['immutable_inference_contract']))
            check('raw input tokens ' + stem, raw['input_token_ids'] == row['input_token_ids'])
            returned.append({'replica': replica, 'ordinal': i, 'raw_token_ref': {'path': str(raw_path.relative_to(R)).replace('\\', '/'), 'sha256': sha(raw_path)}})
            if not final_path.exists():
                unknown.append({'replica': replica, 'ordinal': i, 'status': 'RAW_RETURN_ONLY_POSTCHECK_OR_DECODE_UNKNOWN'})
                continue
            receipt = read(final_path)
            check('complete returned identity ' + stem, contract.validate_returned_identity(receipt, row, protocol['immutable_inference_contract']))
            sequence = raw['full_returned_token_sequences']
            new = receipt['output_token_ids']
            check('full raw token identity ' + stem, sequence == [row['input_token_ids'] + new] and raw['output_token_ids'] == new)
            check('exact generated count ' + stem, 0 < len(new) <= 384 and receipt['actual_forward_returns'] == len(new))
            text = read(study / (stem + '_Decoded_Text.json'))
            check('raw decoded text retained ' + stem, text['raw_text'] == receipt['raw_text'] and text['request_key'] == receipt['request_key'])
            check('full RNG recorded ' + stem, set(receipt['RNG_before']) == set(receipt['RNG_after']) == {'python', 'numpy', 'torch_cpu', 'torch_cuda'})
            check('actual memory bound ' + stem, receipt['peak_allocated_bytes'] <= 12 * 1024**3)
            token_sum += len(new)
            complete_receipts[(replica, i)] = receipt
    runtime_binding = read(P / 'Original_Enabled_Runtime_Binding.json')
    baseline_inventory = read(R / runtime_binding['canonical_immutable_inventory_ref']['path'])
    runtime_matched = True
    for replica in ('primary', 'cold'):
        names = [study / f'{replica}_Loader_Proof.json', study / f'{replica}_Immutable_Before.json',
                 study / f'{replica}_Immutable_After.json', study / f'{replica}_Private_Copy_After.json']
        if not all(x.exists() for x in names):
            runtime_matched = False
            unknown.append({'replica': replica, 'status': 'INCOMPLETE_LOADER_OR_IMMUTABILITY_CLOSURE'})
            continue
        loader, before, after, private = map(read, names)
        check('loader actual copied values ' + replica, loader['four_bit_base'] and loader['source_tensor_values_identical'] and loader['enabled_disabled_restored_unmerged'] and loader['trainable_body_parameters'] == 0)
        check('loaded values unchanged ' + replica, before == after)
        check('private source copy unchanged ' + replica, private['source_tensor_values_identical'] and private['exact_copied_parameters'] == 8798208)
        check('actual same base quantized inventory ' + replica, before == baseline_inventory)
    environment = read(E / 'staged/public_size_environment.json')
    for key, value in runtime_binding['common_actual_environment'].items():
        check('actual environment matched ' + key, environment[key] == value)
    complete = len(complete_receipts) == 5 and runtime_matched and not unknown
    if (study / 'Results.json').exists():
        costs = read(study / 'Results.json')['costs']
    elif (study / 'Failure.json').exists():
        costs = read(study / 'Failure.json')['actual_costs']
    else:
        costs = {key: counts[kind] for key, kind in [('model_load_attempts', 'model_load_attempt'),
            ('model_load_returns', 'model_load_return'), ('generation_attempts', 'generation_attempt'),
            ('generation_returns', 'generation_tensor_return_observed'),
            ('pretrained_forward_attempts', 'pretrained_forward_attempt'),
            ('pretrained_forward_returns', 'pretrained_forward_return')]}
        costs.update(generated_tokens=token_sum, PF_optimizer_backward_training_calls=0)
        unknown.append({'status': 'NO_FINAL_COUNTER_SNAPSHOT_JOURNAL_LOWER_BOUNDS_ONLY'})
        complete = False
    check('no native or training calls', costs['PF_optimizer_backward_training_calls'] == 0)
    for key, kind in [('generation_attempts', 'generation_attempt'),
                      ('generation_returns', 'generation_tensor_return_observed'),
                      ('pretrained_forward_attempts', 'pretrained_forward_attempt'),
                      ('pretrained_forward_returns', 'pretrained_forward_return')]:
        if costs[key] != counts[kind]:
            check('no return counters below durable evidence ' + key, costs[key] >= counts[kind])
            unknown.append({'status': 'COUNTER_JOURNAL_CLOSURE_DIFFERENCE', 'counter': key,
                            'counter_value': costs[key], 'journal_count': counts[kind]})
            complete = False
        else:
            checks.append('exact journal counter ' + key)
    if complete:
        result = read(study / 'Results.json')
        check('complete remote status', result['status'] == 'COMPLETE_ALL4_ORIGINAL118_DISABLED_FIRST_INPUTS_AND_ONE_COLD')
        check('remote exit0', descriptor['exit_code'] == 0)
        check('five actual returns', costs['generation_attempts'] == costs['generation_returns'] == 5)
        check('actual forward and token sums', costs['pretrained_forward_attempts'] == costs['pretrained_forward_returns'] == costs['generated_tokens'] == token_sum)
        check('two actual loads', costs['model_load_attempts'] == costs['model_load_returns'] == 2)
        a, b = complete_receipts[('primary', 0)], complete_receipts[('cold', 0)]
        check('fresh first-context exact token sequence', a['output_token_ids'] == b['output_token_ids'] and a['raw_text'] == b['raw_text'])
    audit = {'status': 'PASS_COMPLETE_ORIGINAL118_DISABLED_ENGINEERING_ONLY' if complete else 'PASS_PRESERVED_PARTIAL_ORIGINAL118_DISABLED_ENGINEERING_UNKNOWN',
        'checks': len(checks), 'check_labels': checks, 'complete_engineering': complete,
        'closed_raw_returns': returned, 'complete_receipt_count': len(complete_receipts),
        'unknowns': unknown, 'actual_costs': costs, 'actual_event_counts': dict(counts),
        'original_enabled_runtime_matching_scope': runtime_binding['scope'],
        'all_primary_raw_invalid_null_responses_retained': True, 'response_quality_success_gate': None,
        'no_original_enabled_calls_repeated': True, 'new_model_tokenizer_PF_training_native_calls_by_reader': 0,
        'full_trajectory_adapter_advantage_or_LLM_superiority': False,
        'workflow_seconds': time.monotonic() - started}
    put(O / 'Independent_Audit.json', audit)
    manifest = {x.name: {'bytes': x.stat().st_size, 'sha256': sha(x)} for x in O.iterdir() if x.is_file()}
    put(O / 'Closed_Manifest.json', {'members': manifest})
    print(json.dumps({'status': audit['status'], 'checks': len(checks), 'complete_receipts': len(complete_receipts)}))


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        if O.exists() and not (O / 'Failure.json').exists():
            put(O / 'Failure.json', {'type': type(error).__name__, 'failure': str(error),
                                   'new_model_native_PF_training_calls': 0})
        raise
