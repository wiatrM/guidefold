"""Tests for tools/enrich/apply.py (F5 offline enrichment, DENSE-PROGRAM.md §4):

- an integration test on the real `examples/monorepo` fixture asserting derived fields never
  contradict the few authored triggers/negative_triggers already present there;
- a round-trip test proving `apply.build_cards()`'s output is accepted by `Index.from_cards`
  unchanged and produces the expected `requires` graph edge.
"""
import importlib.util
import pathlib
import sys

from _router_helpers import make_nodes

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(mod_name, rel_path):
    spec = importlib.util.spec_from_file_location(mod_name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


APPLY = _load("gf_enrich_apply", "tools/enrich/apply.py")
D = APPLY.derive_mod


# --------------------------------------------------------------------- examples/monorepo fixture
def _fixture_skills_for_derive(gf, fixture_root):
    """Build the derive() input list from the real fixture via the CLI's own frontmatter parsing
    (gf.all_skills/gf.md_phrases/gf.md_list), preserving any authored triggers/negative_triggers/
    requires so rule 3 (existing fields win) is exercised on real data, not a synthetic stand-in."""
    cfg = gf.load_map(fixture_root)
    skills = []
    for d, node, fm in gf.all_skills(fixture_root, cfg):
        meta = fm.get("metadata") or {}
        name = d.name
        s = {
            "id": gf.urn(cfg, node, name),
            "name": name,
            "description": str(fm.get("description", "")),
            "body": (d / "SKILL.md").read_text(errors="ignore"),
        }
        existing_triggers = gf.md_phrases(meta, "triggers")
        existing_neg = gf.md_phrases(meta, "negative_triggers")
        existing_req = gf.md_list(meta, "requires")
        if existing_triggers:
            s["triggers"] = existing_triggers
        if existing_neg:
            s["negative_triggers"] = existing_neg
        if existing_req:
            s["requires"] = existing_req
        skills.append(s)
    return skills


def test_fixture_has_some_authored_triggers_and_negative_triggers(gf, fixture_root):
    """Sanity check on the premise of the contradiction test below -- the fixture must actually
    carry authored fields for "existing fields win" to be exercised at all."""
    skills = _fixture_skills_for_derive(gf, fixture_root)
    assert any(s.get("triggers") for s in skills)
    assert any(s.get("negative_triggers") for s in skills)


def test_derived_fields_never_contradict_authored_fields_on_the_real_fixture(gf, fixture_root):
    skills = _fixture_skills_for_derive(gf, fixture_root)
    out = D.derive(skills)

    for s in skills:
        sid = s["id"]
        e = out[sid]
        authored_triggers = s.get("triggers") or []
        authored_neg = s.get("negative_triggers") or []
        authored_req = s.get("requires") or []

        # Rule 3: existing fields are kept verbatim, never dropped or edited.
        for t in authored_triggers:
            assert t in e.triggers, f"{sid}: authored trigger {t!r} missing from derived output"
        for t in authored_neg:
            assert t in e.negative_triggers, f"{sid}: authored negative_trigger {t!r} missing"
        for r in authored_req:
            assert r in e.requires, f"{sid}: authored requires {r!r} missing"

        # No *derived* item should directly contradict this skill's own authored fields -- the
        # same condition must never appear as both an inclusion and an exclusion signal.
        authored_trig_forms = {tuple(D.tokenize(t)) for t in authored_triggers}
        authored_neg_forms = {tuple(D.tokenize(t)) for t in authored_neg}
        for phrase, prov in zip(e.negative_triggers, e.provenance["negative_triggers"]):
            if prov.get("derived"):
                assert tuple(D.tokenize(phrase)) not in authored_trig_forms, (
                    f"{sid}: derived negative_trigger {phrase!r} contradicts an authored trigger"
                )
        for phrase, prov in zip(e.triggers, e.provenance["triggers"]):
            if prov.get("derived"):
                assert tuple(D.tokenize(phrase)) not in authored_neg_forms, (
                    f"{sid}: derived trigger {phrase!r} contradicts an authored negative_trigger"
                )

    # No `requires` cycle anywhere in the derived graph -- a corpus-level sanity check that holds
    # on real data, not just the synthetic 2-skill case in test_enrich_derive.py.
    graph = {sid: set(out[sid].requires) for sid in out}
    for start in graph:
        stack, seen = [start], set()
        while stack:
            n = stack.pop()
            for m in graph.get(n, ()):
                assert m != start or n == start, f"requires cycle back to {start} via {n}"
                if m not in seen:
                    seen.add(m)
                    stack.append(m)


# ---------------------------------------------------------------------------------- round-trip
def test_apply_output_round_trips_through_index_from_cards(gf):
    skills = [
        {
            "id": "skill-a", "name": "Skill A Name",
            "description": "Handles the A workflow end to end.",
            "body": "## Prerequisites\n\nRequires Skill B Name to be installed first.\n",
        },
        {"id": "skill-b", "name": "Skill B Name", "description": "Handles the B workflow.", "body": ""},
    ]
    enrichment = D.derive(skills)
    cards = APPLY.build_cards(skills, enrichment, node="_root", publisher="test")
    assert len(cards) == 2

    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    assert set(idx.cards) == set(cards)

    a_urn = next(u for u, c in cards.items() if c["name"] == "skill-a")
    b_urn = next(u for u, c in cards.items() if c["name"] == "skill-b")
    assert b_urn in idx.graph["requires"][a_urn]

    router = gf.Router(idx)
    kept, drops = router.policy_filter("_root", query="skill a workflow")
    assert a_urn in kept and b_urn in kept
