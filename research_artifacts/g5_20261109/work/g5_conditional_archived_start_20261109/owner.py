"""First conditional original118 adapter-off frontier, paid state/reply, no new science."""
import copy,hashlib,importlib.util,json,os,pickle,random,sys,time,traceback,zlib
from pathlib import Path
from collections import Counter,deque
from paid_prefix import PaidFirstReply,Frontier,put
from continuation import build_original_post_initializer
R=Path(__file__).resolve().parents[2];P=R/'outputs/g5_conditional_archived_start_20261109';O=P/'owner'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(path,name):
    assert name not in sys.modules;spec=importlib.util.spec_from_file_location(name,R/path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def main():
    began=time.monotonic();cpu=time.process_time();O.mkdir(exist_ok=False)
    put(O/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'source_sha256':sha(__file__)})
    while not (O/'Launcher_ACK.json').exists():assert time.monotonic()-began<45;time.sleep(.05)
    ack=read(O/'Launcher_ACK.json');assert ack['actual_pid']==os.getpid() and ack['actual_parent_pid']==os.getppid() and ack['fresh_exact_source_PID_parent_command']
    p=read(P/'Protocol.json');gate=read(P/'FINAL_Gate.json');assert gate['status']=='PASS_G5_CONDITIONAL_ARCHIVED_START_SOURCE' and gate['protocol_sha256']==sha(P/'Protocol.json')
    for path,h in p['source_input_sha256'].items():assert sha(R/path)==h,path
    for path,h in p['runtime_image_sha256'].items():assert sha(path)==h,path
    import importlib.metadata
    assert {n:importlib.metadata.version(n) for n in p['runtime_versions']}==p['runtime_versions']
    counts={'archived_after_decode_entries':0,'archived_after_decode_returns':0,'logical_generation_calls':0,'paid_disabled_reply_uses':0,'logical_native_query_intents':0,'candidate_shunt_constructions':0,'new_initializer_calls':0,'new_model_calls':0,'new_PF_calls':0,'native_input_conversions':0,'actual_commits':0}
    failure=frontier=None;bridge=None;oldpf=None;pp=None;old_profile=sys.getprofile()
    def bound(closure=False):
        assert time.monotonic()-began<(p['science_seconds']+p['closure_seconds'] if closure else p['science_seconds'])
        assert sum(f.stat().st_size for f in O.rglob('*') if f.is_file())<p['storage_bound_bytes']-(0 if closure else 16*1024**2)
    try:
        os.environ['NUMBA_CACHE_DIR']=str(R/'outputs/g5cs9cache');os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.path.insert(0,str(R/'work'))
        import numpy as np,pandas as pd,scipy.sparse as sparse,pandapower as pp
        from pandapower.auxiliary import pandapowerNet
        from frozen_physics_loader import load_stack,AUDIT
        codec=module(p['codec_source'],'g5_common_start_codec');profile=module(p['profile_source'],'g5_common_start_profile');admission=module(p['admission_source'],'g5_common_start_admission')
        rt={'np':np,'pd':pd,'sparse':sparse,'native_class':pandapowerNet}
        def guard(frame,event,arg):
            if event not in ('call','c_call'):return
            mod=frame.f_globals.get('__name__','') if event=='call' else str(getattr(arg,'__module__',''));name=frame.f_code.co_name if event=='call' else str(getattr(arg,'__name__',''))
            if event=='call' and mod.startswith('pandapower.') and name=='create_shunt':counts['candidate_shunt_constructions']+=1
            if mod.startswith(('torch','transformers','pandapower.pf.','pandapower.powerflow','pandapower.optimal_powerflow','pandapower.pd2ppc','pandapower.build_bus','pandapower.build_branch','pandapower.build_gen','numpy.linalg','scipy.linalg','scipy.sparse.linalg','scipy.optimize')) or (mod=='pandapower.run' and name in ('runpp','runopp','rundcpp','rundcopp','runpp_3ph')):
                raise Frontier('UNADMITTED_NATIVE_MODEL_BODY',{'module':mod,'name':name})
        sys.setprofile(guard);v2,runner,reflection=load_stack();assert all(a['all_function_asts_unchanged'] for a in AUDIT);put(O/'Original_Source_AST.json',AUDIT)
        start=p['common_starts'][0];record=read(R/start['paid_record']['path']);desc=record['after'];directory=(R/start['paid_record']['path']).parent
        bound();counts['archived_after_decode_entries']+=1;encoded=(directory/desc['path']).read_bytes();assert len(encoded)==desc['bytes'] and hashlib.sha256(encoded).hexdigest()==desc['sha256'];raw=zlib.decompress(encoded);assert len(raw)==desc['decoded_bytes'] and hashlib.sha256(raw).hexdigest()==desc['decoded_sha256'];net=pickle.loads(raw);counts['archived_after_decode_returns']+=1
        assert type(net) is pandapowerNet and bool(net.converged)
        def snapshot(value):bound();return profile.live_snapshot(value,codec,rt)
        archived_snapshot=snapshot(net);put(O/'Archived_Common_Start.json',archived_snapshot)
        target,proof=build_original_post_initializer(reflection.run_one_scenario_two_best_v2,(R/p['reflection_source']).read_bytes(),p['source_input_sha256'][p['reflection_source']]);put(O/'Conditional_Source_Binding.json',proof)
        bridge=PaidFirstReply(read(R/p['paid_reply_bundle']),0,O/'Paid_Model_Uses.jsonl')
        zones=read(R/p['zones'])['zones'];scenario=read(R/start['recipe'])
        def encode(v):
            if type(v) is pandapowerNet:return ['pandapowerNet_FULL_SNAPSHOT',snapshot(v)]
            if type(v) in (dict,Counter):return [type(v).__module__+'.'+type(v).__qualname__,[[encode(k),encode(x)] for k,x in v.items()]]
            if type(v) in (list,tuple,deque):return [type(v).__module__+'.'+type(v).__qualname__,[encode(x) for x in v],v.maxlen if type(v) is deque else None]
            if type(v) is set:return ['builtins.set',sorted((encode(x) for x in v),key=lambda x:json.dumps(x,sort_keys=True))]
            return codec.typed(v,rt)
        def frame_state():
            f=sys._getframe()
            while f is not None and f.f_code is not target.__code__:f=f.f_back
            assert f is not None;values={};unsupported={}
            for k,v in f.f_locals.items():
                try:values[k]=encode(v)
                except (ValueError,TypeError,AssertionError,NotImplementedError):unsupported[k]=type(v).__module__+'.'+type(v).__qualname__
            assert set(('net','result','failed_sigs','failed_actions','feedback_state','it','zone','zs','global_uv'))<=set(values)
            counts['actual_commits']=len(f.f_locals['result']['executed_actions']);assert counts['actual_commits']==0
            return f,{'typed_locals':values,'unsupported_nonrestored_locals':unsupported,'python_rng':codec.typed(random.getstate(),rt),'numpy_rng':codec.typed(np.random.get_state(),rt),'not_resumed_suspended_frame':True}
        def model(messages):
            bound();counts['logical_generation_calls']+=1
            if counts['logical_generation_calls']==1:
                f,state=frame_state();actual=snapshot(f.f_locals['net']);put(O/'Actual_First_Decision_Start.json',actual)
                # Equality is of the explicitly declared archived solved start, not historical backend arguments.
                if actual!=archived_snapshot:raise Frontier('COMMON_ARCHIVED_STATE_COPY_DIFFERS',{'exact_equality':False})
                put(O/'Exact_First_Messages.json',messages)
            try:value=bridge(messages)
            except Frontier:
                _,state=frame_state();put(O/'Pending_Causal_Frame.json',state);raise
            counts['paid_disabled_reply_uses']+=1;return value
        def native_query(query_net,**kwargs):
            bound();counts['logical_native_query_intents']+=1
            put(O/'Pending_Native_Input.json',{'snapshot':snapshot(query_net),'kwargs':kwargs,'identity_status':'UNBOUND_NOT_CLAIMED_UNEXECUTED','public_body_called':False})
            _,state=frame_state();put(O/'Pending_Causal_Frame.json',state);raise Frontier('NATIVE_IDENTITY_NOT_YET_BOUND',{'new_native_or_PF_calls':0})
        oldpf=pp.runpp;oldgen=runner.base_runner.generate_response
        pp.runpp=admission.prevent_solver_translation(native_query,put,O);runner.base_runner.generate_response=lambda body,tokenizer,messages:model(messages)
        random.seed(p['seed']);np.random.seed(p['seed'])
        try:
            result=target(scenario,net,zones,v2,object(),object(),'reflection_v2');put(O/'Natural_Controller_Return.json',result);raise Frontier('NATURAL_POST_INITIALIZER_RETURN',{'full_trajectory_claim':False})
        finally:runner.base_runner.generate_response=oldgen
    except Frontier as exc:frontier={'kind':exc.kind,'payload':exc.payload}
    except BaseException:failure=traceback.format_exc()
    finally:
        sys.setprofile(old_profile)
        if oldpf is not None:pp.runpp=oldpf
        bound(True)
        if bridge:put(O/'Paid_Model_Checkpoint.json',bridge.snapshot())
        complete=frontier is not None and frontier['kind'] in ('MISSING_DISABLED_GENERATION','NATIVE_IDENTITY_NOT_YET_BOUND') and failure is None
        put(O/'Result.json',{'status':'COMPLETE_CONDITIONAL_ARCHIVED_START_FRONTIER' if complete else 'PARTIAL_CONDITIONAL_FRONTIER_UNKNOWN','frontier':frontier,'failure':failure,'counts':counts,'workflow_seconds':time.monotonic()-began,'CPU_seconds':time.process_time()-cpu,'initializer_contract':'CONDITIONAL_ARCHIVED_SOLVED_INITIAL_STATE','historical_initializer_costs_ref':p['historical_costs_ref'],'historical_backend_or_full_trajectory_superiority':False})
        put(O/'Closed_Manifest.json',{'members':{f.relative_to(O).as_posix():{'bytes':f.stat().st_size,'sha256':sha(f)} for f in O.rglob('*') if f.is_file()}})
        if not complete:raise SystemExit(1)
if __name__=='__main__':main()
