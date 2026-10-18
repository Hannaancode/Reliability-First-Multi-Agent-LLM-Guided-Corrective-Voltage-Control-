"""Complete paired-scale checkpoints; no model loading or scientific retry."""
import hashlib, json, os
from pathlib import Path
import torch
from candidate_complete_state_and_transfer_v2 import cpu_tree, capture_rng, restore_rng

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def atomic(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp')
    with tmp.open('w',encoding='utf8') as f:json.dump(v,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    tmp.replace(p)

def active(model):return {n:p for n,p in model.named_parameters() if p.requires_grad}

def snapshot(model,opt,scaler,cursor,contract):
    value={'parameters':cpu_tree(active(model)),'optimizer':cpu_tree(opt.state_dict()),
           'names':list(active(model)),'scaler':scaler.state_dict(),'rng':capture_rng(),
           'cursor':cursor,'contract':contract}
    verify(value,contract);return value

def verify(v,contract):
    assert set(v)=={'parameters','optimizer','names','scaler','rng','cursor','contract'}
    assert v['contract']==contract and v['names']==list(v['parameters'])
    assert len(v['names'])==len(set(v['names'])) and all('.lora_' in n for n in v['names'])
    c=v['cursor'];assert c['microsteps']%4==0 and c['optimizer_steps']==c['microsteps']//4
    assert c['microsteps'] in range(681) and c['next_epoch']==c['microsteps']//340+1 and c['next_offset']==c['microsteps']%340
    groups=v['optimizer']['param_groups'];assert len(groups)==1 and len(groups[0]['params'])==len(v['names'])
    assert groups[0]['lr']==.0002 and groups[0]['weight_decay']==.01
    state=v['optimizer']['state'];assert set(state)==(set(groups[0]['params']) if c['optimizer_steps'] else set())
    for i,n in zip(groups[0]['params'],v['names']):
        p=v['parameters'][n];assert p.dtype==torch.float32 and torch.isfinite(p).all().item()
        if c['optimizer_steps']:
            m=state[i];assert int(m['step'])==c['optimizer_steps']
            assert m['exp_avg'].shape==m['exp_avg_sq'].shape==p.shape
            assert torch.isfinite(m['exp_avg']).all().item() and torch.isfinite(m['exp_avg_sq']).all().item()
    assert len(v['rng']['torch_CUDA'])==1
    return True

def restore(model,opt,scaler,v,contract):
    verify(v,contract);pp=active(model);assert list(pp)==v['names']
    with torch.no_grad():
        for n,p in pp.items():p.copy_(v['parameters'][n].to(p.device))
    opt.load_state_dict(v['optimizer']);scaler.load_state_dict(v['scaler']);restore_rng(v['rng'])
    for n,p in pp.items():assert torch.equal(p.detach().cpu(),v['parameters'][n])
    saved=cpu_tree(opt.state_dict())
    for i,s in saved['state'].items():
        for name,t in s.items():assert torch.equal(t,v['optimizer']['state'][i][name]) if isinstance(t,torch.Tensor) else t==v['optimizer']['state'][i][name]
    return True

def frozen_hashes(model):
    result={}
    for n,t in model.state_dict().items():
        if '.lora_' in n:continue
        p=t.detach().cpu().contiguous();raw=p.reshape(-1).view(torch.uint8).numpy()
        result[n]={'shape':list(p.shape),'dtype':str(p.dtype),'sha256':hashlib.sha256(memoryview(raw)).hexdigest()}
    return result
