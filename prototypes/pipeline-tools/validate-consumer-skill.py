from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess,sys
validator="/mnt/c/Users/ziomd/.codex/skills/.system/skill-creator/scripts/quick_validate.py"
with TemporaryDirectory(prefix="guidefold-skill-validation-") as tmp:
 folder=Path(tmp)/"guidefold";folder.mkdir()
 source=Path("skills/guidefold/SKILL.md").read_text().replace("<publisher>","meridian")
 (folder/"SKILL.md").write_text(source)
 result=subprocess.run([sys.executable,validator,str(folder)],check=False)
 print("Consumer template instantiated with the Meridian fixture publisher; no source fixture files changed.")
 sys.exit(result.returncode)
