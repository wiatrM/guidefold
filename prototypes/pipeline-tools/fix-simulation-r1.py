from pathlib import Path
p=Path("prototypes/pipeline-wireframes/wireframes.js");s=p.read_text()
old="entry.textContent='Review decision: approve, edit or reject';"
new="entry.textContent=({draft:'Review decision: approve, edit or reject',editing:'Continue editing candidate',approved_for_export:'Continue to export',awaiting_git:'Review Git handoff',published:'Review publication evidence',rejected:'Review rejection reason'}[proposal().stage] || 'Review decision');"
assert old in s;s=s.replace(old,new)
old="link('usage','Check usage evidence',{skill:s.id,from:'proposals'},'button primary')"
new="link('usage','Check usage evidence',{skill:s.id,scope:s.scope,revision:p.digest || s.revision,from:'proposals'},'button primary')"
assert old in s;s=s.replace(old,new)
s=s.replace(" · publication not established</p>", " · publication at import: not established</p>")
p.write_text(s)
p=Path("docs/ui/pipeline/04-wireframes.md");s=p.read_text();s=s.replace("| skill |", "| revision | SHA-256 rewizji przy przejściu Published → Usage; przenoszony razem ze skill i scope (poprawka etapu 5). |\n| skill |");p.write_text(s)
