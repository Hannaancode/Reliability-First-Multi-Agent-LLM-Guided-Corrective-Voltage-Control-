"""One frozen paired-scale arm; full-context QLoRA, no scientific retry."""
import argparse,gc,hashlib,json,os,signal,time,traceback
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8',HF_HUB_DISABLE_IMPLICIT_TOKEN='1')
import torch,numpy as np,random
from transformers import AutoModelForCausalLM,AutoTokenizer,BitsAndBytesConfig,GenerationConfig
from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
from matched_scale_state import active,atomic,sha,snapshot,restore,frozen_hashes
from candidate_complete_state_and_transfer_v2 import capture_rng
from relational_delta_transfer import make_delta_package

ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT);p=argparse.ArgumentParser();p.add_argument('--arm',required=True);arm=p.parse_args().arm
PREP=ROOT/'prep';proto=json.loads((PREP/'protocol.json').read_text());assert arm in proto['arms']
OUT=ROOT/'outputs/science';OUT.mkdir(exist_ok=False);(OUT/'events.jsonl').touch();began=time.monotonic()
fit=json.loads((PREP/'fit.json').read_text());held=json.loads((PREP/'held.json').read_text())
env=json.loads((ROOT/'outputs/environment.json').read_text());declaration=next(m for m in proto['models'] if m['arm']==arm)
contract={'study_id':proto['study_id'],'arm':arm,'protocol_sha256':sha(PREP/'protocol.json'),'fit_sha256':sha(PREP/'fit.json'),'held_sha256':sha(PREP/'held.json'),'base_revision':declaration['revision']}
for n,h in proto['source_hashes'].items():
    if (ROOT/n).is_file():assert sha(ROOT/n)==h
atomic(OUT/'Identity.json',{'contract':contract,'actual_pid':os.getpid(),'environment':env,'new_PF_controller_calls':0})
def event(kind,**v):
    with (OUT/'events.jsonl').open('a',encoding='utf8') as f:
        f.write(json.dumps({'event':kind,'seconds':time.monotonic()-began,**v},separators=(',',':'),allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def deadline(*a):raise TimeoutError('Fixed scientific bound; no retry/extension')
signal.signal(signal.SIGALRM,deadline);signal.alarm(proto['science_seconds'])
phase='initialization';ident='none';calls=0;returns=0;pending=None;gen_rows=[];packages=0;previous=b''
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
torch.use_deterministic_algorithms(True)
def seed():
    random.seed(proto['seed']);np.random.seed(proto['seed']);torch.manual_seed(proto['seed']);torch.cuda.manual_seed_all(proto['seed'])
def load():
    start=time.monotonic();seed();quant=dict(proto['quantization']);quant['bnb_4bit_compute_dtype']=torch.float16
    base=AutoModelForCausalLM.from_pretrained(env['snapshot'],local_files_only=True,trust_remote_code=False,quantization_config=BitsAndBytesConfig(**quant),device_map={'':'cuda:0'},dtype=torch.float16,attn_implementation='sdpa')
    base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':False})
    model=get_peft_model(base,LoraConfig(**proto['lora']))
    for n,v in active(model).items():v.data=v.data.float()
    assert all('.lora_' in n for n in active(model)) and model.is_loaded_in_4bit
    assert all(p.device.type=='cuda' for p in model.parameters())
    # Count calculated independently from pinned configuration during local readiness.
    assert sum(v.numel() for v in active(model).values())==proto['trainable_parameters'][arm]
    opt=torch.optim.AdamW(list(active(model).values()),lr=.0002,weight_decay=.01,betas=(.9,.999),eps=1e-8)
    scaler=torch.amp.GradScaler('cuda',init_scale=1024.,growth_interval=2000)
    event('model_load_return',load_seconds=time.monotonic()-start,trainable_parameters=sum(v.numel() for v in active(model).values()),names=list(active(model)))
    return model,opt,scaler
def before(module,args,kw):
    global calls,pending
    assert pending is None;calls+=1;ids=kw.get('input_ids',args[0] if args else None);assert ids is not None
    pending=(calls,time.monotonic());event('forward_attempt',sequence=calls,phase=phase,id=ident,input_tokens=ids.numel(),input_ids_sha256=hashlib.sha256(ids.detach().cpu().numpy().tobytes()).hexdigest())
def after(module,args,kw,out):
    global returns,pending
    assert pending is not None;number,start=pending;pending=None
    if out is None:event('forward_unreturned',sequence=number,phase=phase,id=ident);return
    values=out.logits[0,-1].detach().float();assert torch.isfinite(values).all().item();torch.cuda.synchronize();returns+=1
    a=values.cpu().numpy();h=hashlib.sha256(a.tobytes()).hexdigest();choice=int(a.argmax())
    event('forward_return',sequence=number,phase=phase,id=ident,logits_sha256=h,argmax=choice,forward_seconds=time.monotonic()-start)
    if phase in ['final','reload']:gen_rows.append({'sequence':number,'logits_sha256':h,'argmax':choice})
def attach(model):
    # Hook the underlying CausalLM root: generate also invokes this root for every token.
    base=model.get_base_model();return [base.register_forward_pre_hook(before,with_kwargs=True),base.register_forward_hook(after,with_kwargs=True,always_call=True)]
def loss(model,row):
    ids=torch.tensor([row['prefix_ids']+row['answer_ids']],device='cuda',dtype=torch.long)
    # Input excludes final answer token; last A positions predict exactly A answer/EOS tokens.
    with torch.autocast('cuda',dtype=torch.float16):
        out=model(input_ids=ids[:,:-1],attention_mask=torch.ones_like(ids[:,:-1]),use_cache=False,logits_to_keep=len(row['answer_ids']))
        assert out.logits.shape[1]==len(row['answer_ids'])
        value=torch.nn.functional.cross_entropy(out.logits[0].float(),ids[0,len(row['prefix_ids']):],reduction='mean')
    assert torch.isfinite(value).item();return value
def cursor(micro):return {'microsteps':micro,'optimizer_steps':micro//4,'next_epoch':micro//340+1,'next_offset':micro%340}
def save_checkpoint(model,opt,scaler,micro,folder='checkpoints'):
    path=OUT/folder/f'step_{micro//4:03d}.pt';path.parent.mkdir(exist_ok=True)
    v=snapshot(model,opt,scaler,cursor(micro),contract)
    with path.open('xb') as f:torch.save(v,f);f.flush();os.fsync(f.fileno())
    event('checkpoint_return',path=path.relative_to(OUT).as_posix(),sha256=sha(path),cursor=v['cursor']);return path
def publish(files,label):
    global packages,previous
    event('preservation_request',number=packages,label=label)
    folder,d,current=make_delta_package(ROOT/'outputs/transfer',packages,files,OUT/'events.jsonl',{'contract':contract,'label':label},previous)
    start=time.monotonic()
    expected={'number':packages,'archive_sha256':d['archive_sha256'],'journal_prefix_sha256':d['journal_prefix_sha256'],'full_state_and_bytes_verified':True}
    while time.monotonic()-start<proto['ACK_seconds']:
        ack=folder/'ack.json'
        if ack.exists():
            assert json.loads(ack.read_text())==expected;previous=current;packages+=1;event('preservation_ack_return',number=packages-1,wait_seconds=time.monotonic()-start);return
        time.sleep(.5)
    raise TimeoutError('No durable verified local ACK; no subsequent scientific call')
def train_group(model,opt,scaler,rows,micro,label):
    global phase,ident
    model.train();model.config.use_cache=False;opt.zero_grad(set_to_none=True);phase=label
    for row in rows:
        ident=row['id'];event('training_microstep_attempt',phase=label,microstep=micro+1,id=ident,weight=row['weight'],answer_tokens=len(row['answer_ids']))
        value=loss(model,row);scaler.scale(value*row['weight']/4).backward();torch.cuda.synchronize();micro+=1
        event('backward_return',phase=label,microstep=micro,id=ident,loss=float(value.detach()),weight=row['weight']);del value
    scaler.unscale_(opt)
    norms={}
    for n,v in active(model).items():
        assert v.grad is not None and torch.isfinite(v.grad).all().item();norms[n]=float(v.grad.norm())
    norm=torch.nn.utils.clip_grad_norm_(list(active(model).values()),1.0);assert torch.isfinite(norm).item()
    scale=scaler.get_scale();event('optimizer_attempt',phase=label,step=micro//4,gradient_norms=norms,scale=scale)
    scaler.step(opt);scaler.update();assert scaler.get_scale()>=scale,'Skipped/overflow optimizer update; no scientific retry'
    torch.cuda.synchronize();opt.zero_grad(set_to_none=True);event('optimizer_return',phase=label,step=micro//4)
    return micro
model=opt=scaler=None;handles=[]
try:
    torch.cuda.reset_peak_memory_stats();model,opt,scaler=load();handles=attach(model);frozen=frozen_hashes(model)
    fixture=sorted(fit,key=lambda r:(-len(r['prefix_ids'])-len(r['answer_ids']),r['id']))[0]
    erows=[fixture]+[r for r in fit if r['id']!=fixture['id']][:3]
    atomic(OUT/'Pre_Forward_Mask.json',{'names':list(active(model)),'trainable_parameters':sum(p.numel() for p in active(model).values()),'frozen':frozen,'engineering_ids':[r['id'] for r in erows]})
    publish({'Identity.json':OUT/'Identity.json','Pre_Forward_Mask.json':OUT/'Pre_Forward_Mask.json'},'pre_forward')
    micro=train_group(model,opt,scaler,erows,0,'engineering_train')
    phase='engineering_eval';ident=fixture['id'];model.eval()
    with torch.no_grad():reference=loss(model,fixture).detach().cpu()
    ck=save_checkpoint(model,opt,scaler,4,'engineering');saved=torch.load(ck,weights_only=False)
    assert frozen_hashes(model)==frozen
    for h in handles:h.remove()
    del model,opt,scaler;gc.collect();torch.cuda.empty_cache()
    model,opt,scaler=load();handles=attach(model);assert frozen_hashes(model)==frozen
    restore(model,opt,scaler,saved,contract);model.eval();phase='engineering_cold_eval'
    with torch.no_grad():cold=loss(model,fixture).detach().cpu()
    assert torch.equal(reference,cold),'Actual cold-restored teacher loss mismatch'
    atomic(OUT/'Engineering_Integration.json',{'passed':True,'fixture_id':fixture['id'],'context_tokens':len(fixture['prefix_ids'])+len(fixture['answer_ids']),
      'genuine_training_forwards':4,'genuine_backward_returns':4,'genuine_optimizer_returns':1,'genuine_eval_forwards':2,
      'loss_before_cold':float(reference),'loss_after_cold':float(cold),'complete_state_exact_restore':True,'frozen_quantized_state_unchanged':True,
      'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),
      'engineering_is_not_learning_result':True})
    publish({'engineering/step_001.pt':ck,'Engineering_Integration.json':OUT/'Engineering_Integration.json'},'engineering_complete_before_science')
    for h in handles:h.remove()
    del model,opt,scaler,saved;gc.collect();torch.cuda.empty_cache()
    model,opt,scaler=load();handles=attach(model);assert frozen_hashes(model)==frozen
    event('new_scientific_initialization',engineering_weights_discarded=True,seed_reset=True)
    cp=save_checkpoint(model,opt,scaler,0);publish({cp.relative_to(OUT).as_posix():cp},'science_initial')
    micro=0
    for epoch in [1,2]:
        for start in range(0,340,4):
            micro=train_group(model,opt,scaler,fit[start:start+4],micro,'train')
            step=micro//4;atomic(OUT/'progress.json',{'stage':'training','epoch':epoch,'microsteps':micro,'optimizer_steps':step,'actual_forwards':calls,'actual_forward_returns':returns})
            if step%20==0 or step in [85,170]:
                cp=save_checkpoint(model,opt,scaler,micro);publish({cp.relative_to(OUT).as_posix():cp},'train_'+str(step))
    assert micro==680 and frozen_hashes(model)==frozen
    model.eval();model.config.use_cache=True
    tokenizer=AutoTokenizer.from_pretrained(str(PREP/'tokenizers'/arm),local_files_only=True,trust_remote_code=False)
    generation=GenerationConfig(do_sample=False,num_beams=1,max_new_tokens=384,repetition_penalty=1.,eos_token_id=151645,pad_token_id=151643,use_cache=True)
    final={}
    def generate_all(tag):
        global phase,ident,gen_rows
        files={};phase=tag
        for i,row in enumerate(held):
            ident=row['id'];gen_rows=[];ids=torch.tensor([row['prefix_ids']],device='cuda',dtype=torch.long)
            event('generation_attempt',phase=tag,id=ident,prompt_tokens=len(row['prefix_ids']))
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.float16):sequence=model.generate(input_ids=ids,attention_mask=torch.ones_like(ids),generation_config=generation,logits_to_keep=1)[0].cpu().tolist()
            generated=sequence[len(row['prefix_ids']):];assert sequence[:len(row['prefix_ids'])]==row['prefix_ids']
            assert generated==[v['argmax'] for v in gen_rows] and 0<len(generated)<=384
            value={'id':ident,'world_sha256':row['world_sha256'],'input_sha256':row['input_sha256'],'prompt_ids_sha256':hashlib.sha256(np.asarray(row['prefix_ids'],dtype=np.int64).tobytes()).hexdigest(),
              'generated_ids':generated,'text':tokenizer.decode(generated,skip_special_tokens=True),'forward_records':gen_rows,'phase':tag}
            if tag=='final':final[ident]=generated
            else:assert generated==final[ident],'Fresh final-model sequence mismatch; no retry'
            path=OUT/tag/(str(i).zfill(3)+'.json');atomic(path,value);files[path.relative_to(OUT).as_posix()]=path
            event('generation_return',phase=tag,id=ident,output_tokens=len(generated),path=path.relative_to(OUT).as_posix())
            atomic(OUT/'progress.json',{'stage':tag,'completed_cases':i+1,'actual_forwards':calls,'actual_forward_returns':returns,'optimizer_steps':170})
            if (i+1)%8==0 or i==len(held)-1:publish(files,tag+'_'+str(i+1));files={}
    generate_all('final');saved=torch.load(cp,weights_only=False)
    for h in handles:h.remove()
    del model,opt,scaler;gc.collect();torch.cuda.empty_cache()
    model,opt,scaler=load();handles=attach(model);restore(model,opt,scaler,saved,contract);model.eval();model.config.use_cache=True;generate_all('reload')
    assert frozen_hashes(model)==frozen and calls==returns
    result={'complete':True,'microsteps':680,'optimizer_steps':170,'engineering_microsteps':4,'engineering_optimizer_steps':1,'generations':192,'all96_fresh_reload_sequences_exact':True,
      'actual_forward_attempts':calls,'actual_forward_returns':returns,'frozen_quantized_state_unchanged':True,'science_workflow_seconds':time.monotonic()-began,
      'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'new_PF_controller_calls':0}
    atomic(OUT/'Actual_Completion.json',result);event('complete',**result);publish({'Actual_Completion.json':OUT/'Actual_Completion.json'},'complete')
except BaseException as e:
    atomic(OUT/'Failure.json',{'type':type(e).__name__,'phase':phase,'id':ident,'actual_forward_attempts':calls,'actual_forward_returns':returns,'unknown_unexecuted_remains':True,'seconds':time.monotonic()-began})
    event('failure',failure_type=type(e).__name__,phase=phase,id=ident);traceback.print_exc();raise
finally:
    signal.alarm(0)
