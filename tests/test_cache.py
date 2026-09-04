"""E1.7: identity-keyed cache. Layout <cache_root>/skills/<urn>/<rev>/ and
<cache_root>/index/<sha>/; cache_root from $GUIDEFOLD_CACHE else ~/.cache/guidefold; URN path
segments are filesystem-safe and round-trippable; both trees are immutable, evicted (never
invalidated) LRU by directory mtime against a configured cap."""
import os
import time

import pytest


def test_cache_root_defaults_to_home_cache_guidefold(gf, monkeypatch):
    monkeypatch.delenv("GUIDEFOLD_CACHE", raising=False)
    assert gf.cache_root() == gf.Path.home() / ".cache" / "guidefold"


def test_cache_root_honors_env_override(gf, monkeypatch, tmp_path):
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "custom-cache"))
    assert gf.cache_root() == tmp_path / "custom-cache"


@pytest.mark.parametrize("urn", [
    "urn:skill:meridian:atlas.identity.turnstile:postgres-auth",
    "urn:skill:acme:_root:name-with-%-percent",
    "urn:skill:acme:_root:simple",
])
def test_urn_segment_encoding_round_trips(gf, urn):
    encoded = gf._encode_urn_segment(urn)
    assert gf._decode_urn_segment(encoded) == urn


def test_urn_segment_encoding_is_filesystem_safe(gf):
    urn = "urn:skill:meridian:atlas.identity:rbac-policies"
    encoded = gf._encode_urn_segment(urn)
    assert ":" not in encoded
    assert "/" not in encoded


def test_encoding_escapes_percent_before_colon_so_round_trip_is_unambiguous(gf):
    # a URN containing a literal '%' must not collide with the escape sequence used for ':'.
    urn = "urn:skill:acme:_root:100%-done"
    encoded = gf._encode_urn_segment(urn)
    assert gf._decode_urn_segment(encoded) == urn


def test_skill_cache_dir_shape(gf, monkeypatch, tmp_path):
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path))
    urn = "urn:skill:meridian:atlas.identity:rbac-policies"
    d = gf.skill_cache_dir(urn, "abc123")
    assert d == tmp_path / "skills" / gf._encode_urn_segment(urn) / "abc123"


def test_index_cache_dir_shape(gf, monkeypatch, tmp_path):
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path))
    d = gf.index_cache_dir("deadbeef")
    assert d == tmp_path / "index" / "deadbeef"


def _touch_dir(path, mtime):
    path.mkdir(parents=True, exist_ok=True)
    (path / "marker").write_text("x")
    os.utime(path, (mtime, mtime))


def test_evict_lru_removes_oldest_mtime_dirs_over_cap(gf, tmp_path):
    root = tmp_path / "skills"
    now = time.time()
    # 5 leaf dirs at depth=2 (skills/<urn>/<rev>), ages oldest -> newest
    leaves = []
    for i in range(5):
        d = root / f"urn{i}" / "rev"
        _touch_dir(d, now - (5 - i) * 100)  # urn0 oldest, urn4 newest
        leaves.append(d)

    gf.evict_lru(root, depth=2, cap=3)

    remaining = {d for d in leaves if d.exists()}
    assert remaining == {leaves[2], leaves[3], leaves[4]}
    assert not leaves[0].exists()
    assert not leaves[1].exists()


def test_evict_lru_is_a_noop_when_under_cap(gf, tmp_path):
    root = tmp_path / "skills"
    now = time.time()
    d = root / "urn0" / "rev"
    _touch_dir(d, now)
    gf.evict_lru(root, depth=2, cap=500)
    assert d.exists()


def test_evict_lru_handles_missing_tree_root(gf, tmp_path):
    # tree_root doesn't exist yet (first run, cache empty) -- must not raise.
    gf.evict_lru(tmp_path / "does-not-exist", depth=2, cap=10)


def test_evict_lru_respects_depth_for_index_tree(gf, tmp_path):
    root = tmp_path / "index"
    now = time.time()
    leaves = []
    for i in range(4):
        d = root / f"sha{i}"   # depth=1 for index/<sha>
        _touch_dir(d, now - (4 - i) * 100)
        leaves.append(d)
    gf.evict_lru(root, depth=1, cap=2)
    remaining = {d for d in leaves if d.exists()}
    assert remaining == {leaves[2], leaves[3]}


def test_cache_cap_reads_config_with_fallback_default(gf):
    assert gf._cache_cap({}, "max_skill_revisions", 500) == 500
    assert gf._cache_cap({"cache": {"max_skill_revisions": 42}}, "max_skill_revisions", 500) == 42
