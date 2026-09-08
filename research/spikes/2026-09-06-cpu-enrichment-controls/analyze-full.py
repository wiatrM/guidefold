#!/usr/bin/env python3
"""Exploratory full-coverage comparison; no confirmatory p-values."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import collections,gzip,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
A=['A_original','F_full_prefix20'];N=['recall10','complete4','recall50','all_gold50','hit1']
q=[json.loads(x) for x in (P/'evaluation-queries.jsonl').open()];values={};records={}
for arm in A:
 with gzip.open(P/f'rankings-{arm}.jsonl.gz','rt') as f:rr=[json.loads(x) for x in f]
 assert [x['query_id'] for x in rr]==[x['id'] for x in q];records[arm]=rr
 v=[]
 for x,r in zip(q,rr):
  g=set(x['skill_ids']);top=set(r['ranked'][:10]);pool=set(r['ranked'])
  v.append([len(g&top)/len(g),int(g<=set(r['selected'])),len(g&pool)/len(g),int(g<=pool),int(bool(r['ranked']) and r['ranked'][0] in g)])
 values[arm]=np.array(v)
strata={'overall':list(range(len(q)))}
for k in (1,2,3):strata['k='+str(k)]=[i for i,x in enumerate(q) if len(x['skill_ids'])==k]
summary={label:{'queries':len(ii),'arms':{a:dict(zip(N,values[a][ii].mean(0).tolist())) for a in A}} for label,ii in strata.items()}
# Components by transitive sharing of labelled positive documents.
touching=collections.defaultdict(set)
for i,x in enumerate(q):
 for g in x['skill_ids']:touching[g].add(i)
unseen=set(range(len(q)));groups=[]
while unseen:
 i=min(unseen);unseen.remove(i);todo=[i];group=[]
 while todo:
  j=todo.pop();group.append(j)
  for g in q[j]['skill_ids']:
   fresh=touching[g]&unseen;unseen.difference_update(fresh);todo.extend(fresh)
 groups.append(sorted(group))
d=values[A[1]]-values[A[0]];sums=np.array([d[ii].sum(0) for ii in groups]);sizes=np.array([len(ii) for ii in groups])
qb=[];cb=[];rng=np.random.default_rng(202609064)
for _ in range(5000):qb.append(d[rng.integers(len(q),size=len(q))].mean(0))
rng=np.random.default_rng(202609065)
for _ in range(5000):
 ix=rng.integers(len(groups),size=len(groups));cb.append(sums[ix].sum(0)/sizes[ix].sum())
qc=np.quantile(qb,[.025,.975],axis=0)*100;cc=np.quantile(cb,[.025,.975],axis=0)*100
contrast={name:{'delta_pp':float(d[:,j].mean()*100),'query_ci95_pp':qc[:,j].tolist(),'gold_component_ci95_pp':cc[:,j].tolist(),'better_queries':int((d[:,j]>1e-12).sum()),'worse_queries':int((d[:,j]< -1e-12).sum())} for j,name in enumerate(N)}
companion={}
for a in A:
 first=sum(x['skill_ids'][0] in r['ranked'][:10] for x,r in zip(q,records[a]));den=sum(len(x['skill_ids'])-1 for x in q)
 hit=sum(len(set(x['skill_ids'][1:])&set(r['ranked'][:10])) for x,r in zip(q,records[a]))
 companion[a]={'first_listed_gold_recall10':first/len(q),'companion_gold_recall10':hit/den,'companion_gold_count':den}
r={'status':'Exploratory full-coverage control added before outcome inspection; no confirmatory significance claim','summary':summary,'contrast':contrast,'first_vs_companion':companion,'components':len(groups),'gpu_used':False,'limitations':['Same public synthetic cohort as five-arm primary study.','F uses full coverage and fixed 20 words per document; not length/coverage-matched to partial LLM expansion.','Cannot attribute F versus B differences solely to LLM generation.','No human execution or unknown-source replication.']}
(P/'full-coverage-results.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
