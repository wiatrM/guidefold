"""tools/expand/doc2query.py — F3 document expansion pseudo-query generator. Pure-logic tests
(input-text assembly, model-sha hashing, cache round-trip, the torch-free module boundary) always
run. The one test that actually invokes the doc2query/msmarco-t5-base-v1 model -- the task's
explicit determinism requirement, "generator output is deterministic for a fixed seed, two runs,
same file" -- is gated by pytest.importorskip("torch")/("transformers") and by the model directory
existing on this machine, forces device="cpu" for portability, and is expected to be run for real
via the GPU venv (/home/mike/.cache/guidefold/gpu-venv/bin/python -m pytest tests/test_doc2query.py)
since the repo's default venv has neither torch nor transformers installed.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPAND_DIR = ROOT / "tools" / "expand"

spec = importlib.util.spec_from_file_location("gf_doc2query", EXPAND_DIR / "doc2query.py")
doc2query = importlib.util.module_from_spec(spec)
sys.modules["gf_doc2query"] = doc2query
spec.loader.exec_module(doc2query)


# ------------------------------------------------------------------ torch-free module boundary
def test_doc2query_module_imports_cleanly_with_torch_blocked(monkeypatch):
    """Module scope (argparse setup, cache helpers, build_input_text) must never import torch --
    only the functions that actually run the model (`_seed_everything`, `load_model`,
    `generate_batch`, `generate_pool`) do, and only when called."""

    class _TorchIsForbidden:
        def find_spec(self, name, path=None, target=None):
            if name == "torch" or name.startswith("torch."):
                raise ImportError(f"torch must never be imported at doc2query.py module scope: {name}")
            return None

    sys.meta_path.insert(0, _TorchIsForbidden())
    try:
        spec2 = importlib.util.spec_from_file_location("gf_doc2query_reload", EXPAND_DIR / "doc2query.py")
        mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mod)
    finally:
        sys.meta_path.pop(0)


# ------------------------------------------------------------------ build_input_text
def test_build_input_text_joins_nonempty_parts_with_period_space():
    assert doc2query.build_input_text("My Skill", "does a thing", "full body text") == \
        "My Skill. does a thing. full body text"


def test_build_input_text_drops_empty_and_whitespace_only_parts():
    assert doc2query.build_input_text("My Skill", "", "   ") == "My Skill"
    assert doc2query.build_input_text("", "", "") == ""
    assert doc2query.build_input_text(None, None, None) == ""


def test_build_input_text_strips_each_part():
    assert doc2query.build_input_text("  name  ", " desc ", "body") == "name. desc. body"


# ------------------------------------------------------------------ model identity hashing
def test_sha256_file_and_model_sha(tmp_path):
    f = tmp_path / "weights.bin"
    content = b"pretend-these-are-model-weights" * 1000
    f.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert doc2query._sha256_file(f) == expected

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "pytorch_model.bin").write_bytes(content)
    assert doc2query.model_sha(model_dir) == expected[:12]
    assert len(doc2query.model_sha(model_dir)) == 12


def test_cache_path_layout(tmp_path):
    p = doc2query.cache_path(tmp_path, "abc123def456", "some-skill-id")
    assert p == tmp_path / "abc123def456" / "some-skill-id.json"


# ------------------------------------------------------------------ cache round trip
def test_write_then_load_cache_exact_match(tmp_path):
    p = tmp_path / "sha" / "skill-a.json"
    doc2query._write_cache(p, "skill-a", ["q1", "q2", "q3"], n=3, seed=42, top_p=0.95)
    got = doc2query._load_cache(p, n=3, seed=42, top_p=0.95)
    assert got == ["q1", "q2", "q3"]


def test_load_cache_missing_file_returns_none(tmp_path):
    assert doc2query._load_cache(tmp_path / "nope.json", n=5, seed=42, top_p=0.95) is None


def test_load_cache_returns_none_on_seed_mismatch(tmp_path):
    p = tmp_path / "skill-a.json"
    doc2query._write_cache(p, "skill-a", ["q1", "q2"], n=2, seed=42, top_p=0.95)
    assert doc2query._load_cache(p, n=2, seed=43, top_p=0.95) is None


def test_load_cache_returns_none_on_top_p_mismatch(tmp_path):
    p = tmp_path / "skill-a.json"
    doc2query._write_cache(p, "skill-a", ["q1", "q2"], n=2, seed=42, top_p=0.95)
    assert doc2query._load_cache(p, n=2, seed=42, top_p=0.90) is None


def test_load_cache_returns_none_when_cached_n_insufficient(tmp_path):
    p = tmp_path / "skill-a.json"
    doc2query._write_cache(p, "skill-a", ["q1", "q2"], n=2, seed=42, top_p=0.95)
    assert doc2query._load_cache(p, n=5, seed=42, top_p=0.95) is None  # asking for more than cached


def test_load_cache_truncates_when_cached_n_is_larger(tmp_path):
    p = tmp_path / "skill-a.json"
    doc2query._write_cache(p, "skill-a", ["q1", "q2", "q3", "q4", "q5"], n=5, seed=42, top_p=0.95)
    assert doc2query._load_cache(p, n=2, seed=42, top_p=0.95) == ["q1", "q2"]


def test_load_cache_returns_none_on_corrupt_json(tmp_path):
    p = tmp_path / "skill-a.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not valid json", encoding="utf-8")
    assert doc2query._load_cache(p, n=1, seed=42, top_p=0.95) is None


# ------------------------------------------------------------------ generate_pool cache bookkeeping
def test_generate_pool_uses_cache_and_reports_n_cached(tmp_path):
    """Cache-bookkeeping check with zero skills left to actually generate -- every skill is
    pre-seeded into the cache, so generate_pool must never load the model (no `load_model` call,
    no wall-clock cost). `generate_pool` still does an unconditional `import torch` (it uses
    `torch.cuda.is_available()` for device auto-detection even when there is nothing to generate),
    so this test needs torch importable -- pass device='cpu' explicitly and skip if torch itself
    is absent, same as the real determinism test below."""
    pytest.importorskip("torch")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "pytorch_model.bin").write_bytes(b"weights")
    msha = doc2query.model_sha(model_dir)
    cache_root = tmp_path / "cache"

    skills = [{"id": "s1", "name": "Alpha", "description": "d1", "body": "b1"},
              {"id": "s2", "name": "Beta", "description": "d2", "body": "b2"}]
    for s in skills:
        doc2query._write_cache(doc2query.cache_path(cache_root, msha, s["id"]), s["id"],
                                [f"{s['id']}-q1", f"{s['id']}-q2"], n=2, seed=42, top_p=0.95)

    out, report = doc2query.generate_pool(skills, n=2, model_dir=model_dir, cache_root=cache_root,
                                           seed=42, top_p=0.95, device="cpu")
    assert out == {"s1": ["s1-q1", "s1-q2"], "s2": ["s2-q1", "s2-q2"]}
    assert report["n_skills"] == 2
    assert report["n_cached"] == 2
    assert report["n_generated"] == 0
    assert report["gpu_wall_clock_s"] == 0.0
    assert report["model_sha"] == msha


# ------------------------------------------------------------------ the real model: determinism
DEFAULT_MODEL_DIR = Path("/home/mike/.cache/guidefold/models/doc2query__msmarco-t5-base-v1")


def test_generator_output_is_deterministic_for_a_fixed_seed_two_runs_same_file(tmp_path):
    """Task's explicit requirement: run generate_pool twice, fresh cache each time, same seed --
    byte-identical output file both times. Forces device='cpu' for portability (this test is meant
    to be run for real via the GPU venv, but must not require a GPU); a tiny synthetic pool and
    n=2 keep real CPU generation fast enough for a unit test."""
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    if not DEFAULT_MODEL_DIR.exists():
        pytest.skip(f"doc2query model not present at {DEFAULT_MODEL_DIR} on this machine")

    skills = [
        {"id": "s1", "name": "Kubernetes Debugging", "description": "diagnose failing pods",
         "body": "kubectl logs, kubectl describe, and events for root-causing CrashLoopBackOff."},
        {"id": "s2", "name": "Invoice Reconciliation", "description": "match payments to invoices",
         "body": "reconcile bank statement lines against outstanding invoices and flag mismatches."},
        {"id": "s3", "name": "Recipe Substitution", "description": "swap ingredients in a recipe",
         "body": "suggest substitutes for missing ingredients while preserving taste and texture."},
    ]

    def _run(cache_root):
        out, report = doc2query.generate_pool(
            skills, n=2, model_dir=DEFAULT_MODEL_DIR, cache_root=cache_root,
            batch_size=8, seed=42, top_p=0.95, device="cpu",
        )
        return out

    out_a = _run(tmp_path / "cache-run-a")
    out_b = _run(tmp_path / "cache-run-b")

    assert set(out_a) == {"s1", "s2", "s3"}
    assert out_a == out_b
    for sid in out_a:
        assert len(out_a[sid]) == 2
        assert all(isinstance(q, str) and q.strip() for q in out_a[sid])
