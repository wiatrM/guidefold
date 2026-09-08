from pathlib import Path
p=Path('../pipeline-hifi/src/tokens.css');s=p.read_text().replace('--row-height:40px;','--table-min-width:640px; --table-first-column:240px; --source-disclosure-width:112px; --row-height:40px;');p.write_text(s)
p=Path('../pipeline-hifi/src/Shared.module.css');s=p.read_text().replace('.table{width:var(--full);','.table{min-width:var(--table-min-width);width:var(--full);').replace('vertical-align:top;overflow-wrap:anywhere;','vertical-align:top;overflow-wrap:normal;')
s+='\n.table th{white-space:nowrap;}.table td:first-child{min-width:var(--table-first-column);}\n';p.write_text(s)
p=Path('../pipeline-hifi/src/routes/CatalogRoutes.module.css');s=p.read_text().replace('.skillCell { display: flex; gap: var(--space-3); align-items: baseline; }','.skillCell { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: baseline; }').replace('.sourceDetails { flex: 1; min-width: 0;','.sourceDetails { flex: 1; min-width: var(--source-disclosure-width);')
p.write_text(s)
p=Path('audit-tokens.py');s=p.read_text().replace("(('form','reading','source-width'),","(('table','source-disclosure'),'Minimalna czytelna szerokość tabeli i linku Source details; zamiast pojedynczych liter w kolumnie jest przewijanie poziome.'),\n(('form','reading','source-width'),");p.write_text(s)
