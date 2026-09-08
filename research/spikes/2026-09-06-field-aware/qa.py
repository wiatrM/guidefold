#!/usr/bin/env python3
"""Independent reporting QA; no training, retrieval on frozen test, or GPU model loading."""
import gzip,json,hashlib,time,sys
from pathlib import Path
import numpy as np
from transformers import AutoTokenizer
P=Path(__file__).resolve().parent
ROOT=P.parents[2]
def read(name):return json.loads((P/name).read_text())
def main():
 r=read('results.json');m=read('manifest.json')
 rows=[json.loads(s) for s in gzip.open(P/'dev-rankings.jsonl.gz','rt')]
 qpath=Path('/home/mike/.cache/guidefold/corpora/skillret/data/queries/train.jsonl')
 queries={q['id']:q for q in (json.loads(s) for s in qpath.open())}
 assert len(rows)==5000
 names=['hit1','recall10','ndcg10_binary','all_gold_injected4']
 recomputed={}
 for arm in ('flat_uniform','field_uniform','flat_mlp','field_mlp','sparse_field_mlp'):
  rr=[x for x in rows if x['arm']==arm]
  assert len({x['query_id'] for x in rr})==1000
  vals=[]
  for x in rr:
   gold=set(queries[x['query_id']]['skill_ids'])
   retrieved=x['ranked'];injected=x['injected']
   gains=[int(s in gold) for s in retrieved]
   dcg=sum(g/np.log2(i+2) for i,g in enumerate(gains))
   ideal=sum(1/np.log2(i+2) for i in range(min(10,len(gold))))
   vals.append([float(gains[0]),len(set(retrieved)&gold)/len(gold),float(dcg/ideal),float(gold<=set(injected))])
  means=np.asarray(vals).mean(0)
  assert np.allclose(means,[r['metrics'][arm][k] for k in names],atol=1e-12)
  recomputed[arm]=dict(zip(names,means.tolist()))
 tok=AutoTokenizer.from_pretrained(m['model'],local_files_only=True)
 prompt='Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:'
 counts={}
 for label,ids in [('train',m['train_ids']),('dev',m['dev_ids'])]:
  strings=[prompt+queries[i]['query'] for i in ids]
  lens=[len(x) for x in tok(strings,truncation=False)['input_ids']]
  counts[label]={'n':len(lens),'max_prompted_tokens':max(lens),'over_1024_including_prompt':sum(x>1024 for x in lens)}
 checks={'unique_dev_rows_per_arm':1000,'total_new_arm_rows':5000,'all_recomputed_metrics_match':True,'prompted_query_lengths':counts,'source_hash_matches':hashlib.sha256((P/'run.py').read_bytes()).hexdigest()==m['source_hashes'][str(P/'run.py')],'negative_overlap':read('training-overlap-audit.json')}
 assert checks['source_hash_matches']
 (P/'qa-results.json').write_text(json.dumps(checks,indent=2)+'\n')
 print(json.dumps(checks,indent=2))
if __name__=='__main__':main()
