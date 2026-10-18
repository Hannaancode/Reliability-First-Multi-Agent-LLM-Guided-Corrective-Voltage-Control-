"""Freeze all3 one-attempt native solver/independent-physics protocol before outcomes."""
import ast,hashlib,inspect,json,os,sys,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandapower,scipy
from pandapower.pypower.ppoption import ppoption
from candidate_process_evidence_utils import frozen_checks
from audit_public118_native_acopf_reference_20261015 import certify
R=Path(__file__).resolve().parents[1];B=R/'outputs/public118_native_acopf_reference_20261015'
INPUT=R/'outputs/public118_native_benchmark_input_closure_20261015'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())

def synthetic_controls():
    # Analytic two-terminal series-current construction, independent of the reader's matrix-element formula.
    base=100.;v=np.array([1.01,.99])*np.exp(1j*np.deg2rad([0,-.3]));tap=1.04*np.exp(1j*np.deg2rad(.2))
    series=(v[0]/tap-v[1])/(.1+.2j);a=(series+.01j*v[0]/tap)/np.conj(tap);b=-series+.01j*v[1]
    sf=v[0]*np.conj(a)*base;st=v[1]*np.conj(b)*base
    bus=np.zeros((2,13));bus[:,0]=[0,1];bus[:,1]=[3,1];bus[:,2]=50;bus[:,3]=20
    bus[:,4]=[1,0];bus[:,5]=[2,0];bus[:,7]=[1.01,.99];bus[:,8]=[0,-.3];bus[:,11]=1.06;bus[:,12]=.94
    gen=np.zeros((2,10));gen[:,0]=[0,1];gen[:,1]=50+np.array([sf.real,st.real])+bus[:,4]*abs(v)**2
    gen[:,2]=20+np.array([sf.imag,st.imag])-bus[:,5]*abs(v)**2
    gen[:,3]=100;gen[:,4]=-100;gen[:,5]=abs(v);gen[:,6]=base;gen[:,7]=1;gen[:,8]=100
    line=np.array([[0,1,.1,.2,.02,100,100,100,1.04,.2,1,-1,1]],dtype=float)
    cost=np.array([[2,0,0,3,2,3,4],[2,0,0,3,1,0,0]],dtype=float)
    native={'bus':bus.copy(),'gen':gen.copy(),'branch':line.copy(),'gencost':cost,'baseMVA':base}
    branch=np.pad(line,((0,0),(0,4)));branch[:,13:17]=[sf.real,sf.imag,st.real,st.imag]
    objective=2*gen[0,1]**2+3*gen[0,1]+4+gen[1,1]**2
    good=certify(native,bus,gen,branch,objective,5e-6);assert good['all_native_constraints_and_saved_fields_pass']
    tests={'independent_series_current_tap_phase_shift_shunt_charging_balance_cost':True}
    for name,kind in [('wrong_saved_flow','flow'),('wrong_objective','cost'),('voltage_violation','voltage'),('generator_active_limit','P'),('angle_violation','angle')]:
        bb=bus.copy();gg=gen.copy();ll=branch.copy();obj=objective
        if kind=='flow':ll[0,13]+=.1
        elif kind=='cost':obj+=1
        elif kind=='voltage':bb[1,7]=1.08
        elif kind=='P':gg[0,1]=101
        else:bb[1,8]=-2
        assert not certify(native,bb,gg,ll,obj,5e-6)['all_native_constraints_and_saved_fields_pass'];tests[name]=True
    altered=bus.copy();altered[0,2]+=1
    try:certify(native,altered,gen,branch,objective,5e-6)
    except AssertionError:tests['changed_native_demand_rejected']=True
    else:raise AssertionError('Native immutable-input boundary missing')
    return tests

def main():
    started=time.perf_counter();B.mkdir(exist_ok=False)
    source=R/'work/public118_native_acopf_reference_20261015.py';reader=R/'work/audit_public118_native_acopf_reference_20261015.py'
    for p in [source,reader,Path(__file__)]:compile(p.read_text(encoding='utf-8'),str(p),'exec')
    audit=json.loads((INPUT/'independent_audit/Independent_Native_Input_Audit.json').read_text());assert audit['status'].startswith('PASS_ALL3')
    inputs=json.loads((INPUT/'Native_Benchmark_Input_Readiness.json').read_text())['all3'];assert len(inputs)==3
    for rec in inputs:
        assert sha(R/rec['full_native_ppc_path'])==rec['full_native_ppc_sha256'] and sha(R/rec['case'])==rec['raw_sha256']
        with np.load(R/rec['full_native_ppc_path'],allow_pickle=False) as z:
            assert z['bus'].shape==(118,13) and z['gen'].shape==(54,10) and z['branch'].shape==(186,13)
            assert np.array_equal(z['bus'][:,0],np.arange(118)) and np.all(z['gen'][:,7]==1) and np.all(z['branch'][:,10]==1)
            assert np.all(z['gen'][:,9]>=0) and np.all(z['gencost'][:,0]==2)
    options=ppoption(OPF_ALG=560,OPF_FLOW_LIM=0,OPF_IGNORE_ANG_LIM=False,VERBOSE=0,OUT_ALL=0,INIT='flat',RETURN_RAW_DER=0)
    assert options['PDIPM_MAX_IT']==150 and options['OPF_VIOLATION']==5e-6
    closure=Path(inspect.getfile(pandapower)).parent/'pypower'
    paths=[source,reader,Path(__file__),R/'work/candidate_process_evidence_utils.py',INPUT/'Native_Benchmark_Input_Readiness.json',INPUT/'independent_audit/Independent_Native_Input_Audit.json']
    paths+=sorted(closure.glob('*.py'))
    paths+=[R/rec[k] for rec in inputs for k in ['case','full_native_ppc_path']]
    pins={str(p.resolve()):sha(p) for p in paths}
    controls=synthetic_controls();frozen=frozen_checks()
    # No library OPF/PF/model function is called by preparation or software controls.
    protocol={'at_utc':datetime.now(timezone.utc).isoformat(),'status':'FROZEN_BEFORE_ANY_SOLVER_OUTCOME',
        'hypothesis':'A single fixed native ACOPF solve per original published variant can supply a source-faithful, independently physically checked feasible reference dispatch. Solver failure cannot certify infeasibility.',
        'case_selection':'ALL3 previously pinned official variants, original source order; no model/solver outcome selection.',
        'cases':inputs,'solver_options':options,'solver_initialization':'Installed PIPS native interior-midpoint path, INIT=flat; no preceding PF or redispatch heuristic, no alternate initialization or solver retry.',
        'padding':'Only zeros appended after original columns: bus17, gen21, branch26. All original native values retained, all active original elements; no constraint/objective/actuator change.',
        'independent_native_tolerance':5e-6,'independent_objective_tolerance':'absolute1e-5 + relative1e-8; all frozen before outcomes',
        'independent_constraints':['all118 complex active/reactive balances incl native shunts','generator P/Q bounds','bus V bounds','both-end RATE_A apparent flow','native ANGMIN/ANGMAX','reference angle','recorded branch-flow replay','generator voltage alignment','polynomial source objective','immutable native physical inputs'],
        'per_case_process_bound_seconds':180,'scientific_workflow_bound_seconds':600,'independent_reader_bound_seconds':180,
        'max_optimizer_iterations_per_case':150,'attempts_per_case':1,'retry_policy':'NONE; preserve exception/timeout/failed solver and all unexecuted identities UNKNOWN',
        'pinned_versions':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'pandapower':pandapower.__version__},
        'source_and_input_sha256':pins,'independent_reader_sha256':sha(reader),
        'scope':'Native ACOPF reference only; generator P/Q/V freedoms differ from original discrete shunt rescue. No LLM/DSE/zero-UV superiority, global optimum or global infeasibility claim.',
        'preparation_and_import_costs_not_free':True,'inner_linear_algebra_FLOPs_and_intrinsic_latency':'UNKNOWN; actual workflow, OPF application time, iterations and named solver function counts charged',
        'all_failures_retained_no_original_assets_changed':True,'three_GPU_resources':'Human-reported; this numerical reference uses CPU only, no allocation justified'}
    put(B/'Protocol.json',protocol)
    put(B/'Software_And_Input_Readiness.json',{'status':'PASS_PROTOCOL_INPUT_SOURCE_CLOSURE_AND_7_INDEPENDENT_ANALYTIC_CONTROLS',
        'controls':controls,'all3_input_identities_pass':True,'preparation_workflow_seconds':time.perf_counter()-started,
        'new_OPF_PF_model_calls':0,'fresh_nine_frozen_checks':frozen,'protocol_sha256':sha(B/'Protocol.json')})
    print(json.dumps({'all3_ready':True,'independent_analytic_controls':len(controls),'new_science_calls':0}))
if __name__=='__main__':main()
