"""tools/eval/dev_expand.py — F3 document expansion (DENSE-PROGRAM.md v2.1 SS4): doc2query
pseudo-queries as extra BM25F index-time signal, evaluated against the frozen **P-flat** baseline
(never P-shipped). Same two-layer convention as tests/test_dev_sparse.py: pure-logic tests (card
merge rules, the expansion-field round-trip through the REAL product Router, the per-arm
one-changed-parameter contract, coverage/index-size arithmetic) always run; the one test that
reads the real 10 123-skill dev corpus AND the real generated doc2query JSONL skips with a reason
when either is not on this machine.
"""
import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "tools" / "eval"
CLI_PATH = ROOT / "skills" / "guidefold" / "scripts" / "guidefold"
VALIDATION_DIR = ROOT / "docs" / "reports" / "bakeoff" / "validation"

sys.path.insert(0, str(ROOT / "tests"))
from _router_helpers import make_card, make_nodes  # noqa: E402

spec = importlib.util.spec_from_file_location("gf_corpora", EVAL_DIR / "corpora.py")
gf_corpora = importlib.util.module_from_spec(spec)
sys.modules["gf_corpora"] = gf_corpora
spec.loader.exec_module(gf_corpora)

spec = importlib.util.spec_from_file_location("gf_dev_sparse", EVAL_DIR / "dev_sparse.py")
dev_sparse = importlib.util.module_from_spec(spec)
sys.modules["gf_dev_sparse"] = dev_sparse
sys.modules["dev_sparse"] = dev_sparse  # dev_expand.py does a plain `import dev_sparse`
spec.loader.exec_module(dev_sparse)

spec = importlib.util.spec_from_file_location("gf_dev_expand", EVAL_DIR / "dev_expand.py")
dev_expand = importlib.util.module_from_spec(spec)
sys.modules["gf_dev_expand"] = dev_expand
spec.loader.exec_module(dev_expand)


def _load_cli():
    loader = SourceFileLoader("guidefold_cli_dev_expand_test", str(CLI_PATH))
    cli_spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(cli_spec)
    loader.exec_module(module)
    return module


def _needs(name):
    problems = gf_corpora.verify(name)
    if problems:
        pytest.skip(f"{name} not on this machine or not the pinned revision: {problems[0]}")


# ------------------------------------------------------------------ torch-free module boundary
def test_dev_expand_module_imports_cleanly_with_torch_blocked(monkeypatch):
    """dev_expand.py never invokes the doc2query model -- it only reads a pre-generated JSONL --
    so it must never need torch, unlike tools/expand/doc2query.py."""
    monkeypatch.setitem(sys.modules, "torch", None)

    class _TorchIsForbidden:
        def find_spec(self, name, path=None, target=None):
            if name == "torch" or name.startswith("torch."):
                raise ImportError(f"torch must never be imported at dev_expand.py module scope: {name}")
            return None

    sys.meta_path.insert(0, _TorchIsForbidden())
    try:
        spec2 = importlib.util.spec_from_file_location("gf_dev_expand_reload", EVAL_DIR / "dev_expand.py")
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
    finally:
        sys.meta_path.pop(0)


# ------------------------------------------------------------------ pseudo-query merge
def test_load_pseudo_queries(tmp_path):
    p = tmp_path / "pseudo.jsonl"
    p.write_text(
        '{"skill_id": "s1", "queries": ["what is x", "how does x work"]}\n'
        '{"skill_id": "s2", "queries": ["y query"]}\n',
        encoding="utf-8",
    )
    out = dev_expand.load_pseudo_queries(p)
    assert out == {"s1": ["what is x", "how does x work"], "s2": ["y query"]}


def test_expansion_text_joins_queries_with_spaces():
    assert dev_expand.expansion_text(["a b", "c"]) == "a b c"
    assert dev_expand.expansion_text([]) == ""


def _tiny_cards_id_map_pseudo():
    cards = {
        "u:1": make_card("u:1", "n", name="skill-one", description="desc one", body="body one"),
        "u:2": make_card("u:2", "n", name="skill-two", description="desc two", body="body two"),
    }
    id_to_urn = {"s1": "u:1", "s2": "u:2"}
    pseudo = {"s1": ["pseudo query one", "another pseudo one"]}  # s2 deliberately has none
    return cards, id_to_urn, pseudo


def test_make_expansion_cards_field_mode_adds_expansion_key_only():
    cards, id_to_urn, pseudo = _tiny_cards_id_map_pseudo()
    out = dev_expand.make_expansion_cards(cards, id_to_urn, pseudo, mode="field")
    assert out["u:1"]["_expansion"] == "pseudo query one another pseudo one"
    assert out["u:2"]["_expansion"] == ""  # no pseudo queries for s2 -> empty, not invented
    # every other field, including _body, is untouched
    for u in cards:
        for f in ("urn", "node", "name", "description", "digest", "triggers", "_body"):
            assert out[u][f] == cards[u][f]


def test_make_expansion_cards_append_mode_folds_into_body_no_new_key():
    cards, id_to_urn, pseudo = _tiny_cards_id_map_pseudo()
    out = dev_expand.make_expansion_cards(cards, id_to_urn, pseudo, mode="append")
    assert "_expansion" not in out["u:1"]
    assert out["u:1"]["_body"] == "body one\npseudo query one another pseudo one"
    assert out["u:2"]["_body"] == cards["u:2"]["_body"]  # no pseudo queries -> body unchanged
    for u in cards:
        for f in ("urn", "node", "name", "description", "digest", "triggers"):
            assert out[u][f] == cards[u][f]


def test_make_expansion_cards_rejects_unknown_mode():
    cards, id_to_urn, pseudo = _tiny_cards_id_map_pseudo()
    with pytest.raises(ValueError):
        dev_expand.make_expansion_cards(cards, id_to_urn, pseudo, mode="bogus")


# ------------------------------------------------------------------ the expansion field itself
def test_make_expansion_index_cls_fields_and_weights():
    cli = _load_cli()
    exp_cls = dev_expand.make_expansion_index_cls(cli, field_weight=2)
    assert exp_cls.FIELDS == cli.Index.FIELDS + ("expansion",)
    assert exp_cls.DEFAULT_WEIGHTS["field.expansion"] == 2
    # every other DEFAULT_WEIGHTS entry inherited unchanged
    for k, v in cli.Index.DEFAULT_WEIGHTS.items():
        assert exp_cls.DEFAULT_WEIGHTS[k] == v

    card = {**make_card("u:1", "n", name="x", description="y", body="z"), "_expansion": "q1 q2"}
    inst = exp_cls.__new__(exp_cls)  # _field_text takes no other instance state
    assert inst._field_text(card, "expansion") == "q1 q2"
    assert inst._field_text(card, "name") == "x"  # delegates to the base implementation


def test_expansion_field_round_trips_through_index_from_cards_and_router_score():
    """The task's explicit requirement: the expansion field is genuinely LIVE through the real
    product Router.score() path, not merely present on the Index object. Built so the query's
    only overlap with the skill is in `_expansion` -- name/description/digest/triggers/body share
    zero terms with it -- so a nonzero score / a candidates-list hit can only come from the new
    field actually participating in BM25F scoring."""
    cli = _load_cli()
    nodes = make_nodes("_root", "n")
    cards = {
        "u:only-expansion": {
            **make_card("u:only-expansion", "n", name="zzz-alpha", description="qqq-beta",
                        body="rrr-gamma"),
            "_expansion": "wombat trampoline nebula",
        },
        "u:no-overlap": {
            **make_card("u:no-overlap", "n", name="totally-unrelated",
                        description="nothing in common", body="filler text only"),
            "_expansion": "",
        },
    }
    exp_cls = dev_expand.make_expansion_index_cls(cli, field_weight=1)
    weights = {f"field.{f}": 1 for f in cli.Index.FIELDS}
    weights["field.expansion"] = 1
    idx = exp_cls.from_cards(cards, nodes, weights=weights)

    assert "wombat" in idx.postings["expansion"]
    assert idx.postings["expansion"]["wombat"] == {"u:only-expansion": 1}
    assert idx.field_len["expansion"]["u:only-expansion"] == 3
    assert idx.field_norm["expansion"]["u:only-expansion"] > 0

    router = cli.Router(idx)
    query = "wombat trampoline"
    cands = router.candidates(query, "n", top_n=50)
    cand_urns = {c["urn"] for c in cands}
    assert "u:only-expansion" in cand_urns

    scored = router.score(cands, query, "n")
    by_urn = {s["urn"]: s["score"] for s in scored}
    assert by_urn["u:only-expansion"] > 0
    assert by_urn.get("u:no-overlap", 0) == 0  # no term overlap anywhere -> never scored


# ------------------------------------------------------------------ index size estimator
def _tiny_flat_and_expansion_indices(cli):
    nodes = make_nodes("_root", "n")
    cards = {
        "u:1": make_card("u:1", "n", name="alpha one", description="desc alpha", body="body alpha text"),
        "u:2": make_card("u:2", "n", name="beta two", description="desc beta", body="body beta text"),
    }
    flat_weights = {f"field.{f}": 1 for f in cli.Index.FIELDS}
    idx_flat = cli.Index.from_cards(cards, nodes, weights=flat_weights)

    exp_cls = dev_expand.make_expansion_index_cls(cli, field_weight=1)
    cards_exp = {u: {**c, "_expansion": "gamma delta epsilon zeta"} for u, c in cards.items()}
    idx_exp = exp_cls.from_cards(cards_exp, nodes, weights={**flat_weights, "field.expansion": 1})
    return idx_flat, idx_exp


def test_estimate_index_bytes_counts_the_sixth_field():
    cli = _load_cli()
    idx_flat, idx_exp = _tiny_flat_and_expansion_indices(cli)
    flat_bytes = dev_expand.estimate_index_bytes(idx_flat)
    exp_bytes = dev_expand.estimate_index_bytes(idx_exp)

    assert flat_bytes["n_fields"] == len(cli.Index.FIELDS) == 5
    assert exp_bytes["n_fields"] == 6
    # norms.bin is exactly 4 bytes * n_docs * n_fields (struct.pack("<{n}I", ...) per field)
    assert flat_bytes["norms_bin_bytes"] == 4 * flat_bytes["n_docs"] * flat_bytes["n_fields"]
    assert exp_bytes["norms_bin_bytes"] == 4 * exp_bytes["n_docs"] * exp_bytes["n_fields"]
    # the expansion field adds real postings for brand-new terms -> strictly larger index
    assert exp_bytes["postings_bin_bytes"] > flat_bytes["postings_bin_bytes"]
    assert exp_bytes["total_bm25_bytes"] > flat_bytes["total_bm25_bytes"]
    assert exp_bytes["n_terms"] > flat_bytes["n_terms"]  # gamma/delta/epsilon/zeta are new terms


# ------------------------------------------------------------------ coverage
def test_compute_coverage_recovers_and_loses_correctly():
    cases = [
        {"id": "q1", "relevant": [{"urn": "u:a", "grade": 3}, {"urn": "u:b", "grade": 2}]},
        {"id": "q2", "relevant": [{"urn": "u:c", "grade": 3}]},
        {"id": "q3", "relevant": [{"urn": "u:d", "grade": 1}]},  # grade 1 -> not "required", excluded
    ]
    baseline = {"q1": ["u:a"], "q2": [], "q3": []}          # misses u:b (q1), misses u:c (q2)
    arm = {"q1": ["u:a", "u:b"], "q2": [], "q3": ["u:d"]}   # recovers u:b; still misses u:c

    summary, per_query = dev_expand.compute_coverage(cases, baseline, arm, topn=50)
    assert summary["n_required_total"] == 3       # u:a, u:b, u:c (u:d excluded, grade 1)
    assert summary["n_recovered"] == 1             # u:b
    assert summary["n_lost"] == 0
    assert summary["net_recovered"] == 1
    assert summary["n_queries_gained"] == 1
    assert summary["n_queries_lost"] == 0
    assert per_query["q1"]["recovered"] == ["u:b"]
    assert "q2" not in per_query and "q3" not in per_query  # nothing recovered/lost -> not recorded

    # now test a LOSS: arm drops something the baseline had
    arm_losing = {"q1": [], "q2": [], "q3": []}
    summary2, _ = dev_expand.compute_coverage(cases, baseline, arm_losing, topn=50)
    assert summary2["n_lost"] == 1  # u:a was in baseline top-n, gone from arm
    assert summary2["net_recovered"] == -1


# ------------------------------------------------------------------ arm construction (coordinate descent)
def _arm_test_fixture():
    nodes = make_nodes("_root", "eng", "eng.backend")
    cards = {
        "u:1": make_card("u:1", "eng.backend", name="skill-one", description="migrate schema",
                          body="run schema migrations safely"),
        "u:2": make_card("u:2", "eng.backend", name="skill-two", description="queue retry",
                          body="background job queue processing"),
    }
    id_to_urn = {"s1": "u:1", "s2": "u:2"}
    pseudo5 = {"s1": ["q1a", "q1b", "q1c", "q1d", "q1e"], "s2": ["q2a", "q2b", "q2c", "q2d", "q2e"]}
    pseudo10 = {"s1": [f"q1-{i}" for i in range(10)], "s2": [f"q2-{i}" for i in range(10)]}
    return cards, nodes, id_to_urn, pseudo5, pseudo10


def test_build_arms_each_arm_differs_from_p_flat_by_exactly_one_parameter():
    cli = _load_cli()
    cards, nodes, id_to_urn, pseudo5, pseudo10 = _arm_test_fixture()
    arms = dev_expand._build_arms(cli, cards, nodes, id_to_urn, pseudo5, pseudo10, "weight2")

    flat_idx = arms["P-flat"][0]
    e1_idx = arms["E-field-1"][0]
    ew_idx = arms["E-field-w"][0]
    append_idx = arms["E-append"][0]

    # E-field-1 vs P-flat: exactly one new weight key (the expansion field, flat weight 1);
    # FIELDS gains exactly one entry; cards gain exactly one populated key (_expansion).
    assert set(e1_idx.weights) - set(flat_idx.weights) == {"field.expansion"}
    assert e1_idx.weights["field.expansion"] == 1
    assert all(flat_idx.weights[k] == e1_idx.weights[k] for k in flat_idx.weights)
    assert set(e1_idx.FIELDS) - set(flat_idx.FIELDS) == {"expansion"}
    for u in flat_idx.cards:
        for f in ("name", "description", "digest", "triggers", "_body"):
            assert flat_idx.cards[u][f] == e1_idx.cards[u][f]
    assert e1_idx.cards["u:1"]["_expansion"] == "q1a q1b q1c q1d q1e"

    # E-field-w (mode="weight2") vs E-field-1: same fields/cards, ONLY the expansion weight moves
    assert ew_idx.FIELDS == e1_idx.FIELDS
    assert ew_idx.cards == e1_idx.cards
    assert set(ew_idx.weights) == set(e1_idx.weights)
    diff = {k for k in ew_idx.weights if ew_idx.weights[k] != e1_idx.weights[k]}
    assert diff == {"field.expansion"}
    assert ew_idx.weights["field.expansion"] == 2 and e1_idx.weights["field.expansion"] == 1

    # E-append vs P-flat: SAME Index class (no expansion field at all), SAME weights, only body text differs
    assert append_idx.FIELDS == flat_idx.FIELDS
    assert append_idx.weights == flat_idx.weights
    assert "_expansion" not in append_idx.cards["u:1"]
    assert append_idx.cards["u:1"]["_body"] != flat_idx.cards["u:1"]["_body"]
    assert flat_idx.cards["u:1"]["_body"] in append_idx.cards["u:1"]["_body"]
    for u in flat_idx.cards:
        for f in ("name", "description", "digest", "triggers"):
            assert flat_idx.cards[u][f] == append_idx.cards[u][f]


def test_build_arms_field_w_mode_n10_changes_only_expansion_text_length():
    cli = _load_cli()
    cards, nodes, id_to_urn, pseudo5, pseudo10 = _arm_test_fixture()
    arms = dev_expand._build_arms(cli, cards, nodes, id_to_urn, pseudo5, pseudo10, "n10")

    e1_idx = arms["E-field-1"][0]   # always n=5, field weight 1
    ew_idx = arms["E-field-w"][0]   # n=10 variant, field weight 1

    assert ew_idx.FIELDS == e1_idx.FIELDS
    assert ew_idx.weights == e1_idx.weights   # weight unchanged in this mode -- text differs instead
    assert ew_idx.cards["u:1"]["_expansion"] != e1_idx.cards["u:1"]["_expansion"]
    assert len(ew_idx.cards["u:1"]["_expansion"].split()) == 10
    assert len(e1_idx.cards["u:1"]["_expansion"].split()) == 5


def test_build_arms_rejects_unknown_field_w_mode():
    cli = _load_cli()
    cards, nodes, id_to_urn, pseudo5, pseudo10 = _arm_test_fixture()
    with pytest.raises(ValueError):
        dev_expand._build_arms(cli, cards, nodes, id_to_urn, pseudo5, pseudo10, "bogus")


# ------------------------------------------------------------------ real corpus + real generated artifact
def test_real_dev_pool_pseudo_queries_cover_every_skill():
    _needs("skillret")
    pseudo_path = VALIDATION_DIR / "doc2query-dev-n5-seed42.jsonl"
    if not pseudo_path.exists():
        pytest.skip(f"{pseudo_path} not built on this machine "
                    f"(tools/expand/doc2query.py generate --n 5 --out {pseudo_path})")
    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, _ = dev_sparse.corpus_to_cards(data["skills"])
    pseudo = dev_expand.load_pseudo_queries(pseudo_path)
    assert len(pseudo) == 10123
    n_matched = sum(1 for sid in id_to_urn if sid in pseudo)
    assert n_matched == len(id_to_urn)
    for queries in pseudo.values():
        assert len(queries) == 5
