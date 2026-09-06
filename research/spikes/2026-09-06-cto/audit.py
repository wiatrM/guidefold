#!/usr/bin/env python3
"""Unchanged-router diagnostic replay, never an admission/quality benchmark."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
import platform
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('golden_audit', ROOT / 'tools/eval/run_golden.py')
golden = importlib.util.module_from_spec(spec)
spec.loader.exec_module(golden)

def distribution(values):
    values = sorted(values)
    if not values:
        return {'n': 0}
    return {'n': len(values), 'min': values[0], 'p50': values[math.ceil(.5 * len(values)) - 1],
            'p95': values[math.ceil(.95 * len(values)) - 1], 'max': values[-1]}

def main():
    cli = golden._load_cli()
    idx = cli.Index.build(golden.MONOREPO_DIR, cli.load_map(golden.MONOREPO_DIR))
    router = cli.Router(idx)
    rows = []
    for c in golden.load_cases():
        candidates = router.candidates(c['query'], c['node'])
        scored = router.score(candidates, c['query'], c['node'])
        allowed, _ = router.policy_filter(c['node'], c['query'])
        selected = router.select(scored, k=4, admissible=set(allowed))
        rows.append({'id': c['id'], 'category': c['category'], 'scored_n': len(scored),
                     'top_score': scored[0]['score'] if scored else None,
                     'selected': [x['urn'] for x in selected]})
    probes = []
    for query in ['zzzxqvvvqqq', 'zzzxqvvvqqq api', 'zzzxqvvvqqq deployment',
                  'Write a rhyming sonnet about a cat called API.',
                  'Translate the word deployment into a love poem.']:
        scored = router.score(router.candidates(query, '_root'), query, '_root')
        allowed, _ = router.policy_filter('_root', query)
        selected = router.select(scored, k=4, admissible=set(allowed))
        probes.append({'query': query, 'scored_n': len(scored),
                       'top_score': scored[0]['score'] if scored else None,
                       'selected': [x['urn'] for x in selected]})
    bodies = []
    for u, card in sorted(idx.cards.items()):
        body = card['_body']
        bodies.append({'urn': u, 'utf8_bytes': len(body.encode('utf-8')),
                       'markdown_atx_heading_count': len(re.findall(r'(?m)^#{1,6} +', body)),
                       'sha256': hashlib.sha256(body.encode('utf-8')).hexdigest()})
    by_category = {}
    for category in sorted({r['category'] for r in rows}):
        subset = [r for r in rows if r['category'] == category]
        by_category[category] = {
            'n': len(subset), 'abstained': sum(not r['selected'] for r in subset),
            'top_score': distribution([r['top_score'] for r in subset if r['top_score'] is not None]),
            'nonempty_below_threshold': sum(r['top_score'] < idx.weights['abstain_threshold']
                                          for r in subset if r['top_score'] is not None)}
    result = {
        'kind': 'structural_development_diagnostic_not_quality_evidence',
        'python': platform.python_version(),
        'git_revision': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                                      text=True, check=True).stdout.strip(),
        'cli_sha256': hashlib.sha256(golden.CLI_PATH.read_bytes()).hexdigest(),
        'weights': idx.weights, 'single_leg_rrf_rank1_score': idx.RRF_SCALE // (idx.RRF_K + 1),
        'by_category': by_category, 'cases': rows, 'synthetic_probes': probes,
        'hydration': {
            'body_bytes': distribution([b['utf8_bytes'] for b in bodies]),
            'heading_count': distribution([b['markdown_atx_heading_count'] for b in bodies]),
            'fits_use_byte_proxy_budget': {str(budget): sum(b['utf8_bytes'] <= budget for b in bodies)
                                          for budget in [1024, 4096, 16384]},
            'bodies': bodies,
            'limitation': 'Byte proxy only. No tokenizer, section relevance, HTTP latency or task utility measured.'}}
    (HERE / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'by_category': by_category, 'synthetic_probes': probes,
                      'hydration': {k: v for k, v in result['hydration'].items() if k != 'bodies'}}, indent=2))

if __name__ == '__main__':
    main()
