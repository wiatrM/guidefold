"""tools/eval/skillretbench.py — Guidefold's first bake-off on real, independently labelled skill
data (SkillRetBench). Two layers, same convention as tests/test_corpora.py: pure-logic tests
(converter mapping decisions, the arm-ablation contract, the stdlib words.bin reader, the
_binary_case metric-reuse trick) always run; corpus-dependent tests skip with a reason when the
pinned data is not on this machine — a skip here is not a pass, and the bake-off report must come
from a machine where these ran for real.
"""
import importlib.util
import struct
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "tools" / "eval"
CLI_PATH = ROOT / "skills" / "guidefold" / "scripts" / "guidefold"

spec = importlib.util.spec_from_file_location("gf_corpora", EVAL_DIR / "corpora.py")
gf_corpora = importlib.util.module_from_spec(spec)
sys.modules["gf_corpora"] = gf_corpora
spec.loader.exec_module(gf_corpora)

spec = importlib.util.spec_from_file_location("gf_skillretbench", EVAL_DIR / "skillretbench.py")
SRB = importlib.util.module_from_spec(spec)
sys.modules["gf_skillretbench"] = SRB
spec.loader.exec_module(SRB)


def _load_cli():
    loader = SourceFileLoader("guidefold_cli_srb_test", str(CLI_PATH))
    cli_spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(cli_spec)
    loader.exec_module(module)
    return module


def _needs(name):
    problems = gf_corpora.verify(name)
    if problems:
        pytest.skip(f"{name} not on this machine or not the pinned revision: {problems[0]}")


# ------------------------------------------------------------------ torch-free module boundary
def test_skillretbench_module_imports_cleanly_with_torch_blocked(monkeypatch):
    """`run`/`convert` (and pytest collecting this file) must never require a GPU venv: distill.py
    and encode.py (which import torch/transformers/sentence-transformers at module scope) may only
    be reached from inside `distill_word_table()`, imported lazily there. Poisoning `torch` at
    both the sys.modules and import-machinery level (same technique as
    test_no_torch_import.py::test_cli_module_imports_cleanly_with_torch_blocked) proves module-
    level code in skillretbench.py never imports it."""
    monkeypatch.setitem(sys.modules, "torch", None)

    class _TorchIsForbidden:
        def find_spec(self, name, path=None, target=None):
            if name == "torch" or name.startswith("torch."):
                raise ImportError(f"torch must never be imported at skillretbench.py module scope: {name}")
            return None

    blocker = _TorchIsForbidden()
    sys.meta_path.insert(0, blocker)
    try:
        loader = SourceFileLoader("gf_skillretbench_no_torch_check", str(EVAL_DIR / "skillretbench.py"))
        mod_spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(mod_spec)
        loader.exec_module(module)  # raises if the module body imports torch anywhere
        assert hasattr(module, "main")
        assert hasattr(module, "distill_word_table")
    finally:
        sys.meta_path.remove(blocker)


# ------------------------------------------------------------------ strip_own_frontmatter
def test_strip_own_frontmatter_removes_only_the_first_block():
    full_text = (
        "---\nname: x\ndescription: y\n---\n\n"
        "# Body heading\n\nSome body text with its own --- horizontal rule --- inside it.\n"
    )
    stripped = SRB.strip_own_frontmatter(full_text)
    assert not stripped.startswith("---\nname: x")
    assert stripped.startswith("# Body heading")
    # The body's own literal "---" text must survive untouched (only the FIRST block is a
    # frontmatter delimiter; anything after is body content, even if it looks similar).
    assert "own --- horizontal rule --- inside it" in stripped


def test_strip_own_frontmatter_is_a_no_op_when_there_is_no_frontmatter():
    text = "# Just a body\n\nNo frontmatter here.\n"
    assert SRB.strip_own_frontmatter(text) == text


# ------------------------------------------------------------------ has_hangul
def test_has_hangul_detects_korean_and_ignores_latin():
    assert SRB.has_hangul("이것은 한국어 질문입니다")
    assert not SRB.has_hangul("This is an English query")
    assert not SRB.has_hangul("")


# ------------------------------------------------------------------ stdlib words.bin reader
def test_read_word_table_matches_a_hand_written_words_bin(tmp_path):
    """Writes a tiny words.bin by hand, in the exact byte layout tools/bakeoff/distill.py's
    write_words_bin() documents (WORDS_MAGIC b"GFW1", header struct "<4sHHIfI", then a newline-
    joined UTF-8 word blob, then vocab_size rows of `dims` signed int8 bytes) — proves
    read_word_table() decodes that format correctly using only stdlib (struct + array), with no
    numpy/torch import, matching the CLI's own int8 decoding convention."""
    words = ["alpha", "beta"]
    dims = 4
    rows = [(1, -1, 2, -2), (127, -128, 0, 5)]
    blob = "\n".join(words).encode("utf-8")
    header = struct.pack("<4sHHIfI", b"GFW1", 1, dims, len(words), 0.5, len(blob))
    path = tmp_path / "words.bin"
    with open(path, "wb") as f:
        f.write(header)
        f.write(blob)
        for row in rows:
            f.write(struct.pack("<4b", *row))

    table = SRB.read_word_table(path)
    assert set(table) == set(words)
    assert table["alpha"] == (1, -1, 2, -2)
    assert table["beta"] == (127, -128, 0, 5)


def test_read_word_table_rejects_bad_magic(tmp_path):
    path = tmp_path / "bad.bin"
    path.write_bytes(struct.pack("<4sHHIfI", b"XXXX", 1, 1, 0, 1.0, 0))
    with pytest.raises(ValueError):
        SRB.read_word_table(path)


# ------------------------------------------------------------------ _binary_case / metric reuse
def test_binary_case_reproduces_standard_binary_recall_and_ndcg():
    """The mathematical claim this runner depends on: forcing every relevant item's grade to a
    single uniform constant >= 2 makes tools/eval/metrics.py's own recall_at_k/ndcg_at_k compute
    exactly standard binary Recall@k / nDCG@k, regardless of which such grade is chosen (the
    constant gain factor 2**g-1 cancels in the DCG/IDCG ratio; recall's >=2 threshold becomes "any
    positive grade" once every grade is uniform and >=2). Grade 1 is excluded from the recall
    check on purpose: metrics.py's own MUST_BE_IN_TOP_K=2 documents grade-1 items as "acceptable,
    not required" and drops them from recall's denominator entirely, so a uniform grade of 1
    yields an empty `required` set and recall_at_k correctly (by design) returns NaN, not 0 —
    that is a real, separate contract, not a bug this test should paper over."""
    gf_metrics_spec = importlib.util.spec_from_file_location("gf_metrics_srb_test", EVAL_DIR / "metrics.py")
    metrics = importlib.util.module_from_spec(gf_metrics_spec)
    gf_metrics_spec.loader.exec_module(metrics)

    case = {"relevant": [{"urn": "a", "grade": 3}, {"urn": "b", "grade": 2}, {"urn": "c", "grade": 2}]}
    ranked = ["x", "b", "a", "c", "y"]

    # Standard binary recall@k: |ranked[:k] ∩ relevant| / |relevant|.
    relevant_urns = {"a", "b", "c"}
    expected_recall_at_3 = len(relevant_urns & set(ranked[:3])) / len(relevant_urns)

    for grade in (2, 5, 100):
        binary_case = {**case, "relevant": [{"urn": r["urn"], "grade": grade} for r in case["relevant"]]}
        assert metrics.recall_at_k(ranked, binary_case, k=3) == pytest.approx(expected_recall_at_3)

    # A uniform grade of 1 sits below the >=2 "required" threshold entirely -- documented as NaN
    # (undefined), never silently 0.
    grade_1_case = {**case, "relevant": [{"urn": r["urn"], "grade": 1} for r in case["relevant"]]}
    below_threshold = metrics.recall_at_k(ranked, grade_1_case, k=3)
    assert below_threshold != below_threshold

    # Standard binary nDCG@k with any single uniform grade must all agree with each other.
    ndcgs = [metrics.ndcg_at_k(ranked, {**case, "relevant": [{"urn": r["urn"], "grade": g} for r in case["relevant"]]}, k=5)
             for g in (1, 2, 5, 100)]
    assert all(v == pytest.approx(ndcgs[0]) for v in ndcgs)


def test_reciprocal_rank_and_average_precision_single_gold_agree():
    """SkillRetBench's own baseline_results.json shows mrr == map for single_skill (one gold item
    per query) — the standard-formula proof this runner's implementation must match."""
    case = {"relevant": [{"urn": "a", "grade": 3}]}
    ranked = ["x", "y", "a", "z"]
    assert SRB.reciprocal_rank(ranked, case) == pytest.approx(SRB.average_precision(ranked, case, k=10))
    assert SRB.reciprocal_rank(ranked, case) == pytest.approx(1 / 3)


def test_reciprocal_rank_zero_when_gold_missing_from_ranking():
    case = {"relevant": [{"urn": "a", "grade": 3}]}
    assert SRB.reciprocal_rank(["x", "y"], case) == 0.0


# ------------------------------------------------------------------ arm ablation contract
def _tiny_cards_and_nodes():
    """A minimal 3-card, 2-node fixture, independent of the real corpus — this test must run in
    CI regardless of whether SkillRetBench is fetched on the machine."""
    cards = {
        "urn:skill:t:cat_a:one": {
            "urn": "urn:skill:t:cat_a:one", "node": "cat_a", "name": "one",
            "description": "does one thing", "digest": "does one thing",
            "triggers": ["one thing"], "negative_triggers": [],
            "requires": ["urn:skill:t:cat_a:two"], "refines": [],
            "status": "active", "replaced_by": None,
            "kind": None, "layer": None, "owner": "t", "_body": "one body text",
        },
        "urn:skill:t:cat_a:two": {
            "urn": "urn:skill:t:cat_a:two", "node": "cat_a", "name": "two",
            "description": "does two thing", "digest": "does two thing",
            "triggers": ["two thing"], "negative_triggers": [],
            "requires": [], "refines": [],
            "status": "active", "replaced_by": None,
            "kind": None, "layer": None, "owner": "t", "_body": "two body text",
        },
        "urn:skill:t:cat_b:three": {
            "urn": "urn:skill:t:cat_b:three", "node": "cat_b", "name": "three",
            "description": "does three thing", "digest": "does three thing",
            "triggers": ["three thing"], "negative_triggers": [],
            "requires": [], "refines": [],
            "status": "active", "replaced_by": None,
            "kind": None, "layer": None, "owner": "t", "_body": "three body text",
        },
    }
    nodes = {"_root": {"paths": ["_root/**"], "owner": "t"},
             "cat_a": {"paths": ["cat_a/**"], "owner": "t"},
             "cat_b": {"paths": ["cat_b/**"], "owner": "t"}}
    return cards, nodes


def test_arms_differ_by_exactly_one_parameter_from_b1():
    cli = _load_cli()
    cards, nodes = _tiny_cards_and_nodes()
    word_vectors = {"one": (1, 2, 3), "two": (2, 3, 4), "three": (3, 4, 5)}
    arms = SRB.build_arms(cli, cards, nodes, word_vectors=word_vectors)
    assert set(arms) == {"B1", "B1-scope", "B1-closure", "B3b+B5", "B1-flat"}

    b1_w = arms["B1"].index.weights
    scope_w = arms["B1-scope"].index.weights
    closure_w = arms["B1-closure"].index.weights
    dense_w = arms["B3b+B5"].index.weights
    flat_w = arms["B1-flat"].index.weights

    def _diff_keys(a, b):
        return {k for k in a if a.get(k) != b.get(k)}

    assert _diff_keys(b1_w, scope_w) == {"w_scope"}
    assert scope_w["w_scope"] == 0 and b1_w["w_scope"] != 0

    assert _diff_keys(b1_w, dense_w) == {"w_dense"}
    assert dense_w["w_dense"] == 1 and b1_w["w_dense"] == 0

    # B1-closure changes no weight at all — only the card data (every requires=[]).
    assert _diff_keys(b1_w, closure_w) == set()
    assert all(c["requires"] == [] for c in arms["B1-closure"].index.cards.values())
    assert arms["B1"].index.cards["urn:skill:t:cat_a:one"]["requires"] == ["urn:skill:t:cat_a:two"]

    # The word table itself is identical (same object/content) across every arm, including B1 —
    # it is inert under w_dense=0, which is what makes the B3b+B5 diff exactly one parameter.
    assert arms["B1"].index.word_vectors == arms["B3b+B5"].index.word_vectors == word_vectors

    # B1-flat (the frozen sparse variant, PR #36) changes exactly the five field.* weights, all
    # to 1 — everything else (w_scope, w_ppr, abstain_threshold, k1/b, ...) stays at B1's default.
    assert _diff_keys(b1_w, flat_w) == set(SRB.FLAT_FIELD_WEIGHTS)
    for key, val in SRB.FLAT_FIELD_WEIGHTS.items():
        assert flat_w[key] == val == 1
        assert b1_w[key] != 1  # shipped defaults are not already flat


def test_dense_arm_is_a_pure_gate_any_positive_w_dense_behaves_the_same():
    """w_dense is documented (Index.DEFAULT_WEIGHTS) as an ON/OFF gate, never a fusion magnitude:
    Router.candidates() only checks `weights.get("w_dense", 0) > 0` before running the dense
    channel at all — the actual RRF fusion never multiplies by w_dense. Confirms build_arms()'s
    choice of w_dense=1 is not an arbitrary magnitude a reviewer needs to tune."""
    cli = _load_cli()
    cards, nodes = _tiny_cards_and_nodes()
    word_vectors = {"one": (1, 2, 3), "two": (2, 3, 4), "three": (3, 4, 5)}
    idx_1 = cli.Index.from_cards(cards, nodes, weights={"w_dense": 1}, word_vectors=word_vectors)
    idx_7 = cli.Index.from_cards(cards, nodes, weights={"w_dense": 7}, word_vectors=word_vectors)
    router_1, router_7 = cli.Router(idx_1), cli.Router(idx_7)
    q = "one thing"
    scored_1 = router_1.score(router_1.candidates(q, "cat_a"), q, "cat_a")
    scored_7 = router_7.score(router_7.candidates(q, "cat_a"), q, "cat_a")
    assert [(s["urn"], s["score"]) for s in scored_1] == [(s["urn"], s["score"]) for s in scored_7]


# ------------------------------------------------------------------ converter (corpus-dependent)
def test_corpus_to_cards_round_trip_for_a_sample_skill():
    _needs("skillretbench")
    d = gf_corpora.load_skillretbench()
    skills = d["corpus"]["skills"]
    cards, nodes, report = SRB.corpus_to_cards(skills)

    assert len(cards) == len(skills) == 501
    assert report["dangling_requires"] == []          # this corpus revision (4bdbf59b): zero

    sample = skills[0]
    u = f"urn:skill:{SRB.PUBLISHER}:{sample['category']}:{sample['skill_id']}"
    assert u in cards
    card = cards[u]
    assert card["name"] == sample["skill_id"]
    assert card["node"] == sample["category"]
    assert card["description"] == sample["description"]
    assert card["status"] == "active"                 # every skill: see the outdated-mapping test
    # digest falls back to description[:200], same convention Index.build() itself uses when a
    # real SKILL.md carries no metadata.digest.
    assert card["digest"] == sample["description"][:200]
    # full_text's own embedded frontmatter must be stripped out of _body.
    assert not card["_body"].lstrip().startswith("---")
    assert sample["category"] in nodes


def test_corpus_to_cards_resolves_composable_skills_to_urns_when_present():
    _needs("skillretbench")
    d = gf_corpora.load_skillretbench()
    skills = d["corpus"]["skills"]
    cards, _, _ = SRB.corpus_to_cards(skills)
    with_deps = next(s for s in skills if s.get("composable_skills"))
    u = f"urn:skill:{SRB.PUBLISHER}:{with_deps['category']}:{with_deps['skill_id']}"
    card = cards[u]
    assert len(card["requires"]) == len(with_deps["composable_skills"])
    for dep_id, dep_urn in zip(with_deps["composable_skills"], card["requires"]):
        assert dep_urn in cards
        assert cards[dep_urn]["name"] == dep_id


def test_queries_to_cases_round_trip_for_a_sample_query():
    _needs("skillretbench")
    d = gf_corpora.load_skillretbench()
    skills = d["corpus"]["skills"]
    queries = d["queries"]["queries"]
    cards, _, _ = SRB.corpus_to_cards(skills)
    cases, report = SRB.queries_to_cases(queries, cards)

    assert report["missing_gold_urn"] == []
    assert report["missing_distractor_urn"] == []

    sample = queries[0]
    case = next(c for c in cases if c["id"] == sample["query_id"])
    assert case["query"] == sample["query"]
    assert case["setting"] == sample["setting"]
    assert case["category"] == SRB.SETTING_TO_CATEGORY[sample["setting"]]
    primary_gold = sample["gold_skills"][0]
    assert case["relevant"][0]["urn"] == cards[
        next(u for u, c in cards.items() if c["name"] == primary_gold)]["urn"]
    assert case["relevant"][0]["grade"] == 3
    assert case["node_scoped"] == cards[case["relevant"][0]["urn"]]["node"]
    assert case["node_root"] == "_root"


# ------------------------------------------------------------------ outdated_redundant mapping
def test_outdated_redundant_setting_names_a_dangling_synthetic_outdated_skill_id_in_this_corpus_revision():
    """Documents, as an assertion (not a silent default), the finding that motivated corpus_to_cards
    always setting status="active": this corpus revision (4bdbf59b) DOES populate
    `outdated_skill_id` on all 150 outdated_redundant queries -- but every single value is the
    synthetic marker "<gold_skill_id>__v1_deprecated", which resolves to zero real entries in this
    corpus's own `skills` list (0/150). distractor_skills is separately empty on those same 150
    queries. So SkillRetBench never names an actual, still-present successor skill for the
    deprecated one in this revision -- there is nothing real for `replaced_by` to point to. If a
    future revision bump changes either fact, this test must fail loudly rather than have
    corpus_to_cards silently keep guessing "active"."""
    _needs("skillretbench")
    d = gf_corpora.load_skillretbench()
    queries = d["queries"]["queries"]
    real_skill_ids = {s["skill_id"] for s in d["corpus"]["skills"]}
    outdated = [q for q in queries if q["setting"] == "outdated_redundant"]
    assert len(outdated) == 150
    assert all(q.get("outdated_skill_id") for q in outdated)
    assert all(
        q["outdated_skill_id"] == f"{q['gold_skills'][0]}__v1_deprecated" for q in outdated
    )
    assert all(q["outdated_skill_id"] not in real_skill_ids for q in outdated)
    assert all(not q.get("distractor_skills") for q in outdated)


# ------------------------------------------------------------------ node_scoped vs node_root (documented tension)
def test_multi_skill_composition_companions_often_cross_the_node_scoped_category_boundary():
    """Quantifies the "budget_constrained grading tension"'s sibling finding for
    multi_skill_composition: policy_filter's _visible_nodes(node) only admits the caller's own
    subtree + ancestors, so when a required companion lives in a DIFFERENT category than the
    primary gold skill (which sets node_scoped), that companion is permanently inadmissible under
    node_scoped -- no ranking improvement can recover it. This is why all_required@4 is reported
    for BOTH node_scoped and node_root in the bake-off report rather than node_scoped alone."""
    _needs("skillretbench")
    d = gf_corpora.load_skillretbench()
    skills = d["corpus"]["skills"]
    queries = d["queries"]["queries"]
    cards, _, _ = SRB.corpus_to_cards(skills)
    cases, _ = SRB.queries_to_cases(queries, cards)
    multi = [c for c in cases if c["setting"] == "multi_skill_composition"]
    assert len(multi) == 200
    cross = sum(
        1 for c in multi
        if any(cards[r["urn"]]["node"] != c["node_scoped"] for r in c["relevant"][1:])
    )
    # Empirically ~77% on this corpus revision; asserting a wide, stable lower bound so the test
    # documents the phenomenon without being brittle to a future revision's exact query mix.
    assert cross / len(multi) > 0.5


# ------------------------------------------------------------------ paired bootstrap (SS5)
def _metrics_module():
    """Same load pattern as test_binary_case_reproduces_standard_binary_recall_and_ndcg — a fresh,
    independent load of metrics.py's pure functions, so this section never depends on execution
    order of other tests in this file."""
    spec = importlib.util.spec_from_file_location("gf_metrics_srb_gate_test", EVAL_DIR / "metrics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_paired_delta_collapses_to_a_point_when_every_case_shows_the_same_delta():
    """When dense beats B1 by an identical amount on every query, resampling with replacement can
    only ever reproduce that same constant delta — the CI must collapse to a single point equal to
    the observed delta, with zero width. This is the strongest test of the resampling arithmetic
    itself: an exact equality, not a probabilistic hand-wave."""
    vals_a = [0.0] * 10
    vals_b = [1.0] * 10
    result = SRB._bootstrap_paired_delta(vals_a, vals_b, n_resamples=200, seed=0)
    assert result["delta"] == pytest.approx(1.0)
    assert result["ci_lo"] == pytest.approx(1.0)
    assert result["ci_hi"] == pytest.approx(1.0)
    assert result["n"] == 10
    assert result["n_resamples"] == 200


def test_bootstrap_paired_delta_is_exactly_reproducible_for_a_fixed_seed():
    """The report's numbers must be exactly reproducible on re-run (no hidden global RNG state) —
    same inputs + same seed => byte-identical output, every field."""
    vals_a = [0.2, 0.4, 0.6, 0.8, 1.0, 0.0, 0.5, 0.3]
    vals_b = [0.3, 0.9, 0.1, 0.7, 0.2, 0.6, 0.4, 0.8]
    r1 = SRB._bootstrap_paired_delta(vals_a, vals_b, n_resamples=500, seed=42)
    r2 = SRB._bootstrap_paired_delta(vals_a, vals_b, n_resamples=500, seed=42)
    assert r1 == r2
    # A different seed need not agree — documents that `seed` really is wired through to the RNG,
    # not silently ignored (these two particular seeds happen to disagree on this input).
    r3 = SRB._bootstrap_paired_delta(vals_a, vals_b, n_resamples=500, seed=7)
    assert r3["ci_lo"] != r1["ci_lo"] or r3["ci_hi"] != r1["ci_hi"]


def test_bootstrap_paired_delta_handles_empty_and_mismatched_inputs_without_raising():
    empty = SRB._bootstrap_paired_delta([], [])
    assert empty["n"] == 0
    assert empty["delta"] != empty["delta"]    # NaN
    assert empty["ci_lo"] != empty["ci_lo"]
    assert empty["ci_hi"] != empty["ci_hi"]

    mismatched = SRB._bootstrap_paired_delta([1.0, 2.0], [1.0])
    assert mismatched["n"] == 2
    assert mismatched["delta"] != mismatched["delta"]   # NaN, not a crash or a wrong-length zip


# ------------------------------------------------------------------ dense coverage (SS4/SS6)
class _FakeRouter:
    """Duck-types Router.candidates(query, node) -> list[{"urn","bm25_rank","dense_rank"}], the
    only method dense_coverage_report calls — lets the coverage arithmetic be tested without a
    real Index/corpus, while still exercising the *actual* candidates()-shaped contract (rank
    dicts reflecting true/unbounded rank even for a pool member that only entered via one channel
    — see Router.candidates() in skills/guidefold/scripts/guidefold)."""

    def __init__(self, by_query):
        self._by_query = by_query

    def candidates(self, query, node):
        return self._by_query[query]


def test_dense_coverage_report_counts_missed_recovered_absent_and_none_bm25_rank_correctly():
    fake = _FakeRouter({
        # single_skill: gold already inside BM25F's own top-50 — NOT missed, regardless of
        # dense_rank.
        "q1": [{"urn": "g1", "bm25_rank": 5, "dense_rank": None},
               {"urn": "other", "bm25_rank": 1, "dense_rank": 1}],
        # single_skill: gold present but beyond the cutoff — missed; dense finds it inside the
        # cutoff — recovered.
        "q2": [{"urn": "g2", "bm25_rank": 999, "dense_rank": 10}],
        # multi_skill_composition: gold absent from candidates() entirely — missed, and
        # necessarily not recovered (no dense_rank to check at all).
        "q3": [{"urn": "other", "bm25_rank": 1, "dense_rank": 1}],
        # multi_skill_composition: gold present with bm25_rank=None (it entered the pool only via
        # the dense channel) but its OWN dense_rank is itself beyond the cutoff — missed, not
        # recovered.
        "q4": [{"urn": "g4", "bm25_rank": None, "dense_rank": 200}],
    })
    cases = [
        {"setting": "single_skill", "node_scoped": "cat_a", "query": "q1", "relevant": [{"urn": "g1"}]},
        {"setting": "single_skill", "node_scoped": "cat_a", "query": "q2", "relevant": [{"urn": "g2"}]},
        {"setting": "multi_skill_composition", "node_scoped": "cat_a", "query": "q3", "relevant": [{"urn": "g3"}]},
        {"setting": "multi_skill_composition", "node_scoped": "cat_a", "query": "q4", "relevant": [{"urn": "g4"}]},
    ]
    report = SRB.dense_coverage_report(fake, cases)

    assert report["single_skill"]["n_gold_missed_by_bm25_top50"] == 1
    assert report["single_skill"]["n_recovered_by_encoder"] == 1
    assert report["single_skill"]["coverage"] == pytest.approx(1.0)

    assert report["multi_skill_composition"]["n_gold_missed_by_bm25_top50"] == 2
    assert report["multi_skill_composition"]["n_recovered_by_encoder"] == 0
    assert report["multi_skill_composition"]["coverage"] == pytest.approx(0.0)

    # Untouched settings report zero misses and an undefined (NaN) coverage, never a crash.
    untouched = report["distractor"]
    assert untouched["n_gold_missed_by_bm25_top50"] == 0
    assert untouched["n_recovered_by_encoder"] == 0
    assert untouched["coverage"] != untouched["coverage"]

    overall = report["OVERALL"]
    assert overall["n_gold_missed_by_bm25_top50"] == 3
    assert overall["n_recovered_by_encoder"] == 1
    assert overall["coverage"] == pytest.approx(1 / 3)


def test_format_coverage_table_smoke():
    fake = _FakeRouter({"q1": [{"urn": "g1", "bm25_rank": 999, "dense_rank": 3}]})
    cases = [{"setting": "single_skill", "node_scoped": "cat_a", "query": "q1", "relevant": [{"urn": "g1"}]}]
    table = SRB.format_coverage_table(SRB.dense_coverage_report(fake, cases))
    assert "single_skill" in table
    assert "OVERALL" in table
    assert "coverage" in table


# ------------------------------------------------------------------ dense-vs-B1 gate report (SS5)
def test_dense_vs_b1_gate_report_matches_hand_computed_deltas_and_pairs_answered_queries_only():
    """Builds a tiny 5-case synthetic set covering every wiring decision in
    dense_vs_b1_gate_report: the "answered" pairing (a case counts toward hit@1/all_required@4
    only when BOTH arms produced a non-empty ranking; qE's dense abstention must exclude it from
    those two, but NOT from ndcg@10/HSR@4, which use the full per-setting population), the
    zero-width bootstrap CI on a perfectly flat delta, HSR@4's undetermined-vs-real distinction,
    and the empty-setting (no cases at all, e.g. budget_constrained here) degrade-gracefully path."""
    metrics_mod = _metrics_module()

    def case(cid, setting, relevant, distractors=None):
        return {"id": cid, "setting": setting, "relevant": relevant, "distractors": distractors or []}

    case_a = case("qA", "single_skill", [{"urn": "a1", "grade": 3}])
    case_b = case("qB", "single_skill", [{"urn": "b1", "grade": 3}])
    case_e = case("qE", "single_skill", [{"urn": "e2", "grade": 2}])
    case_c = case("qC", "distractor", [{"urn": "c1", "grade": 2}], [{"urn": "d1"}])
    case_d = case("qD", "distractor", [{"urn": "e1", "grade": 2}], [{"urn": "f1"}])

    b1 = {"qA": ["a1", "x2"], "qB": ["b1"], "qE": ["e2"], "qC": ["d1", "c1"], "qD": ["e1", "f1"]}
    dense = {"qA": ["x2", "a1"], "qB": ["b1"], "qE": [], "qC": ["c1"], "qD": ["e1", "f1"]}

    cases = [case_a, case_b, case_e, case_c, case_d]
    retrieval_b1 = [(b1[c["id"]], c) for c in cases]
    retrieval_dense = [(dense[c["id"]], c) for c in cases]
    injection_b1, injection_dense = retrieval_b1, retrieval_dense   # same generic (ranked, case) contract

    gates = SRB.dense_vs_b1_gate_report(metrics_mod, cases, retrieval_b1, injection_b1,
                                         retrieval_dense, injection_dense, n_resamples=200)

    assert set(gates) == {"single_skill", "multi_skill_composition", "distractor",
                           "outdated_redundant", "budget_constrained", "OVERALL"}

    ss = gates["single_skill"]
    # hit@1 pairing excludes qE (dense abstains there) — only qA (0.0), qB (1.0) count for dense;
    # both score 1.0 for B1.
    assert ss["hit@1"]["delta"] == pytest.approx(0.5 - 1.0)
    assert ss["hit@1"]["n"] == 2
    # all_required@4 is unaffected here — both arms fit the sole required skill in the top 4 for
    # both qA and qB.
    assert ss["all_required@4"]["delta"] == pytest.approx(0.0)
    # ndcg@10 is NOT pairing-filtered — qE (dense empty) IS included here, dragging dense's mean
    # down below B1's.
    assert ss["ndcg@10"]["b1"] == pytest.approx(1.0)
    assert ss["ndcg@10"]["dense"] < ss["ndcg@10"]["b1"]
    # No distractors are labelled on any single_skill case here — HSR@4 must be undetermined
    # (NaN/None), never silently scored as 0 ("no exposure").
    assert ss["HSR@4"]["b1"] != ss["HSR@4"]["b1"]
    assert ss["HSR@4"]["gate_harmful_exposure"] is None
    assert "distractor_rate" in ss["HSR@4"]["note"]

    dd = gates["distractor"]
    assert dd["HSR@4"]["b1"] == pytest.approx(1.0)      # named distractor in the top 4 for both qC, qD
    assert dd["HSR@4"]["dense"] == pytest.approx(0.5)   # dense drops it for qC only
    assert dd["HSR@4"]["delta"] == pytest.approx(-0.5)
    assert dd["HSR@4"]["gate_harmful_exposure"] is True     # dense is LESS harmful here — must PASS
    # all_required@4 is identical in every resample (both arms score 1.0 on both queries) — the
    # bootstrap CI must collapse to an exact zero-width interval at 0.0, and the +2pp gate must
    # correctly fail on a flat, non-improving delta (never PASS a delta of zero).
    assert dd["all_required@4"]["delta"] == pytest.approx(0.0)
    assert dd["all_required@4"]["ci_lo"] == pytest.approx(0.0)
    assert dd["all_required@4"]["ci_hi"] == pytest.approx(0.0)
    assert dd["all_required@4"]["gate_bundle_completeness"] is False

    # A setting with zero cases in this synthetic set must degrade to an all-NaN/all-None report,
    # never raise or fabricate a number.
    empty_setting = gates["budget_constrained"]
    assert empty_setting["all_required@4"]["n"] == 0
    assert empty_setting["all_required@4"]["gate_bundle_completeness"] is None
    assert empty_setting["hit@1"]["gate_primary_quality"] is None
    assert empty_setting["ndcg@10"]["b1"] != empty_setting["ndcg@10"]["b1"]

    overall = gates["OVERALL"]
    assert overall["hit@1"]["n"] == 4     # every case except qE (dense abstains there)
    assert overall["all_required@4"]["n"] == 4


def test_format_gate_table_renders_undetermined_as_n_a_never_fail():
    metrics_mod = _metrics_module()
    case_e = {"id": "qE", "setting": "single_skill", "relevant": [{"urn": "e2", "grade": 2}], "distractors": []}
    pair = (["e2"], case_e)
    gates = SRB.dense_vs_b1_gate_report(metrics_mod, [case_e], [pair], [pair], [pair], [pair], n_resamples=50)
    table = SRB.format_gate_table(gates)
    assert "n/a" in table            # HSR@4 (and every other setting's gates) are undetermined here
    assert "REFERENCE RUN R1" in table
    assert "OVERALL" in table


def test_format_gate_table_renders_pass_and_fail_for_computed_gates():
    metrics_mod = _metrics_module()
    case_c = {"id": "qC", "setting": "distractor", "relevant": [{"urn": "c1", "grade": 2}], "distractors": [{"urn": "d1"}]}
    case_d = {"id": "qD", "setting": "distractor", "relevant": [{"urn": "e1", "grade": 2}], "distractors": [{"urn": "f1"}]}
    pair_b1 = [(["d1", "c1"], case_c), (["e1", "f1"], case_d)]
    pair_dense = [(["c1"], case_c), (["e1", "f1"], case_d)]
    gates = SRB.dense_vs_b1_gate_report(metrics_mod, [case_c, case_d], pair_b1, pair_b1,
                                         pair_dense, pair_dense, n_resamples=50)
    table = SRB.format_gate_table(gates)
    assert "PASS" in table    # HSR@4 improves (dense is less harmful) on the distractor row
    assert "fail" in table    # all_required@4 shows a flat (non-improving) delta — must not PASS
