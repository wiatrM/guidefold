#!/usr/bin/env python3
"""Explicitly post-hoc exact sign-flip fragility check; does not change the primary gate."""
import collections,datetime,gzip,hashlib,itertools,json,math
from pathlib import Path
P=Path(__file__).resolve().parent
q={r['id']:set(r['skill_ids']) for r in map(json.loads,(P/'cache/evaluation-queries.jsonl').open())}
c={r['query_id']:r['component'] for r in json.loads((P/'gold-sharing-components.json').read_text())['query_components']}
records=collections.defaultdict(dict)
for r in map(json.loads,gzip.open(P/'rankings.jsonl.gz','rt')):records[r['query_id']][r['arm']]=r
assert len(records)==len(q)==2048

def exact(v):
    v=[x for x in v if abs(x)>1e-14];n=len(v)
    if n>20:return {'nonzero_units':n,'computed':False,'reason':'Exact enumeration restricted to <=20 units.'}
    observed=abs(math.fsum(v));extreme=0;total=2**n
    for sign in itertools.product((-1,1),repeat=n):
        statistic=abs(math.fsum(a*b for a,b in zip(sign,v)))
        extreme+=statistic>=observed-1e-12
    return {'nonzero_units':n,'computed':True,'assignments':total,'two_sided_extreme_assignments':extreme,'two_sided_exact_p':extreme/total,'statistic':'absolute sum of paired metric differences; fixed denominator cancels','assumption':'paired arm-label exchangeability / symmetric sign null; this observational retrieval comparison is not a randomized treatment trial'}

out={'status':'post-hoc fragility sensitivity; does not alter preregistered gate','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'primary_gate_preserved':json.loads((P/'results.json').read_text())['advance_to_full_coverage_gate'],'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'metrics':{}}
for metric in ['recall10','all_gold_selected4']:
    changes=[];clusters=collections.defaultdict(float)
    for qid,r in records.items():
        d=r['C_metadata_queries']['metrics'][metric]-r['A_original']['metrics'][metric]
        if abs(d)>1e-14:changes.append({'query_id':qid,'gold_k':len(q[qid]),'component':c[qid],'difference':d,'gold_skill_ids':sorted(q[qid])})
        clusters[c[qid]]+=d
    m={'positive_query_differences':sum(r['difference']>0 for r in changes),'negative_query_differences':sum(r['difference']<0 for r in changes),'unchanged_queries':len(q)-len(changes),'changed_k_counts':dict(collections.Counter(r['gold_k'] for r in changes)),'changed_queries':changes,'query_sign_flip':exact([r['difference'] for r in changes]),'component_sign_flip':exact(list(clusters.values())),'nonzero_components':{str(k):v for k,v in clusters.items() if abs(v)>1e-14}}
    out['metrics'][metric]=m
    print(metric,'changed',len(changes),'query p',m['query_sign_flip']['two_sided_exact_p'],'component p',m['component_sign_flip']['two_sided_exact_p'])
(P/'posthoc-fragility.json').write_text(json.dumps(out,indent=2)+'\n')
