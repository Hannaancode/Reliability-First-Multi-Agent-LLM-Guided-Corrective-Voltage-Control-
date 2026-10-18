"""Actual saved35MB record boundary test, zero new physical/model calls."""
import copy,hashlib,json,os,shutil,struct,time
from pathlib import Path
from bounded_chunk_evidence_store_v1_20261015 import Store,restore,MAX_INDEX_FRAME,CHUNK_BYTES
R=Path(__file__).resolve().parents[1];B=R/'outputs/bounded_chunk_actual_history_engineering_20261015'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    started=time.perf_counter();B.mkdir(exist_ok=False);source=R/'outputs/full_receding_paid_campaign_20261015/actual/Complete_Runtime_History.bin'
    with source.open('rb') as f:
        for index in range(51):
            n=struct.unpack('<Q',f.read(8))[0]
            if index<50:f.seek(n,1)
            else:raw=f.read(n)
    assert len(raw)==35228332 and len(raw)>32*1024**2
    original=hashlib.sha256(raw).hexdigest();source_anchor=sha(R/'work/bounded_chunk_evidence_store_v1_20261015.py')
    store=Store(B/'actual_record',source_anchor=source_anchor,input_anchor=original,max_total_bytes=2*1024**3)
    anchor=store.append('actual_saved_record50_software_fixture_only',raw);store.close()
    recovered=restore(anchor);assert len(recovered)==1 and recovered[0]['payload']==raw
    controls={'actual35228332byte_record_roundtrip_exact':True,'bounded_index_vs_32MiB_failure':anchor['index_bytes']<MAX_INDEX_FRAME+8,
        'every_chunk_at_most1MiB':all(p.stat().st_size<=CHUNK_BYTES for p in (B/'actual_record/objects').iterdir())}
    def rejected(name,fn):
        try:fn()
        except (ValueError,FileNotFoundError):controls[name]=True
        else:raise AssertionError(name+' not rejected')
    altered=copy.deepcopy(anchor);altered['source_anchor']='a'*64;rejected('wrong_source_anchor_rejected',lambda:restore(altered))
    altered=copy.deepcopy(anchor);altered['input_anchor']='b'*64;rejected('wrong_input_anchor_rejected',lambda:restore(altered))
    altered=copy.deepcopy(anchor);altered['index_bytes']-=1;rejected('stale_or_torn_prefix_rejected',lambda:restore(altered))
    obj=next((B/'actual_record/objects').iterdir());original_chunk=obj.read_bytes()
    obj.write_bytes(bytes([original_chunk[0]^1])+original_chunk[1:]);rejected('changed_chunk_rejected',lambda:restore(anchor));obj.write_bytes(original_chunk)
    renamed=obj.with_suffix('.missing');obj.rename(renamed);rejected('missing_chunk_rejected',lambda:restore(anchor));renamed.rename(obj)
    limited=Store(B/'bound_rejection',source_anchor=source_anchor,input_anchor=original,max_total_bytes=16)
    rejected('fixed_storage_bound_rejected_before_payload_write',lambda:limited.append('no-room',b'payload'));limited.close()
    assert list((B/'bound_rejection/objects').iterdir())==[] and (B/'bound_rejection/index.bin').stat().st_size==0
    small=Store(B/'duplicate_and_stale',source_anchor=source_anchor,input_anchor=original,max_total_bytes=1024**2)
    early=small.append('first',b'first');rejected('duplicate_event_identity_rejected',lambda:small.append('first',b'repeat'))
    latest=small.append('second',b'second');small.close();rejected('old_cursor_after_later_commit_rejected',lambda:restore(early));assert [r['payload'] for r in restore(latest)]==[b'first',b'second']
    controls['complete_latest_two_record_cold_prefix_exact']=True
    assert hashlib.sha256(restore(anchor)[0]['payload']).hexdigest()==original
    result={'status':'PASS_ACTUAL_LARGE_RECORD_AND_FAIL_CLOSED_STORAGE_BOUNDARIES','controls':controls,
        'actual_old_fixture_source':str(source.relative_to(R)),'actual_old_record_index':50,'actual_payload_bytes':len(raw),'actual_payload_sha256':original,
        'new_index_bytes':anchor['index_bytes'],'new_object_files':len(list((B/'actual_record/objects').iterdir())),
        'new_component_source_sha256':source_anchor,'source_and_input_anchor':anchor,'workflow_seconds':time.perf_counter()-started,
        'new_PF_model_derivative_forecast_linear_solve_calls':0,'old_runtime_or_study_changed_or_resumed':False,
        'limits':'Storage component only. No full controller/RNG/cost checkpoint cold integration or scientific resume permission. Old26th complete controller state remains unrecovered; oldpartial/audit failures unchanged.'}
    with (B/'Results.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.flush();os.fsync(f.fileno())
    print(json.dumps({'bounded_actual_record_engineering':'PASS','controls':len(controls),'new_science_calls':0}))
if __name__=='__main__':main()
