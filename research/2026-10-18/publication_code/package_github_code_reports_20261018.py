"""Package already screened exact source/reports; never regenerate research."""
import gzip, hashlib, json, re, zipfile
from pathlib import Path
from datetime import datetime, timezone

R=Path(__file__).resolve().parents[1]
B=R/'outputs/github_publication_20261018'
D=B/'code_reports'; D.mkdir(exist_ok=False)
rows=json.loads((B/'snapshot/Snapshot_File_Map.json').read_text(encoding='utf-8'))['files']
CODE={'.py','.m','.ps1','.sh','.jl','.r','.ipynb','.js','.ts','.css','.html'}
DOC={'.md','.txt','.tex','.bib','.csv','.tsv','.yml','.yaml','.toml'}
REPORT=re.compile(r'(audit|result|decision|protocol|readiness|checkpoint|manifest|completion|cost|summary|stop|proof|status|resume|gate|inventory|lock|ack)',re.I)
selected={}
for row in rows:
    p=Path(row['path']); ext=p.suffix.lower()
    cat='source' if ext in CODE else 'documents' if ext in DOC else 'reports' if ext=='.json' and REPORT.search(p.stem) and row['bytes']<=1048576 else None
    if cat:selected[row['path']]={**row,'category':cat}
packs=[]
for cat in ['source','documents','reports']:
    members=[v for v in selected.values() if v['category']==cat]
    name=cat+'_exact_files.zip'; dest=D/name
    with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for row in members:
            raw=(B/row['object']).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==row['sha256']
            z.writestr(row['path'],raw)
            row['remote_archive']=name
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        for row in members:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
    packs.append({'path':name,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'files':len(members),'original_bytes':sum(x['bytes'] for x in members)})
inventory=[]
with gzip.open(B/'snapshot/All_Research_Artifact_Inventory.jsonl.gz','rt',encoding='utf-8') as f:
    for line in f:
        v=json.loads(line); v['local_preparation_status']=v.pop('status')
        if v['path'] in selected:
            v['publication_status']='SELECTED_FOR_PUBLICATION_PENDING_REMOTE_VERIFICATION'
            v['remote_archive']=selected[v['path']]['remote_archive'];v['archive_member']=v['path']
        else:v['publication_status']='LOCAL_ONLY_NOT_UPLOADED'
        v.pop('object',None); inventory.append(v)
with gzip.open(D/'All_Artifact_Coverage.jsonl.gz','wt',encoding='utf-8') as f:
    for v in inventory:f.write(json.dumps(v,separators=(',',':'))+'\n')
with gzip.open(D/'Published_File_Map.json.gz','wt',encoding='utf-8') as f:
    json.dump({'files':list(selected.values())},f,separators=(',',':'))
out={'at_utc':datetime.now(timezone.utc).isoformat(),'status':'PREPARED_PENDING_REMOTE_VERIFICATION','selection':'All screened code and documentation extensions; all screened JSON reports with audit/result/decision/protocol/readiness/checkpoint/manifest/completion/cost/summary/stop/proof/status/resume/gate/inventory/lock/ack in filename and <=1MiB. Outcome-independent selection. Exact bytes; no scientific reruns.',
     'inventoried_files':len(inventory),'inventoried_bytes':sum(x.get('bytes',0) for x in inventory),'selected_files':len(selected),'selected_original_bytes':sum(x['bytes'] for x in selected.values()),'not_uploaded_files':len(inventory)-len(selected),'not_uploaded_bytes':sum(x.get('bytes',0) for x in inventory if x['path'] not in selected),'packs':packs,'limitations':'NOT a complete raw binary/checkpoint/capsule/journal backup. Large raw files, non-selected arrays and per-record files remain local. Credentials, environment directories and downloaded base caches excluded. Core snapshot files may also be directly available outside these archives.',
     'archive_CRC_and_every_member_SHA256':'PASS','new_model_PF_solver_optimizer_calls':0}
(D/'Publication_Coverage_Manifest.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out))
