#!/usr/bin/env python3
"""tools/train/finetune.py — Family E fine-tuning runner (DENSE-PROGRAM.md v2.6 §4 "Why E exists").

Fine-tunes a sentence-embedding base model on this family's synthetic training data
(tools/train/synth_queries.py's per-skill queries, composite queries, hard negatives), using
MultipleNegativesRankingLoss with in-batch negatives plus the family's explicit same-category hard
negatives, over sentence-transformers' pre-v3 training loop (`SentenceTransformer.old_fit`) — NOT
`.fit()`: sentence-transformers 6.0.1's new-style `.fit()` requires the `datasets` package
internally (`fit_mixin.py`: `if not is_datasets_available(): raise ImportError(...)`, because it
delegates to `SentenceTransformerTrainer`) and `datasets` is not installed in the gpu-venv; `old_fit`
needs only `torch` + `transformers`, both already installed, and predates that dependency entirely.

Training row construction (build_training_rows, pure logic, no torch import — tested without the
GPU venv):
  * per-skill row: one row per (skill, generated query) pair — InputExample(texts=[query,
    positive_skill_text] + [HARD_NEGATIVES_N hard-negative skill texts]).
  * composite row: one row per (composite query, each gold skill in that composite) — same shape;
    negatives are that skill's OWN hard negatives (never pooled/shared across the composite — see
    tools/train/synth_queries.py::cmd_hard_negatives's docstring for why one skill's negatives are
    computed excluding the whole composite's gold set, not just that skill's own id).
  * A row whose resolved negative count != n_negatives (a skill/composite id the hard-negatives
    file never covered, e.g. a generation batch run before hard-negatives caught up) is dropped and
    counted in `stats`, never silently under-filled: MultipleNegativesRankingLoss needs a uniform
    `texts` shape across one batch's InputExamples.
  * "positive_text" is the skill's FULL body (skill_text_for_training -> synth_queries.skill_text
    with max_body_chars=None), matching what tools/eval/dev_dense.py actually embeds at eval time
    (skill_texts_for_cards: name+description+full stripped body, truncated only by the model's own
    tokenizer) — the training signal must not see a shorter document than the one scored later.

Batching: NoDuplicatesDataLoader (sentence_transformers.sentence_transformer.datasets), not a plain
shuffled DataLoader — guarantees no duplicate text within a batch, which
MultipleNegativesRankingLoss's in-batch-negatives assumption needs (two rows sharing the SAME
positive text in one batch would make each other's "in-batch negative" a second copy of the correct
answer). Composite-query multi-positive expansion (>=2 rows can share a query string, one per gold
skill) is exactly the case this guards against. old_fit() itself wires
`dataloader.collate_fn = self.smart_batching_collate` on every dataloader in `train_objectives`
before training starts — this script does not set collate_fn itself.

Resumability: old_fit has no `resume_from_checkpoint` kwarg (unlike v3+ `.fit()`), but it always
writes a full `self.save(...)` snapshot to `checkpoint_path/<global_step>/` every
`checkpoint_save_steps`, and `checkpoint_save_total_limit=0` (this script's fixed choice) means
"keep every one, delete none" — so `--resume` picks the highest-numbered step directory under the
identity's checkpoint root and loads it as the starting model, best-effort.

Subcommands:
  rows   build training rows from the three generated-data files and report drop-reason stats —
         torch-free, safe in CI, and the thing to run before spending any GPU time on a batch.
  train  rows, then fine-tune one base-model identity with old_fit; needs the GPU venv.

No import-time torch/transformers/sentence-transformers dependency — build_training_rows,
_hard_negatives_index, _seed_everything and the CLI's `rows` subcommand are exercised by tests
without the GPU venv; only cmd_train touches it, deferred into that function body
(tools/eval/dev_dense.py's Encoder / tools/train/synth_queries.py's Generator convention).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAIN_DIR = Path(__file__).resolve().parent
EVAL_DIR = REPO_ROOT / "tools" / "eval"
for _d in (TRAIN_DIR, EVAL_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

import synth_queries  # tools/train/synth_queries.py -- skill_text, HARD_NEGATIVES_N, _load_skills

GPU_VENV_PYTHON = "/home/mike/.cache/guidefold/gpu-venv/bin/python"
CHECKPOINTS_ROOT = Path("/home/mike/.cache/guidefold/finetune-checkpoints")
HARD_NEGATIVES_N = synth_queries.HARD_NEGATIVES_N


def skill_text_for_training(skill: dict) -> str:
    """Full, untruncated skill text — see module docstring: must match what dev_dense.py embeds at
    eval time, never the generator's own MAX_BODY_CHARS-truncated prompt text."""
    return synth_queries.skill_text(skill, max_body_chars=None)


def _load_jsonl(path) -> list:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _hard_negatives_index(hard_negatives_records: list) -> tuple:
    """Returns (per_skill_negs, composite_negs): per_skill_negs maps skill_id -> [neg_id, ...];
    composite_negs maps tuple(sorted(skill_ids)) -> {skill_id: [neg_id, ...]}. Composite keys are
    sorted because tools/train/synth_queries.py's sample_hard_negatives is fully deterministic
    given (skill_id, gold_set, seed) — the join must not depend on the order skill_ids happened to
    be written in, only the *set* they name."""
    per_skill, composite = {}, {}
    for rec in hard_negatives_records:
        if "hard_negatives" in rec:
            (sid,) = rec["skill_ids"]
            per_skill[sid] = rec["hard_negatives"]
        elif "hard_negatives_by_skill" in rec:
            key = tuple(sorted(rec["skill_ids"]))
            composite[key] = rec["hard_negatives_by_skill"]
    return per_skill, composite


def build_training_rows(skills: list, per_skill_queries: list, composite_queries: list,
                         hard_negatives: list, n_neg: int = HARD_NEGATIVES_N) -> dict:
    """Joins the three generated files into a flat list of training rows
    {"query", "positive_id", "positive_text", "negative_ids", "negative_texts", "kind"}.

    Returns {"rows": [...], "stats": {...}} rather than a bare list so a caller (cmd_train, or a
    test) can see *why* rows were dropped — a silent drop of a large fraction of the data is
    exactly the kind of bug that would ship a systematically weaker recipe without ever failing a
    test.
    """
    by_id = {s["id"]: s for s in skills}
    per_skill_negs, composite_negs = _hard_negatives_index(hard_negatives)

    rows = []
    stats = {
        "per_skill_rows": 0, "composite_rows": 0,
        "dropped_no_queries": 0, "dropped_unknown_skill": 0,
        "dropped_no_hard_negatives": 0, "dropped_wrong_negative_count": 0,
        "dropped_unknown_negative_id": 0,
    }

    def resolve_negatives(neg_ids):
        texts = []
        for nid in neg_ids:
            skill = by_id.get(nid)
            if skill is None:
                return None
            texts.append(skill_text_for_training(skill))
        return texts

    for rec in per_skill_queries:
        sid = rec.get("skill_id")
        queries = rec.get("queries")
        if not queries:
            stats["dropped_no_queries"] += 1
            continue
        skill = by_id.get(sid)
        if skill is None:
            stats["dropped_unknown_skill"] += 1
            continue
        neg_ids = per_skill_negs.get(sid)
        if neg_ids is None:
            stats["dropped_no_hard_negatives"] += 1
            continue
        if len(neg_ids) != n_neg:
            stats["dropped_wrong_negative_count"] += 1
            continue
        neg_texts = resolve_negatives(neg_ids)
        if neg_texts is None:
            stats["dropped_unknown_negative_id"] += 1
            continue
        positive_text = skill_text_for_training(skill)
        for q in queries:
            rows.append({
                "query": q, "positive_id": sid, "positive_text": positive_text,
                "negative_ids": list(neg_ids), "negative_texts": neg_texts, "kind": "per_skill",
            })
            stats["per_skill_rows"] += 1

    for rec in composite_queries:
        query = rec.get("query")
        skill_ids = rec.get("skill_ids") or []
        if not query:
            stats["dropped_no_queries"] += 1
            continue
        key = tuple(sorted(skill_ids))
        negs_by_skill = composite_negs.get(key)
        if negs_by_skill is None:
            stats["dropped_no_hard_negatives"] += 1
            continue
        for sid in skill_ids:
            skill = by_id.get(sid)
            if skill is None:
                stats["dropped_unknown_skill"] += 1
                continue
            neg_ids = negs_by_skill.get(sid)
            if neg_ids is None or len(neg_ids) != n_neg:
                stats["dropped_wrong_negative_count"] += 1
                continue
            neg_texts = resolve_negatives(neg_ids)
            if neg_texts is None:
                stats["dropped_unknown_negative_id"] += 1
                continue
            rows.append({
                "query": query, "positive_id": sid,
                "positive_text": skill_text_for_training(skill),
                "negative_ids": list(neg_ids), "negative_texts": neg_texts, "kind": "composite",
            })
            stats["composite_rows"] += 1

    stats["total_rows"] = len(rows)
    return {"rows": rows, "stats": stats}


def _require_gpu_venv(force_any_python: bool):
    if sys.executable != GPU_VENV_PYTHON and not force_any_python:
        raise SystemExit(
            f"finetune: run under {GPU_VENV_PYTHON} (or pass --force-any-python for a tiny "
            f"CPU smoke test)")


def _seed_everything(seed: int):
    """random.seed first, always — NoDuplicatesDataLoader.__init__ shuffles via the global
    `random` module (not its own Random instance), so determinism depends on this call happening
    before the dataloader is constructed."""
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def _latest_checkpoint_dir(checkpoint_path: Path):
    """old_fit has no native resume_from_checkpoint — best-effort resume: the highest-numbered
    step subdirectory under checkpoint_path is a complete `self.save(...)` directory (loadable via
    SentenceTransformer(that_dir)), written by _save_checkpoint after every checkpoint_save_steps.
    checkpoint_save_total_limit=0 (this script's fixed choice) keeps every one, so the highest step
    number is always the most recent."""
    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        return None
    numbered = [(int(child.name), child) for child in checkpoint_path.iterdir()
                if child.is_dir() and child.name.isdigit()]
    if not numbered:
        return None
    return max(numbered, key=lambda t: t[0])[1]


def cmd_train(args) -> int:
    _require_gpu_venv(args.force_any_python)
    _seed_everything(args.seed)

    skills = synth_queries._load_skills(args)
    per_skill_queries = _load_jsonl(args.per_skill_file)
    composite_queries = _load_jsonl(args.composite_file) if args.composite_file else []
    hard_negatives = _load_jsonl(args.hard_negatives_file)

    built = build_training_rows(skills, per_skill_queries, composite_queries, hard_negatives,
                                 n_neg=args.n_negatives)
    rows, stats = built["rows"], built["stats"]
    print(json.dumps({"row_stats": stats}, indent=2, sort_keys=True))
    if not rows:
        raise SystemExit("finetune train: zero training rows built -- check --per-skill-file / "
                          "--composite-file / --hard-negatives-file / --skills-file inputs")

    from sentence_transformers import InputExample, SentenceTransformer
    from sentence_transformers.sentence_transformer.datasets.no_duplicates_dataloader import (
        NoDuplicatesDataLoader,
    )
    from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss

    examples = [InputExample(texts=[r["query"], r["positive_text"], *r["negative_texts"]])
                for r in rows]
    train_dataloader = NoDuplicatesDataLoader(examples, batch_size=args.batch_size)

    checkpoint_dir = CHECKPOINTS_ROOT / args.identity
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    resume_dir = _latest_checkpoint_dir(checkpoint_dir) if args.resume else None
    source = str(resume_dir) if resume_dir else args.source
    if resume_dir:
        print(f"finetune train: resuming from checkpoint {resume_dir}")

    model = SentenceTransformer(source, revision=None if resume_dir else args.revision)
    if args.device:
        model = model.to(args.device)
    loss = MultipleNegativesRankingLoss(model)

    n_steps = (len(examples) // args.batch_size) * args.epochs
    warmup_steps = (args.warmup_steps if args.warmup_steps is not None
                     else max(1, int(n_steps * 0.1)))

    t0 = time.time()
    model.old_fit(
        train_objectives=[(train_dataloader, loss)],
        epochs=args.epochs,
        warmup_steps=warmup_steps,
        optimizer_params={"lr": args.lr},
        checkpoint_path=str(checkpoint_dir),
        checkpoint_save_steps=args.checkpoint_save_steps,
        checkpoint_save_total_limit=0,  # keep every checkpoint -- resume picks the highest step
        show_progress_bar=args.progress_bar,
        use_amp=(str(model.device).startswith("cuda")),
    )
    dt = time.time() - t0

    final_dir = checkpoint_dir / "final"
    model.save(str(final_dir))

    meta = {
        "identity": args.identity, "source": args.source, "revision": args.revision,
        "resumed_from": str(resume_dir) if resume_dir else None,
        "n_rows": len(rows), "row_stats": stats,
        "epochs": args.epochs, "batch_size": args.batch_size, "lr": args.lr,
        "warmup_steps": warmup_steps, "n_steps": n_steps, "seed": args.seed,
        "device": str(model.device), "train_time_s": dt,
        "gpu_hours": dt / 3600.0 if str(model.device).startswith("cuda") else 0.0,
    }
    (checkpoint_dir / "train_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True))
    print(json.dumps(meta, indent=2, sort_keys=True))
    print(f"finetune train: wrote final checkpoint -> {final_dir}")
    return 0


def cmd_rows(args) -> int:
    """Torch-free: build training rows and report stats only -- for CI/tests and for a quick
    sanity check of a generation batch before spending any GPU time on it."""
    skills = synth_queries._load_skills(args)
    per_skill_queries = _load_jsonl(args.per_skill_file)
    composite_queries = _load_jsonl(args.composite_file) if args.composite_file else []
    hard_negatives = _load_jsonl(args.hard_negatives_file)
    built = build_training_rows(skills, per_skill_queries, composite_queries, hard_negatives,
                                 n_neg=args.n_negatives)
    print(json.dumps({"row_stats": built["stats"]}, indent=2, sort_keys=True))
    if args.out:
        Path(args.out).write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in built["rows"]))
        print(f"finetune rows: wrote {len(built['rows'])} rows -> {args.out}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--corpus", default="dev", choices=["dev", "test-a", "test-b"])
        sp.add_argument("--skills-file", default=None,
                         help="override: JSON list of skill dicts (tests / fixtures)")
        sp.add_argument("--per-skill-file", required=True)
        sp.add_argument("--composite-file", default=None)
        sp.add_argument("--hard-negatives-file", required=True)
        sp.add_argument("--n-negatives", type=int, default=HARD_NEGATIVES_N)

    r = sub.add_parser("rows")
    add_common(r)
    r.add_argument("--out", default=None)
    r.set_defaults(func=cmd_rows)

    t = sub.add_parser("train")
    add_common(t)
    t.add_argument("--identity", required=True)
    t.add_argument("--source", required=True, help="hf_id or local checkpoint dir (base model)")
    t.add_argument("--revision", default=None)
    t.add_argument("--seed", type=int, default=20260905)
    t.add_argument("--epochs", type=int, default=1)
    t.add_argument("--batch-size", type=int, default=32)
    t.add_argument("--lr", type=float, default=2e-5)
    t.add_argument("--warmup-steps", type=int, default=None)
    t.add_argument("--checkpoint-save-steps", type=int, default=500)
    t.add_argument("--resume", action="store_true")
    t.add_argument("--device", default=None)
    t.add_argument("--progress-bar", action="store_true")
    t.add_argument("--force-any-python", action="store_true")
    t.set_defaults(func=cmd_train)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
