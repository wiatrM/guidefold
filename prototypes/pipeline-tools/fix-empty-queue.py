from pathlib import Path
p=Path("prototypes/pipeline-wireframes/wireframes.js");s=p.read_text();assert "<h2>Requires review</h2>" in s;s=s.replace("<h2>Requires review</h2>","<h2>Review queue</h2>");p.write_text(s)
p=Path("prototypes/pipeline-tools/s05-regressions.mjs");s=p.read_text().replace("const url=new URL(page.url());", "report.checks.push({check:'empty queue neutral heading',pass:await page.getByRole('heading',{name:'Review queue',exact:true}).count()===1});\nconst url=new URL(page.url());");p.write_text(s)
