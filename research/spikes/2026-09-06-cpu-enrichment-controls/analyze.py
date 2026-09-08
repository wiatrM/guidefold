#!/usr/bin/env python3
"""Prespecified paired statistics from saved rankings; never reroutes or trains."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
import collections,gzip,hashlib,json,math
from pathlib import Path
import numpy as np
OUT=Path(__file__).resolve().parent
ARMS=['A_original','B_generated','C_roundtrip','D_matched_random','E_extractive']
NAMES=['hit1','recall10','recall50','complete4','ndcg10']
CONTRASTS=[('C_roundtrip','B_generated'),('C_roundtrip','D_matched_random'),('B_generated','E_extractive'),('B_generated','A_original'),('E_extractive','A_original')]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.open()]
def main():
 m=read(OUT/'manifest.json');freeze=read(OUT/'arms-freeze.json');q=rows(OUT/'evaluation-queries.jsonl');assigned=set(m['assigned_skill_ids'])
 assert len(q)==len(m['query_ids'])==2048 and [x['id'] for x in q]==m['query_ids']
 stats={};rankings={};strata=collections.defaultdict(list)
 for i,x in enumerate(q):
  g=set(x['skill_ids']);strata['overall'].append(i);strata['k='+str(len(g))].append(i);strata['any_assigned_gold' if g&assigned else 'no_assigned_gold'].append(i)
  if g<=assigned:strata['all_assigned_gold'].append(i)
 for a in ARMS:
  p=OUT/f'rankings-{a}.jsonl.gz';assert sha(p)==read(OUT/f'complete-{a}.json')['rankings_sha256']
  with gzip.open(p,'rt') as f:rr=[json.loads(x) for x in f]
  assert [x['query_id'] for x in rr]==m['query_ids']
  vals=[]
  for x,r in zip(q,rr):
   g=set(x['skill_ids']);hits=[int(s in g) for s in r['ranked'][:10]]
   dcg=sum(v/math.log2(i+2) for i,v in enumerate(hits));idcg=sum(1/math.log2(i+2) for i in range(min(10,len(g))))
   vals.append([int(bool(hits) and hits[0]),sum(hits)/len(g),len(g&set(r['ranked'][:50]))/len(g),int(g<=set(r['selected'])),dcg/idcg])
  stats[a]=np.array(vals);rankings[a]=rr
 summary={}
 for label,ii in strata.items():
  ss={}
  for a in ARMS:
   values=dict(zip(NAMES,stats[a][ii].mean(0).tolist()))
   first=sum(q[i]['skill_ids'][0] in rankings[a][i]['ranked'][:10] for i in ii)
   companions=sum(len(set(q[i]['skill_ids'][1:])&set(rankings[a][i]['ranked'][:10])) for i in ii)
   denominator=sum(len(q[i]['skill_ids'])-1 for i in ii)
   values.update({'first_listed_gold_recall10':first/len(ii),'companion_gold_recall10':companions/denominator if denominator else None,'companion_gold_denominator':denominator})
   ss[a]=values
  summary[label]={'queries':len(ii),'arms':ss}
 # Shared-positive-skill connected components; union-find independent of retrieval.
 parent=list(range(len(q)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 owner={}
 for i,x in enumerate(q):
  for g in x['skill_ids']:
   if g in owner:parent[find(i)]=find(owner[g])
   else:owner[g]=i
 groups=collections.defaultdict(list)
 for i in range(len(q)):groups[find(i)].append(i)
 groups=sorted(groups.values(),key=lambda x:min(x));sizes=np.array([len(x) for x in groups])
 d=np.stack([stats[a]-stats[b] for a,b in CONTRASTS],axis=1)
 csum=np.array([d[ii].sum(0) for ii in groups])
 query_boot=[];cluster_boot=[]
 rng=np.random.default_rng(202609061)
 for start in range(0,5000,100):
  jj=rng.integers(0,len(q),size=(100,len(q)));query_boot.append(d[jj].mean(1))
 rng=np.random.default_rng(202609062)
 for start in range(0,5000,100):
  jj=rng.integers(0,len(groups),size=(100,len(groups)));cluster_boot.append(csum[jj].sum(1)/sizes[jj].sum(1)[:,None,None])
 qci=np.quantile(np.concatenate(query_boot),[.025,.975],axis=0)*100
 cci=np.quantile(np.concatenate(cluster_boot),[.025,.975],axis=0)*100
 contrasts={};pvalues=[]
 for j,(a,b) in enumerate(CONTRASTS):
  dif=d[:,j];rec={}
  for k,name in enumerate(NAMES):
   v=dif[:,k];rec[name]={'delta_pp':float(v.mean()*100),'query_ci95_pp':qci[:,j,k].tolist(),'gold_component_ci95_pp':cci[:,j,k].tolist(),'better_queries':int((v>1e-12).sum()),'worse_queries':int((v< -1e-12).sum()),'unchanged_queries':int((abs(v)<=1e-12).sum())}
  if j<4:
   # All gold counts are 1,2,3: Recall@10 sums have exact integer sixth units.
   assert set(map(lambda x:len(x['skill_ids']),q))<={1,2,3}
   unit=np.rint(dif[:,1]*6).astype(np.int64)
   signed=np.array([unit[ii].sum() for ii in groups],dtype=np.int64);signed=signed[signed!=0]
   observed=abs(int(signed.sum()));n=len(signed);hits=0
   if n<=20:
    total=1<<n
    for start in range(0,total,4096):
     nums=np.arange(start,min(start+4096,total),dtype=np.uint64)
     signs=((nums[:,None]>>np.arange(n,dtype=np.uint64))&1).astype(np.int64)*2-1
     hits+=int((np.abs(signs@signed)>=observed).sum())
    p=hits/total;method='exact component sign flip'
   else:
    total=100000;rng=np.random.default_rng(202609063)
    for start in range(0,total,1000):
     signs=rng.integers(0,2,size=(1000,n),dtype=np.int64)*2-1
     hits+=int((np.abs(signs@signed)>=observed).sum())
    p=(hits+1)/(total+1);method='Monte Carlo component sign flip, plus-one'
   rec['recall10'].update({'nonzero_components':n,'raw_p':p,'test':method,'permutations':total,'observed_signed_sixth_units':int(signed.sum())});pvalues.append(p)
  else:rec['exploratory']=True
  contrasts[a+' minus '+b]=rec
 order=np.argsort(pvalues);previous=0
 for rank,j in enumerate(order):
  previous=max(previous,min(1.,(4-rank)*pvalues[j]));a,b=CONTRASTS[j]
  contrasts[a+' minus '+b]['recall10']['holm_p']=previous
 primary=contrasts['C_roundtrip minus B_generated']
 gate=primary['recall10']['delta_pp']>0 and primary['recall10']['holm_p']<.05 and primary['complete4']['delta_pp']>=0
 result={'status':'CPU-only internal follow-up; no product admission','summary':summary,'contrasts':contrasts,'filter_continuation_gate':bool(gate),'components':{'count':len(groups),'max_queries':int(max(sizes)),'singletons':int((sizes==1).sum()),'effective_by_size':float(sizes.sum()**2/(sizes*sizes).sum())},'arm_totals':freeze['totals'],'ranking_hashes':{a:sha(OUT/f'rankings-{a}.jsonl.gz') for a in ARMS},'script_sha256':sha(Path(__file__)),'limitations':['Same public synthetic train corpus; partial 512/10123 enrichment, not an external holdout.','Roundtrip measures original self-retrievability, not semantic truth.','D matches item counts but not token lengths; E matches whitespace length but not exact product tokens.','Shared-gold components do not capture all semantic dependence.','No human execution, abstention or no-skill outcomes.','Sequential research chosen after prior pilot; not a novelty or breakthrough claim.']}
 (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'overall':summary['overall'],'contrasts':{k:v['recall10'] for k,v in contrasts.items()},'filter_gate':gate},indent=2))
if __name__=='__main__':main()
