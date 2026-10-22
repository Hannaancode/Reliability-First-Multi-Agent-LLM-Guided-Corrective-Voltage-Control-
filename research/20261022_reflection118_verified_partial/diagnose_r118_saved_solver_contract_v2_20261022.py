"""Saved-input/source diagnosis only. Never runs a power flow or model."""
import copy, hashlib, inspect, json, pickle, sys, time, zlib
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'work'))
import candidate_process_runtime
sys.path.append(str(R / 'work/physics_env/Lib/site-packages'))
import numpy as np
import pandapower as pp
from pandapower.auxiliary import _init_runpp_options
from prior_physical_query_footprints_20261018 import decode
from reflection118_chronological_core_20261022 import frames_equal, sha, put

O = R / 'outputs/r118_saved_solver_contract_diagnosis_v2_20261022'
J = R / 'outputs/critical_research_reset_20261010/severe_joint_current_engineering_20261012/actual/scientific.jsonl'
IDENTITY = '002_fed_combined_load_1p5_line_35_MG1_original_committed_prefix_1'


def scalar(v):
    if isinstance(v, (str, int, float, bool)) or v is None: return v
    if isinstance(v, np.generic): return v.item()
    if isinstance(v, dict): return {str(k): scalar(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [scalar(x) for x in v]
    return {'type': type(v).__name__, 'repr': repr(v)}


def main():
    O.mkdir(exist_ok=False); began = time.monotonic()
    selected = []
    for raw in J.open('rb'):
        e = json.loads(raw); d = e.get('data', {})
        if d.get('id', d.get('identity')) == IDENTITY:
            selected.append({'event': e['event'], 'data': d,
                             'raw_line_sha256': hashlib.sha256(raw).hexdigest()})
    intent = next(x for x in selected if x['event'] == 'PF_intent')
    returned = next(x for x in selected if x['event'] == 'PF_return')
    before = decode(J.parent, intent['data']['before'])
    after = decode(J.parent, returned['data']['after'])
    blocked = R / 'outputs/r118chrono_20261022/local_controller/fed_combined_load_1p5_line_35_MG1/no_llm_fallback_first/pf_000006_before.zlib'
    current = pickle.loads(zlib.decompress(blocked.read_bytes()))
    frames_equal(current, before); frames_equal(before, after)
    old_kwargs = intent['data']['kwargs']
    new_kwargs = dict(algorithm='nr', init='auto', enforce_q_lims=True,
                      max_iteration=80, calculate_voltage_angles=True)
    native = pp.runpp
    def forbidden(*a, **kw): raise AssertionError('ZERO SCIENCE DIAGNOSIS: runpp prohibited')
    pp.runpp = forbidden
    for module in ['pandapower.powerflow', 'pandapower.pf.run_newton_raphson_pf']:
        __import__(module)
    import pandapower.powerflow as pf
    pf._powerflow = forbidden
    def options(kwargs):
        net = copy.deepcopy(before)
        bound = inspect.signature(native).bind(net, **kwargs); bound.apply_defaults()
        args = dict(bound.arguments); args.pop('net'); extra = args.pop('kwargs')
        # This is the exact metadata initializer called by runpp, no converter/solver.
        args.pop('run_control')
        _init_runpp_options(net, passed_parameters=kwargs, **args, **extra)
        return scalar(net._options)
    old = options(old_kwargs); new = options(new_kwargs)
    differences = {k: {'old': old.get(k), 'new': new.get(k)}
                   for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)}
    saved_options = scalar(after.get('_options', {}))
    option_mismatches = {k: {'saved': saved_options.get(k), 'current_old_resolution': v}
                         for k, v in old.items() if saved_options.get(k) != v}
    result = {
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'SAVED_SOLVER_CONTRACT_DIAGNOSIS_ONLY_NO_REUSE_AUTHORIZATION',
        'old_identity': IDENTITY, 'old_journal': J.relative_to(R).as_posix(),
        'intent_line_sha256': intent['raw_line_sha256'],
        'return_line_sha256': returned['raw_line_sha256'],
        'blocked_input_sha256': sha(blocked), 'exact_all_nonresult_frames_match': True,
        'old_recorded_kwargs': old_kwargs, 'required_unchanged_native_kwargs': new_kwargs,
        'old_saved_pandapower_version': str(after.get('version')),
        'current_pandapower_version': pp.__version__,
        'old_resolved_options': old, 'required_resolved_options': new,
        'resolved_option_differences': differences,
        'old_saved_options_mismatches_with_current_old_resolution': option_mismatches,
        'old_saved_converged': bool(after.converged),
        'old_saved_final_Newton_iterations': scalar(after._ppc.get('iterations')),
        'old_saved_success': scalar(after._ppc.get('success')),
        'old_saved_user_pf_options': scalar(before.get('user_pf_options', {})),
        'required_newton_qlimit_pass_history': 'UNKNOWN: final saved iteration count alone does not record every prior Q-limit Newton solve.',
        'source_pins': {str(Path(p).resolve().relative_to(R)): sha(p) for p in
                        [__file__, pp.__file__, inspect.getfile(native), inspect.getfile(_init_runpp_options),
                         R/'work/physics_env/Lib/site-packages/pandapower/pf/run_newton_raphson_pf.py',
                         R/'work/physics_env/Lib/site-packages/pandapower/pypower/newtonpf.py']},
        'new_PF_model_converter_derivative_factor_solve_calls': 0,
        'workflow_seconds': time.monotonic()-began,
        'interpretation': 'Angle/default resolution and saved convergence metadata are diagnostic evidence. No automatic changed-contract reuse, repeated physics, owner restart, or comparison claim.'}
    put(O/'Saved_Contract_Diagnosis.json', result)
    put(O/'Closed_Manifest.json', {'members': {p.name: sha(p) for p in O.iterdir() if p.is_file()}})
    print(json.dumps({k: result[k] for k in ['status','old_saved_pandapower_version', 'current_pandapower_version',
        'resolved_option_differences', 'old_saved_options_mismatches_with_current_old_resolution',
        'old_saved_final_Newton_iterations', 'old_saved_success', 'new_PF_model_converter_derivative_factor_solve_calls']}))


if __name__ == '__main__': main()
