"""Pure request identity for a NEW original118 adapter-disabled diagnostic."""
import hashlib
import json

MODE = 'ORIGINAL118_PRIVATE_LORA_DISABLED'
CASE_ORDER = (
    'fed_combined_load_1p5_line_35_MG1',
    'fed_combined_load_1p5_line_36_MG1',
    'fed_combined_load_1p5_line_84_MG2',
    'fed_combined_load_1p5_line_127_MG3',
)
FIELDS = {'ordinal', 'case_id', 'adapter_mode', 'messages', 'input_token_ids',
          'input_token_ids_sha256', 'canonical_message_sha256', 'enabled_input_source_ref'}


def canonical(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(v):
    return hashlib.sha256(canonical(v)).hexdigest()


def validate_inputs(items):
    assert isinstance(items, list) and len(items) == 4
    for i, row in enumerate(items):
        assert set(row) == FIELDS
        assert type(row['ordinal']) is int and row['ordinal'] == i
        assert row['case_id'] == CASE_ORDER[i] and row['adapter_mode'] == MODE
        assert isinstance(row['messages'], list) and row['messages']
        assert all(set(m) == {'role', 'content'} and isinstance(m['role'], str)
                   and isinstance(m['content'], str) for m in row['messages'])
        ids = row['input_token_ids']
        assert isinstance(ids, list) and ids and all(type(x) is int and x >= 0 for x in ids)
        assert len(ids) + 384 <= 4096
        assert sha(ids) == row['input_token_ids_sha256']
        assert sha(row['messages']) == row['canonical_message_sha256']
        assert set(row['enabled_input_source_ref']) == {'path', 'bytes', 'sha256'}
    return True


def request_key(row, immutable_contract):
    """Mode is mandatory: an enabled model receipt cannot satisfy this key."""
    assert row['adapter_mode'] == MODE
    assert immutable_contract['adapter_mode'] == MODE
    return sha({'model_and_generation_contract': immutable_contract,
                'case_id': row['case_id'], 'messages': row['messages'],
                'input_token_ids': row['input_token_ids']})


def validate_returned_identity(receipt, row, immutable_contract):
    assert receipt['adapter_mode'] == MODE
    assert receipt['request_key'] == request_key(row, immutable_contract)
    assert receipt['input_token_ids'] == row['input_token_ids']
    assert receipt['case_id'] == row['case_id']
    assert receipt['adapter_disabled_during_every_forward'] is True
    return True
