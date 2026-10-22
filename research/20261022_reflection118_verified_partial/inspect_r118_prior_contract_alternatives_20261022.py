"""Targeted saved-reference coverage; no repeated physics, model or audit."""
import gzip, hashlib, json, pickle, sys, time, zlib
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'work'))
import candidate_process_runtime
sys.path.append(str(R/'work/physics_env/Lib/site-packages'))
from reflection118_chronological_core_20261022 import read,put,sha,frames_equal,decode as recent_decode
from prior_physical_query_footprints_20261018 import component,decode
from run_reflection118_chronological_local_20261022 import necessary

def main():
    import pandapower as pp
    def prohibited(*a,**k):raise AssertionError('Saved-reference inspection only')
    pp.runpp=prohibited
    O=R/'outputs/r118_prior_contract_alternatives_20261022';O.mkdir(exist_ok=False);start=time.monotonic()
    target=R/'outputs/r118chrono_20261022/local_controller/fed_combined_load_1p5_line_35_MG1/no_llm_fallback_first/pf_000006_before.zlib'
    net=pickle.loads(zlib.decompress(target.read_bytes()));key,_=component(net)
    indexpath=R/'outputs/prior_physical_query_footprints_20261018/actual/Physical_Component_Input_References.json.gz'
    refs=json.loads(gzip.decompress(indexpath.read_bytes())).get(key,[])
    sources={};rows=[];kw=dict(algorithm='nr',init='auto',enforce_q_lims=True,max_iteration=80,calculate_voltage_angles=True)
    for ref in refs:
        j=R/ref['journal'];before=decode(j.parent,ref['before'])
        if necessary(before)!=necessary(net):continue
        match=True
        try:frames_equal(net,before)
        except (AssertionError,KeyError,ValueError):match=False
        if str(j) not in sources:sources[str(j)]=[json.loads(x) for x in j.open('rb')]
        events=sources[str(j)];identity=ref['id']
        intents=[x['data'] for x in events if x.get('event')=='PF_intent' and x.get('data',{}).get('id',x.get('data',{}).get('identity'))==identity]
        returns=[x['data'] for x in events if x.get('event')=='PF_return' and x.get('data',{}).get('id',x.get('data',{}).get('identity'))==identity]
        row={'journal':ref['journal'],'id':identity,'exact_input_frames':match,'intents':len(intents),'returns':len(returns),
             'recorded_kwargs':intents[0].get('kwargs') if len(intents)==1 else None,'reference':ref}
        row['exact_required_contract']=bool(match and len(intents)==1 and row['recorded_kwargs']==kw and len(returns)==1 and 'after' in returns[0])
        rows.append(row)
    extraspath=R/'outputs/reflection118_chronological_preparation_20261022/Additional_Prior_Attempt_References.json'
    extras=[x for x in read(extraspath).get(key,[]) if x['necessary_input']==necessary(net)]
    current=[]
    C=R/'outputs/r118chrono_20261022/local_controller'
    for p in C.glob('*/*/pf_*.json'):
        rec=read(p);before=recent_decode(p.parent,rec['before'])
        if component(before)[0]!=key or necessary(before)!=necessary(net):continue
        try:frames_equal(before,net)
        except (AssertionError,KeyError,ValueError):continue
        current.append({'record':p.relative_to(R).as_posix(),'sha256':sha(p),'kwargs':rec['kwargs'],'provenance':rec['provenance']['kind']})
    exact=[x for x in rows if x['exact_required_contract']]
    result={'status':'SAVED_REFERENCE_TARGET_LOOKUP_COMPLETE_NOT_UNIVERSAL_HISTORY_OR_REUSE_CERTIFICATE',
        'target':target.relative_to(R).as_posix(),'target_sha256':sha(target),
        'same_shunt_component_index_references':len(refs),'same_load_outage_references':len(rows),
        'exact_required_old_contract_alternatives':len(exact),'old_references':rows,
        'additional_scope_same_component_and_load':extras,'same_study_closed_same_input_records':current,
        'required_contract':kw,'source_pins':{p.relative_to(R).as_posix():sha(p) for p in [Path(__file__),indexpath,extraspath]},
        'coverage':'The prior60426-input index and separately prepared additional lineage index plus all closed current-study calls. Saved-snapshot/untracked histories are not universally resolved.',
        'interpretation':'Any exact alternative is a candidate requiring provenance/use gates. Absence is only scoped; the blocked50/80contract remainsUNKNOWN and cannot be repeated automatically.',
        'new_PF_model_optimizer_converter_derivative_factor_solve_calls':0,'workflow_seconds':time.monotonic()-start}
    put(O/'Prior_Contract_Alternative_Coverage.json',result)
    put(O/'Closed_Manifest.json',{'members':{p.name:sha(p) for p in O.iterdir() if p.is_file()}})
    print(json.dumps({k:result[k] for k in ['same_shunt_component_index_references','same_load_outage_references',
        'exact_required_old_contract_alternatives','same_study_closed_same_input_records','new_PF_model_optimizer_converter_derivative_factor_solve_calls','workflow_seconds']}))

if __name__=='__main__':main()
