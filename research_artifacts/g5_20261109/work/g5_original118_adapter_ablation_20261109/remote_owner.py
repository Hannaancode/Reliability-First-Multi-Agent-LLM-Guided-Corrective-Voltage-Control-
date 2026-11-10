"""Prospective original118 adapter-off first-input engineering, NEVER import locally.

Runs only within a separately admitted isolated remote package. Four immutable
causal requests plus one explicitly paid cold first-context replica; zero PF.
No controller trajectory, parser repair, training, allocation or host API here.
"""
import os
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
import functools
import gc
import hashlib
import json
import random
import time
import traceback
from pathlib import Path

from public_size_u61_preservation import atomic_json, journal, Publisher, file_hash
from g5_original118_ablation_contract import MODE, request_key, validate_inputs

R = Path(__file__).resolve().parents[1]
O = R / 'outputs/public_size_science'
O.mkdir(exist_ok=False)
started = time.monotonic()
p = json.loads((R / 'prep/protocol.json').read_text())
items = json.loads((R / 'prep/All4_Original_Inputs.json').read_text())
environment = json.loads((R / 'outputs/public_size_environment.json').read_text())
validate_inputs(items)
assert p['adapter_mode'] == MODE and p['planned_generations'] == {'primary': 4, 'cold_first_only': 1}
assert p['science_process_seconds'] == 900
atomic_json(O / 'owner.claim', {'actual_pid': os.getpid(), 'parent_pid': os.getppid(),
    'source_sha256': file_hash(__file__), 'protocol_sha256': file_hash(R / 'prep/protocol.json'),
    'adapter_mode': MODE, 'started_at_unix': time.time()})
cost = {'model_load_attempts': 0, 'model_load_returns': 0, 'generation_attempts': 0,
        'generation_returns': 0, 'pretrained_forward_attempts': 0,
        'pretrained_forward_returns': 0, 'generated_tokens': 0,
        'PF_optimizer_backward_training_calls': 0}
previous = '0' * 64


def event(kind, *, closure=False, **data):
    global previous
    bound = p['science_process_seconds'] + (p['science_process_closure_allowance_seconds'] if closure else 0)
    assert time.monotonic() - started < bound
    row = {'kind': kind, 'elapsed_seconds': time.monotonic() - started,
           'previous': previous, **data}
    h = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    journal(O / 'events.jsonl', {'event': row, 'sha256': h})
    previous = h


def progress(stage):
    atomic_json(O / 'progress.json', {'stage': stage, 'costs': cost, 'updated_unix': time.time()})


publisher = Publisher(O, R / 'outputs/public_size_transfer', wait_seconds=120)
try:
    import numpy as np
    import torch
    from transformers import AutoTokenizer
    from candidate_process_pretrained_loader_native13_v2_20261020 import (
        load_isolated_body, preservation_inventory, verify_copy_state, source_adapter_state)
    from original_reflection_serving_pure_20261022 import definitions
    from original_reflection_tokenizer_tensor_view_v2_20261022 import TensorTemplateView
    assert torch.cuda.is_available() and torch.cuda.get_device_name(0) == 'Tesla T4'
    adapter = R / 'work/e/pack/models/zone_agent_shared_lora_qwen05b_ultra_v1'
    for name, h in p['private_adapter_tokenizer_unchanged'].items():
        assert file_hash(adapter / name) == h
    for name, h in p['original_serving_sources'].items():
        assert file_hash(R / name) == h
    for name, h in p['remote_source_hashes'].items():
        assert file_hash(R / name) == h
    assert environment['base_weight_sha256'] == p['base_for_new_experiment']['public_weight_sha256']
    for name, value in p['historical_actual_environment'].items():
        assert environment[name] == value
    tokenizer = AutoTokenizer.from_pretrained(str(adapter), local_files_only=True, trust_remote_code=False)
    for row in items:
        encoded = tokenizer.apply_chat_template(row['messages'], tokenize=True, add_generation_prompt=True)
        ids = encoded['input_ids'] if hasattr(encoded, 'keys') else encoded
        assert ids == row['input_token_ids'] and len(ids) + 384 <= 4096
    original_response = definitions('base', {'torch': torch})['generate_response']
    atomic_json(O / 'Input_Source_Gate.json', {'all4_original_tokens_exact': True,
        'longest_prefix': max(len(x['input_token_ids']) for x in items),
        'new_generation_before_gate': 0, 'adapter_mode': MODE})
    event('input_source_gate_pass')
    publisher.publish('original118_input_source_gate')

    def rng_state():
        nr = np.random.get_state()
        return {'python': random.getstate(),
                'numpy': [nr[0], nr[1].tolist(), nr[2], nr[3], nr[4]],
                'torch_cpu': torch.get_rng_state().tolist(),
                'torch_cuda': [x.tolist() for x in torch.cuda.get_rng_state_all()]}

    def run_model(label, selected):
        random.seed(p['seed']); np.random.seed(p['seed'])
        torch.manual_seed(p['seed']); torch.cuda.manual_seed_all(p['seed'])
        torch.cuda.reset_peak_memory_stats()
        cost['model_load_attempts'] += 1
        event('model_load_attempt', replica=label)
        tick = time.perf_counter()
        model, proof = load_isolated_body(Path(environment['base_snapshot']), adapter, train_body=False)
        assert not any(x.requires_grad for x in model.parameters())
        cost['model_load_returns'] += 1
        event('model_load_return', closure=True, replica=label, seconds=time.perf_counter() - tick)
        atomic_json(O / f'{label}_Loader_Proof.json', proof)
        before = preservation_inventory(model)
        atomic_json(O / f'{label}_Immutable_Before.json', before)
        assert file_hash(O / f'{label}_Immutable_Before.json') == p['historical_immutable_inventory_sha256']
        expected = source_adapter_state(adapter)[1]
        assert all(s.enabled and not s.merged_adapters for s in model.get_layer_status())
        core = model.get_base_model()
        original_forward, original_generate = core.forward, model.generate

        @functools.wraps(original_forward)
        def forward(*args, **kwargs):
            flags = model.get_layer_status()
            assert len(flags) == 168 and all(not s.enabled and not s.merged_adapters for s in flags)
            cost['pretrained_forward_attempts'] += 1
            event('pretrained_forward_attempt', replica=label, number=cost['pretrained_forward_attempts'],
                  disabled_layer_count=168, enabled_layer_count=0, merged_layer_count=0)
            t = time.perf_counter()
            returned = original_forward(*args, **kwargs)
            cost['pretrained_forward_returns'] += 1
            event('pretrained_forward_return', closure=True, replica=label, seconds=time.perf_counter() - t)
            assert torch.isfinite(returned.logits).all()
            return returned

        core.forward = forward
        answers = []
        for row in selected:
            assert time.monotonic() - started < p['science_process_seconds'] - 30
            ids = row['input_token_ids']
            receipt = {'ordinal': row['ordinal'], 'case_id': row['case_id'],
                       'replica': label, 'adapter_mode': MODE,
                       'request_key': request_key(row, p['immutable_inference_contract']),
                       'input_token_ids': ids, 'RNG_before': rng_state()}

            @functools.wraps(original_generate)
            def generated(*args, **kwargs):
                assert not args and kwargs['max_new_tokens'] == 384
                assert not kwargs['do_sample'] and kwargs['use_cache']
                assert kwargs['input_ids'].tolist() == [ids] and bool(kwargs['attention_mask'].all())
                cost['generation_attempts'] += 1
                event('generation_attempt', ordinal=row['ordinal'], replica=label, request_key=receipt['request_key'])
                begin = time.perf_counter(); old_forwards = cost['pretrained_forward_returns']
                with model.disable_adapter(), torch.inference_mode():
                    assert all(not s.enabled and not s.merged_adapters for s in model.get_layer_status())
                    seq = original_generate(*args, **kwargs)
                cost['generation_returns'] += 1
                # Marker survives a subsequent CPU transfer/serialization failure. It
                # does not assert that unrecovered tokens are a verified output.
                event('generation_tensor_return_observed', closure=True, ordinal=row['ordinal'],
                      replica=label, request_key=receipt['request_key'])
                full_sequence = seq.detach().cpu().tolist()
                new = (full_sequence[0][len(ids):] if isinstance(full_sequence, list)
                       and len(full_sequence) == 1 and isinstance(full_sequence[0], list) else None)
                if new is not None:
                    cost['generated_tokens'] += len(new)
                raw_return = {'ordinal': row['ordinal'], 'case_id': row['case_id'],
                    'replica': label, 'request_key': receipt['request_key'], 'adapter_mode': MODE,
                    'full_returned_token_sequences': full_sequence, 'input_token_ids': ids,
                    'output_token_ids': new, 'costs_at_return': dict(cost),
                    'postreturn_assertions_and_text_decode_completed': False,
                    'generation_seconds_before_postchecks': time.perf_counter() - begin}
                atomic_json(O / f'{label}_Original_{row["ordinal"]:02d}_Returned_Tokens.json', raw_return)
                event('generation_tokens_preserved', closure=True, ordinal=row['ordinal'], replica=label,
                      token_file_sha256=file_hash(O / f'{label}_Original_{row["ordinal"]:02d}_Returned_Tokens.json'))
                torch.cuda.synchronize()
                assert all(s.enabled and not s.merged_adapters for s in model.get_layer_status())
                assert len(full_sequence) == 1 and full_sequence[0][:len(ids)] == ids
                assert isinstance(new, list)
                assert 0 < len(new) <= 384 and cost['pretrained_forward_returns'] - old_forwards == len(new)
                receipt.update(output_token_ids=new, generation_seconds=time.perf_counter() - begin,
                    actual_forward_returns=len(new), adapter_disabled_during_every_forward=True,
                    peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    peak_reserved_bytes=torch.cuda.max_memory_reserved())
                assert receipt['peak_allocated_bytes'] <= 12 * 1024**3
                event('generation_return', closure=True, ordinal=row['ordinal'], replica=label,
                      output_tokens=len(new), seconds=receipt['generation_seconds'])
                return seq

            model.generate = generated
            try:
                receipt['raw_text'] = original_response(model, TensorTemplateView(tokenizer), row['messages'])
                atomic_json(O / f'{label}_Original_{row["ordinal"]:02d}_Decoded_Text.json',
                            {'raw_text': receipt['raw_text'], 'request_key': receipt['request_key'],
                             'adapter_mode': MODE, 'case_id': row['case_id'], 'replica': label})
            except BaseException as failure:
                receipt.update(generation_or_decode_failed=True, failure_type=type(failure).__name__,
                               failure=str(failure), actual_costs_at_failure=dict(cost))
                atomic_json(O / f'{label}_Original_{row["ordinal"]:02d}_Failed_Receipt.json', receipt)
                raise
            finally:
                model.generate = original_generate
            receipt['RNG_after'] = rng_state()
            atomic_json(O / f'{label}_Original_{row["ordinal"]:02d}.json', receipt)
            answers.append(receipt)
            progress('preserving_actual_disabled_response')
            publisher.publish(f'{label}_original_{row["ordinal"]:02d}')
        after = preservation_inventory(model)
        assert before == after
        atomic_json(O / f'{label}_Immutable_After.json', after)
        atomic_json(O / f'{label}_Private_Copy_After.json', verify_copy_state(model, expected))
        core.forward = original_forward; model.generate = original_generate
        del model, core, original_forward, original_generate, expected
        gc.collect(); torch.cuda.empty_cache()
        return answers

    primary = run_model('primary', items)
    cold = run_model('cold', items[:1])
    assert primary[0]['input_token_ids'] == cold[0]['input_token_ids']
    assert primary[0]['output_token_ids'] == cold[0]['output_token_ids']
    assert primary[0]['raw_text'] == cold[0]['raw_text']
    assert cost['generation_attempts'] == cost['generation_returns'] == 5
    result = {'status': 'COMPLETE_ALL4_ORIGINAL118_DISABLED_FIRST_INPUTS_AND_ONE_COLD',
        'costs': cost, 'cold_first_context_exact': True, 'adapter_mode': MODE,
        'raw_invalid_or_null_outputs_retained': True, 'no_response_quality_gate': True,
        'original_parser_or_controller_executed': False,
        'full_trajectory_or_LLM_advantage_claim': False,
        'planned_primary_responses_reserved_for_future_exact_mode_reuse': 4,
        'workflow_seconds': time.monotonic() - started,
        'journal_last_before_result': previous}
    atomic_json(O / 'Results.json', result)
    event('closed_results', closure=True, result_sha256=file_hash(O / 'Results.json'))
    progress('complete_preserving'); publisher.publish('closed_original118_disabled_engineering')
except BaseException as exc:
    atomic_json(O / 'Failure.json', {'failure_type': type(exc).__name__, 'failure': str(exc),
        'traceback': traceback.format_exc(), 'actual_costs': cost,
        'workflow_seconds': time.monotonic() - started})
    progress('failed_partial_preserved')
    raise
