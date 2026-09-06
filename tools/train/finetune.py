#!/usr/bin/env python3
"""tools/train/finetune.py — Family E fine-tuning runner (DENSE-PROGRAM.md v2.6 §4 "Why E exists").

Fine-tunes a sentence-embedding base model on this family's synthetic training data
(tools/train/synth_queries.py's per-skill queries, composite queries, hard negatives), with the
MultipleNegativesRanking objective (in-batch negatives plus the family's explicit same-category
hard negatives) over sentence-transformers' `SentenceTransformerTrainer`.

Three implementation choices, fixed here before any E1-E5 run (recorded in
docs/reports/bakeoff/DEV-E-synthetic-training-2026-09-05.md §2 "Training-time implementation note"):
  * Loss = `CachedMultipleNegativesRankingLoss` (GradCache) by default: the *same* objective as
    MultipleNegativesRankingLoss, computed in `--mini-batch-size` chunks so the in-batch-negative
    batch (`--batch-size`, default 64) is no longer bounded by activation memory. `--loss mnrl`
    keeps the plain loss for tiny smoke runs.
  * Precision = bf16 autocast over fp32 master weights (`bf16=True`); the 0.6B base is a Qwen3
    model, which fp16 autocast (the only mode `old_fit`'s `use_amp` offers) can overflow, and pure
    bf16 weights would round a 2e-5 update away.
  * Sequence cap = `--max-seq-length` (default 1024) applied to every training text (query,
    positive, negatives). The dev skill texts are long (median 1,564 tokens under the 0.6B
    tokenizer, p95 5,516, max 34,410 -- measured 2026-09-06), so training on the full body at any
    useful batch size does not fit a 24 GB GPU. Eval is NOT changed: tools/eval/dev_dense.py still
    embeds the full body exactly as it did for E0, so every Ek is scored on the same document
    representation as the zero-shot reference; the cap is a train-time truncation only, and the
    same cap applies to every configuration in the family (E4's base has its own 512 limit, which
    is the binding one there).

Query prompt: the base model's own query-side instruction (tools/eval/dev_dense.py::QUERY_PROMPTS,
looked up by `--source`, overridable with `--query-prompt`) is prepended to every training query,
exactly as dev_dense.py prepends it at eval time -- otherwise E0 (evaluated with the prompt) and a
fine-tuned Ek (trained without it) would not be the same convention. The prompt used is recorded in
the checkpoint's train_meta.json, and dev_dense.py reads it back from there for a local checkpoint
directory so an Ek is never accidentally evaluated with a different (or no) prompt.

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

Batching: `BatchSamplers.NO_DUPLICATES` -- guarantees no duplicate text within a batch across ALL
text columns, which the in-batch-negatives assumption needs (two rows sharing the SAME positive
text in one batch would make each other's "in-batch negative" a second copy of the correct answer;
a hard negative equal to another row's positive is the same problem). Composite-query
multi-positive expansion (>=2 rows can share a query string, one per gold skill) and the 5 per-skill
rows that share one positive are exactly the cases this guards against.

Resumability: the trainer writes a full checkpoint to `<checkpoints>/<identity>/checkpoint-<step>/`
every `--checkpoint-save-steps` (all kept); `--resume` hands the highest-numbered one to
`trainer.train(resume_from_checkpoint=...)`, which restores optimizer/scheduler/sampler state, not
just the weights.

Subcommands:
  rows   build training rows from the three generated-data files and report drop-reason stats —
         torch-free, safe in CI, and the thing to run before spending any GPU time on a batch.
  train  rows, then fine-tune one base-model identity with SentenceTransformerTrainer; needs
         the GPU venv (torch, sentence-transformers, datasets, accelerate).

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
    """Best-effort resume: the highest-numbered checkpoint subdirectory under checkpoint_path.
    Accepts both the trainer's `checkpoint-<step>` directories and bare `<step>` ones (the older
    old_fit layout, still recognised so a pre-existing checkpoint root keeps working). Every
    checkpoint is kept (save_total_limit=None), so the highest step is always the most recent."""
    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        return None
    numbered = []
    for child in checkpoint_path.iterdir():
        if not child.is_dir():
            continue
        name = child.name[len("checkpoint-"):] if child.name.startswith("checkpoint-") else child.name
        if name.isdigit():
            numbered.append((int(name), child))
    if not numbered:
        return None
    return max(numbered, key=lambda t: t[0])[1]


def _query_prompt_for(args) -> str:
    """The base model's own query-side instruction, same table dev_dense.py uses at eval time."""
    if args.query_prompt is not None:
        return args.query_prompt
    import dev_dense  # tools/eval/dev_dense.py -- torch-free at import
    prompt = dev_dense.QUERY_PROMPTS.get(args.source)
    if prompt is None:
        meta = Path(args.source) / "train_meta.json"   # fine-tuning a previous checkpoint (E5)
        if meta.is_file():
            prompt = json.loads(meta.read_text()).get("query_prompt")
    if prompt is None:
        raise SystemExit(f"finetune train: no query prompt known for --source {args.source!r}; "
                          f"pass --query-prompt explicitly (use '' for none)")
    return prompt


def restore_eval_seq_length(model, base_max):
    """Undo the train-time sequence cap on a SentenceTransformer before it is saved, so the
    checkpoint evaluates under the base model's own limit (what E0 was measured with).
    `base_max` None/0 means the base had no explicit limit; nothing is restored then."""
    if not base_max:
        return model
    model.max_seq_length = base_max
    tok = getattr(model, "tokenizer", None)
    if tok is not None and getattr(tok, "model_max_length", None) != base_max:
        tok.model_max_length = base_max
    return model


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
    query_prompt = _query_prompt_for(args)

    import torch
    from datasets import Dataset
    from sentence_transformers import (SentenceTransformer, SentenceTransformerTrainer,
                                       SentenceTransformerTrainingArguments)
    from sentence_transformers.sentence_transformer.losses import (
        CachedMultipleNegativesRankingLoss, MultipleNegativesRankingLoss)
    from sentence_transformers.sentence_transformer.training_args import BatchSamplers

    columns = {"anchor": [query_prompt + r["query"] for r in rows],
               "positive": [r["positive_text"] for r in rows]}
    for i in range(args.n_negatives):
        columns[f"negative_{i + 1}"] = [r["negative_texts"][i] for r in rows]
    train_dataset = Dataset.from_dict(columns)

    checkpoint_dir = CHECKPOINTS_ROOT / args.identity
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    resume_dir = _latest_checkpoint_dir(checkpoint_dir) if args.resume else None
    if resume_dir:
        print(f"finetune train: resuming from checkpoint {resume_dir}")

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    # Same hf_id/revision -> local mirror resolution as tools/eval/dev_dense.py's Encoder, so the
    # base loads offline from ~/.cache/guidefold/models/<id>__/<revision> (never the network).
    local_mirror = (synth_queries.MODELS_ROOT / args.source.replace("/", "__") / args.revision
                    if args.revision else None)
    load_source, load_revision = ((str(local_mirror), None) if local_mirror and local_mirror.is_dir()
                                  else (args.source, args.revision))
    model = SentenceTransformer(load_source, revision=load_revision, device=device,
                                trust_remote_code=True)
    base_max = model.max_seq_length
    model.max_seq_length = (min(base_max, args.max_seq_length) if base_max
                            else args.max_seq_length)
    if args.loss == "cached-mnrl":
        loss = CachedMultipleNegativesRankingLoss(model, mini_batch_size=args.mini_batch_size)
    else:
        loss = MultipleNegativesRankingLoss(model)

    n_steps = (len(rows) // args.batch_size) * args.epochs
    warmup_steps = (args.warmup_steps if args.warmup_steps is not None
                     else max(1, int(n_steps * 0.1)))
    use_bf16 = device.startswith("cuda")
    targs = SentenceTransformerTrainingArguments(
        output_dir=str(checkpoint_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.lr,
        warmup_steps=warmup_steps,
        bf16=use_bf16, fp16=False,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        # NoDuplicatesBatchSampler emits a *partial* batch whenever it cannot fill one without a
        # repeated text; with drop_last=True every such batch is discarded and the trainer can end
        # up with zero steps (seen on the CPU smoke set, 2026-09-06). Partial batches mean a
        # smaller in-batch-negative pool for that step, never a wrong loss.
        dataloader_drop_last=False,
        gradient_checkpointing=args.gradient_checkpointing,
        # Tokenisation happens in the collator; with 0 workers it runs in the training process
        # and starves the GPU (E1 measured 19-47 % GPU utilisation at 120 % CPU, 2026-09-06).
        # Workers move it off the main loop; the batch *composition* is still the sampler's.
        dataloader_num_workers=args.dataloader_workers,
        dataloader_pin_memory=True,
        dataloader_prefetch_factor=(4 if args.dataloader_workers > 0 else None),
        save_strategy="steps", save_steps=args.checkpoint_save_steps, save_total_limit=None,
        logging_steps=25, report_to="none", disable_tqdm=not args.progress_bar,
        seed=args.seed, data_seed=args.seed,
    )
    trainer = SentenceTransformerTrainer(model=model, args=targs, train_dataset=train_dataset,
                                         loss=loss)
    t0 = time.time()
    trainer.train(resume_from_checkpoint=str(resume_dir) if resume_dir else None)
    dt = time.time() - t0

    final_dir = checkpoint_dir / "final"
    # The train-time cap must NOT travel with the checkpoint: SentenceTransformer.save() persists
    # max_seq_length into tokenizer_config.json (model_max_length), and dev_dense.py would then
    # embed documents truncated at the cap while E0 embeds up to the base's own limit -- a
    # different document representation masquerading as a training effect (caught on E1,
    # 2026-09-06, before any number was read). Restore the base's limit before saving.
    restore_eval_seq_length(model, base_max)
    model.save(str(final_dir))

    meta = {
        "identity": args.identity, "source": args.source, "revision": args.revision,
        "loaded_from": load_source, "resumed_from": str(resume_dir) if resume_dir else None,
        "n_rows": len(rows), "row_stats": stats,
        "epochs": args.epochs, "batch_size": args.batch_size, "lr": args.lr,
        "warmup_steps": warmup_steps, "n_steps": n_steps, "seed": args.seed,
        "loss": args.loss, "mini_batch_size": args.mini_batch_size,
        "dataloader_workers": args.dataloader_workers,
        "max_seq_length": model.max_seq_length, "base_max_seq_length": base_max,
        "query_prompt": query_prompt, "precision": ("bf16-autocast over " + str(next(model.parameters()).dtype).replace("torch.", "") + " weights") if use_bf16 else "fp32",
        "gradient_checkpointing": bool(args.gradient_checkpointing),
        "device": device, "train_time_s": dt,
        "gpu_hours": dt / 3600.0 if device.startswith("cuda") else 0.0,
        "log_history": trainer.state.log_history,
    }
    for d in (checkpoint_dir, final_dir):
        (d / "train_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True))
    print(json.dumps({k: v for k, v in meta.items() if k != "log_history"},
                     indent=2, sort_keys=True))
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
    t.add_argument("--batch-size", type=int, default=64,
                   help="in-batch-negatives batch (the loss's effective batch)")
    t.add_argument("--mini-batch-size", type=int, default=8,
                   help="cached-mnrl forward/backward chunk; memory knob only, no effect on the loss")
    t.add_argument("--dataloader-workers", type=int, default=4,
                   help="collator (tokenisation) worker processes; throughput knob only")
    t.add_argument("--loss", choices=["cached-mnrl", "mnrl"], default="cached-mnrl")
    t.add_argument("--max-seq-length", type=int, default=1024,
                   help="train-time token cap for every text (eval keeps the full body)")
    t.add_argument("--query-prompt", default=None,
                   help="override the base model's query instruction ('' for none)")
    t.add_argument("--gradient-checkpointing", action="store_true")
    t.add_argument("--lr", type=float, default=2e-5)
    t.add_argument("--warmup-steps", type=int, default=None)
    t.add_argument("--checkpoint-save-steps", type=int, default=200)
    t.add_argument("--resume", action="store_true")
    t.add_argument("--device", default=None)
    t.add_argument("--progress-bar", action="store_true")
    t.add_argument("--force-any-python", action="store_true")
    t.set_defaults(func=cmd_train)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
