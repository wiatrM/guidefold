#!/usr/bin/env python3
"""End-to-end parity of the default Go/Postgres SEARCH against the reference CLI.

Two modes:
  (default) the frozen 1,000 DEV queries over a flat SKILLRET corpus -- an equivalence check,
  not another quality trial on test-A/test-B. No qrels or query text are sent to the publisher.
  --fixture: the 220 labelled Meridian golden queries (their own node context, from
  tests/golden/*.yaml) PLUS a small hand-designed synthetic set (>=20) that deliberately
  exercises structural features the flat DEV corpus has none of: requires/refines graph edges,
  scope hierarchy depth, negative_triggers, a deprecated skill, abstention, tokenizer accent/
  digit edge cases, and per-field BM25F weight coverage. A dedicated adapter check additionally
  runs the real, unmodified `search_with_backend` client at the k values the product actually
  uses (hook k=3, find's default k=8, interactive k=4) to regression-test the budget.max_cards
  wire field. See docs/reports/bakeoff/PARITY-STRUCTURED-CORPUS-2026-09-05.md for the full
  characterisation this mode was built from.
"""
import argparse, concurrent.futures, gzip, hashlib, json, os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.search_service.index import with_router_index
from tools.search_service.quality import dataset
from tools.search_service.smoke import request
from tools.serve_spike.server import load_cli_snapshot
from tools.serve_spike.repository import canonical

# ---------------------------------------------------------------- E2.9 fixture synthetic set
# One deliberately-engineered query per structural feature that tests/golden/*.yaml's 220 cases
# and the flat SKILLRET DEV corpus above do not reliably stress on their own. `feature` is pure
# metadata (report/debugging only, never compared). See the report for the full rationale and
# what each query actually proved when run against the live service.
FIXTURE_SYNTHETIC_QUERIES = [
    {"qid": "scope-1a", "node": "atlas.identity.turnstile", "feature": "scope-distance (near)",
     "query": "connection pool and lock timeout conventions for postgres"},
    {"qid": "scope-1b", "node": "forge.ontology", "feature": "scope-distance (far)",
     "query": "connection pool and lock timeout conventions for postgres"},
    {"qid": "graph-1", "node": "atlas.identity.turnstile",
     "feature": "graph propagation (decayed closure via requires, ppr_mode=closure default)",
     "query": "paged for a TurnstileAuth alert, 403 spike, need rollout undo"},
    {"qid": "graph-2", "node": "forge.pipelines.streaming",
     "feature": "graph propagation (two simultaneous requires edges)",
     "query": "kafka topic ingestion needs the shared dataset conventions and spark pipeline "
              "conventions reviewed"},
    {"qid": "reqclosure-1", "node": "forge.ontology",
     "feature": "requires closure pulled into select()'s admissible set",
     "query": "ontology-modeling object type migration schema evolution steps"},
    {"qid": "reqclosure-2", "node": "security.audit",
     "feature": "requires closure pulled into select()'s admissible set",
     "query": "hash chained append only audit sink classification label rules"},
    {"qid": "negtrig-1", "node": "_root",
     "feature": "negative_triggers hard-drop in policy_filter",
     "query": "should I write an ADR for this routine refactor change"},
    {"qid": "negtrig-2", "node": "relay.k8s",
     "feature": "negative_triggers hard-drop in policy_filter",
     "query": "air-gapped offline bundle assembly for the edge site install"},
    {"qid": "negtrig-3", "node": "shared",
     "feature": "negative_triggers hard-drop in policy_filter",
     "query": "shared library version bump for the platform release train"},
    {"qid": "deprecated-1", "node": "atlas.identity",
     "feature": "deprecated-skill filtering (replaces-edge propagation is dead under the "
                "shipped ppr_mode=closure default -- see report)",
     "query": "atlas-wide sessions table evaluated roles separately per-service role check "
              "cookie-based session authorization"},
    {"qid": "abstain-1", "node": "_root",
     "feature": "abstention (zero-overlap gibberish -> empty candidates -> select() returns [])",
     "query": "zzqxw glorbnaxfizzquux xyzzyplugh123 wobbleflarp"},
    {"qid": "abstain-2", "node": "atlas.geo",
     "feature": "abstention (same gibberish at a non-root node)",
     "query": "zzqxw glorbnaxfizzquux xyzzyplugh123 wobbleflarp"},
    {"qid": "tok-accents-nfc", "node": "atlas.geo",
     "feature": "tokenizer accent-folding (NFC precomposed é)",
     "query": "géospatial indéxing h3 cell"},
    {"qid": "tok-accents-nfd", "node": "atlas.geo",
     "feature": "tokenizer accent-folding (NFD decomposed e + combining acute U+0301)",
     "query": "géospatial indéxing h3 cell"},
    {"qid": "tok-digits-1", "node": "atlas.geo",
     "feature": "tokenizer digits (alnum token boundaries)",
     "query": "H3 resolution 9 and GiST GIN BRIN index choice for postgres 15"},
    {"qid": "tok-digits-2", "node": "_root",
     "feature": "tokenizer digits (digit glued to a word)",
     "query": "b-tree vs gist vs gin index type for a jsonb column in postgres14"},
    {"qid": "field-triggers-1", "node": "forge.pipelines",
     "feature": "field weight: triggers-only match",
     "query": "chispa assert_df_equality golden-file test"},
    {"qid": "field-digest-1", "node": "security.audit",
     "feature": "field weight: digest-only match",
     "query": "hash chaining append-only sink tamper evidence"},
    {"qid": "field-name-1", "node": "atlas.identity.turnstile",
     "feature": "field weight: name-field exact match",
     "query": "turnstile-oncall-runbook"},
    {"qid": "scope-2a", "node": "atlas.identity.turnstile",
     "feature": "scope-distance (2-hop ancestor)",
     "query": "rbac policy and role evaluation for a new service integration"},
    {"qid": "scope-2b", "node": "shared.auth-sdk",
     "feature": "scope-distance (cross-subtree via requires)",
     "query": "rbac policy and role evaluation for a new service integration"},
    {"qid": "graph-3", "node": "relay.k8s",
     "feature": "refines edge (NOT a propagation input under ppr_mode=closure -- requires-only; "
                "checks refines has no incidental scoring effect)",
     "query": "helm chart conventions and the release process it refines"},
    {"qid": "multi-1", "node": "forge.ontology",
     "feature": "multi-skill composite query (compose_mode default off -> legacy closure-fill)",
     "query": "need both the ontology modeling approach and the postgres schema migration "
              "conventions for a new object type"},
]


def _compute_expected(router, cases):
    expected = {}
    for case in cases:
        q = case['query']; node = case.get('node', '_root')
        allowed, _ = router.policy_filter(node, q)
        ranked = router.score(router.candidates(q, node), q, node)
        selected = router.select(ranked, k=4, admissible=set(allowed), query=q)
        expected[case['qid']] = {'ranked': [[x['urn'], x['score']] for x in ranked[:10]],
                                  'selected': [x['urn'] for x in selected]}
    return expected


def _budget_adapter_checks(cli, router, url, token):
    """Exact regression check for the E2.9 budget.max_cards defect (independently found and
    reproduced by the service worktree's MERIDIAN-GRAPH-PARITY-2026-09-05.md report): runs the
    REAL, unmodified `search_with_backend` adapter -- not a raw HTTP diff -- at the k values the
    product actually uses (hook k=3, find's default k=8, interactive k=4) and asserts no
    parity_mismatch, and that an unrepresentable k (>4) never races the remote at all."""
    tmproot = Path(tempfile.mkdtemp())
    query, node = 'monorepo conventions and adr process for a new service', '_root'
    rows = []
    for label, k, profile in (('hook', 3, 'hook'), ('find_default', 8, 'interactive'),
                               ('interactive', 4, 'interactive')):
        search_cfg = {'backend': 'service', 'url': url, 'deadline_ms': 5000, 'token': token,
                      'config_error': False}
        result = cli.search_with_backend(tmproot, router, query, node, profile=profile, k=k,
                                          search_id=f'parity-fixture-budget-{k}',
                                          search_cfg=search_cfg)
        representable = 0 <= k <= 4
        ok = result['parity_mismatch'] is False and (
            (representable and result['backend'] == 'online_sparse') or
            (not representable and result['backend'] == 'local_sparse'
             and result['degradation_reason'] == 'config'))
        rows.append({'label': label, 'k': k, 'backend': result['backend'],
                      'degradation_reason': result['degradation_reason'],
                      'parity_mismatch': result['parity_mismatch'], 'passed': ok})
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',action='store_true',
                         help='Meridian + 220 golden + synthetic structural probes, instead of the 1,000-query DEV set')
    parser.add_argument('--output',type=Path,default=None)
    args=parser.parse_args()
    output=args.output or (ROOT/'.guidefold/checks/router-parity-fixture.json' if args.fixture else ROOT/'.guidefold/checks/router-parity.json')
    cli,sha=load_cli_snapshot(ROOT/'skills/guidefold/scripts/guidefold')
    if args.fixture:
        print('Preparing Meridian fixture + golden + synthetic corpus',flush=True)
        cards,nodes,cases,index,revision,conversion=dataset('regression',cli)
        cases=list(cases)+[dict(q) for q in FIXTURE_SYNTHETIC_QUERIES]
        repo='meridian-fixture-parity'
        source='meridian_fixture_golden_plus_synthetic'
    else:
        print('Preparing reference DEV corpus and canonical postings',flush=True)
        cards,nodes,cases,index,revision,conversion=dataset('dev',cli)
        repo='skillret-router-parity'
        source='frozen_dev_parity_only'
    data={'format':'guidefold-service-snapshot-v1','repo_id':repo,'revision':revision,'cli_sha256':sha,'nodes':nodes,'cards':cards,'weights':index.weights,'source':source,'assets_included':False}
    envelope={'snapshot':data,'sha256':hashlib.sha256(canonical(data)).hexdigest()}
    bundle=with_router_index(cli,envelope,index)
    (ROOT/'.guidefold/compose/parity-snapshot.json').write_bytes(canonical(bundle)+b'\n')
    print('Prepared',len(cases),'queries,',len(cards),'documents',flush=True)
    env=dict(os.environ,GUIDEFOLD_REPO=repo,GUIDEFOLD_LEXICAL_ENGINE='router')
    def compose(*a):subprocess.run(['docker','compose',*a],cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
    compose('--profile','tools','run','--rm','publish','publish','/input/parity-snapshot.json')
    compose('up','-d','--wait','api')
    url='http://127.0.0.1:'+os.environ.get('GUIDEFOLD_PORT','8765')
    token=(ROOT/'.guidefold/compose/secrets/api_token').read_text().strip()
    router=cli.Router(index)
    expected=_compute_expected(router,cases)
    print('Reference ready; measuring HTTP',flush=True)
    def invoke(case):
        status,body,ms,_=request(url,'/v1/search',token,{'schema_version':'1.1','query':case['query'],'node':case.get('node','_root'),'deadline_ms':5000,'budget':{'max_cards':4}})
        got={'ranked':[[r['urn'],r['score']] for r in body.get('ranked',[])],'selected':[r['urn'] for r in body.get('cards',[])]}
        want=expected[case['qid']]
        revision_ok=all(r['revision']==hashlib.sha256(json.dumps(cards[r['urn']],sort_keys=True,ensure_ascii=False).encode()).hexdigest() for r in body.get('ranked',[])+body.get('cards',[]))
        ok=status==200 and body.get('backend')=='router_bm25f_v1' and got==want and revision_ok
        return {'query_id':case['qid'],'status':status,'passed':ok,'revisions_passed':revision_ok,'elapsed_ms':ms,'snapshot':body.get('snapshot'),'expected_sha256':hashlib.sha256(canonical(want)).hexdigest(),'actual_sha256':hashlib.sha256(canonical(got)).hexdigest(),**({'expected':want,'actual':got,'error':body.get('error')} if not ok else {})}
    started=time.perf_counter()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(invoke,cases))
        budget_rows=_budget_adapter_checks(cli,router,url,token) if args.fixture else []
        result={'schema_version':1,
                'kind':'exact_fixture_router_api_parity' if args.fixture else 'exact_default_router_api_parity',
                'dataset':'meridian_golden_plus_synthetic' if args.fixture else 'frozen_skillret_train_dev',
                'attempted':len(rows),'http_ok':sum(r['status']==200 for r in rows),
                'mismatches':sum(not r['passed'] for r in rows),
                'exact_output_parity_passed':all(r['passed'] for r in rows) and all(b['passed'] for b in budget_rows),
                'scope':'API top10 URN+integer score, selected ordered URNs, immutable card revisions; same query/scope/snapshot; c=4','quality_evaluated':False,'test_a_or_b_queries_used':False,'cli_sha256':sha,'snapshot_sha256':envelope['sha256'],'router_index_sha256':bundle['router_index_sha256'],'documents':len(cards),'wall_s':time.perf_counter()-started,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'services/search').glob('*.go'))},'responses':rows,'budget_adapter_checks':budget_rows}
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k not in ('responses','source_sha256')}),flush=True)
        if not result['exact_output_parity_passed']:raise SystemExit('PARITY FAILED')
    finally:
        env['GUIDEFOLD_REPO']='meridian';compose('up','-d','--wait','api')

if __name__=='__main__':main()
