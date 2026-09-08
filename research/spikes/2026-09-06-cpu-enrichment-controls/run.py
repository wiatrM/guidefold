#!/usr/bin/env python3
"""CPU-only, immutable-index enrichment controls. See PROTOCOL.md."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
import collections, copy, functools, gc, gzip, hashlib, json, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; OUT=Path(__file__).resolve().parent
OLD=OUT.parent/'2026-09-06-query-enrichment'
sys.path.insert(0,str(ROOT/'tools/eval'))
import corpora, dev_sparse
ARMS=['A_original','B_generated','C_roundtrip','D_matched_random','E_extractive']
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p): return [json.loads(s) for s in p.open(encoding='utf-8-sig')]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def h(s): return hashlib.sha256(s.encode()).hexdigest()
def norm(s): return ' '.join(s.lower().split())
def write(name,x): (OUT/name).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def log(x): print(x,flush=True)
def sources():
 b=corpora.corpus_dir('skillret')/'data'
 return b/'skills/train.jsonl', b/'queries/train.jsonl', b/'qrels/train.jsonl'
def prepare():
 assert not (OUT/'manifest.json').exists()
 sf,qf,rf=sources(); qs=rows(qf)
 old=read(OUT.parent/'2026-09-06-field-aware/manifest.json'); prev=read(OLD/'manifest.json')
 exposed=set(old['train_ids']+old['dev_ids']+prev['query_ids'])
 texts={norm(q['query']) for q in qs if q['id'] in exposed}
 eligible=[q for q in qs if q['id'] not in exposed and norm(q['query']) not in texts]
 selected=sorted(eligible,key=lambda q:h('cpu-enrichment-controls-v1'+q['id']))[:2048]
 (OUT/'evaluation-queries.jsonl').write_text(''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in selected))
 files=[sf,qf,rf,OLD/'enrichment.jsonl',OLD/'manifest.json',OUT.parent/'2026-09-06-field-aware/manifest.json',ROOT/'skills/guidefold/scripts/guidefold',ROOT/'tools/eval/dev_sparse.py',Path(__file__),OUT/'PROTOCOL.md']
 write('manifest.json',{'query_ids':[q['id'] for q in selected],'assigned_skill_ids':prev['selected_skill_ids'],'excluded_ids':sorted(exposed),'eligible':len(eligible),'query_sha256':sha(OUT/'evaluation-queries.jsonl'),'source_hashes':{str(p):sha(p) for p in files},'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'gpu_used':False})
 log(f'FROZEN cohort={len(selected)} excluded={len(exposed)}')
def verified():
 m=read(OUT/'manifest.json')
 for p,v in m['source_hashes'].items(): assert sha(Path(p))==v,p
 assert sha(OUT/'evaluation-queries.jsonl')==m['query_sha256']
 return m

def cached_router(cli,index):
 router=cli.Router(index); original=router._bm25_scores
 visible=frozenset(index.cards)
 assert not index.word_vectors
 assert all(c['status']=='active' and not c['negative_triggers'] for c in index.cards.values())
 @functools.lru_cache(maxsize=2048)
 def term_scores(term): return original(term,visible)
 def scores(query,allowed):
  assert allowed==visible
  result={}
  for term,n in collections.Counter(cli.tokenize(query)).items():
   for u,v in term_scores(term).items(): result[u]=result.get(u,0)+v*n
  return result
 router._bm25_scores=scores
 return router,term_scores

def route(router,text):
 admissible,drops=router.policy_filter('_root',text)
 cand=router.candidates(text,'_root',top_n=50)
 scored=router.score(cand,text,'_root')
 picked=router.select(scored,k=4,admissible=set(admissible),query=text)
 return admissible,drops,cand,scored,picked

def parity(cli,index,router,texts,label):
 original=cli.Router(index)
 for text in texts:
  assert route(original,text)==route(router,text), (label,h(text))
 log(f'PARITY {label} {len(texts)} exact full-pipeline matches')
 return {'label':label,'queries':len(texts),'all_full_pipeline_equal':True,'query_text_hashes':[h(t) for t in texts]}

def freeze_arms():
 m=verified(); assert not (OUT/'arms-freeze.json').exists()
 sf,_,_=sources(); skills=sorted(rows(sf),key=lambda s:s['id'])
 cards,nodes,sidurn,_=dev_sparse.corpus_to_cards(skills); urnsid={v:k for k,v in sidurn.items()}
 side=rows(OLD/'enrichment.jsonl'); cli=dev_sparse._load_cli()
 index=cli.Index.from_cards(cards,nodes); router,cache=cached_router(cli,index)
 items=[{'skill_id':r['skill_id'],'kind':kind,'item_index':j,**v} for r in side for kind in ('intents','queries') for j,v in enumerate(r[kind])]
 pitems=sorted(items,key=lambda x:h('cpu-filter-parity-v1'+x['skill_id']+x['kind']+str(x['item_index'])))[:64]
 checks=[parity(cli,index,router,[i['text'] for i in pitems],'filter original')]
 decisions=[]; started=time.time()
 for i,item in enumerate(items):
  _,_,_,ranked,_=route(router,item['text'])
  rankids=[urnsid[x['urn']] for x in ranked]
  source_rank=rankids.index(item['skill_id'])+1 if item['skill_id'] in rankids else None
  decisions.append({**item,'source_rank_top50':source_rank,'keep':source_rank is not None and source_rank<=10})
  if (i+1)%256==0: log(f'FILTER {i+1}/{len(items)} elapsed={time.time()-started:.1f}s')
 all_by=collections.defaultdict(list);keep_by=collections.defaultdict(list)
 for x in decisions:
  all_by[(x['skill_id'],x['kind'])].append(x)
  if x['keep']: keep_by[(x['skill_id'],x['kind'])].append(x)
 texts={a:{} for a in ARMS}; controls=[]; byid={s['id']:s for s in skills}
 for r in side:
  sid=r['skill_id']; b=[];c=[];d=[]
  for kind in ('intents','queries'):
   full=all_by[(sid,kind)]; kept=keep_by[(sid,kind)]
   random=sorted(full,key=lambda x:h('cpu-random-control-v1'+sid+kind+str(x['item_index'])))[:len(kept)]
   b.extend(x['text'] for x in full); c.extend(x['text'] for x in kept); d.extend(x['text'] for x in random)
   controls.append({'skill_id':sid,'kind':kind,'generated':len(full),'retained':len(kept),'random_indices':[x['item_index'] for x in random]})
  s=byid[sid]; words=(s['name']+' '+s['description']+' '+dev_sparse.strip_own_frontmatter(s['body'])).split()
  n=sum(len(t.split()) for t in b); assert len(words)>=n
  e=[' '.join(words[:n])] if n else []
  for a,v in zip(ARMS,[[],b,c,d,e]): texts[a][sid]=v
 write('item-decisions.json',decisions);write('matched-counts.json',controls);write('arm-texts.json',texts)
 totals={a:{'items':sum(len(v) for v in dd.values()),'nonempty_docs':sum(bool(v) for v in dd.values()),'words':sum(len(t.split()) for v in dd.values() for t in v),'product_tokens':sum(len(cli.tokenize(t)) for v in dd.values() for t in v)} for a,dd in texts.items()}
 write('arms-freeze.json',{'manifest_sha256':sha(OUT/'manifest.json'),'files':{f:sha(OUT/f) for f in ['item-decisions.json','matched-counts.json','arm-texts.json']},'totals':totals,'parity':checks,'filter_seconds':time.time()-started,'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'frozen_before_evaluation':not any(OUT.glob('rankings-*.jsonl.gz')),'gpu_used':False})
 log(json.dumps(totals,indent=2))

def evaluate():
 m=verified();freeze=read(OUT/'arms-freeze.json')
 assert freeze['manifest_sha256']==sha(OUT/'manifest.json')
 for p,v in freeze['files'].items(): assert sha(OUT/p)==v
 sf,_,rf=sources(); skills=sorted(rows(sf),key=lambda s:s['id']);queries=rows(OUT/'evaluation-queries.jsonl')
 qrels=collections.defaultdict(set)
 for r in rows(rf):
  if r.get('relevance',1)>0:qrels[r['query_id']].add(r['skill_id'])
 for q in queries: assert set(q['skill_ids'])==qrels[q['id']]
 cards,nodes,sidurn,_=dev_sparse.corpus_to_cards(skills);urnsid={v:k for k,v in sidurn.items()};cli=dev_sparse._load_cli()
 text=read(OUT/'arm-texts.json');checks=[]
 parityq=sorted(queries,key=lambda q:h('cpu-eval-parity-v1'+q['id']))[:64]
 for arm in ARMS:
  path=OUT/f'rankings-{arm}.jsonl.gz'
  if path.exists():
   assert (OUT/f'complete-{arm}.json').exists(),'Incomplete arm: remove only after recording interruption'
   rec=read(OUT/f'complete-{arm}.json');assert rec['rankings_sha256']==sha(path);checks.append(rec);continue
  work=copy.deepcopy(cards)
  for sid,phrases in text[arm].items(): work[sidurn[sid]]['triggers']=phrases
  started=time.time();index=cli.Index.from_cards(work,nodes);router,cache=cached_router(cli,index)
  log(f'INDEX {arm} {time.time()-started:.1f}s')
  check=parity(cli,index,router,[q['query'] for q in parityq],arm)
  with gzip.open(path,'wt') as f:
   for i,q in enumerate(queries):
    _,drops,_,ranked,picked=route(router,q['query'])
    assert not drops
    record={'arm':arm,'query_id':q['id'],'ranked':[urnsid[x['urn']] for x in ranked],'selected':[urnsid[x['urn']] for x in picked]}
    f.write(json.dumps(record)+'\n')
    if (i+1)%256==0:log(f'EVAL {arm} {i+1}/{len(queries)} elapsed={time.time()-started:.1f}s')
  rec={'arm':arm,'queries':len(queries),'rankings_sha256':sha(path),'parity':check,'wall_seconds':time.time()-started,'cache_info':str(cache.cache_info()),'gpu_used':False}
  write(f'complete-{arm}.json',rec);checks.append(rec)
  cache.cache_clear();del router,cache,index,work;gc.collect()
 write('execution.json',{'arms':checks,'run_sha256':sha(Path(__file__)),'gpu_used':False,'timing_claim':'None: research cache and uncontrolled shared machine.'})
if __name__=='__main__': {'prepare':prepare,'freeze-arms':freeze_arms,'evaluate':evaluate}[sys.argv[1]]()
