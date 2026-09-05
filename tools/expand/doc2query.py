#!/usr/bin/env python3
"""tools/expand/doc2query.py — F3 document expansion (DENSE-PROGRAM.md v2.1 SS4): generate `n`
pseudo-queries per skill with doc2query/msmarco-t5-base-v1 (Nogueira & Lin, 2019, "docTTTTTquery"
family), OFFLINE, so the BM25F index carries extra retrieval surface per skill without the hook
ever loading a model at query time -- "neural at index time, lexical at query time". Output: a
JSONL of {"skill_id": ..., "queries": [...]} for every skill in the input pool.

This script is deliberately independent of tools/eval/dev_sparse.py's card scheme: it consumes
raw skill records (id/name/description/body — the SKILLRET train schema, see
tools/eval/corpora.py::load_skillret_dev()), never a Guidefold card. tools/eval/dev_expand.py
(which DOES build cards) merges this file's JSONL output into cards by skill_id; it never
regenerates queries itself and never imports torch.

Model / decoding, pinned so two runs of `generate` produce the SAME file:
  * doc2query/msmarco-t5-base-v1, T5-base, Apache-2.0, loaded from
    /home/mike/.cache/guidefold/models/doc2query__msmarco-t5-base-v1
    (run with HF_HUB_OFFLINE=1 -- this script never fetches over the network).
  * Input text: "<name>. <description>. <body>" (see `build_input_text`), truncated by the
    TOKENIZER at encode time to max_length=320 with truncation=True -- the model card's own
    example recipe ("model-card truncation" per the task brief), not an invented character cutoff.
  * Decoding: nucleus sampling, do_sample=True, top_p=0.95, max_length=64, num_return_sequences=n
    -- again the model card's own recommended recipe (see its README's `model.generate(...,
    do_sample=True, top_p=0.95, num_return_sequences=5)`), chosen over beam search because beam
    search's top-n hypotheses for this model are near-duplicates of each other (low lexical
    diversity), which is exactly what document expansion needs to avoid -- sampling is standard
    doc2query/docT5query practice for this reason.
  * Determinism: every torch/random/numpy RNG is reseeded to `seed + batch_index` immediately
    before each batch's `model.generate()` call (see `_seed_everything`), not once globally at
    startup. That makes a batch's output depend only on its own fixed index, `n`, `seed`,
    `top_p`, and the input texts in it -- never on how many batches ran before it or which skills
    were already cache-hits. Combined with a stable sort of the input skill list by `id` (fixed,
    reproducible batch membership) this is sufficient for two full fresh-cache runs on the same
    machine/GPU/driver/library stack to produce byte-identical output; it is NOT a claim of
    bit-exact reproducibility across different hardware or library versions (documented, not
    tested here).
  * fp16 on CUDA; falls back to fp32 automatically on CPU (fp16 matmul is slow/partially
    unsupported there) -- the CPU path only exists so tests can exercise real generation quickly
    without a GPU.

Cache: .bakeoff-cache/doc2query/<model-sha>/<skill-id>.json, where model-sha is the first 12 hex
characters of sha256(pytorch_model.bin) -- the actual weight identity, computed once per
invocation (~1-2s for 944 MB), never per skill. A cache file also records the n/seed/top_p it was
generated with; a request for <= that many queries at the same seed/top_p reuses the cached file's
own first n entries (order-stable, since queries are generated once, in order, and never
reshuffled), while a request for MORE queries, or a different seed/top_p, is a cache miss and
regenerates that skill instead of silently reusing/truncating incompatible samples.

Subcommands:
  generate   run the model (or read cache) over a skill pool, write the output JSONL, print
             GPU wall-clock (generation time only, cache hits excluded) and N samples to stderr.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPAND_DIR = Path(__file__).resolve().parent
EVAL_DIR = REPO_ROOT / "tools" / "eval"

DEFAULT_MODEL_DIR = Path("/home/mike/.cache/guidefold/models/doc2query__msmarco-t5-base-v1")
DEFAULT_CACHE_ROOT = EXPAND_DIR / ".bakeoff-cache" / "doc2query"

MAX_INPUT_TOKENS = 320   # model card's own example: tokenizer.encode(..., max_length=320, truncation=True)
MAX_OUTPUT_TOKENS = 64   # model card's own example: model.generate(..., max_length=64, ...)
DEFAULT_TOP_P = 0.95     # model card's own example
DEFAULT_SEED = 42
DEFAULT_BATCH_SIZE = 16

sys.path.insert(0, str(EVAL_DIR))
import corpora as gf_corpora  # noqa: E402  tools/eval/corpora.py — ONLY pinned-corpus loader


# ============================================================================ pure logic (no torch)
def build_input_text(name: str, description: str, body: str) -> str:
    """name + description + body, concatenated -- the model never sees anything but this string.
    Truncation to MAX_INPUT_TOKENS happens at the TOKENIZER (see `generate_batch`), matching the
    model card's own recipe, not a hand-rolled character cutoff here."""
    parts = [p.strip() for p in (name or "", description or "", body or "") if p and p.strip()]
    return ". ".join(parts)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_sha(model_dir: Path) -> str:
    """First 12 hex chars of sha256(pytorch_model.bin) -- the actual weight identity, not a
    version string someone could forget to bump."""
    return _sha256_file(Path(model_dir) / "pytorch_model.bin")[:12]


def cache_path(cache_root: Path, msha: str, skill_id: str) -> Path:
    return Path(cache_root) / msha / f"{skill_id}.json"


def _load_cache(path: Path, n: int, seed: int, top_p: float) -> Optional[list]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("seed") != seed or data.get("top_p") != top_p:
        return None
    queries = data.get("queries") or []
    if len(queries) < n:
        return None
    return queries[:n]


def _write_cache(path: Path, skill_id: str, queries: list, n: int, seed: int, top_p: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"skill_id": skill_id, "queries": queries, "n": n, "seed": seed, "top_p": top_p},
                   ensure_ascii=False),
        encoding="utf-8",
    )


# ============================================================================ model (torch-only, lazy)
def _seed_everything(seed: int) -> None:
    import random
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed % (2 ** 32))
    except ImportError:
        pass
    import torch
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def load_model(model_dir: Path, device: str):
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir), torch_dtype=dtype)
    model.to(device)
    model.eval()
    return tokenizer, model


def generate_batch(tokenizer, model, texts: list, n: int, device: str, rng_seed: int,
                    top_p: float = DEFAULT_TOP_P) -> list:
    """One model.generate() call for `texts` (a batch of documents), num_return_sequences=n.
    Returns one list of n query strings per input text, in generation order."""
    import torch

    _seed_everything(rng_seed)
    enc = tokenizer(texts, max_length=MAX_INPUT_TOKENS, truncation=True, padding=True,
                     return_tensors="pt")
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        out = model.generate(
            input_ids=enc["input_ids"], attention_mask=enc["attention_mask"],
            max_length=MAX_OUTPUT_TOKENS, do_sample=True, top_p=top_p,
            num_return_sequences=n,
        )
    decoded = tokenizer.batch_decode(out, skip_special_tokens=True)
    return [decoded[i * n:(i + 1) * n] for i in range(len(texts))]


def generate_pool(skills: list, n: int, model_dir: Path = DEFAULT_MODEL_DIR,
                   cache_root: Path = DEFAULT_CACHE_ROOT, batch_size: int = DEFAULT_BATCH_SIZE,
                   seed: int = DEFAULT_SEED, top_p: float = DEFAULT_TOP_P,
                   device: Optional[str] = None, limit: Optional[int] = None) -> tuple:
    """{skill_id: [queries]}, report. report carries gpu_wall_clock_s (generation time only, cache
    hits excluded)/n_generated/n_cached/device/model_sha/n/seed/top_p/batch_size."""
    import torch

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    msha = model_sha(model_dir)

    ordered = sorted(skills, key=lambda s: s["id"])  # stable, reproducible batch grouping
    if limit is not None:
        ordered = ordered[:limit]

    out = {}
    todo = []  # (skill_id, input_text)
    n_cached = 0
    for s in ordered:
        sid = s["id"]
        cpath = cache_path(cache_root, msha, sid)
        cached = _load_cache(cpath, n, seed, top_p)
        if cached is not None:
            out[sid] = cached
            n_cached += 1
        else:
            text = build_input_text(str(s.get("name", "")), str(s.get("description", "")),
                                     str(s.get("body", "")))
            todo.append((sid, text))

    gpu_wall_clock = 0.0
    if todo:
        tokenizer, model = load_model(model_dir, device)
        for batch_idx, start in enumerate(range(0, len(todo), batch_size)):
            batch = todo[start:start + batch_size]
            texts = [t for _, t in batch]
            t0 = time.time()
            queries_batch = generate_batch(tokenizer, model, texts, n, device,
                                            rng_seed=seed + batch_idx, top_p=top_p)
            gpu_wall_clock += time.time() - t0
            for (sid, _), queries in zip(batch, queries_batch):
                out[sid] = queries
                _write_cache(cache_path(cache_root, msha, sid), sid, queries, n, seed, top_p)

    report = {
        "n_skills": len(ordered), "n_generated": len(todo), "n_cached": n_cached,
        "device": device, "model_sha": msha, "gpu_wall_clock_s": gpu_wall_clock,
        "n": n, "seed": seed, "top_p": top_p, "batch_size": batch_size,
    }
    return out, report


# ============================================================================ CLI
def cmd_generate(args) -> int:
    if args.pool == "dev":
        needs = gf_corpora.verify("skillret")
        if needs:
            print("skillret corpus not available on this machine:", needs[0], file=sys.stderr)
            return 1
        skills = gf_corpora.load_skillret_dev()["skills"]
    else:
        print(f"unknown pool {args.pool!r}", file=sys.stderr)
        return 1

    t0 = time.time()
    out, report = generate_pool(
        skills, n=args.n, model_dir=args.model_dir, cache_root=args.cache_dir,
        batch_size=args.batch_size, seed=args.seed, top_p=args.top_p, device=args.device,
        limit=args.limit,
    )
    report["wall_clock_s"] = time.time() - t0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for sid in sorted(out):
            f.write(json.dumps({"skill_id": sid, "queries": out[sid]}, ensure_ascii=False) + "\n")

    print(json.dumps(report, indent=2), file=sys.stderr)

    if args.samples:
        id_to_skill = {s["id"]: s for s in skills}
        sample_ids = sorted(out)[: args.samples]
        for sid in sample_ids:
            s = id_to_skill.get(sid, {})
            print(f"--- {sid} :: {s.get('name', '?')} ---", file=sys.stderr)
            for q in out[sid]:
                print(f"  {q}", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_gen = sub.add_parser("generate", help="generate pseudo-queries for a skill pool")
    p_gen.add_argument("--pool", default="dev", choices=["dev"])
    p_gen.add_argument("--n", type=int, default=5)
    p_gen.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_gen.add_argument("--top-p", type=float, default=DEFAULT_TOP_P)
    p_gen.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p_gen.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    p_gen.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_ROOT)
    p_gen.add_argument("--device", default=None)
    p_gen.add_argument("--limit", type=int, default=None)
    p_gen.add_argument("--samples", type=int, default=5)
    p_gen.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "generate":
        return cmd_generate(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
