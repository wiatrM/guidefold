"""tools/eval/dev_sparse.py — dev-only diagnosis of the shipped BM25F vs plain textbook BM25 gap
(DENSE-PROGRAM.md SS7). Same two-layer convention as tests/test_skillretbench.py: pure-logic tests
(card/case construction rules, the reference BM25 hand-check, the ablation-arm diff contract, the
structural byte-identical-ranking prediction on a small synthetic fixture) always run; the one
test that reads the real 10 123-skill dev corpus skips with a reason when the pinned SKILLRET
data is not on this machine.
"""
import importlib.util
import math
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "tools" / "eval"
CLI_PATH = ROOT / "skills" / "guidefold" / "scripts" / "guidefold"

sys.path.insert(0, str(ROOT / "tests"))
from _router_helpers import make_card, make_nodes  # noqa: E402

spec = importlib.util.spec_from_file_location("gf_corpora", EVAL_DIR / "corpora.py")
gf_corpora = importlib.util.module_from_spec(spec)
sys.modules["gf_corpora"] = gf_corpora
spec.loader.exec_module(gf_corpora)

spec = importlib.util.spec_from_file_location("gf_dev_sparse", EVAL_DIR / "dev_sparse.py")
dev_sparse = importlib.util.module_from_spec(spec)
sys.modules["gf_dev_sparse"] = dev_sparse
spec.loader.exec_module(dev_sparse)


def _load_cli():
    loader = SourceFileLoader("guidefold_cli_dev_sparse_test", str(CLI_PATH))
    cli_spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(cli_spec)
    loader.exec_module(module)
    return module


def _needs(name):
    problems = gf_corpora.verify(name)
    if problems:
        pytest.skip(f"{name} not on this machine or not the pinned revision: {problems[0]}")


# ------------------------------------------------------------------ torch-free module boundary
def test_dev_sparse_module_imports_cleanly_with_torch_blocked(monkeypatch):
    """Same guarantee as test_skillretbench.py's own test: `convert`/`run` (and pytest collecting
    this file) must never require a GPU venv."""
    monkeypatch.setitem(sys.modules, "torch", None)

    class _TorchIsForbidden:
        def find_spec(self, name, path=None, target=None):
            if name == "torch" or name.startswith("torch."):
                raise ImportError(f"torch must never be imported at dev_sparse.py module scope: {name}")
            return None

    sys.meta_path.insert(0, _TorchIsForbidden())
    try:
        spec2 = importlib.util.spec_from_file_location("gf_dev_sparse_reload", EVAL_DIR / "dev_sparse.py")
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
    finally:
        sys.meta_path.pop(0)


# ------------------------------------------------------------------ slugify / frontmatter
def test_slugify():
    assert dev_sparse.slugify("AI Agents") == "ai-agents"
    assert dev_sparse.slugify("Business & Planning") == "business-planning"
    assert dev_sparse.slugify("  Data & ML  ") == "data-ml"
    assert dev_sparse.slugify("0ae16990-059d-4aa0-b64e-bdc9cc812773") == "0ae16990-059d-4aa0-b64e-bdc9cc812773"


def test_strip_own_frontmatter():
    fm = "---\nname: x\ndescription: y\n---\n\n# Body\ntext here"
    assert dev_sparse.strip_own_frontmatter(fm) == "# Body\ntext here"
    no_fm = "# Body\ntext here"
    assert dev_sparse.strip_own_frontmatter(no_fm) == no_fm   # no match -> no-op, not an error


# ------------------------------------------------------------------ tokenizer isolation
def test_simple_tokenize_has_no_accent_folding_unlike_shared_tokenizer():
    assert dev_sparse.gf_tokenize("café") == ["cafe"]
    assert dev_sparse.simple_tokenize("café") == ["caf"]
    assert dev_sparse.gf_tokenize("naïve") == ["naive"]
    assert dev_sparse.simple_tokenize("naïve") == ["na", "ve"]


# ------------------------------------------------------------------ R-BM25 hand-check (3 documents)
def test_reference_bm25_hand_verified_on_three_documents():
    """Independent hand computation of textbook Okapi BM25 (k1=1.2, b=0.75) for a query that
    matches two of three tiny documents on exactly one term each, and misses the third entirely.
    Tokenised with plain str.split (these texts need nothing fancier) so the check is decoupled
    from tools/bakeoff/tokenizer.py."""
    docs = {
        "u:d1": "the cat sat on the mat",      # 6 tokens, "cat" once
        "u:d2": "the dog sat on the log",      # 6 tokens, "dog" once
        "u:d3": "cats and dogs are friends",   # 5 tokens, neither "cat" nor "dog" occurs
    }
    ref = dev_sparse.ReferenceBM25(docs, str.split)
    scores = ref.score_all("cat dog")

    n, avgdl = 3, (6 + 6 + 5) / 3
    idf = math.log((n - 1 + 0.5) / (1 + 0.5) + 1.0)   # df(cat) == df(dog) == 1, hand-counted

    def expected(tf, dl):
        denom = tf + 1.2 * (1 - 0.75 + 0.75 * dl / avgdl)
        return idf * (tf * 2.2) / denom

    assert scores["u:d1"] == pytest.approx(expected(1, 6))
    assert scores["u:d2"] == pytest.approx(expected(1, 6))
    assert scores["u:d1"] == pytest.approx(scores["u:d2"])   # symmetric by construction
    assert "u:d3" not in scores                              # zero matching terms -> absent, not 0.0

    ranked = ref.rank("cat dog")
    assert ranked[:2] == ["u:d1", "u:d2"]   # tied score -> deterministic urn-ascending tie-break
    assert ranked[2] == "u:d3"              # unscored doc still ranked (no filter, no cap), last


def test_reference_bm25_ranks_every_doc_no_filter_no_cap():
    docs = {f"u:{i}": ("shared term " * 3 if i == 0 else f"unrelated{i} filler") for i in range(20)}
    ref = dev_sparse.ReferenceBM25(docs, str.split)
    ranked = ref.rank("shared term")
    assert len(ranked) == 20             # every doc present, none dropped
    assert ranked[0] == "u:0"            # the only doc that matches, ranked first


# ------------------------------------------------------------------ card/case construction (synthetic)
def test_corpus_to_cards_synthetic():
    skills = [
        {"id": "aaaa", "name": "brainstorming", "major": "Software Engineering", "sub": "Development",
         "description": "explore ideas", "body": "---\nname: brainstorming\n---\n\nBody text"},
        {"id": "bbbb", "name": "other-skill", "major": "Software Engineering", "sub": "Security",
         "description": "scan for vulnerabilities", "body": "no frontmatter here"},
    ]
    cards, nodes, id_to_urn, report = dev_sparse.corpus_to_cards(skills)
    assert report["n_cards"] == 2
    assert report["dup_ids"] == []
    assert set(nodes) == {"_root", "software-engineering",
                           "software-engineering.development", "software-engineering.security"}
    u1 = id_to_urn["aaaa"]
    assert u1 == "urn:skill:skillret:software-engineering.development:aaaa"
    assert cards[u1]["name"] == "brainstorming"
    assert cards[u1]["description"] == "explore ideas"
    assert cards[u1]["digest"] == "explore ideas"
    assert cards[u1]["_body"] == "Body text"          # frontmatter stripped
    assert cards[u1]["triggers"] == [] and cards[u1]["negative_triggers"] == []
    assert cards[u1]["requires"] == [] and cards[u1]["refines"] == []
    assert cards[u1]["status"] == "active"

    u2 = id_to_urn["bbbb"]
    assert cards[u2]["_body"] == "no frontmatter here"   # no frontmatter match -> unchanged


def test_queries_to_cases_synthetic():
    id_to_urn = {"s1": "urn:s1", "s2": "urn:s2"}
    queries = [
        {"id": "q1", "query": "find a skill", "skill_ids": ["s1", "s2"], "k": 2},
        {"id": "q2", "query": "no gold here", "skill_ids": [], "k": 0},
    ]
    qrels = [{"query_id": "q1", "skill_id": "s1", "relevance": 1},
             {"query_id": "q1", "skill_id": "s2", "relevance": 1}]
    cases, report = dev_sparse.queries_to_cases(queries, qrels, id_to_urn)
    assert report["n_cases"] == 1
    assert report["dropped_empty_gold"] == 1
    assert report["qrel_mismatches"] == []
    assert report["missing_urn"] == []
    case = cases[0]
    assert case["node"] == "_root"
    assert case["relevant"] == [{"urn": "urn:s1", "grade": 3}, {"urn": "urn:s2", "grade": 2}]


def test_queries_to_cases_flags_qrel_mismatch_and_missing_urn():
    id_to_urn = {"s1": "urn:s1"}
    queries = [{"id": "q1", "query": "x", "skill_ids": ["s1", "s2"], "k": 2}]
    qrels = [{"query_id": "q1", "skill_id": "s1", "relevance": 1}]   # missing s2 -> mismatch
    cases, report = dev_sparse.queries_to_cases(queries, qrels, id_to_urn)
    assert report["qrel_mismatches"] == ["q1"]
    assert report["missing_urn"] == [("q1", "s2")]
    assert cases[0]["relevant"] == [{"urn": "urn:s1", "grade": 3}]   # s2 dropped, not invented


# ------------------------------------------------------------------ P-onefield card transform
def test_onefield_cards_moves_everything_into_body_and_empties_other_fields():
    cards = {
        "u:1": {"urn": "u:1", "node": "n", "name": "my-skill", "description": "desc text",
                "digest": "dig text", "triggers": ["trig one", "trig two"],
                "negative_triggers": [], "requires": [], "refines": [], "status": "active",
                "replaced_by": None, "kind": None, "layer": None, "owner": None,
                "_body": "body text"},
    }
    out = dev_sparse.onefield_cards(cards)
    c = out["u:1"]
    assert c["name"] == "" and c["description"] == "" and c["digest"] == "" and c["triggers"] == []
    for word in ("my skill", "desc text", "dig text", "trig one", "trig two", "body text"):
        assert word in c["_body"]
    # structural fields untouched
    for f in ("urn", "node", "requires", "negative_triggers", "refines", "status"):
        assert c[f] == cards["u:1"][f]


# ------------------------------------------------------------------ product-path arm fixture
def _arm_fixture_cards_and_nodes():
    nodes = make_nodes("_root", "eng", "eng.backend", "eng.frontend", "biz", "biz.sales")
    topics = {
        "u:1": ("eng.backend", "database migration schema tool", "run schema migrations safely",
                ("db migration",)),
        "u:2": ("eng.backend", "queue worker retry logic", "background job queue processing",
                ("retry queue",)),
        "u:3": ("eng.frontend", "react component state hook", "frontend ui state management", ()),
        "u:4": ("eng.frontend", "css layout grid flexbox", "responsive layout styling", ()),
        "u:5": ("biz.sales", "quarterly sales report pipeline", "aggregate sales numbers", ()),
        "u:6": ("biz.sales", "customer churn prediction", "sales retention forecasting", ()),
    }
    cards = {u: make_card(u, node, description=desc, body=body, triggers=trig)
             for u, (node, desc, body, trig) in topics.items()}
    return cards, nodes


def test_ablation_arms_differ_from_shipped_by_exactly_one_parameter():
    cli = _load_cli()
    cards, nodes = _arm_fixture_cards_and_nodes()
    arms = dev_sparse._build_product_arms(cli, cards, nodes)
    shipped_idx, _, shipped_top_n = arms["P-shipped"]
    assert shipped_top_n == 50

    flat_idx = arms["P-flat"][0]
    diff = {k for k in shipped_idx.weights if shipped_idx.weights[k] != flat_idx.weights[k]}
    assert diff == {f"field.{f}" for f in cli.Index.FIELDS}
    assert all(flat_idx.weights[k] == 1 for k in diff)

    nopprocl_idx = arms["P-nopprocl"][0]
    diff = {k for k in shipped_idx.weights if shipped_idx.weights[k] != nopprocl_idx.weights[k]}
    assert diff == {"w_ppr"}
    assert nopprocl_idx.weights["w_ppr"] == 0

    noscope_idx = arms["P-noscope"][0]
    diff = {k for k in shipped_idx.weights if shipped_idx.weights[k] != noscope_idx.weights[k]}
    assert diff == {"w_scope"}
    assert noscope_idx.weights["w_scope"] == 0

    top200_idx, _, top200_n = arms["P-top200"]
    assert top200_idx is shipped_idx   # literally the same Index/Router -- only top_n differs
    assert top200_n == 200

    onefield_idx = arms["P-onefield"][0]
    assert onefield_idx.weights == shipped_idx.weights   # weights unchanged
    changed = set()
    for u in shipped_idx.cards:
        for f in ("name", "description", "digest", "triggers", "_body"):
            if shipped_idx.cards[u][f] != onefield_idx.cards[u][f]:
                changed.add(f)
        for f in ("urn", "node", "requires", "negative_triggers", "refines", "status"):
            assert shipped_idx.cards[u][f] == onefield_idx.cards[u][f]
    assert changed == {"name", "description", "digest", "triggers", "_body"}

    k1b_idx = arms["P-k1b"][0]
    assert k1b_idx.weights == shipped_idx.weights                 # weights dict unchanged
    assert (shipped_idx.K1, shipped_idx.B) == (1.2, 0.75)
    assert (k1b_idx.K1, k1b_idx.B) == (0.9, 0.4)
    assert k1b_idx.cards.keys() == shipped_idx.cards.keys()       # cards unchanged


def test_noscope_nopprocl_top200_are_byte_identical_to_shipped_ranking():
    """The structural prediction (derived from reading Router.score/_hops/_decayed_closure): with
    zero `requires` edges and every candidate node exactly 2 hops from `_root`, RRF's monotone
    transform of bm25_rank, w_scope's per-query CONSTANT, and PPR-with-no-edges' per-candidate
    affine rescale cannot change relative order; top_n only changes which urns enter the
    candidate pool, never a candidate's true bm25_rank. Confirmed empirically here, not assumed."""
    cli = _load_cli()
    cards, nodes = _arm_fixture_cards_and_nodes()
    arms = dev_sparse._build_product_arms(cli, cards, nodes)
    query = "sales report queue migration schema"
    node = "_root"

    def ranked_urns(arm_name):
        index, router, top_n = arms[arm_name]
        cands = router.candidates(query, node, top_n=top_n)
        scored = router.score(cands, query, node)
        return [s["urn"] for s in scored]

    shipped = ranked_urns("P-shipped")
    assert len(shipped) >= 3   # the query actually matches several cards
    assert ranked_urns("P-noscope") == shipped
    assert ranked_urns("P-nopprocl") == shipped
    assert ranked_urns("P-top200") == shipped
    # P-onefield and P-flat are NOT predicted to match -- they change what's actually scored.


# ------------------------------------------------------------------ bootstrap sanity
def test_bootstrap_paired_delta_zero_when_arms_identical():
    vals = [0.5, 1.0, 0.0, 0.8, 0.3, 1.0, 0.6, 0.2, 0.9, 0.4]
    result = dev_sparse.bootstrap_paired_delta(vals, vals, n_resamples=200, seed=1)
    assert result["delta"] == 0.0
    assert result["ci_lo"] == 0.0 and result["ci_hi"] == 0.0


def test_bootstrap_paired_delta_recovers_observed_mean_difference():
    a = [0.0, 0.0, 0.0, 0.0, 0.0]
    b = [1.0, 1.0, 1.0, 1.0, 1.0]
    result = dev_sparse.bootstrap_paired_delta(a, b, n_resamples=200, seed=1)
    assert result["delta"] == pytest.approx(1.0)
    assert result["ci_lo"] == pytest.approx(1.0) and result["ci_hi"] == pytest.approx(1.0)


# ------------------------------------------------------------------ real dev corpus (skips if absent)
def test_real_dev_corpus_to_cards_and_cases_match_the_frozen_split():
    _needs("skillret")
    data = gf_corpora.load_skillret_dev()
    cards, nodes, id_to_urn, corpus_report = dev_sparse.corpus_to_cards(data["skills"])
    assert corpus_report["n_skills"] == 10123
    assert corpus_report["n_cards"] == 10123
    assert corpus_report["n_majors"] == 6
    assert corpus_report["n_major_sub_nodes"] == 18
    assert corpus_report["dup_ids"] == []
    assert corpus_report["major_slug_collisions"] == {}
    assert corpus_report["sub_slug_collisions"] == {}

    cases, query_report = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)
    assert query_report["n_cases"] == 1000
    assert query_report["qrel_mismatches"] == []
    assert query_report["missing_urn"] == []
    k_counts: dict = {}
    for c in cases:
        k_counts[c["k"]] = k_counts.get(c["k"], 0) + 1
    assert k_counts == {1: 328, 2: 333, 3: 339}   # docs/reports/bakeoff/validation/skillret-dev-split.json
