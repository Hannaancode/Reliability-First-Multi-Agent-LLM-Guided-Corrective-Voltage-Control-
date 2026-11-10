"""Prospective one host then one first saved-only reader; no retries."""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[2]
P = R / 'outputs/g5_original118_adapter_ablation_20261109/execution_preparation'
O = R / 'outputs/g5_original118_adapter_ablation_handoff_20261109'
E = R / 'outputs/g5_original118_adapter_ablation_execution_20261109'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, value):
    with Path(p).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2); f.flush(); os.fsync(f.fileno())


def main():
    assert not O.exists() and not E.exists()
    gate = json.loads((P / 'Launch_Readiness_Audit.json').read_text())
    assert gate['passed'] and gate['independent_source_review_status'] == 'PASS_ORIGINAL118_DISABLED_ENGINEERING_SOURCE'
    for name, h in gate['source_hashes'].items():
        assert sha(R / name) == h
    O.mkdir(exist_ok=False)
    put(O / 'owner.claim', {'actual_pid': os.getpid(), 'parent_pid': os.getppid(),
        'source_sha256': sha(__file__), 'at_utc': datetime.now(timezone.utc).isoformat()})
    roles = {}
    for role in ('Primary', 'Reader'):
        if role == 'Reader':
            state_path = E / 'status.json'
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
            if not (state.get('all_actual_closed_artifacts_preserved') and state.get('runtime_released')
                    and state.get('scientific_process_ended') and (E / 'remote_closed_descriptor.json').exists()):
                roles[role] = {'status': 'UNENTERED_NO_CLOSED_RELEASED_SCIENTIFIC_ARTIFACTS'}
                break
        with (O / (role + '.log')).open('x', encoding='utf-8') as log:
            code = subprocess.call([str(R / 'work/vcsa_module_env/Scripts/python.exe'), '-X', 'utf8',
                str(R / 'work/coordinate_single_source_bound_owner_20261020.py'), '--protocol',
                str((P / ('Reader_Owner_Protocol_v2.json' if role == 'Reader' else 'Primary_Owner_Protocol.json')).relative_to(R))], cwd=R,
                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        roles[role] = {'exit_code': code, 'at_utc': datetime.now(timezone.utc).isoformat()}
        put(O / (role + '_End.json'), roles[role])
        if role == 'Primary':
            end = R / 'outputs/g5_original118_adapter_ablation_coordination_20261109/End_ACK.json'
            if not end.exists() or not json.loads(end.read_text()).get('actual_owned_chain_ended'):
                break
        elif code != 0:
            break
    put(O / 'Completion.json', {'status': 'TERMINAL_REVIEW_ACTUAL_ROLE_RESULTS', 'roles': roles,
        'no_science_retry': True, 'new_model_PF_optimizer_calls_by_coordinator': 0,
        'at_utc': datetime.now(timezone.utc).isoformat()})
    if roles.get('Reader', {}).get('exit_code') != 0:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
