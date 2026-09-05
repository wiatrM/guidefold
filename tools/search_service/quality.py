#!/usr/bin/env python3
"""One frozen ParadeDB quality reference vs unchanged local F0 on pinned corpora.

Shared corpus converters, policy path and metric functions are reused. HTTP sends
query + root scope only, never labels. Per-query evidence survives interruption;
resume does not silently repeat already measured queries. Do not tune on tests.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tools/eval'))
from tools.search_service.index import with_router_index
from tools.search_service.smoke import request
from tools.serve_spike.server import load_cli_snapshot
from tools.serve_spike.repository import canonical
from tools.eval import corpora, skillret, skillretbench, metrics, run_golden


def clean(value):
    if isinstance(value,float) and not math.isfinite(value):
        return None
    if isinstance(value,dict):
        return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [clean(v) for v in value]
    return value


def source_identity():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'services/search').glob('*.go'))}


def dataset(name,cli):
    if name in ('dev','test_a'):
        assert not corpora.verify('skillret')
        data=corpora.corpus_dir('skillret')/'data'
        split='train' if name=='dev' else 'test'
        skills=[json.loads(s) for s in (data/f'skills/{split}.jsonl').open()]
        queries=[json.loads(s) for s in (data/f'queries/{split}.jsonl').open()]
        if name=='dev':
            ids=set(json.loads(corpora.DEV_SPLIT.read_text())['query_ids'])
            queries=[q for q in queries if q['id'] in ids]
        nodes,_,node_of=skillret.build_taxonomy(cli,json.loads((data/'taxonomy.json').read_text()))
        cards,id_to_urn=skillret.build_cards(skills,node_of)
        cases=skillret.build_cases(queries,id_to_urn)
        for c in cases:
            c['id']=c['qid']; c['node']='_root'
        revision=skillret.CORPUS_REVISION
        conversion={'input_queries':len(queries),'cases':len(cases),'documents':len(cards)}
    elif name=='test_b':
        assert not corpora.verify('skillretbench')
        data=corpora.load_skillretbench()
        cards,nodes,card_report=skillretbench.corpus_to_cards(data['corpus']['skills'])
        cases,query_report=skillretbench.queries_to_cases(data['queries']['queries'],cards)
        for c in cases:
            c['qid']=c['id'];c['node']='_root';c['k']=len(c['relevant'])
        revision=corpora.manifest()['corpora']['skillretbench']['revision']
        conversion={'cards':card_report,'queries':query_report}
    else:
        root=ROOT/'examples/monorepo'
        index=cli.Index.build(root,cli.load_map(root))
        cards,nodes=index.cards,index.nodes
        cases=run_golden.load_cases()
        for c in cases:
            c['qid']=c['id'];c['k']=len(c.get('relevant',[]))
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        conversion={'regression_only':True,'input_queries':len(cases)}
    index=cli.Index.from_cards(cards,nodes,weights={'w_dense':0})
    return cards,nodes,cases,index,revision,conversion


def compose(env,*args):
    subprocess.run(['docker','compose',*args],cwd=ROOT,env=env,check=True,
                   stdout=subprocess.DEVNULL)


def aggregate(ret,inj):
    return {'official':skillret.evaluate_full(ret,inj),
            'by_category':skillret.by_category_full(ret,inj),
            'retrieval_denominators':metrics.evaluate(ret),
            'injection_denominators':metrics.evaluate(inj)}


def compare(a_ret,a_inj,b_ret,b_inj):
    pairs={'hit@1':(a_ret,b_ret,metrics.hit_at_1),
           'ndcg@10':(a_ret,b_ret,lambda r,c:metrics.ndcg_at_k(r,c,10)),
           'all_required@4':(a_inj,b_inj,lambda r,c:metrics.all_required_at_k(r,c,4)),
           'HSR@4':(a_inj,b_inj,lambda r,c:metrics.distractor_rate(r,c,4))}
    result={}
    for metric,(a,b,fn) in pairs.items():
        av={c['qid']:fn(r,c) for r,c in a if r}
        bv={c['qid']:fn(r,c) for r,c in b if r}
        result[metric]=skillret.paired_bootstrap_ci(av,bv,n_resamples=1000,seed=0)
    # Supplemental identical-denominator diagnostic. Metric functions unchanged;
    # unlike the historical answered-only table, empty rankings count as a miss.
    full={}
    for metric,(a,b,fn) in pairs.items():
        av={c['qid']:fn(r,c) for r,c in a if not metrics.is_abstention_case(c)}
        bv={c['qid']:fn(r,c) for r,c in b if not metrics.is_abstention_case(c)}
        full[metric]={'f0':metrics._mean(av.values()),'paradedb':metrics._mean(bv.values()),
                      **skillret.paired_bootstrap_ci(av,bv,n_resamples=1000,seed=0)}
    return {'official_common_answered_paired_ci':result,'all_answerable_diagnostic':full}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',choices=('dev','test_a','test_b','regression'),required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'.guidefold/checks/go-quality')
    args=parser.parse_args()
    out=args.output_dir
    out.mkdir(parents=True,exist_ok=True)
    report_path=out/(args.dataset+'.json')
    if report_path.exists():
        raise SystemExit('Completed report exists; refusing to rerun a frozen corpus.')
    cli,sha=load_cli_snapshot(ROOT/'skills/guidefold/scripts/guidefold')
    cards,nodes,cases,index,revision,conversion=dataset(args.dataset,cli)
    assert len({c['qid'] for c in cases})==len(cases)
    repo='quality-'+args.dataset.replace('_','-')
    data={'format':'guidefold-service-snapshot-v1','repo_id':repo,'revision':revision,
          'cli_sha256':sha,'nodes':nodes,'cards':cards,'weights':index.weights,
          'source':'pinned_quality_reference','assets_included':False}
    bundle={'snapshot':data,'sha256':hashlib.sha256(canonical(data)).hexdigest()}
    bundle=with_router_index(cli,bundle,index)
    snapshot_file=ROOT/'.guidefold/compose/quality-snapshot.json'
    snapshot_file.write_bytes(canonical(bundle)+b'\n')
    identity={'variant':'paradedb_bm25_v1','dataset':args.dataset,'scope':'case.node for regression; _root otherwise',
              'snapshot_sha256':bundle['sha256'],'cli_sha256':sha,'go_source_sha256':source_identity(),
              'corpus_revision':revision,'cases_sha256':hashlib.sha256(canonical(cases)).hexdigest(),
              'conversion':conversion,'n_queries':len(cases),'n_skills':len(cards),
              'configuration':'ParadeDB 0.25.6 defaults; name+description+digest+triggers+body concatenation; NUL=>space only in search projection; top50 score desc/URN bytewise asc; isolated IDF per snapshot; score/closure/select shared-policy port',
              'tuning_on_test':False,'test_variant_run_number':1,'production_ready':False}
    identity_file=out/(args.dataset+'-identity.json')
    if identity_file.exists():
        assert json.loads(identity_file.read_text())==identity, 'Frozen identity changed; cannot resume'
    else:
        identity_file.write_text(json.dumps(identity,indent=2)+'\n')
    env=dict(os.environ,GUIDEFOLD_REPO=repo,GUIDEFOLD_LEXICAL_ENGINE='paradedb-experimental')
    compose(env,'--profile','tools','run','--rm','publish','publish','/input/quality-snapshot.json')
    compose(env,'up','-d','--wait','api')
    url='http://127.0.0.1:'+os.environ.get('GUIDEFOLD_PORT','8765')
    token=(ROOT/'.guidefold/compose/secrets/api_token').read_text().strip()
    rows_file=out/(args.dataset+'-responses.jsonl')
    existing=[]
    if rows_file.exists():
        with rows_file.open() as saved:
            existing=[json.loads(line) for line in saved]
    done={r['query_id']:r for r in existing}
    assert len(done)==len(existing)
    def invoke(case):
        payload={'schema_version':'1.1','query':case['query'],'node':case['node'],
                 'profile':'hook','deadline_ms':5000}
        status,body,ms,_=request(url,'/v1/search',token,payload)
        return {'query_id':case['qid'],'status':status,'elapsed_ms':ms,'snapshot':body.get('snapshot'),
                'ranked':body.get('ranked',[]),'cards':body.get('cards',[]),'error':body.get('error')}
    try:
        pending=[c for c in cases if c['qid'] not in done]
        with rows_file.open('a') as file, ThreadPoolExecutor(max_workers=4) as pool:
            for row in pool.map(invoke,pending):
                file.write(json.dumps(row,ensure_ascii=False)+'\n');file.flush()
                done[row['query_id']]=row
                if len(done)%250==0:
                    print(json.dumps({'dataset':args.dataset,'http_completed':len(done),'total':len(cases)}),flush=True)
        assert all(r['status']==200 for r in done.values()), 'HTTP errors retained; quality run incomplete'
        assert all(r['snapshot']=='repository:'+bundle['sha256'] for r in done.values())
        # Shared Python Router baseline, exact same cards, scopes and policy weights.
        print(json.dumps({'dataset':args.dataset,'baseline':'started','queries':len(cases)}),flush=True)
        baseline_file=out/(args.dataset+'-f0.json.gz')
        if baseline_file.exists():
            baseline=json.loads(gzip.decompress(baseline_file.read_bytes()))
            a_ret=[(baseline[c['qid']]['retrieval'],c) for c in cases]
            a_inj=[(baseline[c['qid']]['injection'],c) for c in cases]
        else:
            a_ret,a_inj,records,_=skillret.run_arm_parallel(cli.Router(index),cases,lambda c:c['node'],False,n_workers=4)
            baseline={c['qid']:{'retrieval':r,'injection':i} for (r,c),(i,_) in zip(a_ret,a_inj)}
            baseline_file.write_bytes(gzip.compress(canonical(baseline),mtime=0))
        b_ret=[([r['urn'] for r in done[c['qid']]['ranked']],c) for c in cases]
        b_inj=[([r['urn'] for r in done[c['qid']]['cards']],c) for c in cases]
        result={**identity,'f0':aggregate(a_ret,a_inj),'paradedb':aggregate(b_ret,b_inj),
                'comparison':compare(a_ret,a_inj,b_ret,b_inj),
                'http_attempts':len(done),'http_errors':0,'labels_sent_to_service':False,
                'latency_note':'Quality run timings are diagnostic only; dedicated latency benchmark is separate.'}
        if args.dataset=='test_b':
            # Preserve every budget-constrained case in the full table. Exclude only
            # that predeclared impossible-25-skills stratum from completeness view.
            filt=lambda pairs:[(r,c) for r,c in pairs if c['setting']!='budget_constrained']
            result['without_budget_constrained']={'f0':aggregate(filt(a_ret),filt(a_inj)),
                'paradedb':aggregate(filt(b_ret),filt(b_inj)),
                'comparison':compare(filt(a_ret),filt(a_inj),filt(b_ret),filt(b_inj))}
        report_path.write_text(json.dumps(clean(result),indent=2,allow_nan=False)+'\n')
        print(json.dumps(clean({'dataset':args.dataset,'f0':result['f0']['official'],
                               'paradedb':result['paradedb']['official']})),flush=True)
    finally:
        # Return the developer's local API to the published Meridian catalog.
        compose(dict(os.environ,GUIDEFOLD_REPO='meridian'),'up','-d','--wait','api')


if __name__=='__main__':
    main()
