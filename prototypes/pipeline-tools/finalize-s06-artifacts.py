from pathlib import Path
import json
p=Path('../pipeline-hifi/qa/copy-review.json');d=json.loads(p.read_text())
for e in d['entries']:
 if e['text']=='Source commit':
  e['readAloud']['verdict']='clear in context'
  e['readAloud']['rationale']='Identifies the abbreviated source Git commit next to the organization; not the candidate SHA or publication state. Synthetic root editorial review, 2026-09-06.'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=Path('audit-hifi.mjs');s=p.read_text()
s=s.replace("const views=['import','library','map','skill','proposals','usage','organization'];","const allViews=['import','library','map','skill','proposals','usage','organization'];\nconst views=process.env.VIEWS?process.env.VIEWS.split(','):allViews;\nif(views.some(v=>!allViews.includes(v)))throw Error('Unknown view');\nlet previous={records:[],states:[]};if(process.env.VIEWS)previous=JSON.parse(await fs.readFile(path.join(out,'report.json'),'utf8'));")
s=s.replace("await fs.writeFile(path.join(out,'report.json'),JSON.stringify({fixture:'Meridian fixture',origin,records,states},null,2));","const mergedRecords=[...previous.records.filter(r=>!views.includes(r.view)),...records];\nconst mergedStates=[...previous.states.filter(r=>!views.includes(r.view)),...states];\nfor(const r of mergedRecords)r.screenshotCapturedAt=(await fs.stat(path.join(out,r.view+'-'+r.width+'.png'))).mtime.toISOString();\nawait fs.writeFile(path.join(out,'report.json'),JSON.stringify({generatedAt:new Date().toISOString(),fixture:'Meridian fixture',origin,records:mergedRecords,states:mergedStates},null,2));")
p.write_text(s)
p=Path('../../docs/ui/pipeline/06-ux-ui.md');s=p.read_text().replace('95 tokenów','101 tokenów').replace('119 deklaracjom','129 deklaracjom').replace('685 wystąpień/szablonów, 116 kontekstów dynamicznych','683 wystąpienia/szablony, 115 kontekstów dynamicznych').replace('638,31 kB / 172,19 kB','około 639 kB / 172 kB')
s=s.replace('Wpisane są również powody mobile/desktop, skip-link i offsetu focusu.','Wpisane są również powody mobile/desktop, skip-link, focusu oraz nowych minimalnych szerokości tabeli/kolumn i zwartego układu filtrów.')
s=s.replace('Długi Markdown ma semantyczne nagłówki','Library mieści pierwszy pełny wiersz na y661–718 przy 1280×720; przycisk kontynuacji Import na y661–701. Mobilny kontekst zachowuje krótki source commit. [Pomiar](../../../prototypes/pipeline-hifi/qa/s06-fold.json).\nDługi Markdown ma semantyczne nagłówki')
s=s.replace('## Przegląd\nW toku; etap 7 nie rozpoczyna się przed dwiema rundami i 0 otwartych P1/P2.','## Przegląd\nR1 — Owner: 0/0/0; Designer wizualny: P1=0/P2=1/P3=2. Naprawiono ściskane tabele, brak mobilnego commitu i wynik poniżej folda.\nR2 — oczekuje; etap 7 nie rozpoczyna się przed 0 otwartych P1/P2.')
p.write_text(s)
p=Path('../../docs/ui/UI.md');s=p.read_text().replace('| two/aside/field/steps/metric-columns |','| table-min-width, table-first-column, source-disclosure-width | Czytelne minimum tabeli/kolumn i Source details; poziomy scroll zamiast liter w pionie. |\n| filter-columns, filter-form-columns/areas | Filtry i przyciski w zwartej kompozycji desktopu; pierwszy wynik widoczny w 720 px, na mobile kolejno. |\n| two/aside/field/steps/metric-columns |');p.write_text(s)
