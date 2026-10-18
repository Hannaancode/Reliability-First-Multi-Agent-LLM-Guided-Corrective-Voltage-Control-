"""Additive storage component only; no controller/science/resume authorization.

Payload chunks are fsynced before an atomic logical commit is acknowledged.
Only the newest exact journal anchor is readable; missing/torn/stale evidence
fails closed. Callers must separately preserve actual attempted/executed science.
"""
import hashlib,json,os,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CHUNK_BYTES=1024**2
MAX_RECORD_BYTES=64*1024**2
MAX_INDEX_FRAME=16*1024

def digest(b):return hashlib.sha256(b).hexdigest()
def encode(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def valid_hash(h):return isinstance(h,str) and len(h)==64 and all(c in '0123456789abcdef' for c in h)
def location(path):
    p=Path(path).resolve()
    if not p.is_relative_to(ROOT):raise ValueError('Outside workspace')
    return p

class Store:
    def __init__(self,path,*,source_anchor,input_anchor,max_total_bytes):
        if not valid_hash(source_anchor) or not valid_hash(input_anchor):raise ValueError('Exact SHA256 anchors required')
        if type(max_total_bytes) is not int or max_total_bytes<=0:raise ValueError('Fixed total byte bound required')
        self.root=location(path);self.root.mkdir(exist_ok=False);(self.root/'objects').mkdir()
        self.source=source_anchor;self.input=input_anchor;self.bound=max_total_bytes
        self.stream=(self.root/'index.bin').open('xb');self.last='0'*64;self.ids=set();self.count=0;self.used=0;self.prefix=hashlib.sha256()
    def append(self,event_id,raw):
        if not isinstance(event_id,str) or not event_id or len(event_id)>256 or event_id in self.ids:raise ValueError('New bounded event identity required')
        if type(raw) is not bytes or not 0<len(raw)<=MAX_RECORD_BYTES:raise ValueError('Record exceeds fixed maximum before any writes')
        parts=[raw[i:i+CHUNK_BYTES] for i in range(0,len(raw),CHUNK_BYTES)]
        refs=[{'sha256':digest(part),'bytes':len(part)} for part in parts]
        row={'event_id':event_id,'record_sha256':digest(raw),'record_bytes':len(raw),'parts':refs,'previous':self.last,'source_anchor':self.source,'input_anchor':self.input}
        encoded=encode(row)
        if len(encoded)>MAX_INDEX_FRAME:raise ValueError('Fixed index frame bound')
        new={r['sha256']:part for r,part in zip(refs,parts) if not (self.root/'objects'/(r['sha256']+'.bin')).exists()}
        frame=struct.pack('<Q',len(encoded))+encoded;extra=len(frame)+sum(map(len,new.values()))
        if self.used+extra>self.bound:raise ValueError('Fixed total storage bound; no extension')
        for r,part in zip(refs,parts):
            dest=self.root/'objects'/(r['sha256']+'.bin')
            if dest.exists():
                existing=dest.read_bytes()
                if existing!=part:raise ValueError('Existing immutable chunk mismatch')
            else:
                with dest.open('xb') as f:f.write(part);f.flush();os.fsync(f.fileno())
        self.stream.write(frame);self.stream.flush();os.fsync(self.stream.fileno())
        self.prefix.update(frame);self.used+=extra;self.last=digest(encoded);self.ids.add(event_id);self.count+=1
        return self.anchor()
    def anchor(self):
        return {'path':str(self.root.relative_to(ROOT)),'index_bytes':self.stream.tell(),'index_sha256':self.prefix.hexdigest(),
            'last_record_sha256':self.last,'records':self.count,'source_anchor':self.source,'input_anchor':self.input,
            'max_total_bytes':self.bound,'committed_physical_bytes':self.used,'codec':'bounded_chunk_store_v1_20261015'}
    def close(self):self.stream.close()

def restore(anchor):
    root=location(ROOT/anchor['path']);index=root/'index.bin'
    if anchor.get('codec')!='bounded_chunk_store_v1_20261015':raise ValueError('Wrong codec')
    if index.stat().st_size!=anchor['index_bytes']:raise ValueError('Missing/torn/stale journal; no cursor rollback')
    actual_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if actual_bytes>anchor['max_total_bytes'] or actual_bytes<anchor['committed_physical_bytes']:raise ValueError('Actual byte bound mismatch')
    prefix=hashlib.sha256();previous='0'*64;rows=[];ids=set()
    with index.open('rb') as f:
        while f.tell()<anchor['index_bytes']:
            head=f.read(8)
            if len(head)!=8:raise ValueError('Truncated header')
            length=struct.unpack('<Q',head)[0]
            if not 0<length<=MAX_INDEX_FRAME or f.tell()+length>anchor['index_bytes']:raise ValueError('Index frame bound')
            raw=f.read(length);row=json.loads(raw)
            if encode(row)!=raw or row['previous']!=previous or row['source_anchor']!=anchor['source_anchor'] or row['input_anchor']!=anchor['input_anchor']:raise ValueError('Source/input/chain mismatch')
            if row['event_id'] in ids or not 0<row['record_bytes']<=MAX_RECORD_BYTES:raise ValueError('Duplicate identity/record bound')
            if len(row['parts'])!=(row['record_bytes']+CHUNK_BYTES-1)//CHUNK_BYTES:raise ValueError('Chunk count mismatch')
            pieces=[]
            for i,ref in enumerate(row['parts']):
                if not valid_hash(ref['sha256']):raise ValueError('Invalid object key')
                expected=min(CHUNK_BYTES,row['record_bytes']-i*CHUNK_BYTES)
                if ref['bytes']!=expected:raise ValueError('Chunk byte bound')
                piece=(root/'objects'/(ref['sha256']+'.bin')).read_bytes()
                if len(piece)!=expected or digest(piece)!=ref['sha256']:raise ValueError('Chunk identity mismatch')
                pieces.append(piece)
            payload=b''.join(pieces)
            if len(payload)!=row['record_bytes'] or digest(payload)!=row['record_sha256']:raise ValueError('Whole payload identity mismatch')
            rows.append({'event_id':row['event_id'],'payload':payload,'record_sha256':row['record_sha256']});ids.add(row['event_id'])
            previous=digest(raw);prefix.update(head+raw)
    if prefix.hexdigest()!=anchor['index_sha256'] or previous!=anchor['last_record_sha256'] or len(rows)!=anchor['records']:raise ValueError('Final prefix mismatch')
    return rows
