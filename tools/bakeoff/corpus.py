"""corpus.py — loads the Meridian fixture (examples/monorepo) into skill records.

Reuses the shipped CLI's own frontmatter parsing (`skills/guidefold/scripts/guidefold`)
instead of reimplementing it: that script has no `.py` extension (it ships as a
single executable file inside the skill ZIP), so it is loaded dynamically with
`importlib.machinery.SourceFileLoader`.

Every arm and every distillation step in this directory should build its corpus
by calling `load_corpus()` here, never by walking `examples/monorepo` itself.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"
FIXTURE_ROOT = REPO_ROOT / "examples" / "monorepo"


def _load_cli_module():
    """Dynamically load the stdlib+PyYAML CLI script as a module named `guidefold_cli`.

    The script has no `.py` suffix, so a plain `import` cannot find it; the loader
    below is the mechanism `importlib` documents for exactly this case.
    """
    loader = importlib.machinery.SourceFileLoader("guidefold_cli", str(CLI_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


cli = _load_cli_module()


@dataclass(frozen=True)
class SkillRecord:
    urn: str
    node: str
    name: str
    description: str
    digest: str
    triggers: tuple = field(default_factory=tuple)
    body: str = ""
    status: str = "active"
    requires: tuple = field(default_factory=tuple)
    replaced_by: Optional[str] = None

    def fields_text(self) -> dict:
        """name/description/digest/triggers/body as separate strings, for field-weighted BM25 (B1)."""
        return {
            "name": self.name,
            "description": self.description,
            "digest": self.digest,
            "triggers": " ".join(self.triggers),
            "body": self.body,
        }

    def concat_text(self) -> str:
        """All fields concatenated, for the tier-1 static skill vectors (B4) — see distill.py."""
        parts = [self.name, self.description, self.digest, " ".join(self.triggers), self.body]
        return "\n".join(p for p in parts if p)


def _body_of(skill_md: Path) -> str:
    """Everything after the closing `---` of the frontmatter block."""
    text = skill_md.read_text()
    m = cli.FM.match(text)
    return text[m.end():].strip() if m else text.strip()


def load_corpus(fixture_root: Path = FIXTURE_ROOT) -> list[SkillRecord]:
    """All non-deprecated-and-non-generated... no: ALL skills (including deprecated), excluding the
    generated hierarchy-index skill. Policy filtering (status: deprecated) is a router-stage concern
    (ROUTER-SPEC-v2.md stage 0), not a corpus-loading concern, so deprecated skills stay in the corpus
    with `status="deprecated"` for callers to filter or keep as they see fit.

    `cli.all_skills(root, cfg)` defaults to `include_generated=False`, which already excludes the
    `hierarchy-index` skill written by `guidefold index` — see its `metadata.generated: "true"` guard.
    """
    cfg = cli.load_map(fixture_root)
    records = []
    for skill_dir, node, fm in cli.all_skills(fixture_root, cfg):
        md = fm.get("metadata") or {}
        name = fm.get("name") or skill_dir.name
        record = SkillRecord(
            urn=cli.urn(cfg, node, name),
            node=node,
            name=name,
            description=str(fm.get("description", "")),
            digest=cli.digest_of(fm),
            triggers=tuple(cli.md_list(md, "triggers")),
            body=_body_of(skill_dir / "SKILL.md"),
            status=str(md.get("status", "active")),
            requires=tuple(cli.md_list(md, "requires")),
            replaced_by=md.get("replaced_by"),
        )
        records.append(record)
    return sorted(records, key=lambda r: r.urn)  # deterministic order (ROUTER-SPEC-v2.md: doc ids by sorted URN)


if __name__ == "__main__":
    corpus = load_corpus()
    print(f"{len(corpus)} skills loaded from {FIXTURE_ROOT.relative_to(REPO_ROOT)}")
    for r in corpus:
        flag = f" [{r.status}]" if r.status != "active" else ""
        print(f"- {r.urn}{flag}")
