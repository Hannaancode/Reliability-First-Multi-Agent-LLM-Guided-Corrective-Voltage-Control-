"""Prospective ALL3 native public ACOPF reference: one attempt/case, no retries."""
import argparse,collections,hashlib,json,os,subprocess,sys,time,traceback
from pathlib import Path
from datetime import datetime,timezone

R=Path(__file__).resolve().parents[1]
B=R/'outputs/public118_native_acopf_reference_20261015'

def now():return datetime.now(timezone.utc).isoformat()
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def put(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def check_pins(p):
    for name,h in p['source_and_input_sha256'].items():assert sha(Path(name) if Path(name).is_absolute() else R/name)==h,name
def manifest(directory):
    put(directory/'Closed_Manifest.json',{'at_utc':now(),'members':{str(p.relative_to(directory)):sha(p) for p in directory.rglob('*') if p.is_file()}})
def jsonable(d):
    import numpy as np
    if isinstance(d,dict):return {str(k):jsonable(v) for k,v in d.items()}
    if isinstance(d,(list,tuple)):return [jsonable(v) for v in d]
    if isinstance(d,np.ndarray):return jsonable(d.tolist())
    if isinstance(d,np.generic):return jsonable(d.item())
    if isinstance(d,float) and not __import__('math').isfinite(d):return {'nonfinite':repr(d)}
    return d

def case_worker(index):
    started=time.perf_counter();cpu=time.process_time();p=read(B/'Protocol.json');check_pins(p)
    out=B/'actual'/f'case{index}';out.mkdir(exist_ok=False)
    put(out/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'at_utc':now(),'source_sha256':sha(__file__),'protocol_sha256':sha(B/'Protocol.json')})
    rec=p['cases'][index-1];attempted=returned=False;counts=collections.Counter();opf_seconds=None
    try:
        import numpy as np
        from pandapower.pypower.opf import opf
        from pandapower.pypower.ppoption import ppoption
        with np.load(R/rec['full_native_ppc_path'],allow_pickle=False) as z:
            native={k:z[k].copy() for k in z.files}
        ppc={k:v.copy() for k,v in native.items()};ppc['baseMVA']=float(ppc['baseMVA']);ppc['version']=str(ppc['version'])
        # Zero-only structural PYPOWER extensions: no original value changes.
        for key,width in [('bus',17),('gen',21),('branch',26)]:
            a=ppc[key];assert a.shape[1]<=width;ppc[key]=np.pad(a,((0,0),(0,width-a.shape[1])))
            assert np.array_equal(ppc[key][:,:a.shape[1]],native[key])
        opts=ppoption(**p['solver_options'])
        put(out/'Actual_Input_And_Options.json',{'at_utc':now(),'case':rec['case'],'native_input_sha256':sha(R/rec['full_native_ppc_path']),
            'zero_only_implementation_padding':{'bus':17,'gen':21,'branch':26},'actual_options':opts})
        names={'opf','pipsopf_solver','pips','makeYbus','opf_consfcn','opf_costfcn','opf_hessfcn','dSbus_dV','dSbr_dV','makeAang'}
        def profile(frame,event,arg):
            if event=='call' and frame.f_code.co_name in names and 'pandapower' in frame.f_code.co_filename:
                counts[frame.f_code.co_name]+=1
        put(out/'OPF_Attempt.json',{'at_utc':now(),'actual_pid':os.getpid(),'case':rec['case'],'attempt_index':1,'retries':0})
        attempted=True;t=time.perf_counter();sys.setprofile(profile)
        try:result=opf(ppc,opts)
        finally:sys.setprofile(None);opf_seconds=time.perf_counter()-t
        returned=True
        with (out/'Actual_Solver_Arrays.npz').open('xb') as f:
            np.savez_compressed(f,**{k:result[k] for k in ['bus','gen','branch','gencost','x']});f.flush();os.fsync(f.fileno())
        put(out/'Actual_Solver_Metadata.json',jsonable({k:result[k] for k in ['baseMVA','f','success','et','raw','mu','var','lin','nln'] if k in result}))
        put(out/'Result.json',{'at_utc':now(),'status':'RETURNED','solver_reported_success':bool(result['success']),
            'case':rec['case'],'OPF_attempts':1,'OPF_returns':1,'OPF_exceptions':0,'OPF_call_seconds':opf_seconds,
            'profile_call_counts':dict(counts),'workflow_seconds':time.perf_counter()-started,'process_cpu_seconds':time.process_time()-cpu,
            'new_model_calls':0,'standalone_PF_requests':0,'solver_inner_linear_algebra_counts_and_intrinsic_latency':'NOT_SEPARATELY_MEASURED'})
    except BaseException:
        sys.setprofile(None);(out/'Failure_Traceback.txt').write_text(traceback.format_exc(),encoding='utf-8')
        put(out/'Result.json',{'at_utc':now(),'status':'EXCEPTION_RETAINED','case':rec['case'],'OPF_attempts':int(attempted),
            'OPF_returns':int(returned),'OPF_exceptions':int(attempted and not returned),'OPF_call_seconds':opf_seconds,
            'profile_call_counts':dict(counts),'workflow_seconds':time.perf_counter()-started,'process_cpu_seconds':time.process_time()-cpu,
            'new_model_calls':0,'standalone_PF_requests':0,'physical_feasibility':'UNKNOWN; exception is not infeasibility'})
    manifest(out)

def run():
    p=read(B/'Protocol.json');check_pins(p);started=time.perf_counter()
    out=B/'actual';out.mkdir(exist_ok=False)
    put(out/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'at_utc':now(),'source_sha256':sha(__file__),'protocol_sha256':sha(B/'Protocol.json')})
    jobs=[]
    for index,rec in enumerate(p['cases'],1):
        if time.perf_counter()-started>p['scientific_workflow_bound_seconds']:
            jobs.append({'case':rec['case'],'status':'UNEXECUTED_FIXED_BOUND_UNKNOWN'});continue
        command=[sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--case',str(index)]
        with (out/f'case{index}_console.log').open('xb') as f:
            proc=subprocess.Popen(command,cwd=R,stdout=f,stderr=subprocess.STDOUT)
            launch={'case':rec['case'],'actual_child_pid':proc.pid,'parent_pid':os.getpid(),'command':command,'at_utc':now()}
            put(out/f'case{index}_Launch.json',launch)
            timedout=False
            try:code=proc.wait(timeout=p['per_case_process_bound_seconds'])
            except subprocess.TimeoutExpired:
                timedout=True;proc.kill();code=proc.wait()
            jobs.append({**launch,'exit_code':code,'fixed_bound_terminated':timedout,'result_present':(out/f'case{index}/Result.json').exists()})
    check_pins(p)
    put(out/'Result.json',{'at_utc':now(),'status':'ALL_DECLARED_CASES_TERMINAL','jobs':jobs,'workflow_seconds':time.perf_counter()-started,
        'all_results_present':all(j.get('result_present',False) for j in jobs),'scientific_retries':0,'new_model_calls':0,
        'original_frozen_assets_touched':False,'LLM_or_DSE_superiority':'NOT_TESTED'})
    manifest(out)
    reader=R/'work/audit_public118_native_acopf_reference_20261015.py'
    assert sha(reader)==p['independent_reader_sha256']
    with (B/'independent_reader_console.log').open('xb') as f:
        proc=subprocess.Popen([sys.executable,'-X','utf8',str(reader)],cwd=R,stdout=f,stderr=subprocess.STDOUT)
        put(B/'Reader_Launch.json',{'actual_child_pid':proc.pid,'parent_pid':os.getpid(),'at_utc':now(),'source_sha256':sha(reader)})
        timeout=False
        try:code=proc.wait(timeout=p['independent_reader_bound_seconds'])
        except subprocess.TimeoutExpired:timeout=True;proc.kill();code=proc.wait()
    put(B/'Completion.json',{'at_utc':now(),'all_science_children_ended':True,'reader_ended':True,'reader_exit_code':code,
        'reader_fixed_bound_terminated':timeout,'workflow_seconds':time.perf_counter()-started,'no_retries':True})
    print(json.dumps(read(B/'Completion.json')))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',type=int,choices=[1,2,3]);a.add_argument('--run',action='store_true');args=a.parse_args()
    if args.case:case_worker(args.case)
    elif args.run:run()
    else:a.error('Explicit --case or --run required')
