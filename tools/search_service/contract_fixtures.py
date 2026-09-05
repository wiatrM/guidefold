"""Regenerate native policy conformance vectors from the unchanged shipped Router.

No evaluation corpora or quality metrics are used. BM25 candidate ranks are
inputs, so these vectors test policy/selection independently of the new engine.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.serve_spike.server import load_cli_snapshot

cli, sha = load_cli_snapshot(ROOT / 'skills/guidefold/scripts/guidefold')
nodes = {'_root': {'owner': 'platform', 'paths': ['**']},
         'alpha': {'owner': 'żółć', 'paths': ['services/alpha/**']},
         'alpha.child': {'paths': ['services/alpha/child/**']},
         'beta': {'owner': 'team-beta', 'paths': ['services/beta/**']}}
cards = {}
for i in range(12):
    u = f'u:{i:02d}'
    cards[u] = {'urn': u, 'node': ['_root','alpha','alpha.child','beta'][i%4],
        'name': 'retry-' + str(i), 'description': 'Retry Kafka café 😀 <script>',
        'digest': 'retry database', 'triggers': ['postgres retry'],
        'negative_triggers': ['NO CAFÉ'] if i%5==0 else [],
        'requires': [f'u:{i-1:02d}'] if i else ['u:03'],
        'refines': ['u:00'] if i%3==0 else [],
        'status': 'deprecated' if i%7==0 else 'active',
        'replaced_by': 'u:01' if i%7==0 else None,
        '_body': 'Hello\n\u2028\u2029é 😀\\u2028'}
cases=[]
for ppr in ['closure','pagerank']:
 for abstain in ['magnitude','margin']:
  index=cli.Index.from_cards(cards,nodes,weights={'ppr_mode':ppr,'abstain_mode':abstain})
  router=cli.Router(index)
  for node in nodes:
   for query in ['retry','no cafe','NO CAFÉ']:
    allowed,drops=router.policy_filter(node,query)
    candidates=[{'urn':u,'node':cards[u]['node'],'bm25_rank':i+1,'dense_rank':(20-i if i%2 else None)} for i,u in enumerate(reversed(allowed))]
    scored=router.score(candidates,query,node)
    for k in [0,1,4]:
     selected=router.select(scored,k=k,admissible=set(allowed))
     cases.append({'node':node,'query':query,'weights':index.weights,'k':k,'allowed':allowed,'drops':len(drops),'candidates':candidates,'scored':scored,'selected':[c['urn'] for c in selected]})
fixture={'source_cli_sha256':sha,'nodes':nodes,'cards':cards,'cases':cases,
         'canonical_sha256':hashlib.sha256(json.dumps(cards,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
         'scope_map_sha256':hashlib.sha256(json.dumps(nodes,sort_keys=True).encode()).hexdigest(),
         'card_revision':hashlib.sha256(json.dumps(cards['u:01'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
out=ROOT/'services/search/testdata/policy.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n')
print('Wrote',len(cases),'policy cases to',out)
