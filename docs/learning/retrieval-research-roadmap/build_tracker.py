"""Build the offline tracker from the editable curriculum and local assets."""
from pathlib import Path
import html
import json
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent

def build():
    artifact = json.loads((ROOT / "artifact.json").read_text(encoding="utf-8"))
    data = json.loads((ROOT / "tracker-data.json").read_text(encoding="utf-8"))
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    sections = []
    for block in artifact["manifest"]["blocks"]:
        if block.get("type") != "markdown" or block["id"] == "title":
            continue
        body = block["body"]
        title = body.splitlines()[0].lstrip("# ").strip()
        rendered = md.render("\n".join(body.splitlines()[1:]))
        sections.append(f'<details class="reading" id="reading-{html.escape(block["id"])}"><summary>{html.escape(title)}</summary><div class="prose">{rendered}</div></details>')
    template = (ROOT / "tracker.template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    output = template.replace("<!--READING-->", "\n".join(sections))
    output = output.replace("/*TRACKER_DATA*/", payload)
    output = output.replace("/*TRACKER_SCRIPT*/", (ROOT / "tracker.js").read_text(encoding="utf-8"))
    assert "<!--READING-->" not in output and "/*TRACKER_" not in output
    (ROOT / "sciezka-nauki.html").write_text(output, encoding="utf-8")
    print(f'Built {len(output.encode("utf-8"))} bytes; {len(data["stages"])} stages')

if __name__ == "__main__":
    build()
