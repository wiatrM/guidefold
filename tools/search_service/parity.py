#!/usr/bin/env python3
"""End-to-end parity of the default Go/Postgres SEARCH against the reference CLI.

Uses the frozen 1,000 DEV queries only. This is an equivalence check, not another
quality trial on test-A/test-B. No qrels or query text are sent to the publisher.
"""
import argparse, concurrent.futures, gzip, hashlib, json, os, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.search_service.index import with_router_index
from tools.search_service.quality import dataset
from tools.search_service.smoke import request
from tools.serve_spike.server import load_cli_snapshot
from tools.serve_spike.repository import canonical


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'.guidefold/checks/router-parity.json')
    args=parser.parse_args()
    cli,sha=load_cli_snapshot(ROOT/'skills/guidefold/scripts/guidefold')
    print('Preparing reference DEV corpus and canonical postings',flush=True)
    cards,nodes,cases,index,revision,conversion=dataset('dev',cli)
    repo='skillret-router-parity'
    data={'format':'guidefold-service-snapshot-v1','repo_id':repo,'revision':revision,'cli_sha256':sha,'nodes':nodes,'cards':cards,'weights':index.weights,'source':'frozen_dev_parity_only','assets_included':False}
    envelope={'snapshot':data,'sha256':hashlib.sha256(canonical(data)).hexdigest()}
    bundle=with_router_index(cli,envelope,index)
    (ROOT/'.guidefold/compose/parity-snapshot.json').write_bytes(canonical(bundle)+b'\n')
    print('Prepared',len(cases),'queries,',len(cards),'documents',flush=True)
    env=dict(os.environ,GUIDEFOLD_REPO=repo,GUIDEFOLD_LEXICAL_ENGINE='router')
    def compose(*args):subprocess.run(['docker','compose',*args],cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
    compose('--profile','tools','run','--rm','publish','publish','/input/parity-snapshot.json')
    compose('up','-d','--wait','api')
    url='http://127.0.0.1:'+os.environ.get('GUIDEFOLD_PORT','8765')
    token=(ROOT/'.guidefold/compose/secrets/api_token').read_text().strip()
    router=cli.Router(index)
    expected={}
    for case in cases:
        q=case['query'];node=case.get('node','_root')
        allowed,_=router.policy_filter(node,q)
        ranked=router.score(router.candidates(q,node),q,node)
        selected=router.select(ranked,k=4,admissible=set(allowed))
        expected[case['qid']]={'ranked':[[x['urn'],x['score']] for x in ranked[:10]],'selected':[x['urn'] for x in selected]}
    print('Reference ready; measuring HTTP',flush=True)
    def invoke(case):
        status,body,ms,_=request(url,'/v1/search',token,{'schema_version':'1.1','query':case['query'],'node':case.get('node','_root'),'deadline_ms':5000})
        got={'ranked':[[r['urn'],r['score']] for r in body.get('ranked',[])],'selected':[r['urn'] for r in body.get('cards',[])]}
        want=expected[case['qid']]
        revision_ok=all(r['revision']==hashlib.sha256(json.dumps(cards[r['urn']],sort_keys=True,ensure_ascii=False).encode()).hexdigest() for r in body.get('ranked',[])+body.get('cards',[]))
        ok=status==200 and body.get('backend')=='router_bm25f_v1' and got==want and revision_ok
        return {'query_id':case['qid'],'status':status,'passed':ok,'revisions_passed':revision_ok,'elapsed_ms':ms,'snapshot':body.get('snapshot'),'expected_sha256':hashlib.sha256(canonical(want)).hexdigest(),'actual_sha256':hashlib.sha256(canonical(got)).hexdigest(),**({'expected':want,'actual':got,'error':body.get('error')} if not ok else {})}
    started=time.perf_counter()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(invoke,cases))
        result={'schema_version':1,'kind':'exact_default_router_api_parity','dataset':'frozen_skillret_train_dev','attempted':len(rows),'http_ok':sum(r['status']==200 for r in rows),'mismatches':sum(not r['passed'] for r in rows),'exact_output_parity_passed':all(r['passed'] for r in rows),'scope':'API top10 URN+integer score, selected ordered URNs, immutable card revisions; same query/scope/snapshot; c=4','quality_evaluated':False,'test_a_or_b_queries_used':False,'cli_sha256':sha,'snapshot_sha256':envelope['sha256'],'router_index_sha256':bundle['router_index_sha256'],'documents':len(cards),'wall_s':time.perf_counter()-started,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'services/search').glob('*.go'))},'responses':rows}
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k not in ('responses','source_sha256')}),flush=True)
        if not result['exact_output_parity_passed']:raise SystemExit('PARITY FAILED')
    finally:
        env['GUIDEFOLD_REPO']='meridian';compose('up','-d','--wait','api')

if __name__=='__main__':main()