#!/usr/bin/env python3
"""Generate BM25F conformance vectors from the unchanged CLI, never Go."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.serve_spike.server import load_cli_snapshot
from tools.serve_spike.repository import canonical
from tools.search_service.index import with_router_index
cli,sha=load_cli_snapshot(ROOT/'skills/guidefold/scripts/guidefold')
cards={}
for i,(name,description,body) in enumerate([
 ('api-auth','PostgreSQL authentication and API scope','postgres postgres jwt token authentication'),
 ('postgres-safe','SQL database migration','safe transaction migration '*31),
 ('api-scope','API API policy scope','small'),
 ('unicode','Cafe café ﬁeld Kelvin 한국어','NUL\x00value A\u0301 api'),
 ('empty','',''),
]):
 u=f'urn:skill:test:_root:{name}'
 cards[u]={'urn':u,'node':'_root','name':name,'description':description,'digest':description[:20], 'triggers':['api auth'] if i==0 else [],'negative_triggers':[],'requires':[],'refines':[],'status':'active','_body':body}
nodes={'_root':{'owner':'test','paths':['*']}}
out=[]
for label,weights in [('default',{}),('zero',dict.fromkeys(['field.'+f for f in cli.Index.FIELDS],0)),('large',dict.fromkeys(['field.'+f for f in cli.Index.FIELDS],1000000))]:
 index=cli.Index.from_cards(cards,nodes,weights=weights);router=cli.Router(index)
 snapshot={'cards':cards,'nodes':nodes,'weights':index.weights,'cli_sha256':sha}
 envelope={'snapshot':snapshot,'sha256':hashlib.sha256(canonical(snapshot)).hexdigest()}
 bundle=with_router_index(cli,envelope,index)
 cases=[]
 for q in ['api','api api auth','postgres transaction','cafe field kelvin','한국어','NUL value','missing','', 'api '*2048]:
  for allowed in [set(cards),set(sorted(cards)[1:])]:
   scores=router._bm25_scores(q,allowed)
   cases.append({'query':q,'allowed':sorted(allowed),'scores':scores})
 out.append({'name':label,'bundle':bundle,'cases':cases})
(ROOT/'services/search/testdata/bm25f.json').write_bytes(canonical({'source_cli_sha256':sha,'groups':out})+b'\n')
print(f'Generated {sum(len(g["cases"]) for g in out)} CLI BM25F cases')