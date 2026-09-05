#!/usr/bin/env python3
"""tools/authoring/suggest_triggers.py — authoring loop, part 1, deliverable #2
(docs/MVP.md §5 "3-6 authoring loop": "F5 trigger/negative-trigger suggestions in `validate` (owner
approves in the PR)").

For every skill added or changed between `--base` and `--head` that has an empty `triggers` and/or
an empty `negative_triggers`, produce a ready-to-paste `metadata:` frontmatter block plus the
evidence for each suggested phrase (which body line produced it). **Suggestions only — this script
never writes to a SKILL.md.** An owner reads the PR comment and decides.

Reuses `tools/enrich/derive.py`'s F5 extractor (section mining -> "when to use"/"do not use"
material; sentence mining in unheaded prose) — deterministic, no model. `derive.LLM_EXTENSION_POINT`
documents the (unused) seam for an eventual model-based pass; nothing here calls one, and CI must
never turn one on.

Usage:
    python3 tools/authoring/suggest_triggers.py --root <consumer root> --base <ref> --head <ref> \\
        [--json out.json] [--md out.md]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
import _snapshot as snap  # noqa: E402

REPO_ROOT = snap.REPO_ROOT
_ENRICH_DIR = REPO_ROOT / "tools" / "enrich"


def load_derive_module():
    """Import tools/enrich/derive.py -- the single F5 extractor. Never reimplemented here.

    Registers the module in `sys.modules` *before* `exec_module`, same as `tests/test_enrich_derive.py`
    -- `derive.py`'s `@dataclass` classes need `sys.modules[cls.__module__]` to already exist while
    the class body executes (Python's dataclass field-type resolution looks the defining module up
    by name); skipping this raises `AttributeError: 'NoneType' object has no attribute '__dict__'`."""
    spec = importlib.util.spec_from_file_location("gf_authoring_derive", _ENRICH_DIR / "derive.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["gf_authoring_derive"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------------- evidence lookup
_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def find_evidence_line(body: str, phrase: str) -> str:
    """Best-effort locate the body line that produced a derived phrase, for the suggestion's
    evidence column. This is a *display-time* text search over a phrase `derive.py` already
    extracted and classified -- it does not re-run any of derive.py's section/sentence/heading
    classification, only re-finds where that phrase's own words already live in the source text,
    so the extraction logic itself is never duplicated here."""
    tokens = [t.lower() for t in _WORD_RE.findall(phrase) if len(t) > 2]
    if not tokens:
        return "(no evidence line found)"
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    for want in (tokens[:4], tokens[:2]):
        if not want:
            continue
        for line in lines:
            low = line.lower()
            if all(t in low for t in want):
                return line[:200]
    longest = max(tokens, key=len)
    for line in lines:
        if longest in line.lower():
            return line[:200]
    return "(no evidence line found)"


# --------------------------------------------------------------------------------- suggestion core
def build_skill_dicts(idx) -> list:
    """`derive()` wants the whole corpus at once (edge mining needs every other skill's name/id as
    candidates) -- built from the same `Index.cards` collision_report.py reads, never a second
    parse of SKILL.md."""
    out = []
    for u in sorted(idx.cards.keys()):
        c = idx.cards[u]
        out.append({
            "id": u, "name": c.get("name", ""), "description": c.get("description", ""),
            "body": c.get("_body", ""), "requires": list(c.get("requires") or []),
            "triggers": list(c.get("triggers") or []),
            "negative_triggers": list(c.get("negative_triggers") or []),
        })
    return out


def render_frontmatter_block(triggers: list, negative_triggers: list) -> str:
    """The exact `metadata:` shape docs/CONVENTIONS.md §4 documents -- comma-separated phrases in
    one quoted scalar string per key (Agent Registry rejects non-scalar metadata, ADR-0010)."""
    lines = ["metadata:"]
    if triggers:
        lines.append(f'  triggers: "{", ".join(triggers)}"')
    if negative_triggers:
        lines.append(f'  negative_triggers: "{", ".join(negative_triggers)}"')
    return "\n".join(lines)


def suggestions_for(head_idx, base_idx, derive_mod) -> list:
    """Skills added or changed base -> head that have an empty `triggers` and/or an empty
    `negative_triggers` in HEAD, with F5-derived suggestions for whichever field(s) are empty."""
    added, removed, changed = snap.diff_cards(base_idx, head_idx)
    targets = sorted(u for u in (added | changed)
                      if not head_idx.cards[u].get("triggers") or not head_idx.cards[u].get("negative_triggers"))
    if not targets:
        return []

    skills = build_skill_dicts(head_idx)
    enrichment = derive_mod.derive(skills)

    out = []
    for u in targets:
        card = head_idx.cards[u]
        enr = enrichment.get(u)
        if enr is None:
            continue
        missing_triggers = not card.get("triggers")
        missing_neg = not card.get("negative_triggers")

        sug_triggers, evidence = [], {}
        if missing_triggers:
            for phrase, prov in zip(enr.triggers, enr.provenance["triggers"]):
                if not prov.get("derived"):
                    continue
                sug_triggers.append(phrase)
                evidence[phrase] = find_evidence_line(card.get("_body", ""), phrase)
        sug_neg = []
        if missing_neg:
            for phrase, prov in zip(enr.negative_triggers, enr.provenance["negative_triggers"]):
                if not prov.get("derived"):
                    continue
                sug_neg.append(phrase)
                evidence[phrase] = find_evidence_line(card.get("_body", ""), phrase)

        out.append({
            "urn": u, "node": card.get("node"),
            "missing_triggers": missing_triggers, "missing_negative_triggers": missing_neg,
            "suggested_triggers": sug_triggers, "suggested_negative_triggers": sug_neg,
            "evidence": evidence,
            "frontmatter_block": render_frontmatter_block(sug_triggers, sug_neg),
            "found_nothing": missing_triggers and missing_neg and not sug_triggers and not sug_neg,
        })
    return out


# --------------------------------------------------------------------------------- rendering
def render_markdown(suggestions: list) -> str:
    L = ["## Trigger/negative-trigger suggestions (F5, deterministic — suggestions only, never auto-applied)", ""]
    if not suggestions:
        L.append("No added or changed skill is missing `triggers`/`negative_triggers`.")
        return "\n".join(L)
    for s in suggestions:
        L.append(f"### `{s['urn']}` (node `{s['node']}`)")
        if s["found_nothing"]:
            L.append("")
            L.append("Missing `triggers`/`negative_triggers` and the F5 extractor found no usage or "
                      "exclusion material to derive from — add a `## When to use / when NOT to use` "
                      "section, or write these fields by hand.")
            L.append("")
            continue
        if s["suggested_triggers"] or s["suggested_negative_triggers"]:
            L.append("")
            L.append("Paste into `metadata:`:")
            L.append("```yaml")
            L.append(s["frontmatter_block"])
            L.append("```")
            L.append("")
            L.append("Evidence:")
            for phrase in s["suggested_triggers"]:
                L.append(f"- trigger `{phrase}` <- \"{s['evidence'].get(phrase, '(no evidence line found)')}\"")
            for phrase in s["suggested_negative_triggers"]:
                L.append(f"- negative_trigger `{phrase}` <- \"{s['evidence'].get(phrase, '(no evidence line found)')}\"")
        else:
            L.append("")
            L.append("No suggestions (missing field(s) had nothing to derive).")
        L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="consumer monorepo root (nearest ancestor of guidefold.yaml)")
    ap.add_argument("--base", required=True, help="git ref: before")
    ap.add_argument("--head", required=True, help="git ref: after")
    ap.add_argument("--json", default=None, help="write the machine-readable suggestions here")
    ap.add_argument("--md", default=None, help="write the markdown suggestions here")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    repo_root = snap.git_toplevel(root)
    rel_root = snap.rel_root_of(root, repo_root)
    cli = snap.load_cli(snap.find_cli_path(repo_root))
    derive_mod = load_derive_module()

    with tempfile.TemporaryDirectory(prefix="guidefold-suggest-") as tmp:
        work = Path(tmp)
        _, base_idx = snap.build_snapshot_index(cli, repo_root, rel_root, args.base, work)
        _, head_idx = snap.build_snapshot_index(cli, repo_root, rel_root, args.head, work)

    suggestions = suggestions_for(head_idx, base_idx, derive_mod)
    markdown = render_markdown(suggestions)
    print(markdown)

    if args.json:
        Path(args.json).write_text(json.dumps(suggestions, indent=2, sort_keys=True) + "\n")
    if args.md:
        Path(args.md).write_text(markdown)

    return 0


if __name__ == "__main__":
    sys.exit(main())
