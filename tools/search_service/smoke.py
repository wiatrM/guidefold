#!/usr/bin/env python3
"""Exercise the running Go/ParadeDB Compose stack using its real HTTP contract.

--recovery stops/restarts only this Compose project's DB and API. Secrets are
read from files and never printed. This is an integration check, not a qrels eval.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def request(url, path, token='', payload=None, raw=None):
    data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
    req = urllib.request.Request(url + path, data=data, headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    start = time.perf_counter()
    try:
        response = urllib.request.urlopen(req, timeout=8)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = json.loads(response.read())
        return response.status, body, (time.perf_counter()-start)*1000, dict(response.headers)


def compose(*args, check=True):
    return subprocess.run(['docker', 'compose', *args], cwd=ROOT, check=check,
                          capture_output=True, text=True)


def sql(statement):
    return compose('exec', '-T', 'db', 'psql', '-U', 'postgres', '-d', 'guidefold',
                   '-XAt', '-v', 'ON_ERROR_STOP=1', '-c', statement).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:' + os.environ.get('GUIDEFOLD_PORT', '8765'))
    parser.add_argument('--recovery', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    from jsonschema import Draft202012Validator
    schema = json.loads((ROOT/'tools/serve_spike/contracts/harness-service-v1.1.schema.json').read_text())
    validators = {kind: Draft202012Validator({**schema, '$ref': '#/$defs/'+kind,
                                            'oneOf': [{}]})
                  for kind in ('search_response', 'use_response')}
    token = (ROOT/'.guidefold/compose/secrets/api_token').read_text().strip()
    bundle = json.loads((ROOT/'.guidefold/compose/snapshot.json').read_text())['snapshot']
    checks = []
    def expect(name, endpoint='search', payload=None, status=200, raw=None, auth=None):
        code, body, ms, _ = request(args.url, '/v1/'+endpoint, token if auth is None else auth, payload, raw)
        assert code in (status if isinstance(status, tuple) else (status,)), (name, code, body)
        if code == 200 and body.get('schema_version') == '1.1':
            validators[endpoint+'_response'].validate(body)
        checks.append({'name':name, 'status':code, 'elapsed_ms':round(ms,3)})
        return body
    status, health, _, _ = request(args.url, '/health/ready')
    assert status == 200 and health['runtime'] == 'go' and not health['python_runtime']
    assert health['backend']=='router_bm25f_v1' and health['router_index_revision']
    workspace = {'repo_id': bundle['repo_id'], 'revision':bundle['revision'], 'cwd':'.'}
    base = {'schema_version':'1.1', 'query':'pytest pipeline testing', 'workspace':workspace}
    search = expect('search_response_schema_and_generated_request_id', payload=base)
    assert search['cards'], 'Expected nonempty fixture result'
    assert search['retrieval']['engine'] == 'Guidefold integer BM25F / Postgres postings'
    assert search['retrieval']['exact_legacy_ranking_parity'] is True
    explicit = expect('correlation', payload={**base, 'request_id':'test-request',
                      'session_id':'test-session', 'task_id':'test-task'})
    assert explicit['request_id'] == 'test-request' and explicit['session_id'] == 'test-session'
    card = search['cards'][0]
    use = {'schema_version':'1.1', 'skill_id':card['skill_id'], 'revision':card['revision'],
           'search_id':search['search_id'], 'workspace':workspace}
    body = expect('search_to_use', 'use', use)
    assert body['body'] == bundle['cards'][card['skill_id']]['_body']
    assert body['checksum'] == hashlib.sha256(body['body'].encode()).hexdigest()
    assert body['snapshot'] == search['snapshot'] and body['execution_observed'] is False
    expect('legacy_search', payload={'query':base['query']})
    expect('legacy_use_nullable_search_id', 'use', {k:use[k] for k in ('skill_id','revision')} | {'search_id':None})
    expect('unauthorized', payload=base, status=401, auth='invalid')
    expect('duplicate_key', raw=b'{"query":"one","query":"two"}', status=400)
    expect('invalid_unicode', raw=b'{"query":"\\ud800"}', status=400)
    expect('unknown_field', payload={**base,'typo':True}, status=400)
    expect('body_limit', raw=b' '*16385, status=413)
    expect('float_integer', payload={**base,'deadline_ms':1.0}, status=400)
    expect('wrong_repo', payload={**base,'workspace':{**workspace,'repo_id':'other'}}, status=409)
    expect('stale_revision', payload={**base,'workspace':{**workspace,'revision':'stale'}}, status=409)
    expect('path_traversal', payload={**base,'workspace':{**workspace,'cwd':'../secret'}}, status=400)
    expect('unknown_scope', payload={**base,'workspace':{**workspace,'cwd':'unmapped-area/x'}}, status=422)
    expect('stale_skill', 'use', {**use,'revision':'stale'}, status=409)
    expect('use_budget_atomic', 'use', {**use,'budget':{'max_bytes':1}}, status=413)
    limited = expect('search_budget_atomic', payload={**base,'budget':{'max_bytes':1}})
    assert limited['cards'] == [] and limited['card_context'] == ''
    assert limited['context']['delivery_status'] == 'cannot_fit'
    loaded = [{'skill_id':c['skill_id'],'revision':c['revision'],'state':'hydrated'} for c in search['cards']]
    omitted = expect('loaded_hydrated_no_backfill', payload={**base,'loaded_skills':loaded})
    assert omitted['cards'] == [] and omitted['context']['loaded_cards_omitted'] == len(loaded)
    exposed = expect('loaded_exposed_still_delivered', payload={**base,'loaded_skills':[
        {**item,'state':'exposed'} for item in loaded]})
    assert exposed['cards'] == search['cards']
    scoped = expect('monorepo_scope', payload={**base,'workspace':{**workspace,'cwd':'platforms/forge/pipelines/jobs'}})
    assert scoped['context']['resolved_scopes'] == ['forge.pipelines']
    assert scoped['context']['scope_owners']['forge.pipelines'] == 'pipelines-team'
    multi = expect('target_paths_override_cwd', payload={**base, 'workspace':{**workspace,
        'target_paths':[{'path':'platforms/forge/pipelines/jobs','source':'edited'},
                        {'path':'infra/relay/k8s/manifests','source':'user_explicit'}]}})
    assert set(multi['context']['resolved_scopes']) == {'forge.pipelines','relay.k8s'}
    assert multi['context']['fusion'] == 'max_score_then_urn'
    outside = next(c for c in bundle['cards'].values() if c['node'] == 'relay.k8s' and c['status']=='active')
    # Obtain its revision through the catalog's normal root SEARCH candidates.
    broad = expect('outside_card_lookup', payload={**base,'query':outside['name']})
    target = next(c for c in broad['ranked'] if c['skill_id'] == outside['urn'])
    expect('use_scope_policy', 'use', {**use,'skill_id':target['skill_id'],'revision':target['revision'],
           'workspace':{**workspace,'cwd':'platforms/forge/pipelines/jobs'}}, status=403)
    expect('literal_query_not_sql', payload={**base, 'query':"pytest '); DROP TABLE gf.skills; --"})
    extra = expect('unused_signals_reported', payload={**base,'intent':{'action':'test'},
        'stack':{'languages':['python']},'constraints':['read_only']})
    assert {'intent','stack','constraints'} <= {x['field'] for x in extra['context']['unused_fields']}
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(executor.map(lambda _: request(args.url,'/v1/search',token,base), range(40)))
    assert all(x[0] == 200 and x[1]['cards'] == search['cards'] for x in responses)
    checks.append({'name':'concurrent_determinism','passed_requests':len(responses)})
    health_after = request(args.url, '/health/ready')[1]
    assert health_after['database_search_calls'] > health['database_search_calls']
    assert health_after['database_use_calls'] > health['database_use_calls']
    assert health_after['body_cache'] is False
    # Real DB permissions and the actual index plan, not a mock repository.
    assert sql("SELECT has_table_privilege('guidefold_api','gf.skills','SELECT') AND NOT has_table_privilege('guidefold_api','gf.skills','INSERT')") == 't'
    table = 'gf.search_' + hashlib.sha256((os.environ.get('GUIDEFOLD_TENANT','local')+'\0'+bundle['repo_id']+'\0'+search['snapshot']).encode()).hexdigest()[:48]
    plan = sql("EXPLAIN SELECT urn,paradedb.score(id) FROM " + table + " WHERE search_text ||| 'pytest' ORDER BY paradedb.score(id) DESC, urn COLLATE \"C\" ASC LIMIT 50")
    assert 'TopKScanExecState' in plan, plan
    count = sql('SELECT count(*) FROM gf.skills')
    published = compose('--profile','tools','run','--rm','publish')
    assert '"already_present":true' in published.stdout and sql('SELECT count(*) FROM gf.skills') == count
    checks.append({'name':'database_index_readonly_role_idempotent_publish','passed':True})
    # Another repository must not change this repository's BM25 statistics.
    original = json.loads((ROOT/'.guidefold/compose/snapshot.json').read_text())
    candidate = ROOT/'.guidefold/compose/integration-snapshot.json'
    def write_bundle(data, valid=True):
        raw = json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
        from tools.search_service.index import with_router_index
        from tools.serve_spike.server import load_cli_snapshot
        cli,_=load_cli_snapshot(ROOT/'skills/guidefold/scripts/guidefold')
        value={'snapshot':data,'sha256':hashlib.sha256(raw).hexdigest() if valid else 'invalid'}
        candidate.write_text(json.dumps(with_router_index(cli,value),ensure_ascii=False))
    other = deepcopy(original['snapshot'])
    other['repo_id'] = 'isolation-probe'
    for item in other['cards'].values():
        item['_body'] = 'pytest testing ' * 1000
    write_bundle(other)
    compose('--profile','tools','run','--rm','-e','GUIDEFOLD_REPO=isolation-probe','publish','publish','/input/integration-snapshot.json')
    isolated = expect('other_repository_does_not_change_bm25',payload=base)
    assert isolated['ranked'] == search['ranked'] and isolated['cards'] == search['cards']
    changed = deepcopy(original['snapshot'])
    changed['revision'] = 'integration-revision'
    changed['cards'][card['skill_id']]['_body'] += '\nExact UTF-8: café \0 end.'
    try:
        write_bundle(changed, valid=False)
        failed = compose('--profile','tools','run','--rm','publish','publish','/input/integration-snapshot.json',check=False)
        assert failed.returncode != 0
        assert expect('bad_publication_keeps_head',payload=base)['snapshot'] == search['snapshot']
        write_bundle(changed)
        compose('--profile','tools','run','--rm','publish','publish','/input/integration-snapshot.json')
        expect('snapshot_head_rejects_old_workspace',payload=base,status=409)
        new_card = changed['cards'][card['skill_id']]
        new_revision = hashlib.sha256(json.dumps(new_card,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        new_use = {**use,'revision':new_revision,'workspace':{**workspace,'revision':changed['revision']}}
        changed_body = expect('exact_nul_body_after_atomic_publication','use',new_use)
        assert changed_body['body'] == new_card['_body']
        assert changed_body['checksum'] == hashlib.sha256(new_card['_body'].encode()).hexdigest()
        expect('changed_skill_rejects_old_revision','use',{**new_use,'revision':use['revision']},status=409)
    finally:
        compose('--profile','tools','run','--rm','publish')
    assert expect('reactivate_previous_snapshot',payload=base)['ranked'] == search['ranked']
    if args.recovery:
        try:
            compose('stop','db')
            assert request(args.url,'/health/live')[0] == 200
            assert request(args.url,'/health/ready')[0] in (503,504)
            expect('database_down_no_inmemory_search_fallback',payload=base,status=(503,504))
            expect('database_down_no_body_cache_fallback','use',use,status=(503,504))
        finally:
            compose('up','-d','--wait','db')
        for _ in range(30):
            if request(args.url,'/health/ready')[0] == 200:
                break
            time.sleep(0.5)
        recovered = expect('database_recovery_same_body','use',use)
        assert recovered['checksum'] == body['checksum']
        compose('restart','api')
        compose('up','-d','--wait','api')
        restarted = expect('api_restart_persisted_catalog','use',use)
        assert restarted['checksum'] == body['checksum']
    logs = compose('logs','--no-color','api').stdout
    assert token not in logs and base['query'] not in logs and body['body'] not in logs
    assert 'platforms/forge/pipelines/jobs' not in logs
    assert 'scope_map_revision' in logs and 'card_revisions' in logs
    checks.append({'name':'telemetry_allowlist_redaction','passed':True})
    result = {'passed':True,'checks':checks,'health':health_after,'bm25_explain':plan,
              'recovery_exercised':args.recovery,'production_ready':False}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'checks':len(checks),'concurrent_requests':40,
                      'recovery_exercised':args.recovery}))


if __name__ == '__main__':
    main()
