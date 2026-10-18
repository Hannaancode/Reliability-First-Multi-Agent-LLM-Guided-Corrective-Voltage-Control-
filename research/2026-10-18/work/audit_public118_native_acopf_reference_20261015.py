"""Independent direct complex branch equations; no pandapower/PF/OPF/solve."""
import hashlib,json,os,time
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];B=R/'outputs/public118_native_acopf_reference_20261015'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def put(p,d):
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def verify_manifest(directory):
    m=read(directory/'Closed_Manifest.json')
    for rel,h in m['members'].items():assert sha(directory/rel)==h,rel
    return len(m['members'])

def certify(native,bus,gen,branch,objective,tol):
    b=native['bus'];g=native['gen'];lines=native['branch'];cost=native['gencost'];base=float(native['baseMVA']);n=len(b)
    assert np.array_equal(b[:,0],np.arange(n)) and np.all(g[:,7]==1) and np.all(lines[:,10]==1)
    assert np.isfinite(bus).all() and np.isfinite(gen).all() and np.isfinite(branch).all() and np.isfinite(objective)
    for columns,old,new in [([i for i in range(b.shape[1]) if i not in [7,8]],b,bus),
                            ([i for i in range(g.shape[1]) if i not in [1,2,5]],g,gen),
                            (list(range(lines.shape[1])),lines,branch)]:
        assert np.array_equal(old[:,columns],new[:,columns]),'Original physical input changed'
    voltage=bus[:,7]*np.exp(1j*np.deg2rad(bus[:,8]));f=lines[:,0].astype(int);t=lines[:,1].astype(int)
    y=1/(lines[:,2]+1j*lines[:,3]);charging=1j*lines[:,4]/2
    taps=np.where(lines[:,8]==0,1,lines[:,8])*np.exp(1j*np.deg2rad(lines[:,9]))
    If=(y+charging)/(abs(taps)**2)*voltage[f]-y/np.conj(taps)*voltage[t]
    It=-y/taps*voltage[f]+(y+charging)*voltage[t]
    sf=voltage[f]*np.conj(If);st=voltage[t]*np.conj(It)
    injection=np.zeros(n,dtype=complex);np.add.at(injection,f,sf);np.add.at(injection,t,st)
    injection+=(b[:,4]-1j*b[:,5])/base*abs(voltage)**2
    generation=np.zeros(n,dtype=complex);np.add.at(generation,g[:,0].astype(int),(gen[:,1]+1j*gen[:,2])/base)
    balance=generation-(b[:,2]+1j*b[:,3])/base-injection
    reconstructed=np.column_stack([sf.real,sf.imag,st.real,st.imag])*base
    flow_replay=float(np.max(abs(branch[:,13:17]-reconstructed))/base)
    angle=np.deg2rad(bus[f,8]-bus[t,8]);lo=np.deg2rad(lines[:,11]);hi=np.deg2rad(lines[:,12])
    lo_mask=(lines[:,11]!=0)&(lines[:,11]>-360);hi_mask=(lines[:,12]!=0)&(lines[:,12]<360)
    limited=(lines[:,5]>0)&(lines[:,5]<1e10);thermal=np.maximum(abs(sf),abs(st))-lines[:,5]/base
    metrics={'active_balance_pu':float(np.max(abs(balance.real))),'reactive_balance_pu':float(np.max(abs(balance.imag))),
        'voltage_bounds_pu':float(max(0,np.max(b[:,12]-bus[:,7]),np.max(bus[:,7]-b[:,11]))),
        'P_bounds_pu':float(max(0,np.max(g[:,9]-gen[:,1]),np.max(gen[:,1]-g[:,8]))/base),
        'Q_bounds_pu':float(max(0,np.max(g[:,4]-gen[:,2]),np.max(gen[:,2]-g[:,3]))/base),
        'thermal_apparent_power_pu':float(max(0,np.max(thermal[limited],initial=0))),
        'angle_bounds_radians':float(max(0,np.max((lo-angle)[lo_mask],initial=0),np.max((angle-hi)[hi_mask],initial=0))),
        'reference_angle_radians':float(np.max(abs(np.deg2rad(bus[b[:,1]==3,8]-b[b[:,1]==3,8])))),
        'recorded_branch_flow_reconstruction_pu':flow_replay,
        'generator_voltage_alignment_pu':float(np.max(abs(gen[:,5]-bus[g[:,0].astype(int),7])))}
    expected_cost=0.
    assert len(cost)==len(g) and np.all(cost[:,0]==2),'Only declared polynomial active generation cost supported'
    for i,row in enumerate(cost):
        degree=int(row[3]);expected_cost+=float(np.polyval(row[4:4+degree],gen[i,1]))
    cost_error=abs(expected_cost-objective);cost_ok=cost_error<=1e-5+1e-8*abs(expected_cost)
    passes={k:v<=tol for k,v in metrics.items()};passes['objective_reconstruction']=bool(cost_ok)
    return {'all_native_constraints_and_saved_fields_pass':bool(all(passes.values())),'checks':passes,'maximum_violations':metrics,
       'reconstructed_objective':expected_cost,'saved_objective':float(objective),'objective_absolute_error':cost_error,
       'voltage_min':float(bus[:,7].min()),'voltage_max':float(bus[:,7].max()),'buses_below_original_0_95':int((bus[:,7]<.95).sum()),
       'buses_above_original_1_05':int((bus[:,7]>1.05).sum()),'native_angle_rows':int((lo_mask|hi_mask).sum()),
       'generation_P_MW':float(gen[:,1].sum()),'demand_P_MW':float(b[:,2].sum()),'active_losses_and_shunt_MW':float(injection.real.sum()*base)}

def main():
    started=time.perf_counter();p=read(B/'Protocol.json');out=B/'independent_audit';out.mkdir(exist_ok=False)
    put(out/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'at_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'source_sha256':sha(__file__)})
    assert sha(__file__)==p['independent_reader_sha256']
    for rel,h in p['source_and_input_sha256'].items():assert sha(Path(rel) if Path(rel).is_absolute() else R/rel)==h
    verify_manifest(B/'actual');actual=read(B/'actual/Result.json');rows=[]
    for i,rec in enumerate(p['cases'],1):
        directory=B/'actual'/f'case{i}';summary={'case':rec['case'],'status':'UNKNOWN_UNEXECUTED_OR_NO_CLOSED_OUTPUT'}
        if (directory/'Closed_Manifest.json').exists():
            verify_manifest(directory);result=read(directory/'Result.json');summary['actual_costs']=result
            if result['status']=='RETURNED':
                with np.load(R/rec['full_native_ppc_path'],allow_pickle=False) as z:native={k:z[k].copy() for k in z.files}
                with np.load(directory/'Actual_Solver_Arrays.npz',allow_pickle=False) as z:a={k:z[k].copy() for k in z.files}
                metadata=read(directory/'Actual_Solver_Metadata.json')
                assert np.array_equal(native['gencost'],a['gencost']) and float(metadata['baseMVA'])==float(native['baseMVA'])
                summary['independent_physics']=certify(native,a['bus'],a['gen'],a['branch'],metadata['f'],p['independent_native_tolerance'])
                summary['solver_reported_success']=bool(metadata['success'])
                summary['status']='PASS_NATIVE_FEASIBLE_REFERENCE' if metadata['success'] and summary['independent_physics']['all_native_constraints_and_saved_fields_pass'] else 'RETURNED_WITHOUT_VERIFIED_FEASIBLE_REFERENCE'
                summary['solver_iterations']=metadata['raw']['output']['iterations'];summary['solver_message']=metadata['raw']['output']['message']
                summary['global_optimality']='NOT_PROVEN; local interior-point solver'
            else:summary['status']='UNKNOWN_EXCEPTION_RETAINED_NOT_INFEASIBILITY'
        rows.append(summary)
    from candidate_process_evidence_utils import frozen_checks
    put(out/'Fresh_Frozen_Checks.json',frozen_checks())
    put(out/'Independent_Audit.json',{'status':'COMPLETE_ALL3_DECLARED_IDENTITIES_AND_AVAILABLE_NATIVE_OUTPUTS_AUDITED',
        'all3':rows,'verified_feasible_references':sum(r['status']=='PASS_NATIVE_FEASIBLE_REFERENCE' for r in rows),
        'all3_required_no_selected_subset':True,'workflow_seconds':time.perf_counter()-started,'scientific_calls':0,
        'LLM_DSE_discrete_control_performance':'NOT_TESTED','native_optimum_or_global_infeasibility':'NOT_CERTIFIED',
        'scope':'Native published OPF uses generator P/Q and voltage freedoms; not the discrete shunt-control task. Original 0.95-1.05 diagnostics are not native feasibility bounds.'})
    put(out/'Closed_Manifest.json',{'members':{str(x.relative_to(out)):sha(x) for x in out.rglob('*') if x.is_file()}})
    print(json.dumps({'all3_audited':True,'feasible_references':sum(r['status']=='PASS_NATIVE_FEASIBLE_REFERENCE' for r in rows)}))
if __name__=='__main__':main()
