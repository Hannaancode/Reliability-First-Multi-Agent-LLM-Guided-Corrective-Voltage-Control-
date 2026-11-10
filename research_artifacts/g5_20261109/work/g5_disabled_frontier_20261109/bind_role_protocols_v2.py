"""Additive exact role-protocol binding, zero native/model/controller work."""
import ast,hashlib,json,os
from pathlib import Path
R=Path(__file__).resolve().parents[2];W=R/'work/g5_disabled_frontier_20261109';P=R/'outputs/g5_disabled_frontier_20261109'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(v if isinstance(v,str) else json.dumps(v,indent=2)+'\n');f.flush();os.fsync(f.fileno())
def ref(p):return {'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
for name in ('owner','reader','coordinate'):
    text=(W/(name+'.py')).read_text(encoding='utf-8').replace("P/'Protocol.json'","P/'Protocol_v2.json'")
    if name=='coordinate':text=text.replace("role+'_Protocol.json'","role+'_Protocol_v2.json'")
    ast.parse(text);put(W/(name+'_v2.py'),text)
protocol=read(P/'Protocol.json')
for name in ('owner','reader'):
    p=read(P/(name+'_Protocol.json'));p['single_owner']['source']=(W/(name+'_v2.py')).relative_to(R).as_posix();p['single_owner']['sha256']=sha(W/(name+'_v2.py'));put(P/(name+'_Protocol_v2.json'),p)
for path in [W/'owner_v2.py',W/'reader_v2.py',W/'coordinate_v2.py',W/'bind_role_protocols_v2.py',P/'owner_Protocol_v2.json',P/'reader_Protocol_v2.json']:
    protocol['source_input_sha256'][path.relative_to(R).as_posix()]=sha(path)
protocol['role_protocols']={'owner':ref(P/'owner_Protocol_v2.json'),'reader':ref(P/'reader_Protocol_v2.json')}
protocol['revision']='Additive exact role-protocol pins; owner/reader/coordinator all require same Protocol_v2 digest and independently bound FINAL_Gate. Original prepared source retained, zero execution.'
protocol['snapshot_scope']={'compared':'profile.live_snapshot full_fingerprint and full_typed_mapping, without reduced scientific projection','included':['every supported stored native mapping field/value/type','native class and ADict flag','recorded cross-field object aliases','column Index label bits and object alias groups','supported stored array/block/index strides and buffer overlap'],'excluded':['pickle-byte serialization equality','Python object or pandas manager addresses','arbitrary unsupported extension values or whole interpreter state'],'unsupported':'Fail closed; no type/missing-field fill or normalization fallback.'}
put(P/'Protocol_v2.json',protocol)
put(P/'Role_Binding_v2_Result.json',{'status':'PREPARED_REQUIRES_INDEPENDENT_SOURCE_GATE','protocol_ref':ref(P/'Protocol_v2.json'),'source_only':True,'previous_protocol_ref':ref(P/'Protocol.json'),'old_checks_rerun':False,'native_model_PF_controller_calls':0,'command':'work/vcsa_module_env/Scripts/python.exe -X utf8 work/g5_disabled_frontier_20261109/coordinate_v2.py'})
print(json.dumps({'protocol_ref':ref(P/'Protocol_v2.json'),'source_only':True}))
