import json
from pathlib import Path
for who in ["owner","dev","operator"]:
 d=json.loads(Path(f"prototypes/pipeline-wireframes/qa/s05-{who}-r1.json").read_text())
 d=d.get("report",d)
 tasks=d.get("tasks",d.get("zadania",[]))
 print(who,[(t.get("id"),t.get("clicks",t.get("klikniecia")),t.get("typingOperations",t.get("pisanie")),t.get("select")) for t in tasks])
