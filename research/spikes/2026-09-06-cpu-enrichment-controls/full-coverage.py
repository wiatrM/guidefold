#!/usr/bin/env python3
"""Exploratory full-coverage prefix control; see FULL-COVERAGE-PROTOCOL.md."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import gzip,json,sys,time
from pathlib import Path
import run as base
P=Path(__file__).resolve().parent
ARM='F_full_prefix20'
def freeze():
 assert not (P/'full-coverage-freeze.json').exists()
 m=base.verified();sf,_,_=base.sources()
 base.write('full-coverage-freeze.json',{'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'before_any_cohort_results':not(P/'results.json').exists(),'files':{str(f):base.sha(f) for f in [Path(__file__),P/'FULL-COVERAGE-PROTOCOL.md',P/'manifest.json',sf,P/'run.py']},'arm':ARM,'query_ids':m['query_ids'],'status':'Additional exploratory comparison, not part of the primary four-test family','gpu_used':False})
def evaluate():
 frozen=base.read(P/'full-coverage-freeze.json')
 for f,v in frozen['files'].items():assert base.sha(Path(f))==v
 for a in base.ARMS:assert (P/f'complete-{a}.json').exists()
 assert not (P/f'rankings-{ARM}.jsonl.gz').exists()
 sf,_,_=base.sources();skills=sorted(base.rows(sf),key=lambda x:x['id']);q=base.rows(P/'evaluation-queries.jsonl')
 cards,nodes,sidurn,_=base.dev_sparse.corpus_to_cards(skills);urnsid={v:k for k,v in sidurn.items()};text={}
 for s in skills:
  words=(s['name']+' '+s['description']+' '+base.dev_sparse.strip_own_frontmatter(s['body'])).split()
  phrases=[' '.join(words[:20])] if words else []
  cards[sidurn[s['id']]]['triggers']=phrases;text[s['id']]=phrases
 base.write('full-coverage-arm-texts.json',text)
 cli=base.dev_sparse._load_cli();start=time.time();index=cli.Index.from_cards(cards,nodes);router,cache=base.cached_router(cli,index)
 parityq=sorted(q,key=lambda x:base.h('cpu-eval-parity-v1'+x['id']))[:64]
 check=base.parity(cli,index,router,[x['query'] for x in parityq],ARM)
 with gzip.open(P/f'rankings-{ARM}.jsonl.gz','wt') as f:
  for i,x in enumerate(q):
   _,drops,_,ranked,picked=base.route(router,x['query']);assert not drops
   f.write(json.dumps({'arm':ARM,'query_id':x['id'],'ranked':[urnsid[r['urn']] for r in ranked],'selected':[urnsid[r['urn']] for r in picked]})+'\n')
   if (i+1)%256==0:base.log(f'EVAL {ARM} {i+1}/{len(q)} elapsed={time.time()-start:.1f}s')
 base.write('complete-'+ARM+'.json',{'arm':ARM,'queries':len(q),'rankings_sha256':base.sha(P/f'rankings-{ARM}.jsonl.gz'),'text_sha256':base.sha(P/'full-coverage-arm-texts.json'),'nonempty_docs':sum(bool(v) for v in text.values()),'added_words':sum(len(t.split()) for v in text.values() for t in v),'parity':check,'wall_seconds':time.time()-start,'gpu_used':False})
if __name__=='__main__':{'freeze':freeze,'evaluate':evaluate}[sys.argv[1]]()
