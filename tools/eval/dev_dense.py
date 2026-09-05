#!/usr/bin/env python3
"""tools/eval/dev_dense.py — dev-split dense-arm runner for family E (synthetic in-distribution
training, DENSE-PROGRAM.md v2.6). Same dev split, same cards, same cases, same product path as
tools/eval/dev_sparse.py's P-shipped arm (F0) — this script only adds the dense candidate source
on top, exactly the way tools/eval/skillret.py's R1 does it for test-A, generalized to (a) any
model identity, so a fine-tuned checkpoint is a first-class citizen, not a special case, and
(b) the dev corpus instead of test-A/test-B.

Reused, never reimplemented:
  * tools/eval/corpora.py       load_skillret_dev() — the one place that opens the frozen dev
                                 split.
  * tools/eval/dev_sparse.py    corpus_to_cards / queries_to_cases (dev skills/queries -> cards
                                 + cases, IDENTICAL to F0's own conversion — reusing this module
                                 rather than re-deriving it is what makes F0's existing
                                 dev-sparse-p-shipped.jsonl.gz a valid pairing partner here),
                                 run_product_case (policy_filter -> candidates -> score -> select,
                                 the real product pipeline), bootstrap_paired_delta, write_jsonl_gz.
  * tools/eval/dense_ref.py     DenseCandidateRouter / build_dense_index_and_router (w_dense=1,
                                 unmodified select()) / encode_chunked / quantize / quant_cosine /
                                 write_dense_cache / load_dense_cache — the exact R1 scaffolding,
                                 corpus-agnostic by construction.
  * tools/eval/metrics.py       hit_at_1 / recall_at_k / ndcg_at_k / all_required_at_k.

Retrieval modes (DENSE-PROGRAM.md v2.6, family E addendum 2026-09-05 — evaluate every model in
both, report both, freeze on the better-of-two per model):
  * hybrid       RRF k=60 fusion of the sparse (BM25/F0) and dense channels — dense_ref.py's
                 existing build_dense_index_and_router, unmodified.
  * dense-only   candidates/scores come from the dense channel EXCLUSIVELY (w_sparse=0). Zeroing
                 field.* weights is NOT sufficient for this: Router._bm25_scores still returns a
                 same-value-0 entry for every lexically-matching URN regardless of field weight,
                 and candidates()'s bm25_order[:top_n] union would still admit those URNs into the
                 pool. make_dense_only_router_class / build_dense_only_index_and_router (below,
                 local to this file — dense_ref.py's shared surface is owned by other in-flight
                 family work and stays untouched) override candidates() itself so every candidate's
                 bm25_rank is structurally None.

Metric semantics (DENSE-PROGRAM.md v2.6, family E "Measurement"):
  * all_required@4 (primary)   computed on `injected` — the actual select() output (abstention
                                gate, k_cards=4, dependency closure included) — matching
                                skillret.py's cmd_r1, NOT dev_sparse.py's own per_query_metrics
                                (which deliberately uses raw `ranked` for cross-arm comparability
                                with the non-product R-BM25 reference arms; that convention is
                                right for dev_sparse.py's question and wrong for this one).
  * hit@1 / nDCG@10 / recall@10   computed on `ranked` — the raw scored/retrieval order, before
                                any abstention or closure decision, per the brief's explicit
                                retrieval-vs-injection distinction (commit 931055d fixed exactly
                                this confusion once already; do not reintroduce it).
  * candidate ceiling@N, N in {4,10,15,50}   all_required_at_k(ranked, case, N) — "is the right
                                answer even reachable by retrieval alone", independent of
                                select()'s abstention/closure policy. This dev corpus has
                                requires=[] for every card (dev_sparse.py's own note), so ceiling
                                here is pure retrieval quality, no closure assist.

Subcommands:
  encode   encode dev skills + dev queries with one named model identity, chunked + resumable,
           disk cache keyed by --identity (never by hf_id alone — two identities may share an
           hf_id, e.g. a fine-tuned checkpoint reusing its base's hf_id as a label prefix).
  run      run one cached identity through the full product path over all 1 000 dev cases; write
           the per-query JSONL.gz (same schema as dev_sparse.py's own P-* arms) and a summary.
  latency  batch-1 encode latency for a handful of dev skill texts, GPU (and, when --device cpu
           is also requested, CPU) — the brief's "encode latency (batch-1 GPU and CPU for E4)".
  report   paired bootstrap CIs for one or more arms vs a baseline JSONL.gz (F0 or any Ex),
           per k and overall, plus the candidate-ceiling table.

No import-time torch/transformers/sentence-transformers dependency (this module is imported by
pytest with no GPU venv); the `Encoder` class defers those imports into its own methods, mirroring
tools/bakeoff/encode.py's and dense_ref.py's own convention.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = Path(__file__).resolve().parent
VALIDATION_DIR = REPO_ROOT / "docs" / "reports" / "bakeoff" / "validation"
DENSE_CACHE_ROOT = EVAL_DIR / ".dev-dense-cache"
MODELS_ROOT = Path(os.environ.get("GUIDEFOLD_MODELS_ROOT", "/home/mike/.cache/guidefold/models"))
GPU_VENV_PYTHON = "/home/mike/.cache/guidefold/gpu-venv/bin/python"

sys.path.insert(0, str(EVAL_DIR))
import corpora as gf_corpora  # noqa: E402
import dense_ref  # noqa: E402
import dev_sparse  # noqa: E402  tools/eval/dev_sparse.py — cards/cases/run_product_case/etc.

K_CARDS = dev_sparse.K_CARDS      # 4
EVAL_K = dev_sparse.EVAL_K        # 10
RECORD_TOPN = dev_sparse.RECORD_TOPN  # 50
CEILING_NS = (4, 10, 15, 50)

# Query-side instruction prefixes, verbatim from each model's own docs — same convention and same
# source values as tools/bakeoff/encode.py's QUERY_PROMPTS (not re-derived; SKILLRET-Embedding's
# entry is copied byte-for-byte from there so E0/E1..E5 share the identical prompt convention).
QUERY_PROMPTS = {
    "ThakiCloud/SKILLRET-Embedding-0.6B": (
        "Instruct: a skill search query, retrieve relevant skills that match the query\nQuery: "
    ),
    # BGE family's own README "Usage" (bge-base-en-v1.5 / bge-m3-derived small models): the
    # standard BGE query instruction, applied only on the query side, never to documents.
    "BAAI/bge-base-en-v1.5": "Represent this sentence for searching relevant passages: ",
    # Snowflake's own model card "Using Huggingface transformers"/sentence-transformers usage:
    # query-side instruction, documents get none.
    "Snowflake/snowflake-arctic-embed-m-v1.5": (
        "Represent this sentence for searching relevant passages: "
    ),
}


def _slug_identity(identity: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", identity).strip("-")


def cache_dir_for(identity: str) -> Path:
    return DENSE_CACHE_ROOT / _slug_identity(identity)


# ---------------------------------------------------------------------------- Encoder (deferred GPU deps)
class Encoder:
    """SentenceTransformer(source).encode(texts, is_query=False) -> np.ndarray[float32], unit rows.

    `source` is either an hf_id (optionally pinned via `revision`, or resolved to a local GCS
    mirror under MODELS_ROOT the same way tools/bakeoff/encode.py's `_local_model_path` does) or a
    local checkpoint directory written by tools/train/finetune.py — sentence-transformers' own
    loader handles both transparently and restores whatever pooling module the checkpoint saved,
    so a fine-tuned E1..E5 model needs no special-casing here at all.

    Every model used by family E (SKILLRET-Embedding-0.6B and its fine-tuned descendants, plus the
    small base for E4) ships its own sentence-transformers config (modules.json/1_Pooling) — so,
    unlike tools/bakeoff/encode.py, this Encoder never needs the raw-AutoModel fallback path.
    """

    def __init__(self, source: str, revision: str = None, query_prompt: str = None,
                 batch_size: int = None, device: str = None, dtype=None):
        self.source = source
        self.revision = revision
        self.query_prompt = query_prompt
        self.batch_size = batch_size
        self._device_override = device
        self._dtype_override = dtype
        self._model = None
        self.device = None
        self.dtype = None

    def _resolve_source(self):
        if Path(self.source).is_dir():
            return self.source, None
        if self.revision:
            local = MODELS_ROOT / self.source.replace("/", "__") / self.revision
            if local.is_dir():
                return str(local), None
            return self.source, self.revision
        return self.source, None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        import torch
        from sentence_transformers import SentenceTransformer
        self.device = self._device_override or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = self._dtype_override or (torch.bfloat16 if self.device == "cuda" else torch.float32)
        if self.batch_size is None:
            self.batch_size = 32 if self.device == "cuda" else 8
        source, revision = self._resolve_source()
        kwargs = dict(device=self.device, trust_remote_code=True)
        if revision:
            kwargs["revision"] = revision
        if self.device == "cuda":
            kwargs["model_kwargs"] = {"dtype": self.dtype}
        self._model = SentenceTransformer(source, **kwargs)
        self._model.eval()

    def encode(self, texts: list, is_query: bool = False):
        import numpy as np
        self._ensure_loaded()
        if not texts:
            return np.zeros((0, self._model.get_sentence_embedding_dimension()), dtype=np.float32)
        prompt = self.query_prompt if is_query else None
        import torch
        with torch.no_grad():
            vecs = self._model.encode(
                texts, batch_size=self.batch_size, prompt=prompt,
                convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False,
            )
        return np.asarray(vecs, dtype=np.float32)


def _default_query_prompt(source: str) -> str:
    return QUERY_PROMPTS.get(source)


# ---------------------------------------------------------------------------- corpus / cards (cached in-process)
_DEV_CACHE = {}


def _dev_corpus():
    if "data" not in _DEV_CACHE:
        needs = gf_corpora.verify("skillret")
        if needs:
            raise SystemExit(f"dev_dense: skillret corpus not available: {needs[0]}")
        _DEV_CACHE["data"] = gf_corpora.load_skillret_dev()
    return _DEV_CACHE["data"]


def _dev_cards_and_cases():
    if "cards" not in _DEV_CACHE:
        data = _dev_corpus()
        cards, nodes, id_to_urn, corpus_report = dev_sparse.corpus_to_cards(data["skills"])
        cases, query_report = dev_sparse.queries_to_cases(data["queries"], data["qrels"], id_to_urn)
        _DEV_CACHE["cards"] = (cards, nodes, id_to_urn, cases, corpus_report, query_report)
    return _DEV_CACHE["cards"]


def skill_texts_for_cards(cards: dict) -> dict:
    """urn -> "name description body" — same concatenation dev_sparse.build_reference_docs uses,
    reused rather than re-derived so an encoded skill vector answers the same text F0 was scored
    against."""
    return {u: " ".join([c["name"], c["description"], c["_body"]]) for u, c in cards.items()}


def resumable_encode(enc, texts: list, is_query: bool, chunk_size: int, label: str,
                      checkpoint_path: Path):
    """Like dense_ref.encode_chunked (same chunk-then-stack computation) but checkpoints the
    accumulated float32 matrix to disk after every chunk, so a run killed mid-way (a Bash-tool
    timeout, a machine hiccup) resumes from its last completed chunk on the next invocation
    instead of re-encoding the whole corpus. Deliberately kept local to this script rather than
    folded into dense_ref.py's shared surface: tools/eval/skillret.py and
    tools/eval/skillretbench_r1.py also depend on encode_chunked's current (non-checkpointing)
    contract and are owned by other in-flight family work sharing this GPU box — same computation,
    an additive, not a shared, resumability contract."""
    import numpy as np
    checkpoint_path = Path(checkpoint_path)
    done_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".done.json")
    n_done = 0
    out = [None] * len(texts)
    if checkpoint_path.exists() and done_path.exists():
        done_meta = json.loads(done_path.read_text())
        if done_meta.get("total") == len(texts):
            existing = np.load(checkpoint_path)
            n_done = min(done_meta.get("n_done", 0), len(existing), len(texts))
            for i in range(n_done):
                out[i] = existing[i]
    if n_done:
        print(f"  {label}: resuming from checkpoint at {n_done}/{len(texts)}", flush=True)
    for start in range(n_done, len(texts), chunk_size):
        chunk = texts[start:start + chunk_size]
        t0 = time.time()
        vecs = enc.encode(chunk, is_query=is_query)
        dt = time.time() - t0
        for i in range(len(chunk)):
            out[start + i] = vecs[i]
        n_now = start + len(chunk)
        partial = np.stack(out[:n_now], axis=0).astype(np.float32)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(checkpoint_path, partial)
        done_path.write_text(json.dumps({"n_done": n_now, "total": len(texts)}))
        print(f"  {label}: {n_now}/{len(texts)} "
              f"({dt:.1f}s this chunk, {dt / max(len(chunk), 1) * 1000:.1f} ms/item, "
              f"checkpoint saved)", flush=True)
    return np.stack(out, axis=0).astype(np.float32)


# ---------------------------------------------------------------------------- encode
def cmd_encode(args) -> int:
    if sys.executable != GPU_VENV_PYTHON and not args.force_any_python:
        raise SystemExit(f"dev_dense encode: run under {GPU_VENV_PYTHON} "
                          f"(or pass --force-any-python for a CPU smoke test)")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    cards, nodes, id_to_urn, cases, _, _ = _dev_cards_and_cases()
    data = _dev_corpus()
    skill_text_by_urn = skill_texts_for_cards(cards)
    skill_order = sorted(skill_text_by_urn)  # deterministic order, independent of dict insertion
    skill_texts = [skill_text_by_urn[u] for u in skill_order]

    query_order = [c["id"] for c in cases]
    query_texts = [c["query"] for c in cases]

    query_prompt = args.query_prompt if args.query_prompt is not None else _default_query_prompt(args.source)
    enc = Encoder(args.source, revision=args.revision, query_prompt=query_prompt,
                  batch_size=args.skill_batch_size)

    cache_dir = cache_dir_for(args.identity)
    ckpt_dir = cache_dir / "checkpoints"
    t0 = time.time()
    skill_mat_f32 = resumable_encode(enc, skill_texts, is_query=False,
                                      chunk_size=args.skill_chunk_size, label="skills",
                                      checkpoint_path=ckpt_dir / "skills.f32.npy")
    t_skills = time.time() - t0

    enc_q = Encoder(args.source, revision=args.revision, query_prompt=query_prompt,
                     batch_size=args.query_batch_size or 64,
                     device=enc.device, dtype=enc.dtype)
    t1 = time.time()
    query_mat_f32 = resumable_encode(enc_q, query_texts, is_query=True,
                                      chunk_size=args.query_chunk_size, label="queries",
                                      checkpoint_path=ckpt_dir / "queries.f32.npy")
    t_queries = time.time() - t1

    skill_q = dense_ref.quantize(skill_mat_f32)
    query_q = dense_ref.quantize(query_mat_f32)
    skill_cos = dense_ref.quant_cosine(skill_mat_f32, skill_q)
    query_cos = dense_ref.quant_cosine(query_mat_f32, query_q)

    meta = {
        "identity": args.identity, "source": args.source, "revision": args.revision,
        "query_prompt": query_prompt, "device": enc.device, "dtype": str(enc.dtype),
        "skill_batch_size": enc.batch_size, "query_batch_size": enc_q.batch_size,
        "dims": int(skill_mat_f32.shape[1]),
        "n_skills": len(skill_order), "n_queries": len(query_order),
        "encode_time_s": {"skills": t_skills, "queries": t_queries},
        "encode_ms_per_item": {
            "skills": t_skills / max(len(skill_order), 1) * 1000,
            "queries": t_queries / max(len(query_order), 1) * 1000,
        },
        "quant_cosine_mean": {
            "skills": float(skill_cos.mean()), "queries": float(query_cos.mean()),
        },
    }
    dense_ref.write_dense_cache(cache_dir, skill_order, query_order, skill_q, query_q, meta)
    print(json.dumps(meta, indent=2, sort_keys=True))
    print(f"dev_dense encode: wrote cache -> {cache_dir}")
    return 0


def make_dense_only_router_class(cli):
    """Family-E 'pure dense' measurement mode (coordinator addendum, 2026-09-05 2nd note):
    candidates are sourced from the dense channel ONLY -- every candidate's bm25_rank is
    structurally None, so score()'s RRF has nothing to add for BM25 even in principle. This is
    stronger than zeroing field.* weights: Router._bm25_scores still returns a same-value-0 entry
    for every lexically-matching URN regardless of field weight, and Router.candidates()'s
    `cand_urns = set(bm25_order[:top_n]) | set(dense_order[:top_n])` union would still let those
    URNs into the candidate pool at weight 0 -- not a true "dense-only candidates" measurement.
    policy_filter/score/select/route are all untouched (still the base Router's) -- ADR-0022, no
    arm bypasses the filter; this is an eval-only measurement mode (DENSE-PROGRAM.md family E),
    never a shipped configuration. Kept local to dev_dense.py rather than folded into dense_ref.py:
    tools/eval/skillret.py and tools/eval/skillretbench_r1.py depend on dense_ref.py's current
    (hybrid-only) surface and are owned by other in-flight family work sharing this GPU box."""
    class DenseOnlyRouter(dense_ref.DenseCandidateRouter):
        def candidates(self, query, node, include_deprecated=False, top_n=50):
            visible, drops = self.policy_filter(node, query, include_deprecated)
            visible_set = set(visible)
            dense = self._dense_scores(query, visible_set)
            dense_order = cli._dense_rank(dense)
            dense_rank = {u: i + 1 for i, u in enumerate(dense_order)}
            out = []
            for u in sorted(set(dense_order[:top_n])):
                out.append({"urn": u, "node": self.index.cards[u]["node"],
                            "bm25_rank": None, "dense_rank": dense_rank.get(u)})
            self.last_drops = drops
            return out

    return type("DenseOnlyRefRouter", (DenseOnlyRouter, cli.Router), {})


def build_dense_only_index_and_router(cli, cards, nodes, row_of, skill_mat, query_vec_of):
    """Same index/router wiring as dense_ref.build_dense_index_and_router (w_dense=1, w_scope/
    w_ppr left at DEFAULT_WEIGHTS -- "everything else unchanged" per the coordinator's addendum),
    but built on make_dense_only_router_class so candidate SOURCING, not just scoring weight, is
    dense-only."""
    import numpy as np
    idx = cli.Index.from_cards(cards, nodes, weights={"w_dense": 1}, word_vectors=None)
    normsq = (skill_mat.astype(np.int64) ** 2).sum(axis=1)
    missing = [u for u in cards if u not in row_of]
    if missing:
        raise SystemExit(f"dev_dense dense-only: {len(missing)} cards have no cached embedding "
                          f"(encode cache stale?) e.g. {missing[:3]}")
    idx.skill_normsq = {u: int(normsq[row_of[u]]) for u in cards}
    router_cls = make_dense_only_router_class(cli)
    router = router_cls(idx)
    router.row_of = row_of
    router.skill_mat = skill_mat
    router.query_vec_of = query_vec_of
    router._current_qid = None
    return idx, router


# ---------------------------------------------------------------------------- run (product path)
def cmd_run(args) -> int:
    cli = dev_sparse._load_cli()
    metrics = dev_sparse._load_metrics()
    cards, nodes, id_to_urn, cases, _, _ = _dev_cards_and_cases()
    if args.limit:
        cases = cases[: args.limit]

    meta, row_of, skill_mat, query_vec_of = dense_ref.load_dense_cache(cache_dir_for(args.identity))
    mode = getattr(args, "mode", "hybrid")
    if mode == "hybrid":
        idx, router = dense_ref.build_dense_index_and_router(
            cli, cards, nodes, row_of, skill_mat, query_vec_of, weights={"w_dense": 1})
    elif mode == "dense-only":
        idx, router = build_dense_only_index_and_router(
            cli, cards, nodes, row_of, skill_mat, query_vec_of)
    else:
        raise SystemExit(f"dev_dense run: unknown --mode {mode!r} (want hybrid|dense-only)")

    records = []
    t0 = time.time()
    for case in cases:
        router._current_qid = case["id"]
        rec = dev_sparse.run_product_case(router, case, top_n=args.top_n, k_cards=K_CARDS)
        rec["arm"] = args.identity
        records.append(rec)
    dt = time.time() - t0

    per_q = {}
    for rec, case in zip(records, cases):
        qid = rec["query_id"]
        ranked = rec["ranked"]
        injected = rec["injected"]
        entry = {
            "hit1": metrics.hit_at_1(ranked, case),
            "ndcg10": metrics.ndcg_at_k(ranked, case, EVAL_K),
            "recall10": metrics.recall_at_k(ranked, case, EVAL_K),
            "all_required4": metrics.all_required_at_k(injected, case, K_CARDS),
        }
        for n in CEILING_NS:
            entry[f"ceiling{n}"] = metrics.all_required_at_k(ranked, case, n)
        per_q[qid] = entry

    if args.out:
        out_path = Path(args.out)
    else:
        suffix = "" if mode == "hybrid" else f"-{mode}"
        out_path = VALIDATION_DIR / f"dev-dense-{_slug_identity(args.identity)}{suffix}.jsonl.gz"
    dev_sparse.write_jsonl_gz(out_path, records)

    summary = _summarize(per_q, cases)
    if out_path.name.endswith(".jsonl.gz"):
        summary_path = out_path.parent / (out_path.name[: -len(".jsonl.gz")] + ".summary.json")
    else:
        summary_path = Path(str(out_path) + ".summary.json")
    summary["identity"] = args.identity
    summary["mode"] = mode
    summary["model_meta"] = meta
    summary["run_time_s"] = dt
    summary["n_cases"] = len(cases)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"dev_dense run: {len(cases)} cases, {dt:.1f}s -> {out_path}")
    return 0


def _summarize(per_q: dict, cases: list) -> dict:
    by_k: dict = {}
    for case in cases:
        by_k.setdefault(case["k"], []).append(case["id"])
    cols = ["hit1", "ndcg10", "recall10", "all_required4"] + [f"ceiling{n}" for n in CEILING_NS]

    def block(qids):
        out = {"n": len(qids)}
        for col in cols:
            vals = [per_q[q][col] for q in qids if not _isnan(per_q[q][col])]
            out[col] = sum(vals) / len(vals) if vals else float("nan")
        return out

    out = {"overall": block([c["id"] for c in cases])}
    for k in sorted(by_k):
        out[f"k={k}"] = block(by_k[k])
    return out


def _isnan(x) -> bool:
    return isinstance(x, float) and x != x


# ---------------------------------------------------------------------------- latency
def cmd_latency(args) -> int:
    if sys.executable != GPU_VENV_PYTHON and not args.force_any_python:
        raise SystemExit(f"dev_dense latency: run under {GPU_VENV_PYTHON} "
                          f"(or pass --force-any-python for a CPU-only smoke test)")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    cards, _, _, cases, _, _ = _dev_cards_and_cases()
    skill_text_by_urn = skill_texts_for_cards(cards)
    sample_texts = list(skill_text_by_urn.values())[: args.n]
    query_prompt = args.query_prompt if args.query_prompt is not None else _default_query_prompt(args.source)

    results = {}
    devices = ["cuda"] if not args.also_cpu else ["cuda", "cpu"]
    for device in devices:
        try:
            enc = Encoder(args.source, revision=args.revision, query_prompt=None,
                          batch_size=1, device=device)
            enc._ensure_loaded()  # pay model-load cost before timing
            times = []
            for t in sample_texts:
                t0 = time.time()
                enc.encode([t], is_query=False)
                times.append(time.time() - t0)
            times_sorted = sorted(times)
            results[device] = {
                "n": len(times), "mean_ms": sum(times) / len(times) * 1000,
                "p50_ms": times_sorted[len(times_sorted) // 2] * 1000,
                "p95_ms": times_sorted[int(len(times_sorted) * 0.95)] * 1000 if len(times_sorted) > 1 else times_sorted[0] * 1000,
            }
        except Exception as e:  # noqa: BLE001 — report, never silently skip a requested device
            results[device] = {"error": str(e)}
    print(json.dumps({"identity": args.identity, "source": args.source, "batch1_latency": results},
                      indent=2, sort_keys=True))
    return 0


# ---------------------------------------------------------------------------- report (paired CIs)
def cmd_report(args) -> int:
    baseline = _load_records(Path(args.baseline))
    baseline_per_q, baseline_cases_by_id = _records_to_per_q(baseline)

    for arm_path_str in args.arms:
        arm_path = Path(arm_path_str)
        arm_records = _load_records(arm_path)
        arm_per_q, _ = _records_to_per_q(arm_records)
        common = sorted(set(baseline_per_q) & set(arm_per_q))
        if not common:
            print(f"{arm_path.name}: no overlapping query_ids with baseline {Path(args.baseline).name}")
            continue
        by_k: dict = {}
        for qid in common:
            k = baseline_cases_by_id[qid]
            by_k.setdefault(k, []).append(qid)
        report = {"arm": arm_path.name, "baseline": Path(args.baseline).name, "n_common": len(common)}
        cols = ["hit1", "ndcg10", "recall10", "all_required4"]
        for scope_name, qids in [("overall", common)] + [(f"k={k}", v) for k, v in sorted(by_k.items())]:
            scope_report = {}
            for col in cols:
                a = [baseline_per_q[q][col] for q in qids if not _isnan(baseline_per_q[q][col]) and not _isnan(arm_per_q[q][col])]
                b = [arm_per_q[q][col] for q in qids if not _isnan(baseline_per_q[q][col]) and not _isnan(arm_per_q[q][col])]
                scope_report[col] = dev_sparse.bootstrap_paired_delta(a, b, seed=args.seed)
            report[scope_name] = scope_report
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _load_records(path: Path) -> list:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _records_to_per_q(records: list) -> tuple:
    metrics = dev_sparse._load_metrics()
    _, _, _, cases, _, _ = _dev_cards_and_cases()
    case_by_id = {c["id"]: c for c in cases}
    per_q = {}
    k_by_id = {}
    for rec in records:
        qid = rec["query_id"]
        case = case_by_id.get(qid)
        if case is None:
            continue
        ranked, injected = rec["ranked"], rec["injected"]
        per_q[qid] = {
            "hit1": metrics.hit_at_1(ranked, case),
            "ndcg10": metrics.ndcg_at_k(ranked, case, EVAL_K),
            "recall10": metrics.recall_at_k(ranked, case, EVAL_K),
            "all_required4": metrics.all_required_at_k(injected, case, K_CARDS),
        }
        k_by_id[qid] = case["k"]
    return per_q, k_by_id


# ---------------------------------------------------------------------------- CLI
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("encode")
    e.add_argument("--identity", required=True)
    e.add_argument("--source", required=True, help="hf_id or local checkpoint directory")
    e.add_argument("--revision", default=None)
    e.add_argument("--query-prompt", default=None)
    e.add_argument("--skill-batch-size", type=int, default=None)
    e.add_argument("--query-batch-size", type=int, default=None)
    e.add_argument("--skill-chunk-size", type=int, default=200)
    e.add_argument("--query-chunk-size", type=int, default=200)
    e.add_argument("--force-any-python", action="store_true")
    e.set_defaults(func=cmd_encode)

    r = sub.add_parser("run")
    r.add_argument("--identity", required=True)
    r.add_argument("--out", default=None)
    r.add_argument("--top-n", type=int, default=50)
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--mode", choices=["hybrid", "dense-only"], default="hybrid",
                    help="hybrid = RRF k=60 fusion with F0's sparse channel (w_dense=1, the "
                         "existing E0/R1-style measurement); dense-only = candidates/scores come "
                         "from the dense channel exclusively (w_sparse=0, DENSE-PROGRAM.md family "
                         "E addendum 2026-09-05: report both modes for every model, freeze on the "
                         "better of the two per model)")
    r.set_defaults(func=cmd_run)

    lat = sub.add_parser("latency")
    lat.add_argument("--identity", required=True)
    lat.add_argument("--source", required=True)
    lat.add_argument("--revision", default=None)
    lat.add_argument("--query-prompt", default=None)
    lat.add_argument("--n", type=int, default=20)
    lat.add_argument("--also-cpu", action="store_true")
    lat.add_argument("--force-any-python", action="store_true")
    lat.set_defaults(func=cmd_latency)

    rep = sub.add_parser("report")
    rep.add_argument("--baseline", required=True)
    rep.add_argument("--arms", nargs="+", required=True)
    rep.add_argument("--seed", type=int, default=0)
    rep.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
