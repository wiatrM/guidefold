"""Read-only BM25 audit; isolates existing definitions via AST to avoid torch imports."""
import ast
import sys
import collections
import math
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools/bakeoff'), str(ROOT / 'tools/eval')]
import corpus, tokenizer, compare_b0, metrics
source = (ROOT / 'tools/bakeoff/arms.py').read_text()
tree = ast.parse(source)
wanted = {'FIELD_WEIGHTS', 'BM25_K1', 'BM25_B', 'BM25Index', '_BM25_CACHE', '_corpus_key', '_bm25_index', 'arm_b1'}
nodes = [n for n in tree.body if (isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in wanted) or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in wanted for t in n.targets)) or (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id in wanted)]
ns = {'math': math, 'Counter': collections.Counter, 'tokenize': tokenizer.tokenize, 'DEFAULT_LIMIT': 50}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / 'tools/bakeoff/arms.py'), 'exec'), ns)
records = corpus.load_corpus()
cases = compare_b0.load_cases()
def clean(obj):
    if isinstance(obj, float) and not math.isfinite(obj): return None
    if isinstance(obj, dict): return {k: clean(v) for k,v in obj.items()}
    if isinstance(obj, list): return [clean(v) for v in obj]
    return obj

def detail(results):
    answered = [(r,c) for r,c in results if c.get('relevant')]
    complete_all = sum(all(v['urn'] in r[:4] for v in c['relevant'] if v['grade'] >= 2) for r,c in answered)
    strict_primary = sum(bool(r) and any(v['grade'] == 3 and v['urn'] == r[0] for v in c['relevant']) for r,c in answered)
    original = metrics.evaluate(results)
    return dict(original, strict_primary_hits=strict_primary, strict_primary_denominator=len(answered), strict_primary_at_1=strict_primary / len(answered) if answered else None, all_required_complete_count=complete_all, all_required_denominator=len(answered), all_required_complete_at_4=complete_all / len(answered) if answered else None)

report = {'note': 'Exploratory same-fixture sweep, not independent held-out evidence. Exact BM25Index AST definitions from arms.py; no torch import, no code changes.', 'n_cases': len(cases), 'n_skills': len(records), 'arms': {}}
for body_weight in [0, 1, 2, 3, 6]:
    weights = dict(ns['FIELD_WEIGHTS'], body=body_weight)
    idx = ns['BM25Index'](records, field_weights=weights)
    results = []
    for case in cases:
        scores = idx.scores(tokenizer.tokenize(case['query']))
        order = sorted(range(len(records)), key=lambda i: (-scores[i], records[i].urn))
        ranked = [records[i].urn for i in order if scores[i] > 0][:50]
        results.append((ranked, case))
    by_cat = {}
    for category in sorted({c['category'] for c in cases}):
        by_cat[category] = detail([(r,c) for r,c in results if c['category'] == category])
    raw = [{'case_id': c['id'], 'category': c['category'], 'ranked_urns': r} for r,c in results]
    arm = {'weights': weights, 'overall': detail(results), 'by_category': by_cat, 'rankings': raw}
    report['arms'][str(body_weight)] = arm
    print(json.dumps(clean({'body_weight': body_weight, 'overall': arm['overall'], 'multi_skill': by_cat['multi_skill'], 'sibling_ambiguity': by_cat['sibling_ambiguity'], 'stale_adversarial': by_cat['stale_adversarial']}), sort_keys=True))

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
out = args.out
out.parent.mkdir(parents=True, exist_ok=True)
import hashlib, subprocess
paths = [ROOT / 'tools/bakeoff' / f for f in ('arms.py', 'corpus.py', 'tokenizer.py')]
paths += [ROOT / 'tools/eval' / f for f in ('metrics.py', 'compare_b0.py', 'audit_e13.py')]
paths += [ROOT / 'skills/guidefold/scripts/guidefold']
paths += sorted((ROOT / 'tests/golden').glob('*.yaml'))
cfg = corpus.cli.load_map(corpus.FIXTURE_ROOT)
paths += [d / 'SKILL.md' for d, _, _ in corpus.cli.all_skills(corpus.FIXTURE_ROOT, cfg)]
report['git_sha'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
report['source_sha256'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
report['unanswerable_ids'] = [c['id'] for c in cases if not c.get('relevant')]
report['grade3_counts'] = dict(collections.Counter(sum(v['grade'] == 3 for v in c['relevant']) for c in cases if c.get('relevant')))
report['distractor_denominators'] = dict(collections.Counter(c['category'] for c in cases if c.get('distractors')))
report['recall_gate_max_gain_pp'] = (1 - report['arms']['1']['overall']['recall@8']) * 100
report['body_lengths'] = [dict(urn=r.urn, status=r.status, characters=len(r.body)) for r in records]
scores = {'A': (3, 9), 'B': (1, 2)}
report['dense_parity_counterexample'] = dict(scores=scores, cli_order=corpus.cli._dense_rank(scores), cosine_order=sorted(scores, key=lambda u: (-scores[u][0] / math.sqrt(scores[u][1]), u)))
out.write_text(json.dumps(clean(report), indent=2, sort_keys=True, allow_nan=False) + '\n')
print('RAW_OUTPUT', out)

