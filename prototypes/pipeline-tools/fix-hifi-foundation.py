from pathlib import Path
p=Path("prototypes/pipeline-hifi/src/data.ts");s=p.read_text().replace("state==='partial'?fixture.skills.slice(0,8):fixture.skills", "state==='partial'?[proposalSkill,...fixture.skills.filter(s=>s.id!==proposalSkill.id).slice(0,7)]:fixture.skills")
s=s.replace("export const bodyPrefix=(s:Skill)=>s.raw.slice(0,s.raw.length-s.body.length);", "export const bodyPrefix=(s:Skill)=>s.raw.match(/^---\\r?\\n[\\s\\S]*?\\r?\\n---(?:\\r?\\n)+/)?.[0] ?? '';")
p.write_text(s)
p=Path("prototypes/pipeline-hifi/index.html");s=p.read_text().replace('<meta name="theme-color" content="#081014">','');p.write_text(s)
