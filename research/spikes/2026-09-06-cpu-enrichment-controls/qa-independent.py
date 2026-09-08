#!/usr/bin/env python3
"""Independent artifact QA: no import of runner, analyzer or router."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
import collections,gzip,hashlib,json,math,re
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
A=['A_original','B_generated','C_roundtrip','D_matched_random','E_extractive']
M=['hit1','recall10','recall50','complete4','ndcg10']
C=[(2,1),(2,3),(1,4),(1,0),(4,0)]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def lines(p):return [json.loads(x) for x in p.open(encoding='utf-8-sig')]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(s):return hashlib.sha256(s.encode()).hexdigest()
def normalized(s):return ' '.join(s.lower().split())
def main():
 manifest=load(P/'manifest.json');frozen=load(P/'arms-freeze.json');result=load(P/'results.json')
 for filename,want in manifest['source_hashes'].items():assert digest(Path(filename))==want
 for filename,want in frozen['files'].items():assert digest(P/filename)==want
 assert frozen['manifest_sha256']==digest(P/'manifest.json') and frozen['frozen_before_evaluation']
 assert digest(P/'evaluation-queries.jsonl')==manifest['query_sha256']
 sourcefiles=[Path(x) for x in manifest['source_hashes']]
 sf=next(p for p in sourcefiles if str(p).endswith('skills/train.jsonl'))
 qf=next(p for p in sourcefiles if str(p).endswith('queries/train.jsonl'))
 rf=next(p for p in sourcefiles if str(p).endswith('qrels/train.jsonl'))
 allq=lines(qf);skills={x['id']:x for x in lines(sf)};known=set(manifest['excluded_ids'])
 oldtexts={normalized(x['query']) for x in allq if x['id'] in known}
 eligible=[x for x in allq if x['id'] not in known and normalized(x['query']) not in oldtexts]
 expected=sorted(eligible,key=lambda x:key('cpu-enrichment-controls-v1'+x['id']))[:2048]
 q=lines(P/'evaluation-queries.jsonl');assert q==expected
 assert manifest['query_ids']==[x['id'] for x in q] and len(set(manifest['query_ids']))==2048
 labels=collections.defaultdict(set)
 for x in lines(rf):
  if x.get('relevance',1)>0:labels[x['query_id']].add(x['skill_id'])
 for x in q:assert labels[x['id']]==set(x['skill_ids'])
 # Check original item identity, mask threshold, random counts and extractive text.
 old=P.parent/'2026-09-06-query-enrichment';original=lines(old/'enrichment.jsonl');decisions=load(P/'item-decisions.json');text=load(P/'arm-texts.json')
 by=collections.defaultdict(list)
 for x in decisions:
  by[(x['skill_id'],x['kind'])].append(x)
  assert x['keep']==(x['source_rank_top50'] is not None and x['source_rank_top50']<=10)
 assert len(decisions)==1603
 for row in original:
  sid=row['skill_id'];b=[];c=[];d=[]
  for kind in ('intents','queries'):
   group=by[(sid,kind)]
   assert [(x['text'],x['evidence']) for x in group]==[(x['text'],x['evidence']) for x in row[kind]]
   good=[x for x in group if x['keep']]
   rand=sorted(group,key=lambda x:key('cpu-random-control-v1'+sid+kind+str(x['item_index'])))[:len(good)]
   b.extend(x['text'] for x in group);c.extend(x['text'] for x in good);d.extend(x['text'] for x in rand)
  assert text[A[0]][sid]==[] and text[A[1]][sid]==b and text[A[2]][sid]==c and text[A[3]][sid]==d
  s=skills[sid];body=re.sub(r'^---\n.*?\n---\n?','',s['body'],count=1,flags=re.S).lstrip('\n')
  n=len(' '.join(b).split());words=(s['name']+' '+s['description']+' '+body).split()
  assert text[A[4]][sid]==([' '.join(words[:n])] if n else [])
  assert len(' '.join(text[A[4]][sid]).split())==n
 # Reconstruct every metric solely from saved IDs and independently loaded qrels.
 values=np.zeros((len(q),5,5));rr={}
 for a,arm in enumerate(A):
  filename=P/f'rankings-{arm}.jsonl.gz';assert digest(filename)==result['ranking_hashes'][arm]
  with gzip.open(filename,'rt') as f:records=[json.loads(x) for x in f]
  assert [x['query_id'] for x in records]==manifest['query_ids'];rr[arm]=records
  for i,(query,rec) in enumerate(zip(q,records)):
   assert rec['arm']==arm
   ranked=rec['ranked'];selected=rec['selected'];gold=labels[query['id']]
   assert len(ranked)<=50 and len(ranked)==len(set(ranked)) and set(ranked)<=set(skills)
   assert len(selected)<=4 and len(selected)==len(set(selected)) and set(selected)<=set(ranked)
   top=set(ranked[:10]);ideal=sum(math.log(2)/math.log(pos+1) for pos in range(1,min(10,len(gold))+1))
   actual=sum(math.log(2)/math.log(pos+1) for pos,sid in enumerate(ranked[:10],1) if sid in gold)
   values[i,a]=[int(bool(ranked) and ranked[0] in gold),len(top&gold)/len(gold),len(set(ranked)&gold)/len(gold),int(gold.issubset(selected)),actual/ideal]
 groups=collections.defaultdict(list);assigned=set(manifest['assigned_skill_ids'])
 for i,x in enumerate(q):
  gold=labels[x['id']];groups['overall'].append(i);groups['k='+str(len(gold))].append(i);groups['any_assigned_gold' if assigned&gold else 'no_assigned_gold'].append(i)
  if gold<=assigned:groups['all_assigned_gold'].append(i)
 for name,ii in groups.items():
  assert result['summary'][name]['queries']==len(ii)
  for a,arm in enumerate(A):
   want=result['summary'][name]['arms'][arm]
   np.testing.assert_allclose(values[ii,a].mean(0),[want[x] for x in M],rtol=0,atol=1e-12)
   first=sum(q[i]['skill_ids'][0] in rr[arm][i]['ranked'][:10] for i in ii)/len(ii)
   num=sum(len(set(q[i]['skill_ids'][1:])&set(rr[arm][i]['ranked'][:10])) for i in ii)
   den=sum(len(q[i]['skill_ids'])-1 for i in ii)
   assert abs(want['first_listed_gold_recall10']-first)<1e-12
   assert want['companion_gold_denominator']==den
   assert want['companion_gold_recall10']==(num/den if den else None)
 # Independent graph BFS rather than union-find.
 touching=collections.defaultdict(set)
 for i,x in enumerate(q):
  for gold in labels[x['id']]:touching[gold].add(i)
 unseen=set(range(len(q)));components=[]
 while unseen:
  start=min(unseen);unseen.remove(start);stack=[start];component=[]
  while stack:
   i=stack.pop();component.append(i)
   for gold in labels[q[i]['id']]:
    fresh=touching[gold]&unseen;unseen.difference_update(fresh);stack.extend(fresh)
  components.append(sorted(component))
 assert len(components)==result['components']['count']
 differences=np.stack([values[:,a]-values[:,b] for a,b in C],axis=1)
 component_sums=np.array([differences[x].sum(0) for x in components]);sizes=np.array([len(x) for x in components])
 qboot=[];cboot=[];rng=np.random.default_rng(202609061)
 for _ in range(5000):
  counts=np.bincount(rng.integers(len(q),size=len(q)),minlength=len(q))
  qboot.append(np.tensordot(counts,differences,axes=1)/len(q))
 rng=np.random.default_rng(202609062)
 for _ in range(5000):
  counts=np.bincount(rng.integers(len(components),size=len(components)),minlength=len(components))
  cboot.append(np.tensordot(counts,component_sums,axes=1)/(counts@sizes))
 qci=np.quantile(qboot,[.025,.975],axis=0)*100;cci=np.quantile(cboot,[.025,.975],axis=0)*100
 pvalues=[];exact=[]
 for j,(a,b) in enumerate(C):
  rec=result['contrasts'][A[a]+' minus '+A[b]]
  for k,metric in enumerate(M):
   d=differences[:,j,k];r=rec[metric]
   assert abs(d.mean()*100-r['delta_pp'])<1e-10
   assert (d>1e-12).sum()==r['better_queries'] and (d< -1e-12).sum()==r['worse_queries']
   np.testing.assert_allclose(qci[:,j,k],r['query_ci95_pp'],rtol=0,atol=1e-10)
   np.testing.assert_allclose(cci[:,j,k],r['gold_component_ci95_pp'],rtol=0,atol=1e-10)
  if j==4:continue
  unit=np.rint(differences[:,j,1]*6).astype(np.int64)
  weights=[int(unit[ii].sum()) for ii in components];weights=[w for w in weights if w]
  # Exact signed-sum probability distribution, avoiding sampled/per-bit implementation.
  dist={0:1}
  for w in weights:
   nxt=collections.defaultdict(int)
   for total,count in dist.items():nxt[total+w]+=count;nxt[total-w]+=count
   dist=nxt
  threshold=abs(sum(weights));p_exact=sum(n for total,n in dist.items() if abs(total)>=threshold)/(2**len(weights))
  if len(weights)<=20:p=p_exact
  else:
   rng=np.random.default_rng(202609063);count=0;w=np.array(weights)
   for _ in range(100):
    sign=rng.integers(0,2,size=(1000,len(weights)),dtype=np.int64)
    sums=np.where(sign,w,-w).sum(axis=1);count+=int((abs(sums)>=threshold).sum())
   p=(count+1)/100001
  assert abs(p-rec['recall10']['raw_p'])<1e-14
  pvalues.append(p);exact.append({'contrast':A[a]+' minus '+A[b],'exact_dynamic_program_p':p_exact,'reported_p':p,'nonzero_components':len(weights)})
 order=sorted(range(4),key=lambda i:pvalues[i]);last=0
 for rank,i in enumerate(order):
  last=max(last,min(1,(4-rank)*pvalues[i]));a,b=C[i]
  assert abs(last-result['contrasts'][A[a]+' minus '+A[b]]['recall10']['holm_p'])<1e-14
 parity=sum(load(P/f'complete-{arm}.json')['parity']['queries'] for arm in A)+sum(x['queries'] for x in frozen['parity'])
 output={'status':'PASS','ranking_rows':len(q)*len(A),'metric_cells':int(values.size),'source_hashes_checked':len(manifest['source_hashes']),'cohort_ids_excluded':len(known),'strata_checked':len(groups),'query_and_component_bootstraps_recomputed':5000,'full_pipeline_parity_queries':parity,'component_p_tests':exact,'normalized_text_duplicate_extra_rows':len(q)-len({normalized(x['query']) for x in q}),'gpu_used':False,'qa_sha256':digest(Path(__file__))}
 (P/'independent-qa.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
if __name__=='__main__':main()
