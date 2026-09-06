#!/usr/bin/env python3
"""Structural corpus checks; never a semantic correctness score."""
import collections, hashlib, json, statistics, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/eval'))
import corpora
sf=corpora.corpus_dir('skillret')/'data/skills/train.jsonl'
rows=[json.loads(x) for x in sf.open()]
def norm(t):return ' '.join(str(t).lower().split())
def group(field):
 c=collections.Counter(norm(s.get(field,'')) for s in rows)
 return {'duplicate_groups_nonempty':sum(n>1 and bool(t) for t,n in c.items()),'extra_copies_nonempty':sum(n-1 for t,n in c.items() if n>1 and t),'largest_group':max(c.values())}
report={'source_sha256':hashlib.sha256(sf.read_bytes()).hexdigest(),'n':len(rows),'duplicates':{f:group(f) for f in ['name','description','body']},'fields':{},'interpretation':'Structural diagnostics only. Repeated names/descriptions can be legitimate; this does not measure correctness or task utility and performs no deletion.'}
for field in ['name','description','body']:
 lens=sorted(len(str(s.get(field,''))) for s in rows)
 report['fields'][field]={'empty':sum(not str(s.get(field,'')).strip() for s in rows),'chars_p50':statistics.median(lens),'chars_p95':lens[int(.95*(len(lens)-1))],'chars_max':max(lens),'under_30_chars':sum(n<30 for n in lens)}
p=Path(__file__).with_name('corpus-quality.json')
if p.exists():assert json.loads(p.read_text())==report
p.write_text(json.dumps(report,indent=2)+'\n')
print('PASS: structural audit reproduces saved result')
