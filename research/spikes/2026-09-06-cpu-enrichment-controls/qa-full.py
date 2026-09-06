#!/usr/bin/env python3
"""Independent checks of full-coverage text, rankings, qrels, metrics and intervals."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import collections,gzip,hashlib,json,re
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
rows=lambda p:[json.loads(x) for x in p.open()]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=load(P/'manifest.json');frozen=load(P/'full-coverage-freeze.json');r=load(P/'full-coverage-results.json')
for filename,want in frozen['files'].items():assert sha(Path(filename))==want
sf=Path(next(f for f in m['source_hashes'] if f.endswith('skills/train.jsonl')));rf=Path(next(f for f in m['source_hashes'] if f.endswith('qrels/train.jsonl')))
labels=collections.defaultdict(set)
for x in rows(rf):
 if x.get('relevance',1)>0:labels[x['query_id']].add(x['skill_id'])
text=load(P/'full-coverage-arm-texts.json');skills=rows(sf)
assert len(text)==len(skills)==10123
for s in skills:
 body=re.sub(r'^---\n.*?\n---\n?','',s['body'],count=1,flags=re.S).lstrip('\n')
 words=(s['name']+' '+s['description']+' '+body).split()
 assert text[s['id']]==([' '.join(words[:20])] if words else [])
q=rows(P/'evaluation-queries.jsonl');arms=['A_original','F_full_prefix20'];names=['recall10','complete4','recall50','all_gold50','hit1'];v=[]
for a in arms:
 p=P/f'rankings-{a}.jsonl.gz';assert sha(p)==load(P/f'complete-{a}.json')['rankings_sha256']
 with gzip.open(p,'rt') as f:records=[json.loads(x) for x in f]
 assert [x['query_id'] for x in records]==m['query_ids']
 values=[]
 for x,rec in zip(q,records):
  g=labels[x['id']];assert g==set(x['skill_ids'])
  ranked=rec['ranked'];selected=rec['selected']
  assert len(ranked)<=50 and len(set(ranked))==len(ranked) and len(selected)<=4 and set(selected)<=set(ranked)
  values.append([sum(s in ranked[:10] for s in g)/len(g),float(all(s in selected for s in g)),sum(s in ranked for s in g)/len(g),float(all(s in ranked for s in g)),float(bool(ranked) and ranked[0] in g)])
 v.append(np.array(values))
for stratum,summary in r['summary'].items():
 ids=[i for i,x in enumerate(q) if stratum=='overall' or len(labels[x['id']])==int(stratum[2:])]
 assert len(ids)==summary['queries']
 for j,a in enumerate(arms):np.testing.assert_allclose(v[j][ids].mean(0),[summary['arms'][a][n] for n in names],atol=1e-12,rtol=0)
# Union-find components; analyzer used BFS.
parent=list(range(len(q)));owners={}
def root(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
for i,x in enumerate(q):
 for s in labels[x['id']]:
  if s in owners:parent[root(i)]=root(owners[s])
  else:owners[s]=i
clusters=collections.defaultdict(list)
for i in range(len(q)):clusters[root(i)].append(i)
groups=sorted(clusters.values(),key=min);assert len(groups)==r['components']
d=v[1]-v[0];sums=np.array([d[ii].sum(0) for ii in groups]);sizes=np.array([len(ii) for ii in groups]);qb=[];cb=[]
rng=np.random.default_rng(202609064)
for _ in range(5000):
 counts=np.bincount(rng.integers(len(q),size=len(q)),minlength=len(q));qb.append(counts@d/len(q))
rng=np.random.default_rng(202609065)
for _ in range(5000):
 counts=np.bincount(rng.integers(len(groups),size=len(groups)),minlength=len(groups));cb.append(counts@sums/(counts@sizes))
qci=np.quantile(qb,[.025,.975],axis=0)*100;cci=np.quantile(cb,[.025,.975],axis=0)*100
for j,n in enumerate(names):
 x=r['contrast'][n];assert abs(d[:,j].mean()*100-x['delta_pp'])<1e-10
 assert int((d[:,j]>1e-12).sum())==x['better_queries'] and int((d[:,j]< -1e-12).sum())==x['worse_queries']
 np.testing.assert_allclose(qci[:,j],x['query_ci95_pp'],atol=1e-10,rtol=0);np.testing.assert_allclose(cci[:,j],x['gold_component_ci95_pp'],atol=1e-10,rtol=0)
output={'status':'PASS','skills_text_verified':len(skills),'ranking_rows_recomputed':2*len(q),'metric_cells':2*len(q)*5,'bootstrap_repetitions_recomputed':5000,'full_pipeline_parity_queries':load(P/'complete-F_full_prefix20.json')['parity']['queries'],'gpu_used':False,'qa_sha256':sha(Path(__file__))}
(P/'full-coverage-qa.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
