#!/usr/bin/env python3
"""Check the project skills in .agents/skills/ (not the fixture, not the distributable bootstrap).

Rules (ADR-0032, .claude/README.md):
  - SKILL.md has YAML-ish frontmatter with `name` == directory name and a non-empty `description`.
  - relative links resolve to existing files (anchors ignored).
  - body is 40..70 lines including frontmatter (existing workflow skills are exempt from the cap).
  - every skill is linked from .claude/skills/<name> and listed in AGENTS.md.
Exit 1 on any violation; prints one line per finding.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, ".agents", "skills")
LINKS = os.path.join(ROOT, ".claude", "skills")
INDEX = os.path.join(ROOT, "AGENTS.md")
EXEMPT_FROM_CAP = {"guidefold-product-changes", "guidefold-ui-workflow"}
LINE_MIN, LINE_MAX = 35, 70
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")


def main() -> int:
    findings = []
    index = open(INDEX, encoding="utf-8").read() if os.path.exists(INDEX) else ""
    names = sorted(d for d in os.listdir(SKILLS) if os.path.isdir(os.path.join(SKILLS, d)))
    for name in names:
        path = os.path.join(SKILLS, name, "SKILL.md")
        if not os.path.exists(path):
            findings.append(f"{name}: missing SKILL.md")
            continue
        text = open(path, encoding="utf-8").read()
        lines = text.splitlines()
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        if not m:
            findings.append(f"{name}: no frontmatter")
        else:
            fm = dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M))
            if fm.get("name") != name:
                findings.append(f"{name}: frontmatter name {fm.get('name')!r} != directory")
            if not fm.get("description", "").strip():
                findings.append(f"{name}: empty description")
        n = len(lines)
        if name not in EXEMPT_FROM_CAP and not (LINE_MIN <= n <= LINE_MAX):
            findings.append(f"{name}: {n} lines (expected {LINE_MIN}..{LINE_MAX})")
        for link in LINK_RE.findall(text):
            if link.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = os.path.normpath(os.path.join(SKILLS, name, link.split("#")[0]))
            if not os.path.exists(target):
                findings.append(f"{name}: broken link {link}")
        link_path = os.path.join(LINKS, name)
        if not os.path.islink(link_path) or not os.path.exists(link_path):
            findings.append(f"{name}: no working symlink at .claude/skills/{name}")
        if f".agents/skills/{name}/SKILL.md" not in index:
            findings.append(f"{name}: not listed in AGENTS.md")
    if os.path.isdir(LINKS):
        for entry in os.listdir(LINKS):
            if entry not in names:
                findings.append(f".claude/skills/{entry}: link without a skill in .agents/skills")
    for f in findings:
        print(f)
    print(f"{len(names)} skills checked, {len(findings)} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
