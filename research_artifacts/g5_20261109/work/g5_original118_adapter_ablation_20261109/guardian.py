"""One prospective remote child, fixed science+closure ceiling; no retries."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from public_size_u61_preservation import atomic_json, file_hash

ROOT = Path(__file__).resolve().parents[1]
P = json.loads((ROOT / 'prep/protocol.json').read_text())
started = time.monotonic()
source = ROOT / 'work/run_g5_original118_adapter_disabled_remote_20261109.py'
assert file_hash(source) == P['remote_source_hashes'][source.relative_to(ROOT).as_posix()]
O = ROOT / 'outputs'
assert not (O / 'public_size_scientific_pid.json').exists()
atomic_json(O / 'public_size_guardian_claim.json', {
    'actual_pid': os.getpid(), 'parent_pid': os.getppid(), 'source_sha256': file_hash(__file__),
    'protocol_sha256': file_hash(ROOT / 'prep/protocol.json'),
    'proc_start_identity': Path('/proc/self/stat').read_text().split()[21],
    'started_unix': time.time()})
timeout = storage_stop = False
with (O / 'public_size_science.log').open('x') as log:
    child = subprocess.Popen([sys.executable, str(source)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    atomic_json(O / 'public_size_scientific_pid.json', {
        'pid': child.pid, 'parent_pid': os.getpid(), 'source': source.relative_to(ROOT).as_posix(),
        'source_sha256': file_hash(source), 'started_at_unix': time.time(),
        'actual_cmdline': Path(f'/proc/{child.pid}/cmdline').read_bytes().replace(b'\0', b' ').decode(),
        'proc_start_identity': Path(f'/proc/{child.pid}/stat').read_text().split()[21]})
    total_bound = P['science_process_seconds'] + P['science_process_closure_allowance_seconds']
    while child.poll() is None:
        elapsed = time.monotonic() - started
        size = sum(x.stat().st_size for x in O.rglob('*') if x.is_file())
        timeout = elapsed >= total_bound
        storage_stop = size >= P['storage_bound_bytes']
        if timeout or storage_stop:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=15)
            break
        time.sleep(.5)
    code = child.wait()
study = O / 'public_size_science'
manifest = {}
if study.exists():
    manifest = {x.relative_to(study).as_posix(): {'bytes': x.stat().st_size, 'sha256': file_hash(x)}
                for x in study.rglob('*') if x.is_file() and x.name != 'progress.json' and not x.name.endswith('.tmp')}
    parts = O / 'public_size_closed_parts'; parts.mkdir(exist_ok=False)
    for number, (name, record) in enumerate(sorted(manifest.items())):
        record['parts'] = []
        with (study / name).open('rb') as f:
            for i, raw in enumerate(iter(lambda: f.read(2 * 1024**2), b'')):
                part = f'file_{number:05d}_part_{i:04d}.bin'
                (parts / part).write_bytes(raw)
                record['parts'].append({'name': part, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
atomic_json(O / 'public_size_closed_descriptor.json', {
    'members': manifest, 'science_pid': child.pid, 'exit_code': code,
    'hard_bound_enforced': timeout, 'storage_bound_enforced': storage_stop,
    'guardian_seconds': time.monotonic() - started, 'scientific_process_ended': True,
    'guardian_claim': json.loads((O / 'public_size_guardian_claim.json').read_text()),
    'child_identity': json.loads((O / 'public_size_scientific_pid.json').read_text())})
atomic_json(O / 'public_size_guardian_End.json', {'actual_pid': os.getpid(),
    'parent_pid': os.getppid(), 'source_sha256': file_hash(__file__),
    'all_actual_child_artifacts_closed': True, 'scientific_exit_code': code,
    'workflow_seconds': time.monotonic() - started})
atomic_json(O / 'public_size_exit.json', {'exit_code': code, 'scientific_process_ended': True,
                                         'hard_bound_enforced': timeout, 'storage_bound_enforced': storage_stop})
