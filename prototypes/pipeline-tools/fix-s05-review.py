from pathlib import Path
for name in ["04-wireframes.md","05-simulation.md"]:
 p=Path("docs/ui/pipeline")/name;s=p.read_text().replace("U4 Q4/5", "U4 AC5 (co najmniej 4 z 5 prawdziwych osób)")
 if name=="05-simulation.md":
  s=s.replace("Syntetyczne „na głos”", "Parafrazy syntetycznego myślenia na głos")
  s="\n".join(line.replace("„","").replace("”","") if line.startswith(("| P1 ","| P2 ","| P3 ")) else line for line in s.split("\n"))
 p.write_text(s)
p=Path("skills/guidefold/SKILL.md");s=p.read_text();s="\n".join(line for line in s.split("\n") if not line.startswith("compatibility:"))
s=s.replace("# Guidefold organizational guidance", "# Guidefold organizational guidance\n\nRequires Python 3 and PyYAML. Agent Registry access also needs a configured gcloud CLI and registry\npermissions. Service search needs a configured URL and bearer token.")
p.write_text(s)
