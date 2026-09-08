#!/usr/bin/env python3
"""Read-only TRAIN label structure audit and outcome-independent review packet."""
import collections,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
m=json.loads((P/'manifest.json').read_text())
paths={kind:Path(next(f for f in m['source_hashes'] if f.endswith(kind+'/train.jsonl'))) for kind in ['skills','queries','qrels']}
rows=lambda p:[json.loads(s) for s in p.open()]
skills={x['id']:x for x in rows(paths['skills'])};q=rows(paths['queries']);rels=rows(paths['qrels'])
byid={x['id']:x for x in q};pairs=collections.Counter((x['query_id'],x['skill_id']) for x in rels);gold=collections.defaultdict(set)
for x in rels:
 if x['relevance']>0:gold[x['query_id']].add(x['skill_id'])
texts=collections.defaultdict(list);counts=collections.defaultdict(collections.Counter);bad=[]
for x in q:
 k=x['k'];counts[k]['queries']+=1;counts[k]['has_original_query']+=int(bool(x.get('original_query')))
 texts[' '.join(x['query'].lower().split())].append(x)
 if k!=len(x['skill_ids']) or len(set(x['skill_ids']))!=k:bad.append([x['id'],'gold count mismatch'])
 if set(x['skill_ids'])!=gold[x['id']]:bad.append([x['id'],'qrels mismatch'])
 if [skills[s]['name'] for s in x['skill_ids']]!=x['skill_names']:bad.append([x['id'],'name/id mismatch'])
collisions=[{'query_ids':[x['id'] for x in xx],'gold_sets':[x['skill_ids'] for x in xx]} for xx in texts.values() if len(xx)>1]
result={'status':'Structural audit; semantic relevance is not inferred by this script','train_queries':len(q),'train_skills':len(skills),'train_qrels':len(rels),'duplicate_query_ids':len(q)-len(byid),'duplicate_qrel_pair_extra_rows':sum(n-1 for n in pairs.values()),'orphan_qrels':sum(x['query_id'] not in byid or x['skill_id'] not in skills for x in rels),'relevance_counts':dict(collections.Counter(x['relevance'] for x in rels)),'structural_violations':bad,'by_k':dict(counts),'normalized_duplicate_query_groups':len(collisions),'normalized_duplicate_groups_with_different_gold':sum(len({tuple(sorted(x)) for x in c['gold_sets']})>1 for c in collisions),'duplicate_details':collisions[:25],'source_sha256':{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()}}
(P/'label-structure-audit.json').write_text(json.dumps(result,indent=2)+'\n')
# Balanced review packet from the current cohort, independent of individual ranking outcomes.
cohort=rows(P/'evaluation-queries.jsonl');packet=[]
for k in (1,2,3):
 selected=sorted((x for x in cohort if x['k']==k),key=lambda x:hashlib.sha256(('cpu-label-review-v1'+x['id']).encode()).hexdigest())[:40]
 for x in selected:
  order=sorted(x['skill_ids'],key=lambda sid:hashlib.sha256(('cpu-label-order-v1'+x['id']+sid).encode()).hexdigest())
  packet.append({'query_id':x['id'],'query':x['query'],'review_order_skills':[{'skill_id':sid,'name':skills[sid]['name'],'description':skills[sid]['description'],'body':skills[sid]['body'],'source_url':skills[sid].get('source_url'),'reviewer_1_label':None,'reviewer_1_evidence':None,'reviewer_2_label':None,'reviewer_2_evidence':None,'adjudicated_label':None} for sid in order]})
if not (P/'label-review-packet.json').exists(): (P/'label-review-packet.json').write_text(json.dumps({'status':'Prepared, NOT reviewed. 40 queries per k, selected without retrieval success/failure. Original label order randomized; ranking outcomes omitted.','label_options':['required_for_request','relevant_optional','irrelevant','unclear'],'instructions':'Judge against the actual request and full skill source. Cite the request span and source span. Distinguish AND requirements from OR alternatives. Two independent human reviewers, then adjudication. Do not automatically delete original labels or evaluate a model against its own judgments. The strata-balanced sample requires weights for corpus-level prevalence estimates.','queries':packet},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='duplicate_details'},indent=2))
print('Prepared 120 unreviewed queries,',sum(len(x['review_order_skills']) for x in packet),'positive-label review items.')
