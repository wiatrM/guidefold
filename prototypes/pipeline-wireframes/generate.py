from pathlib import Path
import json
import hashlib

ROOT = Path(__file__).resolve().parent
fixture = json.loads((ROOT / 'fixture.json').read_text(encoding='utf-8-sig'))
for skill in fixture['skills']:
    assert hashlib.sha256(skill['raw'].encode()).hexdigest() == skill['revision'], skill['name']
data = json.dumps(fixture, ensure_ascii=False).replace('<', '\\u003c')
css = (ROOT / 'wireframes.css').read_text(encoding='utf-8-sig')
js = (ROOT / 'wireframes.js').read_text(encoding='utf-8-sig')
views = {'import':'Import','library':'Library','map':'Map','skill':'Skill','proposals':'Proposals','usage':'Usage & quality','organization':'Organization'}
for view, title in views.items():
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · Guidefold low-fi</title><style>{css}</style></head>
<body data-view="{view}"><a class="skip" href="#main">Skip to content</a><div id="app"></div><noscript>This local wireframe requires JavaScript to render the fixture.</noscript>
<script type="application/json" id="fixture">{data}</script><script>{js}</script></body></html>'''
    (ROOT / f'{view}.html').write_text(html, encoding='utf-8')
print(f'Generated {len(views)} self-contained views; {len(fixture["skills"])} verified skill digests.')
