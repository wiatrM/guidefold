#!/usr/bin/env python3
"""Paired source-only prompt quality ablation; no retrieval queries read."""
import importlib.util, json, hashlib, os, sys, time
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent/'2026-09-06-query-enrichment'
spec=importlib.util.spec_from_file_location('enrich',BASE/'run.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
OUT=Path(__file__).resolve().parent
ADD='''\nSpecificity requirements: Preserve the actual platform, framework, technology, domain, or repository workflow whenever the skill is limited to one. Include that distinguishing scope in each item; do not turn a named-platform operation into a generic operation. Queries must be direct requests to perform a concrete task, not questions about the document, its phases, its list of tools, or its title. Avoid relying on an internal skill identifier as the only scope cue. Never imply broader compatibility or a capability absent from the source. All prior JSON and evidence constraints still apply.'''
def write(n,x):(OUT/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def main():
 import torch
 from transformers import AutoTokenizer,AutoModelForCausalLM
 sf,_,_=e.sources();allskills=e.rows(sf);excluded=set(e.read(BASE/'manifest.json')['selected_skill_ids'])
 salt='scope-prompt-v1'+e.sha(sf)
 chosen=sorted([s for s in allskills if s['id'] not in excluded],key=lambda s:e.h(salt+s['id']))[:32]
 audit=sorted([s['id'] for s in chosen],key=lambda x:e.h('scope-audit-v1'+x))[:8]
 manifest={'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'skill_source_sha256':e.sha(sf),'skills':[s['id'] for s in chosen],'audit_skill_ids':audit,'n':32,'arms':['original_prompt','scoped_task_prompt'],'same_source_and_decoder':True,'baseline_prompt_sha256':e.h(e.SYSTEM),'scoped_prompt_sha256':e.h(e.SYSTEM+ADD),'parent_script_sha256':e.sha(BASE/'run.py'),'script_sha256':e.sha(Path(__file__)),'model':str(e.MODEL),'max_new_tokens':448,'batch_size':8,'seed':e.SEED,'no_real_queries_or_qrels_read':True,'retrieval_results_not_used':True}
 if (OUT/'manifest.json').exists():raise RuntimeError('Do not overwrite paired experiment')
 write('manifest.json',manifest)
 torch.manual_seed(e.SEED);torch.set_num_threads(2)
 tok=AutoTokenizer.from_pretrained(str(e.MODEL),local_files_only=True,trust_remote_code=False,padding_side='left')
 if tok.pad_token_id is None:tok.pad_token=tok.eos_token
 model=AutoModelForCausalLM.from_pretrained(str(e.MODEL),local_files_only=True,trust_remote_code=False,dtype=torch.float16,attn_implementation='sdpa').to('cuda').eval()
 inputs=[]
 for s in chosen:
  head='NAME: '+s['name']+'\nDESCRIPTION: '+s['description'];ht=tok.encode(head,add_special_tokens=False)
  body=e.dev_sparse.strip_own_frontmatter(s['body']);bt=tok.encode(body,add_special_tokens=False)
  excerpt=body if len(bt)<=1600 else tok.decode(bt[:1200])+'\n[... excerpt omitted ...]\n'+tok.decode(bt[-400:])
  inputs.append({'skill_id':s['id'],'name':s['name'],'source':tok.decode(ht[:350])+'\nBODY:\n'+excerpt})
 write('source-inputs.json',inputs)
 results=[];t0=time.time()
 with (OUT/'paired-generation.jsonl').open('w') as f:
  for arm,prompt in [('original_prompt',e.SYSTEM),('scoped_task_prompt',e.SYSTEM+ADD)]:
   for start in range(0,len(inputs),8):
    batch=inputs[start:start+8]
    prompts=[tok.apply_chat_template([{'role':'system','content':prompt},{'role':'user','content':'SOURCE DOCUMENT:\n'+p['source']}],tokenize=False,add_generation_prompt=True) for p in batch]
    x=tok(prompts,return_tensors='pt',padding=True,truncation=False).to('cuda');t=time.time()
    with torch.inference_mode():out=model.generate(**x,max_new_tokens=448,do_sample=False,pad_token_id=tok.pad_token_id,eos_token_id=tok.eos_token_id)
    sec=time.time()-t
    for i,p in enumerate(batch):
     ids=out[i,x['input_ids'].shape[1]:].tolist()
     if tok.eos_token_id in ids:ids=ids[:ids.index(tok.eos_token_id)+1]
     raw=tok.decode(ids,skip_special_tokens=True);accepted,rejected=e.checked_items(raw,p['source'])
     r={'arm':arm,'skill_id':p['skill_id'],'raw':raw,'accepted':accepted,'rejections':rejected,'input_tokens':int(x['attention_mask'][i].sum()),'output_tokens':len(ids),'batch_seconds':sec,'cap_hit':len(ids)>=448};results.append(r);f.write(json.dumps(r,ensure_ascii=False)+'\n')
    f.flush();print(f'GEN {arm} {start+len(batch)}/32 {sec:.1f}s',flush=True)
 summary={}
 for arm in manifest['arms']:
  rr=[r for r in results if r['arm']==arm];rejections={}
  for r in rr:
   for k,v in r['rejections'].items():rejections[k]=rejections.get(k,0)+v
  summary[arm]={'docs':len(rr),'accepted_intents':sum(len(r['accepted']['intents']) for r in rr),'accepted_queries':sum(len(r['accepted']['queries']) for r in rr),'empty_docs':sum(not(r['accepted']['intents'] or r['accepted']['queries']) for r in rr),'rejections':rejections,'cap_hits':sum(r['cap_hit'] for r in rr),'input_tokens':sum(r['input_tokens'] for r in rr),'output_tokens':sum(r['output_tokens'] for r in rr)}
 write('generation-summary.json',{'summary':summary,'generation_wall_seconds':time.time()-t0,'paired_sha256':e.sha(OUT/'paired-generation.jsonl'),'source_sha256':e.sha(OUT/'source-inputs.json'),'caveat':'Source-only prompt feasibility, not retrieval improvement or full semantic validation. Same corpus source;32 docs disjoint from first512.'})
 print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
