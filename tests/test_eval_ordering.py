"""Guards the distinction between the Router's two orderings.

`Router.select` emits cards general -> specific (root-most first) because that is the order an
agent should *read* them in (E1.5). That is a presentation decision taken after ranking has
already chosen membership. Scoring a ranking metric against it asks "is the root-most card the
most relevant one?", which is false by construction, and it understated hit@1 by ~64 points
before this was caught.

These tests exist so that conflation cannot silently return.
"""
import importlib.util
import pathlib
import sys
from importlib.machinery import SourceFileLoader

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "monorepo"


@pytest.fixture(scope="module")
def router_and_index():
    spec = importlib.util.spec_from_loader(
        "gf_ord", SourceFileLoader("gf_ord", str(ROOT / "skills" / "guidefold" / "scripts" / "guidefold")))
    gf = importlib.util.module_from_spec(spec)
    sys.modules["gf_ord"] = gf
    spec.loader.exec_module(gf)
    cfg = gf.load_map(FIXTURE)
    idx = gf.Index.build(FIXTURE, cfg)
    return gf, idx, gf.Router(idx)


QUERY = "handle an outage in turnstile auth"
NODE = "atlas.identity"


def test_select_emits_general_to_specific(router_and_index):
    """E1.5's injection contract: root-most node first, monotonically non-decreasing depth."""
    gf, idx, router = router_and_index
    cards = router.route(QUERY, NODE, k=4)
    depths = [len(c["node"].split(".")) if c["node"] != "_root" else 0 for c in cards]
    assert depths == sorted(depths), f"injection order is not general->specific: {depths}"


def test_score_order_is_by_relevance_not_depth(router_and_index):
    """The ranking itself must be sorted by score descending, tie-broken on urn."""
    gf, idx, router = router_and_index
    scored = router.score(router.candidates(QUERY, NODE), QUERY, NODE)
    keys = [(-c["score"], c["urn"]) for c in scored]
    assert keys == sorted(keys), "score order is not (-score, urn)"


def test_the_two_orderings_actually_differ(router_and_index):
    """The guard that matters. If these ever coincide for every query, someone has quietly made
    `select` return score order (breaking E1.5's read-order contract) or made `score` sort by
    depth (breaking E1.1's "scope is never the first sort key"). Either way, a metric computed
    on the wrong one would stop being detectably wrong."""
    gf, idx, router = router_and_index
    differed = 0
    probes = [
        ("handle an outage in turnstile auth", "atlas.identity"),
        ("add RBAC to the graph service", "atlas.identity"),
        ("write an ADR for the new session store", "atlas.identity"),
        ("tune a slow spark job reading a wide dataset", "forge.pipelines"),
    ]
    for q, node in probes:
        scored = router.score(router.candidates(q, node), q, node)
        by_score = [c["urn"] for c in scored][:4]
        by_inject = [c["urn"] for c in router.select(scored, k=4, admissible=set(router.policy_filter(node, q)[0]))]
        if by_score != by_inject:
            differed += 1
    assert differed, "score order and injection order coincided on every probe — one of them is wrong"


def test_runner_reports_retrieval_and_injection_separately(router_and_index):
    """`run_cases` must return two result sets, and they must not be the same object or content."""
    spec = importlib.util.spec_from_file_location("rg", ROOT / "tools" / "eval" / "run_golden.py")
    rg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rg)
    gf, idx, router = router_and_index
    cases = [{"query": QUERY, "node": NODE, "cwd": "platforms/atlas/identity",
              "category": "simple", "relevant": [], "distractors": []}]
    retrieval, injection = rg.run_cases(router, cases)
    assert len(retrieval) == len(injection) == 1
    assert retrieval[0][0] != injection[0][0], (
        "runner produced identical retrieval and injection lists — the orderings were conflated")


def test_injection_respects_the_card_cap(router_and_index):
    gf, idx, router = router_and_index
    scored = router.score(router.candidates(QUERY, NODE), QUERY, NODE)
    assert len(router.select(scored, k=4, admissible=set(router.policy_filter(NODE, QUERY)[0]))) <= 4
