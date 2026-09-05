"""BM25 fixed-point contract, against the reference formula (peer review, 2026-09-05).

The CLI ranks in integers so results are bit-reproducible (ADR-0020). That only works if every
term of the BM25 formula lives on the SAME fixed-point scale. Before this test existed, the
weighted TF was unscaled while k1 was scaled by 2**20, which made the score near-linear in TF
(no saturation) and truncated low-TF terms to 0. Measured on the unfixed code, equal-length
documents with the term repeated 1 / 10 / 100 times scored 1 / 24 / 249. BM25 says 1 : 1.96 : 2.17.
"""
import importlib.util
import math
import pathlib
import sys
from importlib.machinery import SourceFileLoader

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from _router_helpers import make_card  # noqa: E402


@pytest.fixture(scope="module")
def gf():
    spec = importlib.util.spec_from_loader("gf_bm25", SourceFileLoader("gf_bm25", str(ROOT / "skills/guidefold/scripts/guidefold")))
    m = importlib.util.module_from_spec(spec); sys.modules["gf_bm25"] = m; spec.loader.exec_module(m)
    return m


def _corpus(gf):
    def doc(n):  # equal length: the term n times, filler for the rest
        return " ".join(["kafka"] * n + [f"filler{i}" for i in range(100 - n)])
    cards = {f"u:d{n}": make_card(f"u:d{n}", "_root", name=f"d{n}", description="", digest="",
                                  triggers=[], body=doc(n)) for n in (1, 10, 100)}
    for j in range(6):
        cards[f"u:o{j}"] = make_card(f"u:o{j}", "_root", name=f"o{j}", description="", digest="",
                                     triggers=[], body=" ".join(f"x{j}_{i}" for i in range(100)))
    idx = gf.Index.from_cards(cards, {"_root": {"paths": ["**"], "owner": "p"}}, word_vectors=None)
    return idx, cards


def _reference(idx, urn, tf, w):
    """Float BM25 term score in the CLI's form idf * wtf / (k1 + wtf), wtf = w*tf/norm.

    `norm` is read back from the index rather than assumed: a first draft of this test assumed
    norm == 1 for "equal-length" documents and was wrong, because its filler tokens `x0_5`
    tokenised into two tokens each. The point of the test is the fixed-point arithmetic, not the
    corpus shape, so the reference uses the same length normaliser the CLI computed."""
    n = len(idx.cards); df = 3
    idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
    norm = idx.field_norm["body"][urn] / idx.IDF_SCALE
    wtf = w * tf / norm
    return idf * wtf / (idx.K1 + wtf)


def test_bm25_saturates_like_the_reference_formula(gf):
    idx, cards = _corpus(gf)
    s = gf.Router(idx)._bm25_scores("kafka", set(cards))
    w = idx.weights["field.body"]
    got = [s[f"u:d{n}"] for n in (1, 10, 100)]
    ref = [_reference(idx, f"u:d{n}", n, w) for n in (1, 10, 100)]
    for n, g, r in zip((1, 10, 100), got, ref):
        assert g > 0, f"tf={n} truncated to zero — fixed-point scale mismatch"
    # ratios are scale-free: the integer scores must reproduce the reference shape
    assert got[1] / got[0] == pytest.approx(ref[1] / ref[0], rel=0.01)
    assert got[2] / got[0] == pytest.approx(ref[2] / ref[0], rel=0.01)
    # and that shape is saturating, not linear
    assert got[2] / got[0] < 3.0, "no TF saturation: score is near-linear in tf"


def test_bm25_absolute_value_matches_reference_on_the_fixed_point_scale(gf):
    idx, cards = _corpus(gf)
    s = gf.Router(idx)._bm25_scores("kafka", set(cards))
    w = idx.weights["field.body"]
    assert s["u:d10"] / idx.IDF_SCALE == pytest.approx(_reference(idx, "u:d10", 10, w), rel=0.01)
