"""Router composer (ADR-0022 §4 / ADR-0024 §4, DENSE-PROGRAM.md v2.4 family C): the deterministic
integer composer `select()` runs when `compose_mode="on"` -- score-plateau bundle detection (no
`requires` edges needed), term-coverage-aware fill over the plateau pool, `cannot_fit` reporting,
and a byte-identical fallback to the legacy closure-fill (`_select_closure`) for every query the
detector does not flag as a bundle.
"""
from _router_helpers import make_card, make_nodes


def _scored(urn, node, score):
    return {"urn": urn, "node": node, "score": score}


def _adm(idx):
    """The admissible set a policy filter with no scope/trigger constraints would produce --
    every non-deprecated card (mirrors test_router_select.py's `_adm`)."""
    return {u for u, c in idx.cards.items() if c["status"] != "deprecated"}


def _urns(out):
    return {c["urn"] for c in out}


# --------------------------------------------------------------- off by default / backward compat
def test_compose_mode_defaults_to_off(gf):
    cards = {"u:a": make_card("u:a", "_root", description="a")}
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    assert idx.weights["compose_mode"] == "off"


def test_compose_off_never_sets_multi_skill_or_cannot_fit(gf):
    cards = {
        "u:a": make_card("u:a", "_root", description="a"),
        "u:b": make_card("u:b", "_root", description="b"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"))
    router = gf.Router(idx)
    scored = [_scored("u:a", "_root", 100), _scored("u:b", "_root", 85)]
    router.select(scored, k=2, abstain_threshold=0, admissible=_adm(idx), query="a b")
    assert router.last_multi_skill is False
    assert router.last_cannot_fit is False


# --------------------------------------------------------------- bundle detection
def test_bundle_detected_on_score_plateau(gf):
    cards = {f"u:{u}": make_card(f"u:{u}", "_root", description=u) for u in ("a", "b", "c")}
    idx = gf.Index.from_cards(cards, make_nodes("_root"), weights={"compose_mode": "on"})
    router = gf.Router(idx)
    # tau_pct defaults to 20 -> threshold = 100 * 80 // 100 = 80; b (85) clears it, c (50) does not.
    scored = [_scored("u:a", "_root", 100), _scored("u:b", "_root", 85), _scored("u:c", "_root", 50)]
    router.select(scored, k=2, abstain_threshold=0, admissible=_adm(idx), query="a b c")
    assert router.last_multi_skill is True


def test_no_bundle_on_a_single_dominant_winner(gf):
    cards = {f"u:{u}": make_card(f"u:{u}", "_root", description=u) for u in ("a", "b", "c")}
    idx = gf.Index.from_cards(cards, make_nodes("_root"), weights={"compose_mode": "on"})
    router = gf.Router(idx)
    scored = [_scored("u:a", "_root", 100), _scored("u:b", "_root", 50), _scored("u:c", "_root", 10)]
    router.select(scored, k=2, abstain_threshold=0, admissible=_adm(idx), query="a b c")
    assert router.last_multi_skill is False


def test_non_bundle_query_is_byte_identical_to_compose_off(gf):
    """The composer's whole point is that it only ever changes the answer on queries its own
    detector flags; every other query must fall back to the exact legacy closure fill."""
    cards = {
        "u:top": make_card("u:top", "_root", description="top", requires=["u:dep"]),
        "u:dep": make_card("u:dep", "_root", description="dep"),
        "u:mid": make_card("u:mid", "_root", description="mid"),
    }
    scored = [
        _scored("u:top", "_root", 100),
        _scored("u:mid", "_root", 50),   # well below the tau=20 plateau threshold (80)
        _scored("u:dep", "_root", 10),
    ]
    idx_on = gf.Index.from_cards(dict(cards), make_nodes("_root"), weights={"compose_mode": "on"})
    idx_off = gf.Index.from_cards(dict(cards), make_nodes("_root"), weights={"compose_mode": "off"})
    router_on, router_off = gf.Router(idx_on), gf.Router(idx_off)
    out_on = router_on.select(list(scored), k=2, abstain_threshold=0, admissible=_adm(idx_on), query="top mid")
    out_off = router_off.select(list(scored), k=2, abstain_threshold=0, admissible=_adm(idx_off), query="top mid")
    assert out_on == out_off
    assert router_on.last_multi_skill is False


# --------------------------------------------------------------- coverage-aware fill
def _coverage_scenario(gf, weights):
    cards = {
        "u:top1": make_card("u:top1", "_root", description="invoice tool"),
        "u:top2": make_card("u:top2", "_root", description="invoice helper"),   # redundant w/ top1
        "u:payment": make_card("u:payment", "_root", description="payment tool"),
        "u:reminder": make_card("u:reminder", "_root", description="reminder tool"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"), weights=weights)
    router = gf.Router(idx)
    scored = [
        _scored("u:top1", "_root", 100),
        _scored("u:top2", "_root", 95),
        _scored("u:payment", "_root", 90),
        _scored("u:reminder", "_root", 85),
    ]
    return idx, router, scored


def test_coverage_fill_prefers_complementary_skills_over_a_redundant_one(gf):
    idx, router, scored = _coverage_scenario(gf, {"compose_mode": "on", "compose_coverage": True})
    out = router.select(scored, k=2, abstain_threshold=0, admissible=_adm(idx),
                         query="invoice payment reminder")
    assert router.last_multi_skill is True
    assert _urns(out) == {"u:top1", "u:payment"}   # covers invoice+payment, not the redundant top2


def test_coverage_off_fills_in_plain_score_order(gf):
    idx, router, scored = _coverage_scenario(gf, {"compose_mode": "on", "compose_coverage": False})
    out = router.select(scored, k=2, abstain_threshold=0, admissible=_adm(idx),
                         query="invoice payment reminder")
    assert _urns(out) == {"u:top1", "u:top2"}   # naive top-2 by score -- both cover only "invoice"


def test_cannot_fit_true_when_the_bundle_does_not_fit_the_budget(gf):
    idx, router, scored = _coverage_scenario(gf, {"compose_mode": "on", "compose_coverage": True})
    router.select(scored, k=2, abstain_threshold=0, admissible=_adm(idx),
                  query="invoice payment reminder")
    assert router.last_cannot_fit is True   # "reminder" is a real, uncovered plateau member left out


def test_cannot_fit_false_when_the_budget_is_ample(gf):
    idx, router, scored = _coverage_scenario(gf, {"compose_mode": "on", "compose_coverage": True})
    out = router.select(scored, k=4, abstain_threshold=0, admissible=_adm(idx),
                         query="invoice payment reminder")
    assert router.last_cannot_fit is False
    # top2 is correctly left out too -- it is genuinely redundant with top1, not a missed need.
    assert _urns(out) == {"u:top1", "u:payment", "u:reminder"}


def test_cannot_fit_also_reported_with_coverage_off(gf):
    idx, router, scored = _coverage_scenario(gf, {"compose_mode": "on", "compose_coverage": False})
    router.select(scored, k=2, abstain_threshold=0, admissible=_adm(idx),
                  query="invoice payment reminder")
    assert router.last_cannot_fit is True


def test_empty_query_falls_back_to_plain_order_fill_even_with_coverage_on(gf):
    idx, router, scored = _coverage_scenario(gf, {"compose_mode": "on", "compose_coverage": True})
    out = router.select(scored, k=2, abstain_threshold=0, admissible=_adm(idx), query="")
    assert _urns(out) == {"u:top1", "u:top2"}


# --------------------------------------------------------------- admissibility and requires still bind
def test_admissibility_binds_inside_the_composer_pool(gf):
    idx, router, scored = _coverage_scenario(gf, {"compose_mode": "on", "compose_coverage": True})
    admissible = _adm(idx) - {"u:payment"}   # policy_filter excluded it (out of scope / negative trigger)
    out = router.select(scored, k=2, abstain_threshold=0, admissible=admissible,
                         query="invoice payment reminder")
    assert "u:payment" not in _urns(out)
    assert _urns(out) == {"u:top1", "u:reminder"}


def test_requires_closure_still_counts_toward_k_inside_the_composer(gf):
    cards = {
        "u:main": make_card("u:main", "_root", description="invoice payment reminder",
                             requires=["u:dep"]),
        "u:dep": make_card("u:dep", "_root", description="dependency helper"),
        "u:other": make_card("u:other", "_root", description="invoice"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"), weights={"compose_mode": "on"})
    router = gf.Router(idx)
    scored = [
        _scored("u:main", "_root", 100),
        _scored("u:other", "_root", 90),
        _scored("u:dep", "_root", 5),   # far too low-scored to ever win on coverage or score alone
    ]
    out = router.select(scored, k=4, abstain_threshold=0, admissible=_adm(idx),
                         query="invoice payment reminder")
    urns = _urns(out)
    assert "u:dep" in urns          # pulled in by requires closure, not by coverage or score
    assert "u:other" not in urns    # fully redundant with u:main -- correctly left out


def test_requires_closure_dependency_still_excluded_when_not_admissible(gf):
    """Same rule as test_router_select.py's legacy version, exercised through
    `_select_composed`'s OWN closure-pull (`is_bundle` must be True here, or this would just
    fall back to `_select_closure` and never touch the composer's own admissibility check)."""
    cards = {
        "u:main": make_card("u:main", "_root", description="invoice payment reminder",
                             requires=["u:dep"]),
        "u:dep": make_card("u:dep", "_root", description="dependency helper", status="deprecated"),
        "u:other": make_card("u:other", "_root", description="invoice payment reminder helper"),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"), weights={"compose_mode": "on"})
    router = gf.Router(idx)
    # u:dep is deliberately absent from `scored`, matching real usage: `candidates()`/
    # `policy_filter()` would never have surfaced a deprecated card as a candidate in the first
    # place -- `select()` only ever learns about it through the `requires` graph. u:other sits
    # within tau of u:main's score so the plateau detector fires and this goes through
    # `_select_composed`, not the closure fallback.
    scored = [_scored("u:main", "_root", 100), _scored("u:other", "_root", 85)]
    out = router.select(scored, k=4, abstain_threshold=0, admissible=_adm(idx),
                         query="invoice payment reminder")
    assert router.last_multi_skill is True
    assert _urns(out) == {"u:main"}   # ADR-0022: a filtered-out dependency stays unresolved


# --------------------------------------------------------------- determinism
def test_composer_output_deterministic_across_fresh_interpreters(gf, tmp_path):
    """Mirrors test_index_artifact.py's cross-interpreter check: a bare set()'s iteration order
    varies per-process under PYTHONHASHSEED randomisation, not per-call, so two calls in the same
    process could agree by accident even if the composer leaked set-iteration order into its
    output. This runs the composer in two genuinely separate interpreters and diffs stdout."""
    import subprocess
    import sys

    script = f'''
import sys
sys.path.insert(0, {str((tmp_path.parent)) !r})
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
loader = SourceFileLoader("guidefold", {str(gf.__file__)!r})
spec = spec_from_loader(loader.name, loader)
gf = module_from_spec(spec)
loader.exec_module(gf)

cards = {{
    "u:top1": {{"urn": "u:top1", "node": "_root", "name": "top1", "description": "invoice tool",
                "digest": "invoice tool", "triggers": [], "negative_triggers": [], "requires": [],
                "refines": [], "status": "active", "replaced_by": None, "kind": None, "layer": None,
                "owner": None, "_body": ""}},
    "u:top2": {{"urn": "u:top2", "node": "_root", "name": "top2", "description": "invoice helper",
                "digest": "invoice helper", "triggers": [], "negative_triggers": [], "requires": [],
                "refines": [], "status": "active", "replaced_by": None, "kind": None, "layer": None,
                "owner": None, "_body": ""}},
    "u:payment": {{"urn": "u:payment", "node": "_root", "name": "payment", "description": "payment tool",
                   "digest": "payment tool", "triggers": [], "negative_triggers": [], "requires": [],
                   "refines": [], "status": "active", "replaced_by": None, "kind": None, "layer": None,
                   "owner": None, "_body": ""}},
    "u:reminder": {{"urn": "u:reminder", "node": "_root", "name": "reminder", "description": "reminder tool",
                    "digest": "reminder tool", "triggers": [], "negative_triggers": [], "requires": [],
                    "refines": [], "status": "active", "replaced_by": None, "kind": None, "layer": None,
                    "owner": None, "_body": ""}},
}}
nodes = {{"_root": {{"paths": ["**"], "owner": "team"}}}}
idx = gf.Index.from_cards(cards, nodes, weights={{"compose_mode": "on"}})
router = gf.Router(idx)
admissible = set(cards)
scored = [
    {{"urn": "u:top1", "node": "_root", "score": 100}},
    {{"urn": "u:top2", "node": "_root", "score": 95}},
    {{"urn": "u:payment", "node": "_root", "score": 90}},
    {{"urn": "u:reminder", "node": "_root", "score": 85}},
]
out = router.select(scored, k=2, abstain_threshold=0, admissible=admissible,
                     query="invoice payment reminder")
print([c["urn"] for c in out], router.last_multi_skill, router.last_cannot_fit)
'''
    r1 = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    r2 = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr
    assert r1.stdout == r2.stdout
    assert "u:top1" in r1.stdout and "u:payment" in r1.stdout
