#!/usr/bin/env python3
"""Latency-only workload for the native service. Uses pinned documents and DEV text.

prepare writes a separate benchmark snapshot; run exercises an already published
benchmark repo. No quality labels, model cache writes, or production claims.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def one(url, token, payload):
    start = time.perf_counter()
    req = urllib.request.Request(url+'/v1/search',data=json.dumps(payload).encode(),
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        try:
            r = urllib.request.urlopen(req, timeout=8)
        except urllib.error.HTTPError as e:
            r = e
        with r:
            body = json.loads(r.read())
            return {'status':r.status,'elapsed_ms':(time.perf_counter()-start)*1000,
                    'server_ms':float(r.headers.get('X-Guidefold-Server-Ms','nan')),
                    'ranked_sha256':digest(body.get('ranked')),'selected_sha256':digest(body.get('cards')),
                    'stages_ms':body.get('stages_ms',{}),'snapshot':body.get('snapshot'),
                    'error':body.get('error'),'backend':body.get('backend')}
    except Exception as e:
        return {'status':0,'elapsed_ms':(time.perf_counter()-start)*1000,'error':type(e).__name__}


def worker():
    p=json.load(sys.stdin)
    token = Path(p['token_file']).read_text().strip()
    print(json.dumps(one(p['url'],token,p['payload'])))


def prepare(args):
    from tools.search_service.index import with_router_index
    from tools.eval import corpora, skillret
    from tools.serve_spike.server import load_cli_snapshot
    from tools.serve_spike.repository import canonical
    cli, sha = load_cli_snapshot(ROOT/'skills/guidefold/scripts/guidefold')
    assert not corpora.verify('skillret')
    data = corpora.corpus_dir('skillret')/'data'
    skills=[json.loads(line) for line in (data/'skills/test.jsonl').read_text().splitlines()]
    taxonomy=json.loads((data/'taxonomy.json').read_text())
    nodes, _, node_of = skillret.build_taxonomy(cli,taxonomy)
    cards, _ = skillret.build_cards(skills,node_of)
    index=skillret.build_r0_index(cli,cards,nodes)
    snapshot={'format':'guidefold-service-snapshot-v1','repo_id':'skillret-service-bench',
              'revision':skillret.CORPUS_REVISION,'cli_sha256':sha,'nodes':nodes,'cards':cards,
              'weights':index.weights,'source':'pinned_public_documents_latency_only','assets_included':False}
    bundle={'snapshot':snapshot,'sha256':hashlib.sha256(canonical(snapshot)).hexdigest()}
    bundle=with_router_index(cli,bundle,index)
    output=ROOT/'.guidefold/compose/benchmark-snapshot.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(canonical(bundle)+b'\n')
    print(json.dumps({'cards':len(cards),'sha256':bundle['sha256'],'output':str(output)}))


def summary(rows):
    def stats(v):
        v=sorted(v)
        return {f'p{p}':round(v[max(0,math.ceil(len(v)*p/100)-1)],3) for p in (50,95,99)} if v else None
    ok=[r for r in rows if r['status']==200]
    stages=sorted({k for r in ok for k in r['stages_ms']})
    return {'attempted':len(rows),'ok':len(ok),'errors':len(rows)-len(ok),
            'client_ms':stats([r['elapsed_ms'] for r in ok]),
            'server_ms':stats([r['server_ms'] for r in ok]),
            'over_400_ms':sum(r['elapsed_ms']>400 for r in rows),
            'over_300_ms':sum(r['elapsed_ms']>300 for r in rows),
            'stages_ms':{k:stats([r['stages_ms'][k] for r in ok]) for k in stages}}


def run(args):
    from tools.serve_spike.probe import load_queries
    token=(ROOT/'.guidefold/compose/secrets/api_token').read_text().strip()
    url='http://127.0.0.1:'+os.environ.get('GUIDEFOLD_PORT','8765')
    health=json.load(urllib.request.urlopen(url+'/health/ready'))
    assert health['repository']['repo_id']=='skillret-service-bench' and health['n_skills']==6006
    queries, provenance=load_queries(args.count)
    def payload(q):
        return {'schema_version':'1.1','query':q['query'],'node':'_root','profile':'hook','deadline_ms':5000}
    for q in queries[:10]:
        assert one(url,token,payload(q))['status']==200
    result={'schema_version':1,'workload':provenance,'health_before':health,
            'environment':{'platform':platform.platform(),'python':sys.version,'cpu_count':os.cpu_count(),
                           'transport':'WSL2 to Docker Desktop loopback; HTTP, new TCP connection per request',
                           'resources_isolated':False},
            'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted((ROOT/'services/search').glob('*.go'))},
            'images':json.loads(subprocess.check_output(['docker','image','inspect','guidefold-search:local',
                                                       'paradedb/paradedb:0.25.6-pg17'],text=True)),
            'production_ready':False,'quality_evaluated':False,'legacy_ranking_parity_claimed':False,'arms':{}}
    # Keep only reproducibility fields; no unrelated host/container metadata or secrets.
    result['images']=[{'id':i['Id'],'digests':i['RepoDigests'],'size_bytes':i['Size']} for i in result['images']]
    for arm,concurrency,fresh,burst in [('http_c1',1,False,False),('http_c4',4,False,False),
                                       ('fresh_c1',1,True,False),('burst_fresh_c4',4,True,True)]:
        def invoke(q):
            if fresh:
                started=time.perf_counter()
                out=subprocess.run([sys.executable,str(Path(__file__).resolve()),'worker'],
                    input=json.dumps({'url':url,'token_file':str(ROOT/'.guidefold/compose/secrets/api_token'),'payload':payload(q)}),
                    text=True,capture_output=True,timeout=10,check=True)
                row=json.loads(out.stdout)
                row['http_ms']=row['elapsed_ms']
                row['elapsed_ms']=(time.perf_counter()-started)*1000
            else:
                row=one(url,token,payload(q))
            return {'query_id':q['id'],**row}
        started=time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            if burst:
                rows=[]
                for offset in range(0,len(queries),concurrency):
                    rows.extend(executor.map(invoke,queries[offset:offset+concurrency]))
            else:
                rows=list(executor.map(invoke,queries))
        result['arms'][arm]={'concurrency':concurrency,'fresh_process':fresh,'burst':burst,
                            'wall_seconds':time.perf_counter()-started,'summary':summary(rows),'responses':rows}
        print(json.dumps({'arm':arm,**summary(rows)}),flush=True)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
    arms=result['arms']
    reference=arms['http_c1']['responses']
    compared=[(a,b) for name,arm in arms.items() if name!='http_c1' for a,b in zip(reference,arm['responses'])]
    result['determinism']={'paired_responses':len(compared),'passed':all(
        a['status']==b['status']==200 and a['query_id']==b['query_id'] and a['snapshot']==b['snapshot']
        and a['ranked_sha256']==b['ranked_sha256'] and a['selected_sha256']==b['selected_sha256'] for a,b in compared)}
    result['gates']={name:{'client_400_passed':v['summary']['ok']==args.count and v['summary']['client_ms']['p95']<=400,
                          'server_300_passed':v['summary']['ok']==args.count and v['summary']['server_ms']['p95']<=300}
                     for name,v in arms.items()}
    result['health_after']=json.load(urllib.request.urlopen(url+'/health/ready'))
    args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker':
        worker()
    else:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('command',choices=('prepare','run'))
        parser.add_argument('--count',type=int,default=200)
        parser.add_argument('--output',type=Path,default=ROOT/'.guidefold/checks/go-paradedb-latency.json')
        args=parser.parse_args()
        prepare(args) if args.command=='prepare' else run(args)
