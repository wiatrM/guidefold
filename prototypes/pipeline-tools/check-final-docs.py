from pathlib import Path
import re,json
root=Path('.').resolve()
docs=[Path(p) for p in ['AGENTS.md','CLAUDE.md','CONTRIBUTING.md','README.md','docs/DOCUMENTATION-RULES.md','docs/PRODUCT-PIVOT.md','docs/PIVOT-ARCHITECTURE.md','docs/PIVOT-BACKLOG.md','docs/PIVOT-REVIEW.md','docs/ui/IA.md','docs/ui/UX.md','docs/ui/UI.md','ui/README.md','ui/design-qa.md']]
docs+=list(Path('docs/ui/pipeline').glob('*.md'))+list(Path('.agents/skills').glob('*/SKILL.md'))
errors=[]
for p in docs:
 s=p.read_text()
 for match in re.finditer(r'\[[^\]]*\]\(([^)]+)\)',s):
  link=match[1].strip('<>').split('#')[0]
  if not link or re.match(r'^[\w+-]+:',link) or link.startswith('//'):continue
  if not (p.parent/link).exists():errors.append({'file':str(p),'link':link})
caps=[]
for p in Path('docs/ui/pipeline').glob('*.md'):
 n=len(p.read_text().splitlines());limit=30 if p.name=='README.md' else 40 if p.name.startswith('00-') else 120
 caps.append({'file':p.name,'lines':n,'limit':limit});assert n<=limit,(p,n,limit)
 if p.name!='README.md':
  footer=p.read_text().split('## Przegląd')[-1].strip().splitlines();assert len(footer)<=5,(p,footer)
print(json.dumps({'checkedDocuments':len(docs),'missingLinks':errors,'lineCaps':caps},ensure_ascii=False,indent=2))
if errors:raise SystemExit(1)
