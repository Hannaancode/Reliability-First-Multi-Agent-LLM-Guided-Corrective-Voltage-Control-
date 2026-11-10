"""Additive local-only denial/custody fix; no host import or remote calls."""
import ast, hashlib, json, os
from pathlib import Path
R=Path(__file__).resolve().parents[2]
W=R/'work/g5_original118_adapter_ablation_20261109'
P=R/'outputs/g5_original118_adapter_ablation_20261109/execution_preparation'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:
        f.write(v if isinstance(v,str) else json.dumps(v,indent=2)+'\n');f.flush();os.fsync(f.fileno())
def ref(p):return {'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
old=(W/'host.py').read_text(encoding='utf-8')
helper='''def allocation_recovery_disposition(error, stage, allocation_requests, runtime_allocated):
    status=getattr(getattr(error,'response',None),'status_code',None)
    denied=status in (401,403,429)
    uncertain=(stage=='allocating_one_selected_T4' and allocation_requests==1 and not runtime_allocated
      and not denied and (isinstance(error,(requests.exceptions.Timeout,requests.exceptions.ConnectionError))
      or (isinstance(error,requests.exceptions.HTTPError) and isinstance(status,int) and status>=500)))
    return {'failure_http_status':status,'definite_denial':denied,'allocation_outcome_uncertain':uncertain}

'''
assert old.count('def main():')==1
new=old.replace('def main():',helper+'def main():',1)
a="""    except BaseException as error:
        state.update(stage='failed_or_uncertain_preserved_attempt',failure_type=type(error).__name__);save()
        if state['science_started']:
"""
b="""    except BaseException as error:
        state.update(allocation_recovery_disposition(error,state['stage'],state['allocation_requests'],state['runtime_allocated']))
        state.update(stage='failed_or_uncertain_preserved_attempt',failure_type=type(error).__name__);save()
        if state['science_started'] and not state.get('definite_denial'):
"""
assert new.count(a)==1;new=new.replace(a,b)
a="if client and state['allocation_requests']==1 and not state['runtime_allocated']:"
b="if client and state.get('allocation_outcome_uncertain') and not state.get('definite_denial') and state['allocation_requests']==1 and not state['runtime_allocated']:"
assert new.count(a)==1;new=new.replace(a,b)
ast.parse(new);put(W/'host_v2.py',new)
reader=(W/'saved_reader_v2.py').read_text(encoding='utf-8')
assert reader.count('Primary_Owner_Protocol.json')==1
reader=reader.replace('Primary_Owner_Protocol.json','Primary_Owner_Protocol_v2.json');ast.parse(reader);put(W/'saved_reader_v3.py',reader)
coord=(W/'coordinator_v2.py').read_text(encoding='utf-8')
coord=coord.replace('Reader_Owner_Protocol_v2.json','Reader_Owner_Protocol_v3.json').replace('Primary_Owner_Protocol.json','Primary_Owner_Protocol_v2.json')
ast.parse(coord);put(W/'coordinator_v3.py',coord)
primary=read(P/'Primary_Owner_Protocol.json');primary['single_owner'].update(source=(W/'host_v2.py').relative_to(R).as_posix(),sha256=sha(W/'host_v2.py'));put(P/'Primary_Owner_Protocol_v2.json',primary)
readerp=read(P/'Reader_Owner_Protocol_v2.json');readerp['single_owner'].update(source=(W/'saved_reader_v3.py').relative_to(R).as_posix(),sha256=sha(W/'saved_reader_v3.py'));put(P/'Reader_Owner_Protocol_v3.json',readerp)
# New meaningful pure classification checks, no requests/host import and no native entry.
class E(Exception):
    def __init__(self,status=None):self.response=type('Response',(),{'status_code':status})()
class Timeout(E):pass
class ConnectionError(E):pass
class HTTPError(E):pass
requests=type('Requests',(),{'exceptions':type('Exceptions',(),{'Timeout':Timeout,'ConnectionError':ConnectionError,'HTTPError':HTTPError})})()
fn=next(n for n in ast.parse(helper).body if isinstance(n,ast.FunctionDef));ns={'requests':requests}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'<pure-denial-predicate>','exec'),ns)
checks=[]
for status in (401,403,429):
    x=ns[fn.name](HTTPError(status),'allocating_one_selected_T4',1,False)
    assert x['definite_denial'] and not x['allocation_outcome_uncertain'] and x['failure_http_status']==status
    checks.append('definite_'+str(status)+'_no_GET')
for error in (Timeout(),ConnectionError(),HTTPError(503)):
    x=ns[fn.name](error,'allocating_one_selected_T4',1,False);assert x['allocation_outcome_uncertain'];checks.append(type(error).__name__+'_exact_assignment_recovery_only')
for error,stage,allocated in ((RuntimeError(),'allocating_one_selected_T4',False),(HTTPError(400),'allocating_one_selected_T4',False),(Timeout(),'preconditions',False),(Timeout(),'allocating_one_selected_T4',True)):
    assert not ns[fn.name](error,stage,1,allocated)['allocation_outcome_uncertain'];checks.append('not_uncertain_'+type(error).__name__+'_'+stage+'_'+str(allocated))
receipt={'status':'PASS_LOCAL_ONLY_DENIAL_BOUNDARY','checks':checks,'count':len(checks),'actual_network_GPU_model_native_calls':0,'preserved_source_ref':ref(W/'host.py'),'new_source_ref':ref(W/'host_v2.py'),'scope':'Definite denial never triggers exact-assignment recovery GET or closed-artifact retry; only uncertain assignment transport permits exact identity recovery. Cleanup/release remains required when a runtime was actually allocated.'}
put(P/'Local_Denial_Boundary_Checks.json',receipt)
gate=read(P/'Prepared_Launch_Bindings_v3.json')
for p in [W/'host_v2.py',W/'saved_reader_v3.py',W/'coordinator_v3.py',W/'finalize_local_admission_v2.py',P/'Primary_Owner_Protocol_v2.json',P/'Reader_Owner_Protocol_v3.json',P/'Local_Denial_Boundary_Checks.json']:
    gate['source_hashes'][p.relative_to(R).as_posix()]=sha(p)
gate.update(coordinator_source=(W/'coordinator_v3.py').relative_to(R).as_posix(),primary_owner_protocol=(P/'Primary_Owner_Protocol_v2.json').relative_to(R).as_posix(),reader_owner_protocol=(P/'Reader_Owner_Protocol_v3.json').relative_to(R).as_posix(),delta='Additive local definite-denial recovery guard; remote scientific payload/mode/generation/bounds unchanged. Previous source/protocols retained. Saved reader and coordinator only update exact host protocol path.')
put(P/'Prepared_Launch_Bindings_v4.json',gate)
print(json.dumps({'binding':ref(P/'Prepared_Launch_Bindings_v4.json'),'host':ref(W/'host_v2.py'),'reader':ref(W/'saved_reader_v3.py'),'coordinator':ref(W/'coordinator_v3.py'),'pure_checks':len(checks),'science_calls':0}))
