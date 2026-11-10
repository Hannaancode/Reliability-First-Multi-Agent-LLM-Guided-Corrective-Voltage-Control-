"""One missing initializer-input observation; no original policy or solver call."""
import ast,copy,hashlib,importlib.util,json,os,sys,time,traceback
from pathlib import Path
from types import SimpleNamespace
R=Path(__file__).resolve().parents[2];P=R/'outputs/g5_initializer_observation_20261109';O=P/'owner'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())
def module(path,name):
    assert name not in sys.modules;spec=importlib.util.spec_from_file_location(name,R/path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def main():
    began=time.monotonic();cpu=time.process_time();O.mkdir(exist_ok=False)
    put(O/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'source_sha256':sha(__file__)})
    while not (O/'Launcher_ACK.json').exists():assert time.monotonic()-began<45;time.sleep(.05)
    ack=read(O/'Launcher_ACK.json');assert ack['actual_pid']==os.getpid() and ack['actual_parent_pid']==os.getppid() and ack['fresh_exact_source_PID_parent_command']
    p=read(P/'Protocol.json');gate=read(P/'FINAL_Gate.json');assert gate['status']=='PASS_G5_INITIALIZER_INPUT_OBSERVATION_SOURCE' and gate['protocol_sha256']==sha(P/'Protocol.json')
    for path,h in p['source_input_sha256'].items():assert sha(R/path)==h,path
    for path,h in p['runtime_image_sha256'].items():assert sha(path)==h,path
    import importlib.metadata
    assert {n:importlib.metadata.version(n) for n in p['runtime_versions']}==p['runtime_versions']
    counts={'new_base_JSON_decode_entries':0,'new_base_JSON_decode_returns':0,'old_NET_decodes':0,'source_apply_scenario_entries':0,'source_run_pf_wrapper_entries':0,'intercepted_public_call_intents':0,'actual_input_snapshot_returns':0,'native_public_body_calls':0,'native_conversion_PF_model_controller_metric_commit_calls':0}
    failure=None;observation=None;old_profile=sys.getprofile();oldpf=None;pp=None
    def bound(closure=False):
        assert time.monotonic()-began<(p['science_seconds']+p['closure_seconds'] if closure else p['science_seconds'])
        assert sum(x.stat().st_size for x in O.rglob('*') if x.is_file())<p['storage_bound_bytes']-(0 if closure else 16*1024**2)
    try:
        os.environ['NUMBA_CACHE_DIR']=str(R/'outputs/g5io9cache');os.environ['PYTHONDONTWRITEBYTECODE']='1'
        import numpy as np,pandas as pd,scipy.sparse as sparse,pandapower as pp
        from pandapower.auxiliary import pandapowerNet
        codec=module(p['codec_source'],'g5_initializer_observation_codec');profile=module(p['profile_source'],'g5_initializer_observation_profile');admission=module(p['admission_source'],'g5_initializer_capture')
        rt={'np':np,'pd':pd,'sparse':sparse,'native_class':pandapowerNet}
        def guard(frame,event,arg):
            if event not in ('call','c_call'):return
            mod=frame.f_globals.get('__name__','') if event=='call' else str(getattr(arg,'__module__',''));name=frame.f_code.co_name if event=='call' else str(getattr(arg,'__name__',''))
            if event=='call' and frame.f_code.co_filename==str(R/p['source_v0']):
                if name=='apply_scenario_to_net':counts['source_apply_scenario_entries']+=1
                elif name=='run_pf':counts['source_run_pf_wrapper_entries']+=1
                elif name!='<module>':raise admission.InitialAdmissionStop('UNADMITTED_SOURCE_CALL',{'name':name})
            if mod.startswith(('torch','transformers','pandapower.pf.','pandapower.powerflow','pandapower.optimal_powerflow','pandapower.pd2ppc','pandapower.build_bus','pandapower.build_branch','pandapower.build_gen','numpy.linalg','scipy.linalg','scipy.sparse.linalg','scipy.optimize')) or (mod=='pandapower.run' and name in ('runpp','runopp','rundcpp','rundcopp','runpp_3ph')):
                raise admission.InitialAdmissionStop('UNADMITTED_NATIVE_BODY',{'module':mod,'name':name})
        sys.setprofile(guard)
        tree=ast.parse((R/p['source_v0']).read_text(encoding='utf-8'));defs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('apply_scenario_to_net','run_pf')];assert len(defs)==2
        scope={'pp':pp};exec(compile(ast.Module(body=defs,type_ignores=[]),str(R/p['source_v0']),'exec'),scope)
        reflection=ast.parse((R/p['source_reflection']).read_text(encoding='utf-8'));target=next(n for n in reflection.body if isinstance(n,ast.FunctionDef) and n.name=='run_one_scenario_two_best_v2')
        statements=target.body[2:5];assert [ast.unparse(n) for n in statements]==p['exact_initializer_statements']
        wrapper=ast.parse('def observe(base_net, scenario, zones, v2):\n    pass').body[0];wrapper.body=copy.deepcopy(statements)
        env={'copy':copy};exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),'<original-initializer-three-statements>','exec'),env)
        put(O/'Source_Statement_Binding.json',{'function_AST_sha256':{n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for n in defs},'statement_AST_sha256':hashlib.sha256(ast.dump(ast.Module(body=statements,type_ignores=[]),include_attributes=False).encode()).hexdigest(),'full_controller_invoked':False})
        bound();counts['new_base_JSON_decode_entries']+=1;base=pp.from_json(str(R/p['base_net']));counts['new_base_JSON_decode_returns']+=1
        scenario=read(R/p['recipe']);zones=read(R/p['zones'])['zones'];saved=read(R/p['saved_input_snapshot']);record=read(R/p['paid_initial_record'])
        def snapshot(value):
            bound();result=profile.live_snapshot(value,codec,rt);counts['actual_input_snapshot_returns']+=1;return result
        def capture(net,**kwargs):
            counts['intercepted_public_call_intents']+=1;assert counts['intercepted_public_call_intents']==1
            bound();result=admission.compare_and_preserve(net,kwargs,saved,record['kwargs'],record['provenance'],snapshot,put,O)
            raise admission.InitialAdmissionStop('INITIAL_INPUT_CAPTURED_EXACT',result)
        oldpf=pp.runpp;pp.runpp=admission.prevent_solver_translation(capture,put,O)
        try:env['observe'](base,scenario,zones,SimpleNamespace(v0=SimpleNamespace(**scope)))
        except admission.InitialAdmissionStop as exc:
            observation={'kind':exc.kind,'payload':exc.payload}
            if exc.kind not in ('INITIAL_INPUT_CAPTURED_EXACT','INITIAL_PAID_INPUT_NOT_EXACT'):failure='Unclosed input observation: '+exc.kind
        else:failure='Original initializer unexpectedly returned without explicit observation boundary'
    except BaseException:failure=traceback.format_exc()
    finally:
        sys.setprofile(old_profile)
        if oldpf is not None:pp.runpp=oldpf
        bound(True)
        put(O/'Result.json',{'status':'COMPLETE_DISTINCT_ACTUAL_INITIAL_INPUT_OBSERVATION' if observation and failure is None else 'PARTIAL_ACTUAL_INPUT_OBSERVATION_UNKNOWN','observation':observation,'failure':failure,'counts':counts,'workflow_seconds':time.monotonic()-began,'CPU_seconds':time.process_time()-cpu,'previous_failure_preserved':p['old_failure_ref'],'old_NET_decodes_or_original_controller_repeated':False,'new_scientific_performance_or_admission_claim':False})
        put(O/'Closed_Manifest.json',{'members':{x.relative_to(O).as_posix():{'bytes':x.stat().st_size,'sha256':sha(x)} for x in O.rglob('*') if x.is_file()}})
        if failure:raise SystemExit(1)
if __name__=='__main__':main()
