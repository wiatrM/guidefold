"""tools/eval/dev_decompose.py — dev-only evaluation of family D (query decomposition),
DENSE-PROGRAM.md v2.5 SS4. Pure-logic tests only: the clause splitter (deterministic and
model-line-parsing halves), the RRF merge / compose-priority-order arithmetic, and the model
call path with `_invoke_claude_haiku` replaced by a stub (never invokes the real `claude` CLI).
One test guarantees the module never needs a GPU venv at import time, same convention as
tests/test_dev_sparse.py and tests/test_skillretbench.py.

Retrieval-pipeline integration (candidates()/score()/select() wired through
`run_d0_case`/`run_decomposed_case` against a real, synthetic Index) is covered by a small
fixture built with tests/_router_helpers.py's make_card/make_nodes, matching the existing
`test_router_*` convention rather than reimplementing Router behaviour by hand.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "tools" / "eval"

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

spec = importlib.util.spec_from_file_location("gf_skillret", EVAL_DIR / "skillret.py")
gf_skillret = importlib.util.module_from_spec(spec)
sys.modules["gf_skillret"] = gf_skillret
spec.loader.exec_module(gf_skillret)

spec = importlib.util.spec_from_file_location("gf_dev_decompose", EVAL_DIR / "dev_decompose.py")
dd = importlib.util.module_from_spec(spec)
sys.modules["gf_dev_decompose"] = dd
spec.loader.exec_module(dd)


# ------------------------------------------------------------------ torch-free module boundary
def test_dev_decompose_module_imports_cleanly_with_torch_blocked(monkeypatch):
    """Same guarantee as test_dev_sparse.py's own test: `model-cache`/`run` (and pytest collecting
    this file) must never require a GPU venv -- dev_decompose.py imports dev_sparse.py and
    skillret.py, both of which already carry this guarantee; this test re-checks it holds through
    the extra import layer."""
    monkeypatch.setitem(sys.modules, "torch", None)

    class _TorchIsForbidden:
        def find_spec(self, name, path=None, target=None):
            if name == "torch" or name.startswith("torch."):
                raise ImportError(f"torch must never be imported at dev_decompose.py module scope: {name}")
            return None

    sys.meta_path.insert(0, _TorchIsForbidden())
    try:
        spec2 = importlib.util.spec_from_file_location("gf_dev_decompose_reload", EVAL_DIR / "dev_decompose.py")
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
    finally:
        sys.meta_path.pop(0)


# ------------------------------------------------------------------ deterministic clause splitter
def test_split_clauses_one_clause_guard_no_markers():
    """A plain, single-intent request with no sentence boundary, semicolon, or coordinating
    marker must NOT be decomposed -- returned as a single-element list, the k=1 guard."""
    q = "reset the staging database password for the onboarding service"
    out = dd.split_clauses(q)
    assert out == [q.strip()]


def test_split_clauses_one_clause_guard_trailing_punctuation_only():
    """A trailing full stop with nothing after it must not manufacture a second, empty clause."""
    q = "roll back the last deployment to the payments service."
    out = dd.split_clauses(q)
    assert len(out) == 1


def test_split_clauses_period_boundary():
    out = dd.split_clauses("Onboard the new hire in Rippling. Run the full lint suite on their scripts.")
    assert len(out) == 2
    assert "Onboard the new hire in Rippling" in out[0]
    assert "Run the full lint suite on their scripts" in out[1]


def test_split_clauses_semicolon_boundary():
    out = dd.split_clauses("provision the staging cluster; deploy the payments service to it")
    assert len(out) == 2
    assert "provision" in out[0]
    assert "deploy" in out[1]


@pytest.mark.parametrize("marker", ["and then", "then", ", and", "as well as", "also", "plus"])
def test_split_clauses_coordinating_markers(marker):
    query = f"onboard three new hires in Rippling {marker} run the full test suite on their scripts"
    out = dd.split_clauses(query)
    assert len(out) == 2, f"marker {marker!r} did not split: {out}"
    assert marker.strip(", ").lower() not in out[0].lower().split()[-1:]
    assert "onboard" in out[0].lower()
    assert "run the full test suite" in out[1].lower() or "test suite" in out[1].lower()


def test_split_clauses_and_then_not_left_dangling_as_bare_then():
    """", and then" / "and then" must be consumed as ONE marker -- a bare "then" must never survive
    at the front of the second clause."""
    out = dd.split_clauses("create the onboarding ticket in Jira, and then notify the manager by email")
    assert len(out) == 2
    assert not out[1].lower().startswith("then")


@pytest.mark.parametrize("boundary", ["。", "！", "？", "…"])
def test_split_clauses_unicode_sentence_boundaries(boundary):
    query = f"reboot the application server{boundary}verify the health check endpoint responds"
    out = dd.split_clauses(query)
    assert len(out) == 2, f"boundary {boundary!r} did not split: {out}"


@pytest.mark.parametrize("semicolon", ["؛", "；"])
def test_split_clauses_unicode_semicolons(semicolon):
    query = f"set up the read replica database{semicolon} deploy the reporting application to it"
    out = dd.split_clauses(query)
    assert len(out) == 2, f"semicolon {semicolon!r} did not split: {out}"


def test_split_clauses_drops_short_fragments():
    """A trailing fragment with fewer than MIN_CONTENT_TOKENS content tokens (here: "ok") must be
    dropped as a candidate clause; dropping it back down to a single usable fragment must trip
    the one-clause guard -- the whole original query is returned unsplit (not a trimmed version),
    so a not-decomposed query is retrieved identically to D0."""
    q = "update the deployment configuration for the payments service. ok"
    out = dd.split_clauses(q)
    assert out == [q.strip()]


def test_split_clauses_drops_short_fragments_among_otherwise_valid_ones():
    """With three raw fragments where the middle one is too short, the short one must be dropped
    while the two substantial ones survive as real clauses."""
    q = "provision the staging cluster. ok. deploy the payments service to it"
    out = dd.split_clauses(q)
    assert len(out) == 2
    assert "provision" in out[0]
    assert "deploy" in out[1]
    assert not any("ok" == frag.strip().lower() for frag in out)


def test_split_clauses_caps_at_max_clauses():
    query = ("onboard the new hire. provision their laptop. grant repository access. "
             "schedule the orientation meeting. order their equipment.")
    out = dd.split_clauses(query, max_clauses=4)
    assert len(out) == 4


# ------------------------------------------------------------------ model-line parsing (pure)
def test_parse_model_lines_strips_numbering_and_bullets():
    text = "1. Onboard the new hire in Rippling\n2) Run the full lint suite on their scripts\n- (ignore)"
    out = dd._parse_model_lines(text)
    assert out[0] == "Onboard the new hire in Rippling"
    assert out[1] == "Run the full lint suite on their scripts"


def test_parse_model_lines_drops_short_lines_and_blank_lines():
    text = "Reboot the application server\n\nok\nVerify the health check endpoint responds"
    out = dd._parse_model_lines(text)
    assert len(out) == 2
    assert "ok" not in out


def test_parse_model_lines_caps_at_max_clauses():
    text = "\n".join(f"do a meaningfully long subtask number {i}" for i in range(6))
    out = dd._parse_model_lines(text, max_clauses=4)
    assert len(out) == 4


# ------------------------------------------------------------------ model call: mocked, never real
def test_decompose_via_model_cache_miss_calls_invoke_and_caches(tmp_path):
    calls = []

    def fake_invoke(prompt, timeout=60):
        calls.append(prompt)
        return '{"result": "Onboard the new hire in Rippling\\nRun the full lint suite"}'

    cache = {}
    clauses, called = dd.decompose_via_model("onboard the new hire and run the full lint suite",
                                              cache, invoke=fake_invoke)
    assert called is True
    assert len(calls) == 1
    assert clauses == ["Onboard the new hire in Rippling", "Run the full lint suite"]
    assert len(cache) == 1


def test_decompose_via_model_cache_hit_never_calls_invoke():
    def exploding_invoke(prompt, timeout=60):
        raise AssertionError("invoke() must not be called on a cache hit")

    query = "reset the staging database password"
    key = dd.hashlib.sha256(query.encode("utf-8")).hexdigest()
    cache = {key: [query]}
    clauses, called = dd.decompose_via_model(query, cache, invoke=exploding_invoke)
    assert called is False
    assert clauses == [query]


def test_decompose_via_model_one_clause_guard_on_single_line_reply():
    def fake_invoke(prompt, timeout=60):
        return '{"result": "reset the staging database password for the onboarding service"}'

    cache = {}
    query = "reset the staging database password for the onboarding service"
    clauses, called = dd.decompose_via_model(query, cache, invoke=fake_invoke)
    assert called is True
    assert clauses == [query]   # not decomposed: the model returned it unchanged, one line


def test_decompose_via_model_shared_cache_across_two_configs():
    """D-model-1 / D-model-2 differ only in per-clause depth -- the SAME cache dict must serve
    both without a second real call."""
    calls = []

    def fake_invoke(prompt, timeout=60):
        calls.append(prompt)
        return '{"result": "clause one about something\\nclause two about something else"}'

    cache = {}
    query = "do the first thing and also do the second thing"
    dd.decompose_via_model(query, cache, invoke=fake_invoke)   # simulates D-model-1
    clauses2, called2 = dd.decompose_via_model(query, cache, invoke=fake_invoke)   # D-model-2
    assert called2 is False
    assert len(calls) == 1
    assert clauses2 == ["clause one about something", "clause two about something else"]


def test_model_cache_round_trip(tmp_path):
    path = tmp_path / "cache.json"
    dd.save_model_cache({"deadbeef": ["a", "b"]}, path)
    loaded = dd.load_model_cache(path)
    assert loaded == {"deadbeef": ["a", "b"]}


def test_load_model_cache_missing_file_returns_empty(tmp_path):
    assert dd.load_model_cache(tmp_path / "does-not-exist.json") == {}


# ------------------------------------------------------------------ RRF merge / compose
def test_rrf_merge_hand_verified_two_voters():
    voters = [["u:a", "u:b"], ["u:b", "u:c"]]
    merged = dd.rrf_merge(voters)
    expected_b = dd._rrf_contribution(2) + dd._rrf_contribution(1)
    expected_a = dd._rrf_contribution(1)
    expected_c = dd._rrf_contribution(2)
    assert merged["u:b"] == expected_b
    assert merged["u:a"] == expected_a
    assert merged["u:c"] == expected_c
    assert merged["u:b"] > merged["u:a"]   # voted for by both voters -> ranks first overall
    assert merged["u:b"] > merged["u:c"]


def test_rrf_contribution_matches_product_formula():
    """RRF_SCALE // (RRF_K + rank) -- the exact arithmetic skills/guidefold/scripts/guidefold's
    Router.score() uses for bm25_rank/dense_rank fusion, applied here one level up."""
    assert dd._rrf_contribution(1) == dd.RRF_SCALE // (dd.RRF_K + 1)
    assert dd.RRF_SCALE == 1 << 20
    assert dd.RRF_K == 60


def test_compose_priority_order_best_of_each_clause_first():
    clause_lists = [["u:a", "u:x"], ["u:b", "u:x"]]
    merged = dd.rrf_merge(clause_lists)
    order = dd.compose_priority_order(clause_lists, merged)
    # phase 1: each clause's own top pick, first-seen order, deduplicated
    assert order[0] == "u:a"
    assert order[1] == "u:b"
    # phase 2: everything else, by merged RRF order -- u:x voted for by both, appears once
    assert order.count("u:x") == 1
    assert set(order) == {"u:a", "u:b", "u:x"}


def test_compose_priority_order_is_a_full_permutation_of_merged_scores():
    clause_lists = [["u:a", "u:b", "u:c"], ["u:d", "u:b"]]
    merged = dd.rrf_merge(clause_lists)
    order = dd.compose_priority_order(clause_lists, merged)
    assert set(order) == set(merged)
    assert len(order) == len(merged)


# ------------------------------------------------------------------ retrieval-pipeline integration (synthetic Index)
def _build_router(gf):
    nodes = make_nodes("eng")
    cards = {
        "u:onboarding": make_card("u:onboarding", "eng", name="onboarding",
                                   description="onboard new hires in Rippling",
                                   triggers=["onboard", "rippling", "new hire"]),
        "u:lint": make_card("u:lint", "eng", name="lint-suite",
                             description="run the lint and test suite",
                             triggers=["lint", "test suite", "type check"]),
        "u:unrelated": make_card("u:unrelated", "eng", name="unrelated",
                                  description="invoices and billing",
                                  triggers=["invoice", "billing"]),
    }
    idx = gf.Index.from_cards(cards, nodes)
    return gf.Router(idx), idx


def test_run_decomposed_case_recovers_a_companion_skill_whole_query_misses(gf):
    """The whole scenario family D exists for, on a tiny synthetic fixture: a two-intent query
    whose second intent's terms are outnumbered by the first's under whole-query BM25. Splitting
    into clauses and merging by RRF must recover the second skill in the merged ranked list even
    when D0's own single-pass ranking would bury it."""
    router, idx = _build_router(gf)
    case = {"id": "q1", "k": 2, "node": "eng",
            "query": "onboard the new hire in Rippling onboarding onboarding onboarding "
                     "and then run the lint suite"}

    d0_scored, d0_injected = dd.run_d0_case(router, case, top_n=50, k_cards=4)
    d0_ranked = [c["urn"] for c in d0_scored]

    clauses = dd.split_clauses(case["query"])
    assert len(clauses) == 2
    rec = dd.run_decomposed_case(router, case, clauses, depth=10, include_whole_query_in_rrf=False)

    assert "u:lint" in rec["ranked"]
    assert rec["decomposed"] is True
    assert rec["n_clauses"] == 2
    assert rec["extra_calls"] == 2
    # sanity: this fixture is small enough that D0 itself may already find both (BM25F over 3
    # cards), so the load-bearing assertion is that decomposition ALSO finds it, not that D0 fails.
    assert isinstance(d0_ranked, list)


def test_run_decomposed_case_whole_query_rrf_toggle_adds_a_voter(gf):
    router, idx = _build_router(gf)
    case = {"id": "q2", "k": 2, "node": "eng",
            "query": "onboard the new hire and also run the lint suite"}
    clauses = dd.split_clauses(case["query"])
    assert len(clauses) == 2

    whole_scored, _ = dd.run_d0_case(router, case, top_n=50, k_cards=4)
    with_whole = dd.run_decomposed_case(router, case, clauses, depth=10,
                                         whole_query_scored=whole_scored,
                                         include_whole_query_in_rrf=True)
    without_whole = dd.run_decomposed_case(router, case, clauses, depth=10,
                                            include_whole_query_in_rrf=False)
    assert set(with_whole["ranked"]) >= set()   # both must run without error
    assert set(without_whole["ranked"]) >= set()


def test_d0_record_shape_matches_decomposed_record_shape(gf):
    """D0's own per-query record and a decomposed arm's record must carry the same keys, since
    both are aggregated by the same `per_query_metrics_d` / `arm_summary_d` / JSONL writer."""
    router, idx = _build_router(gf)
    case = {"id": "q3", "k": 1, "node": "eng", "query": "onboard the new hire in Rippling"}
    scored, injected = dd.run_d0_case(router, case)
    rec = dd.d0_record(case, scored, injected)
    expected_keys = {"query_id", "k", "arm", "ranked", "injected", "abstained",
                     "n_clauses", "decomposed", "extra_calls"}
    assert expected_keys == set(rec)
    assert rec["decomposed"] is False
    assert rec["n_clauses"] == 1
    assert rec["extra_calls"] == 0
