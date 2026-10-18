"""New-mode chunked history adapter; original physical commit/state function ASTs.

This is a component, never a scientific owner or old-study resume mechanism.
"""
import ast,hashlib,json
from pathlib import Path
import paid_joint_commit_v1 as original
from bounded_chunk_evidence_store_v1_20261015 import Store,restore as restore_chunks
SOURCE=Path(original.__file__);TREE=ast.parse(SOURCE.read_text(encoding='utf-8'))
FUNCTIONS=[n for n in TREE.body if isinstance(n,ast.FunctionDef)]
MODE='ACTUAL_PAID_PROTECTED_CHUNKED_RECEDING_LOOKAHEAD_V2'
environment=original.__dict__.copy();environment['MODE']=MODE
exec(compile(ast.Module(body=FUNCTIONS,type_ignores=[]),str(SOURCE),'exec'),environment)
for definition in FUNCTIONS:globals()[definition.name]=environment[definition.name]
HISTORY_KEY='__COMPLETE_DURABLE_PAID_QUERY_HISTORY_PREFIX__'
SOURCE_CERTIFICATE={'original_source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'all_original_commit_validate_state_save_restore_function_ASTs_exact':True,
    'change':'New isolated MODE and chunked history transport only. No action/operation/cap/protection/cost semantic change.',
    'no_scientific_launch_or_automatic_old_resume':True}

class History:
    def __init__(self,path,*,source_anchor,input_anchor,max_bytes):
        self.store=Store(path,source_anchor=source_anchor,input_anchor=input_anchor,max_total_bytes=max_bytes)
        self.source=source_anchor;self.input=input_anchor;self.previous='0'*64;self.count=0
    def append(self,event,payload):
        record={'event':event,'payload':payload,'previous':self.previous,'source_anchor':self.source,'input_anchor':self.input}
        encoded=json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        self.store.append(f'{self.count:08d}:{event}',encoded)
        self.previous=hashlib.sha256(encoded).hexdigest();self.count+=1
    def anchor(self):
        value=self.store.anchor();value['logical_last_record_sha256']=self.previous;return value
    def close(self):self.store.close()

def verify_history(anchor):
    blocks=restore_chunks(anchor);records=[];previous='0'*64
    for i,block in enumerate(blocks):
        record=json.loads(block['payload'])
        assert record['previous']==previous and record['source_anchor']==anchor['source_anchor'] and record['input_anchor']==anchor['input_anchor']
        assert block['event_id']==f'{i:08d}:'+record['event']
        previous=hashlib.sha256(block['payload']).hexdigest();records.append(record)
    assert previous==anchor['logical_last_record_sha256']
    return records

def save_complete(path,state,anchors):
    assert HISTORY_KEY in state['paid_query_registry'];verify_history(state['paid_query_registry'][HISTORY_KEY])
    return save(path,state,anchors)

def restore_complete(path,receipt):
    state=restore(path,receipt)
    assert HISTORY_KEY in state['paid_query_registry']
    return state,verify_history(state['paid_query_registry'][HISTORY_KEY])
