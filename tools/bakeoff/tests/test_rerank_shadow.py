"""Tests for rerank_shadow.py -- the E1.6 offline reranker over shadow telemetry.

A `FakeReranker` stands in for the real 0.6B cross-encoder (`arms.Reranker`) everywhere here: these
tests are about the jsonl bookkeeping (resumability, hash-only skip, verdict schema), not about
whether the model itself is accurate -- that question belongs to `report_b6.py` and `test_arms.py`,
which do load the real model. `score_pending`'s `reranker=` parameter exists for exactly this
substitution (dependency injection for testability).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rerank_shadow  # noqa: E402
from corpus import SkillRecord  # noqa: E402

RECORDS = [
    SkillRecord(urn=f"urn:skill:meridian:_root:skill-{i}", node="_root",
                name=f"skill-{i}", description=f"skill {i} description", digest=f"d{i}")
    for i in range(4)
]


class FakeReranker:
    """Records every call it receives and never touches torch/transformers."""

    def __init__(self, score_fn=None):
        self.calls = []
        self._score_fn = score_fn

    def score_batch(self, query, records, desc_max=500, body_max=2000, max_length=4096):
        self.calls.append((query, [r.urn for r in records]))
        if self._score_fn is not None:
            return self._score_fn(query, records)
        # Default: reverse the incoming order (last candidate scores highest) so a rank-1 change
        # is easy to assert on.
        return list(range(len(records)))


def _write_request(path: Path, request_id: str, top20_urns: list, query: str = None,
                    query_sha256: str = "deadbeef"):
    record = {
        "type": "shadow_request",
        "request_id": request_id,
        "ts": "2026-09-04T00:00:00Z",
        "cli_version": "0.1.0",
        "index_sha": "abc1234",
        "node": "_root",
        "query_sha256": query_sha256,
        "top20": [{"urn": u, "score": 100 - i} for i, u in enumerate(top20_urns)],
    }
    if query is not None:
        record["query"] = query
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def test_resumable_skips_already_scored_request_ids(tmp_path):
    """Prove the E1.6 non-negotiable: a request that already has a shadow_verdict is never
    re-scored, even across separate invocations of score_pending / separate FakeReranker instances."""
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()
    path = telemetry_dir / "shadow-2026-09-04.jsonl"
    urns = [r.urn for r in RECORDS]
    _write_request(path, "req-1", urns, query="add rbac to this endpoint")

    fake1 = FakeReranker()
    summary1 = rerank_shadow.score_pending(telemetry_dir, RECORDS, reranker=fake1)
    assert summary1["scored"] == 1
    assert summary1["pending"] == 1
    assert len(fake1.calls) == 1

    verdicts = [json.loads(l) for l in path.read_text().splitlines() if '"shadow_verdict"' in l]
    assert len(verdicts) == 1
    assert verdicts[0]["request_id"] == "req-1"

    # Second run: same file, a FRESH FakeReranker. If resumability were broken, this reranker
    # would be invoked again for req-1.
    fake2 = FakeReranker()
    summary2 = rerank_shadow.score_pending(telemetry_dir, RECORDS, reranker=fake2)
    assert summary2["scored"] == 0
    assert summary2["pending"] == 0
    assert summary2["already_scored"] == 1
    assert fake2.calls == []  # never called -- the whole point of resumability

    # Exactly one verdict on disk still -- no duplicate was appended.
    verdicts_after = [json.loads(l) for l in path.read_text().splitlines() if '"shadow_verdict"' in l]
    assert len(verdicts_after) == 1


def test_a_new_request_added_later_is_scored_without_rescoring_the_old_one(tmp_path):
    """Resumability must add exactly the new work, not redo the old work alongside it."""
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()
    path = telemetry_dir / "shadow-2026-09-04.jsonl"
    urns = [r.urn for r in RECORDS]
    _write_request(path, "req-1", urns, query="add rbac to this endpoint")

    rerank_shadow.score_pending(telemetry_dir, RECORDS, reranker=FakeReranker())

    _write_request(path, "req-2", urns, query="rotate the signing key")
    fake = FakeReranker()
    summary = rerank_shadow.score_pending(telemetry_dir, RECORDS, reranker=fake)
    assert summary["scored"] == 1
    assert summary["already_scored"] == 1
    assert [c[0] for c in fake.calls] == ["rotate the signing key"]

    verdicts = {json.loads(l)["request_id"] for l in path.read_text().splitlines() if '"shadow_verdict"' in l}
    assert verdicts == {"req-1", "req-2"}


def test_hash_only_request_is_skipped_never_guessed(tmp_path):
    """A shadow_request written without --telemetry-raw has no `query` field. Its hash cannot be
    reversed, so it must be counted and skipped -- the reranker must never even be called."""
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()
    path = telemetry_dir / "shadow-2026-09-04.jsonl"
    _write_request(path, "req-hash-only", [r.urn for r in RECORDS], query=None)

    fake = FakeReranker()
    summary = rerank_shadow.score_pending(telemetry_dir, RECORDS, reranker=fake)
    assert summary["scored"] == 0
    assert summary["skipped_no_raw_query"] == 1
    assert fake.calls == []

    verdicts = [l for l in path.read_text().splitlines() if '"shadow_verdict"' in l]
    assert verdicts == []


def test_verdict_records_rank1_change_and_spearman(tmp_path):
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()
    path = telemetry_dir / "shadow-2026-09-04.jsonl"
    urns = [r.urn for r in RECORDS]  # baseline order: skill-0, skill-1, skill-2, skill-3
    _write_request(path, "req-1", urns, query="a query")

    # FakeReranker reverses order -> new rank1 is skill-3, a change from baseline rank1 skill-0.
    rerank_shadow.score_pending(telemetry_dir, RECORDS, reranker=FakeReranker())

    verdict = next(json.loads(l) for l in path.read_text().splitlines() if '"shadow_verdict"' in l)
    assert verdict["rank1_baseline"] == urns[0]
    assert verdict["rank1_reranked"] == urns[-1]
    assert verdict["rank1_changed"] is True
    # A total reversal of 4 items has a known Spearman rho of -1.0.
    assert verdict["spearman_vs_baseline"] == -1.0
    assert verdict["n_candidates"] == 4
    assert verdict["reranker_model"] == "pipizhao/SkillRouter-Reranker-0.6B"


def test_identical_order_gives_no_rank1_change_and_spearman_one(tmp_path):
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()
    path = telemetry_dir / "shadow-2026-09-04.jsonl"
    urns = [r.urn for r in RECORDS]
    _write_request(path, "req-1", urns, query="a query")

    identity_fn = lambda query, records: list(range(len(records), 0, -1))  # descending -> same order
    rerank_shadow.score_pending(telemetry_dir, RECORDS, reranker=FakeReranker(score_fn=identity_fn))

    verdict = next(json.loads(l) for l in path.read_text().splitlines() if '"shadow_verdict"' in l)
    assert verdict["rank1_changed"] is False
    assert verdict["spearman_vs_baseline"] == 1.0


def test_already_scored_request_ids_scans_every_file_in_the_directory(tmp_path):
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()
    day1 = telemetry_dir / "shadow-2026-09-01.jsonl"
    day2 = telemetry_dir / "shadow-2026-09-02.jsonl"
    _write_request(day1, "req-day1", [r.urn for r in RECORDS], query="q1")
    _write_request(day2, "req-day2", [r.urn for r in RECORDS], query="q2")

    rerank_shadow.score_pending(telemetry_dir, RECORDS, reranker=FakeReranker())

    already = rerank_shadow.already_scored_request_ids(telemetry_dir)
    assert already == {"req-day1", "req-day2"}
