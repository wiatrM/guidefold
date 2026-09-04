"""E1.4 coverage assertions on the real Meridian fixture (examples/monorepo): every skill has
kind + layer, the refines/replaces graph is non-trivial, and negative_triggers is used
selectively rather than on every skill. Also guards against triggers leaking golden-set queries
verbatim (E1.1's eval set must stay independent of authored metadata)."""
from pathlib import Path

import yaml

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _fixture_skills(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    return list(gf.all_skills(fixture_root, cfg))


def test_fixture_has_kind_and_layer_on_all_26_skills(gf, fixture_root):
    skills = _fixture_skills(gf, fixture_root)
    assert len(skills) == 26
    missing = []
    for d, node, fm in skills:
        md = fm.get("metadata") or {}
        if md.get("kind") not in gf.KIND_VALUES:
            missing.append((str(d.relative_to(fixture_root)), "kind", md.get("kind")))
        if md.get("layer") not in gf.LAYER_VALUES:
            missing.append((str(d.relative_to(fixture_root)), "layer", md.get("layer")))
    assert not missing, f"skills missing valid kind/layer: {missing}"


def test_fixture_has_at_least_8_refines_edges(gf, fixture_root):
    skills = _fixture_skills(gf, fixture_root)
    total = sum(len(gf.md_list(fm.get("metadata") or {}, "refines")) for _, _, fm in skills)
    assert total >= 8, f"expected >= 8 refines edges, found {total}"


def test_fixture_has_at_least_1_replaces_edge(gf, fixture_root):
    skills = _fixture_skills(gf, fixture_root)
    total = sum(len(gf.md_list(fm.get("metadata") or {}, "replaces")) for _, _, fm in skills)
    assert total >= 1, f"expected >= 1 replaces edge, found {total}"


def test_fixture_negative_triggers_used_selectively(gf, fixture_root):
    """8-12 of the 26 skills: enough to be meaningful, not so many it looks like every skill
    was given one by rote."""
    skills = _fixture_skills(gf, fixture_root)
    count = sum(1 for _, _, fm in skills
                if gf.md_list(fm.get("metadata") or {}, "negative_triggers"))
    assert 8 <= count <= 12, f"expected 8-12 skills with negative_triggers, found {count}"


def _golden_queries():
    queries = set()
    for f in GOLDEN_DIR.glob("*.yaml"):
        data = yaml.safe_load(f.read_text()) or {}
        for case in data.get("cases", []):
            q = case.get("query")
            if q:
                queries.add(q.strip())
    return queries


def test_triggers_do_not_leak_golden_set_queries_verbatim(gf, fixture_root):
    """Eval-leak guard (E1.1): triggers/negative_triggers are authored from the skill body, never
    reverse-engineered from tests/golden/*.yaml. A verbatim match here would mean a trigger was
    copy-pasted from an eval query instead of derived independently."""
    golden = _golden_queries()
    assert golden, "expected to find golden-set queries to check against"
    skills = _fixture_skills(gf, fixture_root)
    leaks = []
    for d, node, fm in skills:
        md = fm.get("metadata") or {}
        for key in ("triggers", "negative_triggers"):
            for phrase in gf.md_list(md, key):
                if phrase in golden:
                    leaks.append((str(d.relative_to(fixture_root)), key, phrase))
    assert not leaks, f"trigger phrases verbatim-equal to a golden query: {leaks}"
