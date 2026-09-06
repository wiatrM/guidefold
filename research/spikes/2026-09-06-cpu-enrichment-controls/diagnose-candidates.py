#!/usr/bin/env python3
"""Post-hoc descriptive candidate-pool decomposition; no training or new routing."""
import collections,gzip,json
from pathlib import Path
P=Path(__file__).resolve().parent
q=[json.loads(s) for s in (P/'evaluation-queries.jsonl').open()]
result={}
for file in sorted(P.glob('rankings-*.jsonl.gz')):
 arm=file.name[len('rankings-'):-len('.jsonl.gz')]
 with gzip.open(file,'rt') as f: records=[json.loads(s) for s in f]
 assert [r['query_id'] for r in records]==[x['id'] for x in q]
 groups=collections.defaultdict(list)
 for x,r in zip(q,records):
  g=set(x['skill_ids']);k=len(g);selected=set(r['selected']);pool=set(r['ranked'])
  rank={sid:i+1 for i,sid in enumerate(r['ranked'])}
  entry={'complete_delivered':g<=selected,'all_gold_in_10':g<=set(r['ranked'][:10]),'all_gold_in_50':g<=pool,'blocked_by_candidate_miss':not g<=pool,'recoverable_with_oracle_rerank':g<=pool and not g<=selected,'first_listed_present_50':x['skill_ids'][0] in pool,'companions_missing_50':len(set(x['skill_ids'][1:])-pool),'companion_count':k-1,'minimum_rank_covering_all_gold':max(rank[s] for s in g) if g<=pool else None}
  groups['overall'].append(entry);groups['k='+str(k)].append(entry)
 out={}
 for label,vv in groups.items():
  n=len(vv);den=sum(x['companion_count'] for x in vv)
  summary={'queries':n}
  for name in ['complete_delivered','all_gold_in_10','all_gold_in_50','blocked_by_candidate_miss','recoverable_with_oracle_rerank','first_listed_present_50']:
   summary[name+'_count']=sum(x[name] for x in vv);summary[name+'_pct']=100*sum(x[name] for x in vv)/n
  summary['companion_gold_recall50_pct']=100*(den-sum(x['companions_missing_50'] for x in vv))/den if den else None
  assert summary['complete_delivered_count']+summary['recoverable_with_oracle_rerank_count']+summary['blocked_by_candidate_miss_count']==n
  summary['oracle_rank_cover_histogram']={str(rank):sum(x['minimum_rank_covering_all_gold']==rank for x in vv) for rank in range(1,51)}
  out[label]=summary
 result[arm]=out
(P/'candidate-diagnostics.json').write_text(json.dumps({'status':'Post-hoc descriptive oracle bounds, not a tested algorithm','arms':result,'limitations':['Gold lists treated as required conjunctions; annotation semantics need human review.','Oracle reranking knows labels; it is only an upper bound within this fixed pool.','Recall50 is per-gold average, whereas all_gold_in_50 is query-level conjunction.']},indent=2)+'\n')
print(json.dumps({a:{k:{n:v for n,v in s.items() if n in ['queries','all_gold_in_50_pct','complete_delivered_pct','recoverable_with_oracle_rerank_pct','blocked_by_candidate_miss_pct','companion_gold_recall50_pct']} for k,s in by.items()} for a,by in result.items()},indent=2))
