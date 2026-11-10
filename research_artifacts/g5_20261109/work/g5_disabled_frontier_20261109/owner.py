"""Original first-case causal prefix, paid initial physics/reply only, then stop."""
import copy,hashlib,importlib.util,json,os,pickle,random,sys,time,traceback,zlib
from collections import Counter,deque
from pathlib import Path
from paid_prefix import PaidFirstReply,Frontier,put,sha as value_sha
R=Path(__file__).resolve().parents[2];P=R/'outputs/g5_disabled_frontier_20261109';O=P/'owner'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(path,name):
    assert name not in sys.modules
    spec=importlib.util.spec_from_file_location(name,R/path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def main():
    began=time.monotonic();cpu=time.process_time();O.mkdir(exist_ok=False)
    put(O/'owner.claim',{'actual_pid':os.getpid(),'parent_pid':os.getppid(),'source_sha256':digest(__file__),'command':str(Path(__file__).resolve())})
    while not (O/'Launcher_ACK.json').exists():assert time.monotonic()-began<45;time.sleep(.05)
    ack=read(O/'Launcher_ACK.json');assert ack['actual_pid']==os.getpid() and ack['actual_parent_pid']==os.getppid() and ack['fresh_exact_source_PID_parent_command']
    p=read(P/'Protocol.json');gate=read(P/'FINAL_Gate.json');assert gate['status']=='PASS_G5_PAID_DISABLED_FRONTIER_SOURCE' and gate['protocol_sha256']==digest(P/'Protocol.json')
    for path,h in p['source_input_sha256'].items():assert digest(R/path)==h,path
    for path,h in p['runtime_image_sha256'].items():assert digest(path)==h,path
    import importlib.metadata
    assert {name:importlib.metadata.version(name) for name in p['runtime_versions']}==p['runtime_versions']
    counts={'new_model_calls':0,'new_PF_calls':0,'native_input_conversions':0,'native_algorithm_calls':0,'actual_commits':0,'initial_paid_PF_reuses':0,'paid_reply_uses':0,'saved_NET_decode_attempts':0,'saved_NET_decode_returns':0,'base_json_decode_entries':0,'base_json_decode_returns':0,'candidate_shunt_constructions':0,'logical_PF_calls':0,'logical_generation_calls':0}
    failure=frontier=None;bridge=None;old_profile=sys.getprofile();oldpf=None;pp=None
    def bound(closure=False):
        assert time.monotonic()-began<(p['owner_science_seconds']+p['closure_seconds'] if closure else p['owner_science_seconds']),'Original bound reached; no extension'
        assert sum(f.stat().st_size for f in O.rglob('*') if f.is_file()) < p['storage_bound_bytes']-(0 if closure else 16*1024**2),'Fixed preservation bound'
    try:
        os.environ['NUMBA_CACHE_DIR']=str(R/'outputs/g5df9cache');os.environ['PYTHONDONTWRITEBYTECODE']='1'
        sys.path.insert(0,str(R/'work'))
        import numpy as np,pandas as pd,scipy.sparse as sparse,pandapower as pp
        import pandapower.powerflow as pf
        from pandapower.auxiliary import pandapowerNet
        from frozen_physics_loader import load_stack,AUDIT
        codec=module(p['codec_source'],'g5_frontier_value_codec')
        profile=module(p['profile_source'],'g5_frontier_state_profile')
        rt={'np':np,'pd':pd,'sparse':sparse,'native_class':pandapowerNet}
        def snapshot(value):bound();return profile.live_snapshot(value,codec,rt)
        def guard(frame,event,arg):
            if event not in ('call','c_call'):return
            mod=frame.f_globals.get('__name__','') if event=='call' else str(getattr(arg,'__module__',''))
            name=frame.f_code.co_name if event=='call' else str(getattr(arg,'__name__',''))
            if event=='call' and name=='create_shunt' and mod.startswith('pandapower.'):counts['candidate_shunt_constructions']+=1
            if mod.startswith(('torch','transformers','pandapower.pf.','pandapower.powerflow','pandapower.optimal_powerflow','pandapower.pd2ppc','pandapower.build_bus','pandapower.build_branch','pandapower.build_gen','numpy.linalg','scipy.linalg','scipy.sparse.linalg','scipy.optimize')) or (mod=='pandapower.run' and name in ('runpp','runopp','rundcpp','rundcopp','runpp_3ph')):
                raise Frontier('FORBIDDEN_NATIVE_OR_MODEL_BODY',{'module':mod,'name':name})
        sys.setprofile(guard)
        v2,runner,reflection=load_stack();assert all(a['all_function_asts_unchanged'] for a in AUDIT)
        put(O/'Original_Source_AST.json',AUDIT)
        counts['base_json_decode_entries']+=1;base=pp.from_json(str(R/p['base_net']));counts['base_json_decode_returns']+=1
        zones=read(R/p['zones'])['zones'];scenario=read(R/p['recipe'])
        rec=read(R/p['initial_record']);directory=(R/p['initial_record']).parent
        def decode(desc):
            bound();counts['saved_NET_decode_attempts']+=1;raw=(directory/desc['path']).read_bytes();assert len(raw)==desc['bytes'] and hashlib.sha256(raw).hexdigest()==desc['sha256']
            raw=zlib.decompress(raw);assert len(raw)==desc['decoded_bytes'] and hashlib.sha256(raw).hexdigest()==desc['decoded_sha256'];net=pickle.loads(raw);counts['saved_NET_decode_returns']+=1;assert type(net) is pandapowerNet;return net
        saved_before,saved_after=decode(rec['before']),decode(rec['after'])
        put(O/'Saved_Initial_Before.json',snapshot(saved_before));put(O/'Saved_Initial_After.json',snapshot(saved_after))
        bridge=PaidFirstReply(read(P/'Paid_First_Response_Bundle.json'),0,O/'Model_Paid_Use.jsonl')
        target=reflection.run_one_scenario_two_best_v2
        def encode(v):
            if type(v) is pandapowerNet:return ['pandapowerNet_FULL_SNAPSHOT',snapshot(v)]
            if type(v) in (dict,Counter):return [type(v).__module__+'.'+type(v).__qualname__,[[encode(k),encode(x)] for k,x in v.items()]]
            if type(v) in (list,tuple,deque):return [type(v).__module__+'.'+type(v).__qualname__,[encode(x) for x in v],v.maxlen if type(v) is deque else None]
            if type(v) is set:return ['builtins.set',sorted((encode(x) for x in v),key=lambda x:json.dumps(x,sort_keys=True))]
            return codec.typed(v,rt)
        def capture_frame():
            f=sys._getframe()
            while f is not None and f.f_code is not target.__code__:f=f.f_back
            assert f is not None,'Original controller frame missing'
            values={};unsupported={}
            for k,v in f.f_locals.items():
                try:values[k]=encode(v)
                except (TypeError,ValueError,AssertionError,NotImplementedError):unsupported[k]=type(v).__module__+'.'+type(v).__qualname__
            result=f.f_locals.get('result',{});counts['actual_commits']=len(result.get('executed_actions',[]));assert counts['actual_commits']==0
            assert set(('net','result','failed_sigs','failed_actions','feedback_state','it','zone','zs','global_uv'))<=set(values),'Critical causal field not represented'
            return {'source_line':f.f_lineno,'typed_locals':values,'unsupported_nonrestored_locals':unsupported,'python_rng':codec.typed(random.getstate(),rt),'numpy_rng':codec.typed(np.random.get_state(),rt),'not_a_resumed_suspended_frame':True}
        def physics(net,**kwargs):
            bound();counts['logical_PF_calls']+=1
            if counts['logical_PF_calls']==1:
                actual=snapshot(net);assert actual==snapshot(saved_before) and kwargs==rec['kwargs'],'Original initial input not exact paid source; stop before any solve'
                put(O/'Actual_Initial_Input.json',actual);net.clear();net.update(copy.deepcopy(saved_after));counts['initial_paid_PF_reuses']+=1;return
            put(O/'Pending_Native_Input.json',{'full_snapshot':snapshot(net),'kwargs':kwargs,'classification':'UNBOUND_NATIVE_IDENTITY_NOT_CLAIMED_UNEXECUTED','new_public_or_backend_call':False})
            put(O/'Boundary_Source_Frame.json',capture_frame());raise Frontier('NATIVE_IDENTITY_NOT_YET_BOUND',{'logical_PF_call':counts['logical_PF_calls'],'new_native_conversion_or_solve':False})
        def model(messages):
            bound();counts['logical_generation_calls']+=1
            try:answer=bridge(messages)
            except Frontier:
                put(O/'Boundary_Source_Frame.json',capture_frame());raise
            counts['paid_reply_uses']+=1;return answer
        oldpf=pp.runpp;oldgen=runner.base_runner.generate_response;pp.runpp=physics;runner.base_runner.generate_response=lambda body,tokenizer,messages:model(messages)
        random.seed(p['seed']);np.random.seed(p['seed'])
        try:
            result=target(scenario,base,zones,v2,object(),object(),'reflection_v2')
            raise AssertionError('Controller unexpectedly ended before an admitted frontier')
        finally:runner.base_runner.generate_response=oldgen
    except Frontier as exc:frontier={'kind':exc.kind,'payload':exc.payload}
    except BaseException:failure=traceback.format_exc()
    finally:
        sys.setprofile(old_profile)
        if oldpf is not None:pp.runpp=oldpf
        bound(True)
        if bridge:put(O/'Paid_Model_Checkpoint.json',bridge.snapshot())
        put(O/'Result.json',{'status':'COMPLETE_PAID_DISABLED_CAUSAL_FRONTIER' if frontier and failure is None and frontier['kind'] in ('MISSING_DISABLED_GENERATION','NATIVE_IDENTITY_NOT_YET_BOUND') else 'PARTIAL_FRONTIER_UNKNOWN','frontier':frontier,'failure':failure,'counts':counts,'workflow_seconds':time.monotonic()-began,'CPU_seconds':time.process_time()-cpu,'historical_costs_ref':p['historical_costs_ref'],'no_performance_or_full_trajectory_claim':True})
        put(O/'Closed_Manifest.json',{'members':{f.relative_to(O).as_posix():{'bytes':f.stat().st_size,'sha256':digest(f)} for f in O.rglob('*') if f.is_file()}})
        if failure or not frontier or frontier['kind'] not in ('MISSING_DISABLED_GENERATION','NATIVE_IDENTITY_NOT_YET_BOUND'):raise SystemExit(1)
if __name__=='__main__':main()
