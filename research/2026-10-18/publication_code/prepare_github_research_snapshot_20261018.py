"""Non-destructive public-repo snapshot, explicit full inventory and secret screening.

Large raw files remain local with an explicit NOT_UPLOADED record. No scientific
data is regenerated, no environment/cache/credential store is exported.
"""
import gzip,hashlib,json,os,re,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R/'outputs/github_publication_20261018';S=B/'snapshot'
MAX_FILE=8*1024**2;PACK_RAW=16*1024**2
IGNORE={'__pycache__','.git','node_modules','.venv','venv','env','site-packages','reporting_matplotlib_cache','vcsa_public_base_cache','tokenizer_cache'}
IGNORE_PREFIX=('cpu_gguf_runtime','github_publication_20261018')
SECRET_NAME=re.compile(r'(^\.env($|\.)|application_default_credentials|(^|[._-])(credentials|cookies|client_secret)([._-]|$)|\.pem$|\.key$)',re.I)
SECRET=[re.compile(x,re.I) for x in [r'gh[pousr]_[A-Za-z0-9_]{25,}',r'github_pat_[A-Za-z0-9_]{25,}',r'hf_[A-Za-z0-9]{25,}',r'AIza[A-Za-z0-9_-]{30,}',r'ya29\.[A-Za-z0-9._-]{25,}',r'1//[A-Za-z0-9_-]{35,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'colab-runtime-proxy-token=[A-Za-z0-9._%=-]{20,}',r'["\x27](?:access_token|refresh_token|client_secret|api_key|auth_token|runtime_proxy_token|token)["\x27]\s*[:=]\s*["\x27][A-Za-z0-9._/=+-]{25,}["\x27]']]
TEXT={'.py','.m','.md','.txt','.json','.jsonl','.csv','.tsv','.yml','.yaml','.toml','.ps1','.sh','.jl','.r','.ipynb','.tex','.bib','.log','.html','.js','.ts','.css','.svg'}
BIN={'.npz','.npy','.png','.jpg','.jpeg','.pdf','.pt','.safetensors','.pkl','.pickle','.gz'}
PUBLIC_TOKENIZER='c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539'
def digest(b):return hashlib.sha256(b).hexdigest()
def put(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')
def main():
    started=time.perf_counter();S.mkdir(parents=True,exist_ok=False);(B/'objects').mkdir()
    included=[];inventory=[];ignored=[];secret_paths=[];unique={};counts={}
    files=[p for p in R.iterdir() if p.is_file()]
    for folder in ['work','outputs']:
        for base,dirs,names in os.walk(R/folder):
            kept=[]
            for name in dirs:
                p=Path(base)/name
                if name in IGNORE or name.endswith('_env') or name.startswith(IGNORE_PREFIX):ignored.append(str(p.relative_to(R)).replace('\\','/'))
                else:kept.append(name)
            dirs[:]=kept
            files.extend(Path(base)/n for n in names)
    for i,path in enumerate(sorted(files,key=lambda p:str(p).casefold())):
        rel=path.relative_to(R).as_posix()
        try:size=path.stat().st_size
        except OSError:inventory.append({'path':rel,'status':'UNREADABLE_NOT_UPLOADED'});continue
        row={'path':rel,'bytes':size};suffix=path.suffix.lower()
        if SECRET_NAME.search(path.name):row['status']='WITHHELD_POSSIBLE_CREDENTIAL_FILE';secret_paths.append(rel)
        elif size>MAX_FILE:row['status']='LARGE_RAW_ARTIFACT_LOCAL_ONLY_NOT_UPLOADED'
        elif suffix not in TEXT|BIN and path.name not in ['LICENSE','owner.claim','requirements.txt']:
            row['status']='CONTAINER_BINARY_OR_UNKNOWN_TYPE_LOCAL_ONLY_NOT_UPLOADED'
        else:
            raw=path.read_bytes();h=digest(raw);row['sha256']=h
            secret=False
            if suffix in TEXT and h!=PUBLIC_TOKENIZER:
                text=raw.decode('utf-8',errors='replace');secret=any(p.search(text) for p in SECRET)
            if secret:row['status']='WITHHELD_POSSIBLE_SECRET_CONTENT';secret_paths.append(rel)
            else:
                row['status']='INCLUDED_EXACT_BYTES';row['object']='objects/'+h
                included.append(row.copy())
                if h not in unique:
                    target=B/'objects'/h;target.write_bytes(raw);unique[h]={'path':target,'bytes':len(raw)}
        counts[row['status']]=counts.get(row['status'],0)+1;inventory.append(row)
        if i%1000==0:put(B/'Preparation_Progress.json',{'files_seen':i,'total':len(files),'unique_objects':len(unique),'seconds':time.perf_counter()-started})
    # Publication inventory never claims raw checkpoint/capsule backup completeness.
    with gzip.open(S/'All_Research_Artifact_Inventory.jsonl.gz','wt',encoding='utf-8') as f:
        for row in inventory:f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    put(S/'Snapshot_File_Map.json',{'files':included,'ignored_runtime_or_environment_directories':ignored,'raw_large_artifacts_not_uploaded':True})
    packs=[];batch=[];batch_bytes=0
    def pack(items):
        name=f'Research_Objects_{len(packs)+1:03d}.zip';dest=S/name
        with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for h in items:z.write(unique[h]['path'],'objects/'+h)
        with zipfile.ZipFile(dest) as z:assert z.testzip() is None
        packs.append({'path':name,'bytes':dest.stat().st_size,'sha256':digest(dest.read_bytes()),'objects':len(items)})
    for h,v in sorted(unique.items()):
        if batch and batch_bytes+v['bytes']>PACK_RAW:pack(batch);batch=[];batch_bytes=0
        batch.append(h);batch_bytes+=v['bytes']
    if batch:pack(batch)
    excluded=[row for row in inventory if row['status']!='INCLUDED_EXACT_BYTES']
    result={'at_utc':datetime.now(timezone.utc).isoformat(),'status':'PREPARED_NOT_PUSHED','repository':'Hannaancode/Reliability-First-Multi-Agent-LLM-Guided-Corrective-Voltage-Control-',
        'source_workspace':str(R),'research_files_inventoried':len(inventory),'research_bytes_inventoried':sum(x.get('bytes',0) for x in inventory),
        'included_files':len(included),'unique_objects':len(unique),'unique_uncompressed_bytes':sum(v['bytes'] for v in unique.values()),
        'not_uploaded_files':len(excluded),'not_uploaded_bytes':sum(x.get('bytes',0) for x in excluded),'status_counts':counts,'screened_secret_paths_withheld':secret_paths,
        'packs':packs,'pack_upload_bytes':sum(x['bytes'] for x in packs),'workflow_seconds':time.perf_counter()-started,
        'scope':'Exact-code/small-artifact publication plus explicit research artifact inventory; NOT a complete70GB raw-binary backup. No base-model cache/venv/credentials. File-size selection is outcome-independent.',
        'no_original_artifact_modified':True,'no_new_model_PF_solver_calls':True}
    put(S/'Snapshot_Manifest.json',result)
    print(json.dumps({k:result[k] for k in ['included_files','unique_objects','not_uploaded_files','pack_upload_bytes','workflow_seconds','status_counts']}))
if __name__=='__main__':main()
