"""Verify the published research snapshot; optionally extract into a NEW directory."""
import argparse, gzip, hashlib, json, zipfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archive-directory',type=Path,required=True)
    p.add_argument('--extract-to',type=Path)
    a=p.parse_args(); base=a.archive_directory.resolve()
    manifest=json.loads((base/'Publication_Coverage_Manifest.json').read_text(encoding='utf-8'))
    with gzip.open(base/'Published_File_Map.json.gz','rt',encoding='utf-8') as f:rows=json.load(f)['files']
    count=0
    # Validate every archive and member before optional extraction.
    for pack in manifest['packs']:
        file=base/pack['path']; assert file.stat().st_size==pack['bytes']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==pack['sha256']
        expected=[r for r in rows if r['remote_archive']==pack['path']]
        with zipfile.ZipFile(file) as z:
            assert z.testzip() is None
            assert set(z.namelist())=={r['path'] for r in expected}
            for r in expected:
                raw=z.read(r['path']);assert len(raw)==r['bytes']
                assert hashlib.sha256(raw).hexdigest()==r['sha256'];count+=1
    assert count==manifest['selected_files']
    if a.extract_to:
        target=a.extract_to.resolve();target.mkdir(parents=True,exist_ok=False)
        for pack in manifest['packs']:
            with zipfile.ZipFile(base/pack['path']) as z:
                for name in z.namelist():
                    out=(target/name).resolve();assert out.is_relative_to(target)
                    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(name))
    print(json.dumps({'status':'PASS','files':count,'extracted':bool(a.extract_to),'new_scientific_calls':0}))
if __name__=='__main__':main()
