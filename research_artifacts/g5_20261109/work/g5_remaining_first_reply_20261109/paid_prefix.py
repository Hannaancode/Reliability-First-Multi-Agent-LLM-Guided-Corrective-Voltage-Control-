"""One paid adapter-off reply at the original generation boundary; no inference."""
import hashlib
import json
import os
from pathlib import Path

MODE='ORIGINAL118_PRIVATE_LORA_DISABLED'
class Frontier(BaseException):
    def __init__(self,kind,payload):self.kind,self.payload=kind,payload
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(v):return hashlib.sha256(canonical(v)).hexdigest()
def put(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False);f.flush();os.fsync(f.fileno())

class PaidFirstReply:
    def __init__(self,bundle,case_index,journal_path):
        assert bundle['adapter_mode']==MODE
        assert type(case_index) is int and 0<=case_index<4
        self.row=bundle['rows'][case_index];self.bundle_sha256=sha(bundle)
        receipt=self.row['receipt'];assert receipt['case_id']==self.row['case_id'] and receipt['ordinal']==case_index
        assert receipt['request_key']==sha({'model_and_generation_contract':bundle['immutable_inference_contract'],'case_id':self.row['case_id'],'messages':self.row['messages'],'input_token_ids':self.row['input_token_ids']})
        assert receipt['RNG_before']==receipt['RNG_after'],'This finite paid-prefix bridge does not repair stochastic state'
        self.path=Path(journal_path);self.tip='0'*64;self.cursor=0;self.pending=None;self.events=[]
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                x=json.loads(line);assert x['previous']==self.tip and x['sha256']==sha({k:v for k,v in x.items() if k!='sha256'})
                assert x['bundle_sha256']==self.bundle_sha256 and x['case_id']==self.row['case_id']
                self.events.append(x);self.tip=x['sha256']
            if self.events:
                assert self.events[0]['kind']=='PAID_FIRST_REPLY_RESERVED'
                if len(self.events)>=2:
                    assert self.events[1]['kind']=='PAID_FIRST_REPLY_READY';self.cursor=1
                if len(self.events)>=3:
                    assert len(self.events)==3 and self.events[2]['kind']=='UNMEASURED_GENERATION_BOUNDARY'
                    self.pending=self.events[2]['data']
                if self.cursor==0:raise Frontier('UNCLOSED_PAID_USE_EXPOSURE_UNKNOWN',self.snapshot())
    def event(self,kind,data):
        x={'kind':kind,'data':data,'previous':self.tip,'bundle_sha256':self.bundle_sha256,'case_id':self.row['case_id']}
        x['sha256']=sha(x)
        with self.path.open('a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
        self.events.append(x);self.tip=x['sha256']
    def __call__(self,messages):
        if self.cursor==0:
            assert messages==self.row['messages'],'Original first causal messages changed; no cached substitution'
            receipt=self.row['receipt'];assert receipt['adapter_mode']==MODE and receipt['replica']=='primary'
            assert receipt['input_token_ids']==self.row['input_token_ids'] and receipt['adapter_disabled_during_every_forward'] is True
            self.event('PAID_FIRST_REPLY_RESERVED',{'receipt_ref':self.row['receipt_ref'],'request_key':receipt['request_key'],'messages_sha256':sha(messages)})
            # The journal is durable before caller exposure. A later cold read cannot prove caller exposure.
            self.event('PAID_FIRST_REPLY_READY',{'raw_text_sha256':sha(receipt['raw_text']),'recorded_RNG_after':receipt['RNG_after'],'new_model_calls':0})
            self.cursor=1
            return receipt['raw_text']
        pending={'case_id':self.row['case_id'],'adapter_mode':MODE,'logical_generation_ordinal':1,
                 'messages':messages,'messages_sha256':sha(messages),'measured':False,
                 'prior_paid_receipt_ref':self.row['receipt_ref'],'no_tokenization_or_generation':True}
        if self.pending is None:self.event('UNMEASURED_GENERATION_BOUNDARY',pending);self.pending=pending
        else:assert self.pending==pending,'Conflicting pending generation on cold metadata continuation'
        raise Frontier('MISSING_DISABLED_GENERATION',pending)
    def snapshot(self):
        return {'bundle_sha256':self.bundle_sha256,'case_id':self.row['case_id'],'paid_reply_cursor':self.cursor,
                'journal_tip':self.tip,'events':len(self.events),'pending':self.pending,
                'caller_exposure_after_fsync':'UNKNOWN_FROM_JOURNAL_ALONE','cold_scope':'PAID_GENERATION_PREFIX_METADATA_ONLY_NOT_CONTROLLER_RESTART'}
