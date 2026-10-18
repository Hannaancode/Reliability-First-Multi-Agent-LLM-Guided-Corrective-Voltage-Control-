"""Credential-screened local data bridge to the connected GitHub tools."""
import argparse,base64,hashlib,json
from pathlib import Path
from prepare_github_research_snapshot_20261018 import SECRET,SECRET_NAME,PUBLIC_TOKENIZER,TEXT
R=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--relative',required=True);p.add_argument('--offset',type=int,default=0);p.add_argument('--count',type=int,default=200000);p.add_argument('--text',action='store_true');a=p.parse_args()
    path=(R/a.relative).resolve();assert path.is_relative_to(R) and path.is_file() and not SECRET_NAME.search(path.name)
    raw=path.read_bytes();h=hashlib.sha256(raw).hexdigest()
    if path.suffix.lower() in TEXT and h!=PUBLIC_TOKENIZER:
        text=raw.decode('utf-8');assert not any(x.search(text) for x in SECRET),'Possible credential content: do not export'
    if a.text:
        print(json.dumps({'relative':a.relative,'bytes':len(raw),'sha256':h,'content':raw.decode('utf-8')}));return
    chunk=raw[a.offset:a.offset+a.count]
    print(json.dumps({'relative':a.relative,'file_bytes':len(raw),'file_sha256':h,'offset':a.offset,'bytes':len(chunk),'base64':base64.b64encode(chunk).decode()}))
if __name__=='__main__':main()
