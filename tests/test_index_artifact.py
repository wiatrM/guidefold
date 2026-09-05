"""E1.4: the on-disk index artifact -- write_index_artifact / load_index_artifact /
check_index_artifact, plus the binary plumbing underneath them (varint, mmap, lazy postings and
dense vectors).

Round-trip fidelity is proven by running the SAME Router pipeline over an in-memory Index and
over an artifact-backed one and asserting identical output -- never by hand-computing expected
bytes, which would just re-implement the serializer as a second copy of itself. The dense channel
has no real distilled table yet (E1.4 ships w_dense=0, ADR-0020): its on-disk format and
lazy-load path are exercised here with a hand-built synthetic word->vector table, never invented
skill vectors.
"""
import gc
import hashlib
import inspect
import json
from datetime import datetime

import pytest

from _router_helpers import make_card, make_nodes


def _write_artifact(gf, idx, dest, sha="testsha"):
    """Same file-writing contract as write_index_artifact, for a pre-built Index -- used only to
    exercise the on-disk format (esp. the dense channel) from an Index built with a synthetic
    word_vectors table, since write_index_artifact itself always builds with word_vectors=None
    (no distilled table ships this release)."""
    files = gf._serialize_artifact_files(idx)
    dest.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for name, data in files.items():
        (dest / name).write_bytes(data)
        checksums[name] = hashlib.sha256(data).hexdigest()
    manifest = {
        "format_version": 1, "git_sha": sha, "build_time": "2026-01-01T00:00:00+00:00",
        "builder": "test", "teacher": {"id": None, "hf_commit_sha": None, "license": None},
        "student_dims": gf._dense_dims(idx), "quant_scale": 127, "weights": idx.weights,
        "counts": {"cards": len(idx.cards), "terms": len(idx.idf), "words": len(idx.word_vectors)},
        "checksums": checksums,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


# -------------------------------------------------------------------- varint
@pytest.mark.parametrize("n", [0, 1, 63, 127, 128, 129, 300, 16384, 2**20, 2**32 - 1, 2**32])
def test_varint_round_trips_every_value(gf, n):
    encoded = gf._varint_encode(n)
    value, pos = gf._varint_decode(encoded, 0)
    assert value == n
    assert pos == len(encoded)


def test_varint_encoding_is_never_negative_and_never_signed(gf):
    # single-byte values stay under 0x80; this is unsigned LEB128, no zig-zag encoding anywhere.
    assert gf._varint_encode(0) == b"\x00"
    assert gf._varint_encode(127) == b"\x7f"
    assert gf._varint_encode(128) == b"\x80\x01"


def test_varint_decode_reads_only_its_own_record_from_a_longer_buffer(gf):
    buf = gf._varint_encode(300) + gf._varint_encode(5) + b"trailing garbage"
    v1, pos = gf._varint_decode(buf, 0)
    v2, pos = gf._varint_decode(buf, pos)
    assert (v1, v2) == (300, 5)


# -------------------------------------------------------------------- mmap
def test_open_mmap_returns_none_pair_for_a_zero_byte_file(gf, tmp_path):
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    fh, mm = gf._open_mmap(empty)
    assert (fh, mm) == (None, None)


def test_open_mmap_maps_a_non_empty_file_little_endian_readable(gf, tmp_path):
    p = tmp_path / "data.bin"
    p.write_bytes(b"\x01\x02\x03\x04")
    fh, mm = gf._open_mmap(p)
    try:
        assert bytes(mm[0:4]) == b"\x01\x02\x03\x04"
    finally:
        mm.close()
        fh.close()


# ------------------------------------------------------- round trip: real fixture
def test_loaded_artifact_matches_in_memory_index_on_every_bm25_field(gf, fixture_root, tmp_path):
    cfg = gf.load_map(fixture_root)
    mem_idx = gf.Index.build(fixture_root, cfg)
    dest = tmp_path / "artifact"
    gf.write_index_artifact(fixture_root, cfg, dest, "testsha1")
    loaded = gf.load_index_artifact(dest)

    assert loaded.idf == mem_idx.idf
    # loaded.graph is a _LazyGraph (R4: backed by mmap'd graph.bin/graph.idx, never the whole
    # edge-type mapping materialised at once) -- compare it against the in-memory plain-dict graph
    # by walking the same (edge_type, urn) space mem_idx.graph itself is keyed over, decoding one
    # doc's adjacency at a time exactly as Router would.
    for et in gf.Index.GRAPH_EDGE_TYPES:
        for u in mem_idx.cards:
            assert loaded.graph[et].get(u, []) == mem_idx.graph[et].get(u, []), (et, u)
            assert loaded.graph.get(et, {}).get(u, []) == mem_idx.graph[et].get(u, []), (et, u)
    assert loaded.nodes == mem_idx.nodes
    for field in gf.Index.FIELDS:
        assert loaded.field_norm[field] == mem_idx.field_norm[field]
        for term, tf_by_urn in mem_idx.postings[field].items():
            assert loaded.postings[field].get(term) == tf_by_urn
    assert loaded.postings["name"].get("no-such-term-anywhere") is None


def test_lazy_card_materialization_is_byte_identical_to_the_in_memory_build(gf, fixture_root, tmp_path):
    """R4 acceptance: idx.cards is a _LazyCards backed by cards.jsonl/cards.idx/cards.hdr, never a
    plain dict, once loaded from an artifact -- but every field Router ever reads off a materialised
    card must come back identical to what Index.build() produced directly from the tree (modulo
    requires/refines, which are deliberately dropped here: the graph already carries that
    adjacency and Router never reads those two keys off a card at query time)."""
    cfg = gf.load_map(fixture_root)
    mem_idx = gf.Index.build(fixture_root, cfg)
    dest = tmp_path / "artifact"
    gf.write_index_artifact(fixture_root, cfg, dest, "testsha-lazycards")
    loaded = gf.load_index_artifact(dest)

    assert isinstance(loaded.cards, gf._LazyCards)
    assert set(loaded.cards.keys()) == set(mem_idx.cards.keys())
    for u, c in mem_idx.cards.items():
        got = loaded.cards[u]
        assert got == {
            "urn": u, "node": c["node"], "name": c["name"], "description": c["description"],
            "digest": c.get("digest", ""), "triggers": c.get("triggers", []),
            "negative_triggers": c.get("negative_triggers", []),
            "requires": [], "refines": [],
            "status": c.get("status", "active"), "replaced_by": c.get("replaced_by"),
            "kind": c.get("kind"), "layer": c.get("layer"), "owner": c.get("owner"),
            "_body": "",
        }, u
        # .get() is the other read path (Router never uses bare __getitem__ everywhere) and must
        # agree; a missing urn must come back None rather than raising.
        assert loaded.cards.get(u) == got
    assert loaded.cards.get("urn:skill:does-not-exist:anywhere:x") is None
    assert "urn:skill:does-not-exist:anywhere:x" not in loaded.cards


def test_cards_hdr_header_table_is_in_sorted_urn_order(gf, fixture_root, tmp_path):
    """R4 acceptance: cards.hdr's doc-id order is sorted-URN order, matching cards.idx/postings/
    vectors -- there is exactly one doc-id numbering for the whole artifact, and header_items()
    must walk it in that same order (Router.policy_filter relies on this for deterministic
    drop-order, matching what `sorted(self.index.cards.items())` produced before this PR)."""
    cfg = gf.load_map(fixture_root)
    dest = tmp_path / "artifact"
    gf.write_index_artifact(fixture_root, cfg, dest, "testsha-hdrorder")
    loaded = gf.load_index_artifact(dest)

    urns_from_header = [u for u, _node, _status, _has_neg in loaded.cards.header_items()]
    assert urns_from_header == sorted(urns_from_header)
    assert urns_from_header == sorted(loaded.cards.keys())


def test_loaded_artifact_router_output_matches_in_memory_router_for_real_queries(gf, fixture_root, tmp_path):
    """The acceptance test that matters: Router ranks identically whether its Index came from
    scanning the tree in memory or from the lazily-loaded on-disk artifact."""
    cfg = gf.load_map(fixture_root)
    mem_router = gf.Router(gf.Index.build(fixture_root, cfg))
    dest = tmp_path / "artifact"
    gf.write_index_artifact(fixture_root, cfg, dest, "testsha2")
    art_router = gf.Router(gf.load_index_artifact(dest))

    queries = [
        ("write an ADR for this cross-platform decision", "_root"),
        ("we're paged right now, help me handle this outage", "atlas.identity.turnstile"),
        ("add RBAC to this new admin-only endpoint", "atlas.identity"),
        ("what's the default connection pool size per replica", "_root"),
        ("completely unrelated gibberish xyzzy plugh", "atlas.identity.turnstile"),
    ]
    for query, node in queries:
        assert mem_router.route(query, node) == art_router.route(query, node), query


def test_real_fixture_artifact_ships_an_empty_dense_channel_this_release(gf, fixture_root, tmp_path):
    """E1.4 ships w_dense=0: no distilled word table yet (ADR-0020) -- do not invent vectors."""
    cfg = gf.load_map(fixture_root)
    dest = tmp_path / "artifact"
    manifest = gf.write_index_artifact(fixture_root, cfg, dest, "testsha3")
    assert manifest["student_dims"] == 0
    assert manifest["weights"]["w_dense"] == 0
    assert (dest / "words.bin").stat().st_size == 0
    assert (dest / "vectors.i8").stat().st_size == 0
    loaded = gf.load_index_artifact(dest)
    assert loaded.word_vectors == {}
    assert loaded.skill_vectors == {}
    assert loaded.skill_normsq == {}


def test_mmap_file_handles_survive_gc_between_load_and_use(gf, fixture_root, tmp_path):
    """Regression guard: _open_mmap's file object must be kept alive on the Index instance for
    the life of any mmap slice -- letting it get garbage collected closes the fd out from under
    the mmap (OSError: [Errno 9] Bad file descriptor)."""
    cfg = gf.load_map(fixture_root)
    dest = tmp_path / "artifact"
    gf.write_index_artifact(fixture_root, cfg, dest, "testsha4")
    loaded = gf.load_index_artifact(dest)
    gc.collect()
    router = gf.Router(loaded)
    result = router.route("write an ADR for this cross-platform decision", "_root")
    assert result


def test_manifest_counts_terms_as_distinct_vocabulary_size_not_per_field_sum(gf, fixture_root, tmp_path):
    """counts.terms must match exactly what terms.bin holds (len(idx.idf)) -- summing distinct
    terms per field would double-count any term appearing in more than one field."""
    cfg = gf.load_map(fixture_root)
    mem_idx = gf.Index.build(fixture_root, cfg)
    dest = tmp_path / "artifact"
    manifest = gf.write_index_artifact(fixture_root, cfg, dest, "testsha5")
    assert manifest["counts"]["terms"] == len(mem_idx.idf)
    per_field_sum = sum(len(mem_idx.postings[f]) for f in gf.Index.FIELDS)
    # the fixture has overlapping vocabulary across fields (e.g. "postgres" in both description
    # and body), so the two numbers really do differ on real data (3803 vs 2298 measured).
    assert per_field_sum > manifest["counts"]["terms"]


# ---------------------------------------------------- reproducibility (byte-identical rebuild)
def test_write_index_artifact_is_byte_identical_for_the_same_real_git_sha(gf, fixture_root, tmp_path):
    """E1.4 acceptance: 'artifact reproducible from a SHA'. Uses the real committed sha of this
    repo (fixture_root lives inside the actual gf-b1b-index checkout), so build_time is derived
    from that commit's own timestamp -- deterministic, not the 'worktree' wall-clock fallback --
    and the whole manifest.json comes out byte-identical too, not just the file checksums."""
    cfg = gf.load_map(fixture_root)
    sha = gf._git_head_short(fixture_root)
    assert sha != "worktree", "expected a real commit sha for this repo"

    dest1, dest2 = tmp_path / "a", tmp_path / "b"
    m1 = gf.write_index_artifact(fixture_root, cfg, dest1, sha)
    m2 = gf.write_index_artifact(fixture_root, cfg, dest2, sha)

    assert set(m1["checksums"]) == set(m2["checksums"])
    for name in m1["checksums"]:
        b1 = (dest1 / name).read_bytes()
        b2 = (dest2 / name).read_bytes()
        assert b1 == b2, f"{name} differs between two builds of the same sha"
        assert m1["checksums"][name] == m2["checksums"][name]
    assert (dest1 / "manifest.json").read_bytes() == (dest2 / "manifest.json").read_bytes()


def test_worktree_sha_still_matches_on_every_file_except_possibly_build_time(gf, fixture_root, tmp_path):
    """The one documented exception: the uncommitted 'worktree' sha has no stable commit time to
    anchor build_time to, so manifest.json's build_time is excluded from the reproducibility
    claim for this case -- every other file, and every other manifest key, must still match."""
    cfg = gf.load_map(fixture_root)
    dest1, dest2 = tmp_path / "a", tmp_path / "b"
    m1 = gf.write_index_artifact(fixture_root, cfg, dest1, "worktree")
    m2 = gf.write_index_artifact(fixture_root, cfg, dest2, "worktree")
    for name in m1["checksums"]:
        assert (dest1 / name).read_bytes() == (dest2 / name).read_bytes()
    m1c, m2c = dict(m1), dict(m2)
    m1c.pop("build_time"); m2c.pop("build_time")
    assert m1c == m2c


def test_commit_time_returns_none_for_the_worktree_fallback_sha(gf, fixture_root):
    assert gf._commit_time(fixture_root, "worktree") is None


def test_index_artifact_bytes_are_identical_across_two_fresh_interpreter_builds(run_cli, fixture_copy, tmp_path):
    """The two byte-identical-rebuild tests above call write_index_artifact() twice within the
    SAME Python process, so they'd never catch a bug where a bare `set()`'s iteration order (which
    varies per-process under PYTHONHASHSEED randomisation, not per-call) leaked into the serialized
    bytes -- both calls would share one hash seed and always agree with each other even if that
    seed-dependence existed. This test runs `guidefold index` as two genuinely separate
    subprocesses (each gets its own random PYTHONHASHSEED, confirmed unset in this environment) and
    diffs every file. (One real such site was audited: Index._build_bm25's per-document
    `doc_terms = set()` has hash-order-dependent iteration, but every consumer of the resulting
    idf/doc_freq dict either does key lookup or sorts before serializing, so it doesn't leak here
    -- this test is the empirical backstop for that claim.)"""
    # run_cli's default env (used when no env= override is passed) sets GUIDEFOLD_CACHE to
    # tmp_path / ".cache-guidefold" -- the SAME tmp_path fixture_copy was built from -- so this is
    # where both subprocess builds land (fixture_copy isn't a git repo, so sha == "worktree").
    dest = tmp_path / ".cache-guidefold" / "index" / "worktree"

    r1 = run_cli(["index"], cwd=fixture_copy)
    assert r1.returncode == 0, r1.stderr
    snapshot1 = {p.name: p.read_bytes() for p in dest.iterdir()}

    r2 = run_cli(["index"], cwd=fixture_copy)
    assert r2.returncode == 0, r2.stderr
    snapshot2 = {p.name: p.read_bytes() for p in dest.iterdir()}

    assert set(snapshot1) == set(snapshot2)
    for name in snapshot1:
        if name == "manifest.json":
            m1, m2 = json.loads(snapshot1[name]), json.loads(snapshot2[name])
            m1.pop("build_time"); m2.pop("build_time")  # "worktree" sha: wall-clock, excluded (E1.4)
            assert m1 == m2
            continue
        assert snapshot1[name] == snapshot2[name], f"{name} differs across two fresh-interpreter builds"


def test_commit_time_returns_a_parseable_iso8601_timestamp_for_a_real_sha(gf, fixture_root):
    sha = gf._git_head_short(fixture_root)
    t = gf._commit_time(fixture_root, sha)
    assert t is not None
    # `git show -s --format=%cI` yields a trailing "Z" for UTC. datetime.fromisoformat only
    # learned to accept "Z" in CPython 3.11, and the CLI must work on 3.10 (see ci.yml matrix),
    # so normalise before parsing rather than narrowing what the manifest is allowed to contain.
    datetime.fromisoformat(t.replace("Z", "+00:00"))  # raises ValueError if not valid ISO-8601


# ------------------------------------------------------------------ index --check
def test_check_index_artifact_passes_immediately_after_a_fresh_build(gf, fixture_copy):
    cfg = gf.load_map(fixture_copy)
    sha = gf._git_head_short(fixture_copy)  # fixture_copy is not a git repo -> "worktree"
    dest = fixture_copy / ".cache-index"
    gf.write_index_artifact(fixture_copy, cfg, dest, sha)
    ok, problems = gf.check_index_artifact(fixture_copy, cfg, sha, dest)
    assert ok, problems
    assert problems == []


def test_check_index_artifact_fails_on_a_deliberately_stale_artifact_then_passes_after_rebuild(gf, fixture_copy):
    cfg = gf.load_map(fixture_copy)
    sha = gf._git_head_short(fixture_copy)
    dest = fixture_copy / ".cache-index"
    gf.write_index_artifact(fixture_copy, cfg, dest, sha)

    skill_md = (fixture_copy / "platforms" / "atlas" / "identity" / "turnstile" / ".agents"
                / "skills" / "postgres-auth" / "SKILL.md")
    assert skill_md.is_file()
    skill_md.write_text(skill_md.read_text() + "\n## Edited for the staleness test\nnew content.\n")

    ok, problems = gf.check_index_artifact(fixture_copy, cfg, sha, dest)
    assert not ok
    assert any("stale" in p for p in problems), problems

    gf.write_index_artifact(fixture_copy, cfg, dest, sha)
    ok2, problems2 = gf.check_index_artifact(fixture_copy, cfg, sha, dest)
    assert ok2, problems2


def test_check_index_artifact_reports_no_artifact_yet(gf, fixture_copy):
    cfg = gf.load_map(fixture_copy)
    ok, problems = gf.check_index_artifact(fixture_copy, cfg, "worktree", fixture_copy / "does-not-exist")
    assert not ok
    assert any("run `guidefold index` first" in p for p in problems)


def test_check_index_artifact_detects_a_tampered_file_on_disk(gf, fixture_copy):
    cfg = gf.load_map(fixture_copy)
    sha = gf._git_head_short(fixture_copy)
    dest = fixture_copy / ".cache-index"
    gf.write_index_artifact(fixture_copy, cfg, dest, sha)
    # R4: graph.json no longer exists on disk (superseded by graph.bin/graph.idx, ADR-0021 budget
    # -- see _serialize_artifact_files); graph.bin is the on-disk graph representation now, and it
    # is checksummed in manifest.json exactly like every other file, so tampering it must still
    # be caught the same way.
    (dest / "graph.bin").write_bytes(b"\xff\xff\xff\xff tampered \xff\xff")
    ok, problems = gf.check_index_artifact(fixture_copy, cfg, sha, dest)
    assert not ok
    assert any("tampered or truncated" in p for p in problems)


def test_check_index_artifact_detects_a_tampered_cards_idx(gf, fixture_copy):
    """R4 acceptance: tampering cards.idx (the byte-offset table into cards.jsonl that lazy card
    materialisation relies on) must be caught by `index --check` just like any other artifact
    file -- a corrupted offset table would otherwise silently hand Router garbage or truncated
    JSON the first time a card is materialised, long after `index --check` last said "clean"."""
    cfg = gf.load_map(fixture_copy)
    sha = gf._git_head_short(fixture_copy)
    dest = fixture_copy / ".cache-index"
    gf.write_index_artifact(fixture_copy, cfg, dest, sha)
    (dest / "cards.idx").write_bytes(b"\x00\x00\x00\x00 not a real offset table")
    ok, problems = gf.check_index_artifact(fixture_copy, cfg, sha, dest)
    assert not ok
    assert any("tampered or truncated" in p for p in problems)


def test_index_check_subprocess_fails_stale_then_passes_after_rebuild(run_cli, fixture_copy):
    built = run_cli(["index"], cwd=fixture_copy)
    assert built.returncode == 0, built.stderr

    clean = run_cli(["index", "--check"], cwd=fixture_copy)
    assert clean.returncode == 0, clean.stdout

    skill_md = (fixture_copy / "platforms" / "atlas" / "identity" / "turnstile" / ".agents"
                / "skills" / "postgres-auth" / "SKILL.md")
    skill_md.write_text(skill_md.read_text() + "\n## Edited for the staleness test\nnew content.\n")

    stale = run_cli(["index", "--check"], cwd=fixture_copy)
    assert stale.returncode == 1
    assert "STALE" in stale.stdout

    rebuilt = run_cli(["index"], cwd=fixture_copy)
    assert rebuilt.returncode == 0, rebuilt.stderr

    clean_again = run_cli(["index", "--check"], cwd=fixture_copy)
    assert clean_again.returncode == 0, clean_again.stdout


def test_index_writes_counts_summary_line(run_cli, fixture_copy):
    result = run_cli(["index"], cwd=fixture_copy)
    assert result.returncode == 0, result.stderr
    assert "cards=26" in result.stdout
    assert "words=0" in result.stdout


# ------------------------------------------------------- dense channel (synthetic, ADR-0020)
def test_dense_channel_round_trips_through_words_bin_vectors_i8_and_words_idx(gf, tmp_path):
    word_vectors = {"turnstile": (1, 0), "gate": (0, 1), "release": (-1, 0)}
    cards = {
        "urn:skill:acme:_root:turnstile-guide": make_card(
            "urn:skill:acme:_root:turnstile-guide", "_root",
            description="turnstile gate", digest="turnstile gate", body="turnstile gate",
        ),
        "urn:skill:acme:_root:release-guide": make_card(
            "urn:skill:acme:_root:release-guide", "_root",
            description="release", digest="release", body="release",
        ),
    }
    idx = gf.Index.from_cards(cards, make_nodes("_root"), word_vectors=word_vectors)
    dest = tmp_path / "dense-artifact"
    _write_artifact(gf, idx, dest)

    loaded = gf.load_index_artifact(dest)
    assert len(loaded.word_vectors) == 3
    assert loaded.word_vectors.get("turnstile") == (1, 0)
    assert loaded.word_vectors.get("gate") == (0, 1)
    assert loaded.word_vectors.get("release") == (-1, 0)
    assert loaded.word_vectors.get("no-such-word") is None

    turnstile_urn = "urn:skill:acme:_root:turnstile-guide"
    release_urn = "urn:skill:acme:_root:release-guide"
    assert loaded.skill_vectors.get(turnstile_urn) == idx.skill_vectors[turnstile_urn]
    assert loaded.skill_vectors.get(release_urn) == idx.skill_vectors[release_urn]
    assert loaded.skill_normsq.get(turnstile_urn) == idx.skill_normsq[turnstile_urn]
    assert loaded.skill_normsq.get(release_urn) == idx.skill_normsq[release_urn]

    # Router must rank identically whether the dense channel comes from memory or from disk.
    mem_router = gf.Router(idx)
    art_router = gf.Router(loaded)
    assert (mem_router.route("turnstile gate incident", "_root")
            == art_router.route("turnstile gate incident", "_root"))


def test_word_vectors_values_peek_never_materializes_the_whole_table(gf, tmp_path):
    """Router's _dense_scores learns `dims` via len(next(iter(idx.word_vectors.values()))) --
    _LazyVectors.values() must be a generator so that peek touches exactly one row, never the
    whole on-disk table."""
    word_vectors = {"a": (1, 2, 3), "b": (4, 5, 6)}
    cards = {"u1": make_card("u1", "_root", description="a b", body="a b")}
    idx = gf.Index.from_cards(cards, make_nodes("_root"), word_vectors=word_vectors)
    dest = tmp_path / "peek-artifact"
    _write_artifact(gf, idx, dest)
    loaded = gf.load_index_artifact(dest)

    values_iter = loaded.word_vectors.values()
    assert inspect.isgenerator(values_iter)
    first = next(values_iter)
    assert len(first) == 3


def test_lazy_vectors_len_reflects_row_count_and_zero_when_empty(gf, fixture_root, tmp_path):
    cfg = gf.load_map(fixture_root)
    dest = tmp_path / "artifact"
    gf.write_index_artifact(fixture_root, cfg, dest, "testsha6")
    loaded = gf.load_index_artifact(dest)
    assert len(loaded.word_vectors) == 0   # {} this release, len() of a plain dict


def test_overflowing_int8_component_raises_a_helpful_adr_0020_error(gf):
    cards = {"u1": make_card("u1", "_root", description="hi", body="hi")}
    idx = gf.Index.from_cards(cards, make_nodes("_root"), word_vectors={"hi": (300, 0)})
    with pytest.raises(ValueError, match="ADR-0020"):
        gf._serialize_artifact_files(idx)
