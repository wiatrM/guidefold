#!/usr/bin/env python3
"""tools/train/synth_queries.py — Family E generator: synthetic training queries over a skill
pool, from skill text alone (DENSE-PROGRAM.md v2.6 §4 "Why E exists").

Reproduces, over the *tenant's own* skill pool, the recipe SkillRet v3 itself used to build its
own training queries (its query records carry a `generator_model` field — see
`tools/eval/corpora.py::load_skillret()` docstring): an LLM writes natural-language tasks that a
skill's documentation would answer. This module never reads a query or a qrel; it reads only
skill records (`id`/`name`/`description`/`body` or `skill_md`, `major`/`sub`). That is the whole
point of the family: the resulting encoder should be in-distribution on the tenant's own skills
without ever having seen a labelled query for them.

Three kinds of training pair, per DENSE-PROGRAM.md §4/"Data":
  * per-skill   — 5 natural queries per skill, varied phrasing, skill name not copied verbatim
                  in >= 2 of the 5.
  * composite   — one natural task whose answer is a *set* of 2-3 skills that plausibly
                  co-occur (same taxonomy leaf `major.sub`, since this corpus carries no
                  `requires`/`similar` edges — see the docstring on `sample_composite_sets`).
                  Target ~= 30% of training pairs.
  * hard negative — for each positive, 3 same-category siblings the query does not need (the
                  HSR failure mode SkillResolve names): no LLM call, pure sampling.

Generator: a local open LLM on the 4090, `Qwen/Qwen2.5-7B-Instruct` (Apache-2.0), bf16, batched.
Every run logs its prompts template, sampling params and seed into the output's sidecar
`<output>.manifest.json` so a run is reproducible up to GPU floating-point non-determinism
(wsl-gpu-compute SKILL.md: batch-size-dependent reduction order is not bit-reproducible; this is
offline data generation, not a runtime determinism claim).

Subcommands:
  generate        batched LLM generation, resumable (checkpoints to the output JSONL as it goes;
                  a rerun with the same --out skips skill/composite ids already present).
  hard-negatives  pure sampling, no LLM, appends to a training file.
  leakage-check   asserts no generated query (raw or normalised) appears in a labelled query set.
  audit           samples N per-skill query groups for the manual "good/repetitive/drifted" table.

No import-time torch/transformers dependency (mirrors tools/bakeoff/encode.py's Tier-2-only
discipline) so `leakage-check`/`audit`/tests never need the GPU venv.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = REPO_ROOT / "tools" / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

MODEL_HF_ID = "Qwen/Qwen2.5-7B-Instruct"
MODEL_REVISION = "a09a35458c702b33eeacc393d103063234e8bc28"
MODELS_ROOT = Path("/home/mike/.cache/guidefold/models")
GPU_VENV_PYTHON = "/home/mike/.cache/guidefold/gpu-venv/bin/python"

PER_SKILL_N = 5
COMPOSITE_TARGET_FRACTION = 0.30
HARD_NEGATIVES_N = 3
MAX_BODY_CHARS = 3000  # prompt budget; bodies run up to ~184k chars in this dataset family

# ---------------------------------------------------------------------------
# skill text — reads name/description/body only, never a query or qrel
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def skill_text(skill: dict, max_body_chars: int = MAX_BODY_CHARS) -> str:
    """name + description + (body or skill_md, own frontmatter block stripped, optionally
    truncated). `max_body_chars=None` disables truncation entirely — used by finetune.py to build
    the fine-tuning "positive document" text, which must match (as closely as a plain-Python
    string can) what tools/eval/dev_dense.py actually embeds at eval time
    (`skill_texts_for_cards`: name+description+full stripped body, truncated only by the model's
    own tokenizer, never by this function) — a generation prompt, by contrast, has a real LLM
    context budget and keeps the MAX_BODY_CHARS default.

    Same fields dev_sparse.py's cards use for the shipped BM25F body field — deliberately not a
    new convention, so a reader who knows one script's card shape recognises the other's."""
    name = (skill.get("name") or "").strip()
    description = (skill.get("description") or "").strip()
    body = skill.get("body") or skill.get("skill_md") or ""
    body = _FRONTMATTER_RE.sub("", body).strip()
    if max_body_chars is not None and len(body) > max_body_chars:
        body = body[:max_body_chars].rsplit(" ", 1)[0] + " …"
    parts = [p for p in (name, description, body) if p]
    return "\n\n".join(parts)


def taxonomy_leaf(skill: dict) -> tuple:
    return (skill.get("major") or "", skill.get("sub") or "")


# ---------------------------------------------------------------------------
# composite sampling — same taxonomy leaf/category (this corpus carries no requires/similar
# edges to fall back on; DENSE-PROGRAM.md's "or nearest neighbours by the shipped sparse
# ranking" alternative is not exercised here — see the generator-audit note in the family
# report for why taxonomy co-occurrence alone was judged sufficient at this budget).
# ---------------------------------------------------------------------------

def build_taxonomy_groups(skills: list) -> dict:
    """(major, sub) -> [skill_id, ...], stable order (input order)."""
    groups: dict = {}
    for s in skills:
        groups.setdefault(taxonomy_leaf(s), []).append(s["id"])
    return groups


def sample_composite_sets(skills: list, n_sets: int, seed: int,
                           sizes: tuple = (2, 3)) -> list:
    """n_sets tuples of 2-3 skill ids drawn from the same taxonomy leaf (major.sub).

    Groups with fewer than 2 members cannot form a composite and are skipped. Deterministic
    given (skills order, n_sets, seed): a rerun with the same inputs reproduces the same sets,
    which is what lets `leakage-check` and `finetune.py`'s artefact hash be meaningful."""
    groups = build_taxonomy_groups(skills)
    eligible = [g for g in groups.values() if len(g) >= 2]
    if not eligible:
        return []
    rng = random.Random(seed)
    out = []
    for i in range(n_sets):
        group = eligible[i % len(eligible)]
        size = min(sizes[rng.randrange(len(sizes))], len(group))
        out.append(tuple(sorted(rng.sample(group, size))))
    # de-duplicate identical sets (possible with small groups), preserve order
    seen = set()
    uniq = []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def composite_sets_for_target_rows(skills: list, target_rows: int, seed: int,
                                    sizes: tuple = (2, 3)) -> list:
    """Request composite sets until their total ROW count -- sum(len(s) for s in sets) -- reaches
    target_rows, keeping only whole sets (a set is never split).

    This exists because a composite *set* of size k expands to k training rows at fine-tune time
    (`finetune.py::build_training_rows` emits one (composite_query, gold_skill_k, its_own_negatives)
    row per gold skill in the set, since each gold skill needs its own hard-negative pool) -- so
    "target_rows" (== COMPOSITE_TARGET_FRACTION of all training pairs, matching this module's own
    docstring "Target ~= 30% of training pairs") is a row count, not a set count. Passing it
    directly as `n_sets` to `sample_composite_sets` -- which is what an earlier version of
    `cmd_generate_composite` did -- silently overshoots by close to the average set size (~2.5x for
    sizes=(2, 3)): asking for N sets when N *rows* were wanted yields ~2.5*N rows, and also asks the
    generator for ~2.5x more LLM calls than the target implies.

    `sample_composite_sets(skills, n_sets, seed)` is monotonic in n_sets for a fixed seed (same
    `random.Random(seed)` draw stream, just extended: `eligible[i % len(eligible)]`'s round-robin
    group choice and the per-i rng draws for i < the smaller n_sets are unaffected by later i), so
    regrowing the estimate and re-calling from scratch is correct, not merely convenient -- it
    always returns a superset (as an ordered, deduplicated prefix-extension) of any run with a
    smaller n_sets.

    Terminates even if the corpus's eligible-group pool is too small to ever reach target_rows:
    the de-duplicated set count is bounded (finitely many (group, subset) combinations exist), so
    growing n_sets eventually stops adding new unique sets even though `out` (pre-dedup) keeps
    growing -- 3 consecutive no-progress rounds is treated as "pool exhausted" and breaks rather
    than looping forever chasing an unreachable target."""
    avg_size = sum(sizes) / len(sizes)
    n_sets = max(1, math.ceil(target_rows / avg_size))
    sets = sample_composite_sets(skills, n_sets, seed=seed, sizes=sizes)
    stagnant_rounds = 0
    while sum(len(s) for s in sets) < target_rows and stagnant_rounds < 3:
        prev_unique = len(sets)
        n_sets = max(n_sets + 1, math.ceil(n_sets * 1.2))
        sets = sample_composite_sets(skills, n_sets, seed=seed, sizes=sizes)
        stagnant_rounds = stagnant_rounds + 1 if len(sets) == prev_unique else 0
    out, total = [], 0
    for s in sets:
        if total >= target_rows:
            break
        out.append(s)
        total += len(s)
    return out


def sample_hard_negatives(skill_id: str, gold_ids: set, groups: dict,
                           leaf_of: dict, n: int, seed: int, fallback_ids: list = None) -> list:
    """n same-category siblings of skill_id that are not in gold_ids (the query's own answer
    set) — the HSR failure mode (SkillResolve: risky same-capability siblings).

    When the taxonomy leaf has fewer than n eligible siblings, tops up from `fallback_ids` (meant
    to be the whole corpus's skill-id list) so training rows still get a uniform negative count —
    finetune.py's MultipleNegativesRankingLoss batches need every row in a batch to carry the same
    number of text columns, so "fewer than n" is only ever a real answer when the WHOLE corpus
    (minus skill_id and gold_ids) has fewer than n skills, which cannot happen at these corpora's
    scale (501+). Never returns skill_id itself or a gold id."""
    leaf = leaf_of.get(skill_id)
    candidates = [sid for sid in groups.get(leaf, []) if sid != skill_id and sid not in gold_ids]
    if len(candidates) < n and fallback_ids:
        have = set(candidates) | {skill_id} | gold_ids
        pool = [sid for sid in fallback_ids if sid not in have]
        needed = n - len(candidates)
        if len(pool) <= needed:
            candidates = candidates + pool
        else:
            candidates = candidates + _sample_det(pool, needed, seed, f"{skill_id}:fallback")
    if len(candidates) <= n:
        return candidates
    return _sample_det(candidates, n, seed, skill_id)


def _sample_det(candidates: list, n: int, seed: int, key: str) -> list:
    h = random.Random(f"{seed}:{key}:negatives")
    return h.sample(candidates, n)


# ---------------------------------------------------------------------------
# leakage check — the family's own non-negotiable
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalise(s: str) -> str:
    """lowercase, NFKC-fold, strip punctuation, collapse whitespace — the same normalisation
    named in DENSE-PROGRAM.md v2.6's "Why E exists" paragraph, rule 1."""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = _PUNCT_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def leakage_check(generated_queries: list, labelled_queries: list) -> list:
    """Returns the list of generated queries (raw strings) that collide — exact string OR
    exact normalised-string match — with any labelled (dev/test) query. Empty list == clean.
    Cheap by construction (labelled set is at most a few thousand strings): builds both a raw
    and a normalised lookup set once, then a single pass over the generated queries."""
    raw_labelled = set(labelled_queries)
    norm_labelled = {normalise(q) for q in labelled_queries}
    violations = []
    for q in generated_queries:
        if q in raw_labelled or normalise(q) in norm_labelled:
            violations.append(q)
    return violations


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------

PER_SKILL_SYSTEM = (
    "You write short, realistic user requests for an internal tool-retrieval benchmark. "
    "Given the documentation for one internal tool (a \"skill\"), write natural-language tasks "
    "a person would type that this exact tool would be the right one to solve. "
    "Vary the phrasing and the scenario across the 5 queries — different users, different "
    "wording, different levels of detail. At least 2 of the 5 must NOT mention the tool's own "
    "name or a close variant of it; describe the need instead. "
    "Reply with ONLY a JSON object: {\"queries\": [\"...\", \"...\", \"...\", \"...\", \"...\"]}"
)

COMPOSITE_SYSTEM = (
    "You write short, realistic user requests for an internal tool-retrieval benchmark. "
    "Given documentation for two or three internal tools (\"skills\") that plausibly get used "
    "together on the same task, write ONE natural-language request that genuinely needs ALL of "
    "them — not a request satisfiable by just one. Do not enumerate the tools by name; describe "
    "the task. Reply with ONLY a JSON object: {\"query\": \"...\"}"
)


def per_skill_prompt(text: str) -> list:
    return [
        {"role": "system", "content": PER_SKILL_SYSTEM},
        {"role": "user", "content": f"Tool documentation:\n\n{text}"},
    ]


def composite_prompt(texts: list) -> list:
    joined = "\n\n---\n\n".join(f"Tool {i + 1} documentation:\n\n{t}" for i, t in enumerate(texts))
    return [
        {"role": "system", "content": COMPOSITE_SYSTEM},
        {"role": "user", "content": joined},
    ]


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_field(raw: str, key: str):
    """Best-effort JSON extraction: model output is asked to be JSON-only but sampling can add
    stray text around it; take the first {...} span and parse. Returns None on failure (caller
    logs it as a generator failure, per the family's "report generator failures honestly" rule
    — never silently drops nor fabricates)."""
    m = _JSON_OBJ_RE.search(raw or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    val = obj.get(key)
    if key == "queries":
        if isinstance(val, list) and all(isinstance(x, str) and x.strip() for x in val):
            return [x.strip() for x in val]
        return None
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


# ---------------------------------------------------------------------------
# generation loop (GPU venv only)
# ---------------------------------------------------------------------------

class Generator:
    """Thin batched wrapper over Qwen2.5-7B-Instruct. Import-time torch/transformers only
    inside this class — module import stays safe on any Python (tests, CI, leakage-check)."""

    def __init__(self, hf_id: str = MODEL_HF_ID, revision: str = MODEL_REVISION,
                 device: str = None, dtype=None, batch_size: int = 8):
        import torch
        import transformers
        self.torch = torch
        self.backend = "transformers"
        self.backend_version = transformers.__version__
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = dtype or (torch.bfloat16 if self.device == "cuda" else torch.float32)
        self.batch_size = batch_size
        self.hf_id = hf_id
        self.revision = revision
        local = MODELS_ROOT / hf_id.replace("/", "__") / revision
        source = str(local) if local.is_dir() else hf_id
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok_kwargs = {} if local.is_dir() else {"revision": revision}
        self.tokenizer = AutoTokenizer.from_pretrained(source, **tok_kwargs)
        self.tokenizer.padding_side = "left"
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        model_kwargs = {} if local.is_dir() else {"revision": revision}
        self.model = AutoModelForCausalLM.from_pretrained(
            source, dtype=self.dtype, device_map=self.device, **model_kwargs)
        self.model.eval()

    def generate_batch(self, message_lists: list, max_new_tokens: int, temperature: float,
                        top_p: float, seed: int) -> list:
        prompts = [self.tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
                   for m in message_lists]
        self.torch.manual_seed(seed)
        enc = self.tokenizer(prompts, return_tensors="pt", padding=True, truncation=True,
                              max_length=4096).to(self.model.device)
        with self.torch.no_grad():
            out = self.model.generate(
                **enc, max_new_tokens=max_new_tokens, do_sample=True,
                temperature=temperature, top_p=top_p,
                pad_token_id=self.tokenizer.pad_token_id)
        gen_only = out[:, enc["input_ids"].shape[1]:]
        return self.tokenizer.batch_decode(gen_only, skip_special_tokens=True)


class VLLMGenerator:
    """Same interface as Generator (generate_batch(message_lists, max_new_tokens, temperature,
    top_p, seed) -> list[str]), backed by vLLM's continuous-batching engine instead of a plain
    transformers.generate() loop — a naive HF batch waits for the single slowest sequence in the
    batch to finish (up to max_new_tokens), so it does not scale batch size into real throughput;
    vLLM's PagedAttention/continuous batching keeps the GPU fed as individual sequences finish.
    Import-time vllm only inside this class (mirrors Generator's own torch-import discipline) so
    module import — and every other subcommand — stays usable without vllm installed.

    Sampling is NOT bit-identical to Generator's at the same seed (different batching/kernel
    paths); the seed and sampling params are what this module pins and records, not bitwise
    reproducibility across backends (wsl-gpu-compute SKILL.md)."""

    def __init__(self, hf_id: str = MODEL_HF_ID, revision: str = MODEL_REVISION,
                 batch_size: int = 24, gpu_memory_utilization: float = 0.85):
        import vllm
        from vllm import LLM
        from transformers import AutoTokenizer
        self.backend = "vllm"
        self.backend_version = vllm.__version__
        self.batch_size = batch_size
        self.hf_id = hf_id
        self.revision = revision
        self.device = "cuda"
        self.dtype = "bfloat16"
        local = MODELS_ROOT / hf_id.replace("/", "__") / revision
        source = str(local) if local.is_dir() else hf_id
        extra = {} if local.is_dir() else {"revision": revision}
        self.tokenizer = AutoTokenizer.from_pretrained(source, **extra)
        self.llm = LLM(model=source, dtype="bfloat16",
                        gpu_memory_utilization=gpu_memory_utilization, **extra)

    def generate_batch(self, message_lists: list, max_new_tokens: int, temperature: float,
                        top_p: float, seed: int) -> list:
        from vllm import SamplingParams
        prompts = [self.tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
                   for m in message_lists]
        params = SamplingParams(max_tokens=max_new_tokens, temperature=temperature, top_p=top_p,
                                 seed=seed)
        # vLLM's offline LLM.generate() returns RequestOutputs in the same order as the input
        # prompt list (documented guarantee) — do not re-key by prompt text, which would silently
        # collapse two skills that happen to render an identical prompt.
        outputs = self.llm.generate(prompts, params, use_tqdm=False)
        return [o.outputs[0].text for o in outputs]


def make_generator(backend: str, batch_size: int):
    """Factory so cmd_generate_per_skill/cmd_generate_composite don't need to know which
    concrete class implements generate_batch(); --backend transformers|vllm (see module
    docstring: throughput note, batching)."""
    if backend == "vllm":
        return VLLMGenerator(batch_size=batch_size)
    return Generator(batch_size=batch_size)


def _require_gpu_venv(force_any_python: bool):
    if sys.executable != GPU_VENV_PYTHON and not force_any_python:
        raise SystemExit(
            f"synth_queries: run under {GPU_VENV_PYTHON} (or pass --force-any-python for a "
            f"tiny local smoke test)")


def _read_done_ids(out_path: Path, id_field) -> set:
    if not out_path.exists():
        return set()
    done = set()
    with out_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            done.add(id_field(rec))
    return done


def cmd_generate_per_skill(args):
    _require_gpu_venv(args.force_any_python)
    skills = _load_skills(args)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = _read_done_ids(out_path, lambda r: r["skill_id"])
    todo = [s for s in skills if s["id"] not in done][: args.limit] if args.limit else \
        [s for s in skills if s["id"] not in done]
    print(f"synth_queries per-skill: {len(done)} done, {len(todo)} remaining of {len(skills)}")
    if not todo:
        return
    gen = make_generator(args.backend, args.batch_size)
    _write_manifest(out_path, {
        "kind": "per_skill", "model_hf_id": gen.hf_id, "model_revision": gen.revision,
        "seed": args.seed, "temperature": args.temperature, "top_p": args.top_p,
        "max_new_tokens": args.max_new_tokens, "n_per_skill": PER_SKILL_N,
        "prompt_system": PER_SKILL_SYSTEM, "device": gen.device, "dtype": str(gen.dtype),
        "batch_size": args.batch_size, "generation_backend": gen.backend,
        "backend_version": gen.backend_version,
    })
    n_fail = 0
    t0 = time.time()
    with out_path.open("a", encoding="utf-8") as f:
        for start in range(0, len(todo), args.batch_size):
            batch = todo[start:start + args.batch_size]
            texts = [skill_text(s) for s in batch]
            msgs = [per_skill_prompt(t) for t in texts]
            raw = gen.generate_batch(msgs, args.max_new_tokens, args.temperature, args.top_p,
                                      seed=args.seed + start)
            for s, r in zip(batch, raw):
                queries = parse_json_field(r, "queries")
                rec = {"skill_id": s["id"], "raw": r if queries is None else None,
                       "queries": queries}
                if queries is None:
                    n_fail += 1
                f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            done_n = start + len(batch)
            print(f"  per-skill {done_n}/{len(todo)} "
                  f"({(time.time() - t0):.1f}s, {n_fail} parse failures so far)")
    print(f"per-skill generation done: {len(todo)} skills, {n_fail} parse failures, "
          f"{time.time() - t0:.1f}s total -> {out_path}")


def cmd_generate_composite(args):
    _require_gpu_venv(args.force_any_python)
    skills = _load_skills(args)
    by_id = {s["id"]: s for s in skills}
    if args.n:
        # explicit override: --n is a literal set count (test/smoke-run knob, unchanged meaning)
        sets = sample_composite_sets(skills, args.n, seed=args.seed)
    else:
        # default: --n omitted means "hit the ~30%-of-training-pairs target", and a *pair* is a
        # training ROW (finetune.py emits one row per gold skill in a set), not a set -- see
        # composite_sets_for_target_rows's docstring for why sets != rows here.
        target_rows = int(len(skills) * PER_SKILL_N * COMPOSITE_TARGET_FRACTION
                          / (1 - COMPOSITE_TARGET_FRACTION))
        sets = composite_sets_for_target_rows(skills, target_rows, seed=args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = _read_done_ids(out_path, lambda r: tuple(r["skill_ids"]))
    todo = [t for t in sets if t not in done]
    print(f"synth_queries composite: {len(sets)} sampled sets, {len(done)} done, "
          f"{len(todo)} remaining")
    if not todo:
        return
    gen = make_generator(args.backend, args.batch_size)
    _write_manifest(out_path, {
        "kind": "composite", "model_hf_id": gen.hf_id, "model_revision": gen.revision,
        "seed": args.seed, "temperature": args.temperature, "top_p": args.top_p,
        "max_new_tokens": args.max_new_tokens, "target_fraction": COMPOSITE_TARGET_FRACTION,
        "prompt_system": COMPOSITE_SYSTEM, "device": gen.device, "dtype": str(gen.dtype),
        "batch_size": args.batch_size, "generation_backend": gen.backend,
        "backend_version": gen.backend_version,
        "n_sets_sampled": len(sets),
    })
    n_fail = 0
    t0 = time.time()
    with out_path.open("a", encoding="utf-8") as f:
        for start in range(0, len(todo), args.batch_size):
            batch = todo[start:start + args.batch_size]
            texts = [[skill_text(by_id[sid]) for sid in t] for t in batch]
            msgs = [composite_prompt(ts) for ts in texts]
            raw = gen.generate_batch(msgs, args.max_new_tokens, args.temperature, args.top_p,
                                      seed=args.seed + start)
            for t, r in zip(batch, raw):
                query = parse_json_field(r, "query")
                rec = {"skill_ids": list(t), "raw": r if query is None else None,
                       "query": query}
                if query is None:
                    n_fail += 1
                f.write(json.dumps(rec, sort_keys=True) + "\n")
            f.flush()
            done_n = start + len(batch)
            print(f"  composite {done_n}/{len(todo)} "
                  f"({(time.time() - t0):.1f}s, {n_fail} parse failures so far)")
    print(f"composite generation done: {len(todo)} sets, {n_fail} parse failures, "
          f"{time.time() - t0:.1f}s total -> {out_path}")


def cmd_hard_negatives(args):
    """Emit exactly HARD_NEGATIVES_N negatives per gold skill (topped up from a repo-wide
    fallback pool when the same-taxonomy-leaf sibling pool runs short), so every training row —
    per-skill or composite — has a uniform negative count for finetune.py's batching.

    Per-skill records get a flat `hard_negatives` list (one positive == one skill).
    Composite records get `hard_negatives_by_skill: {skill_id: [neg, neg, neg]}` — one entry per
    gold skill in the composite, each computed excluding the *whole* composite's gold set, never
    just that skill's own id. This mirrors how composite rows are actually consumed at training
    time: one (composite_query, that_skill_text, its_own_negatives) row per gold skill, so
    negatives must be keyed per skill, not pooled and capped across the composite."""
    skills = _load_skills(args)
    groups = build_taxonomy_groups(skills)
    leaf_of = {s["id"]: taxonomy_leaf(s) for s in skills}
    all_ids = [s["id"] for s in skills]
    per_skill = [json.loads(l) for l in Path(args.per_skill_file).read_text().splitlines() if l]
    composite = []
    if args.composite_file and Path(args.composite_file).exists():
        composite = [json.loads(l) for l in Path(args.composite_file).read_text().splitlines()
                     if l]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for rec in per_skill:
            if not rec.get("queries"):
                continue
            gold = {rec["skill_id"]}
            negs = sample_hard_negatives(rec["skill_id"], gold, groups, leaf_of,
                                          HARD_NEGATIVES_N, args.seed, fallback_ids=all_ids)
            f.write(json.dumps({"skill_ids": [rec["skill_id"]], "hard_negatives": negs},
                                sort_keys=True) + "\n")
            n += 1
        for rec in composite:
            if not rec.get("query"):
                continue
            gold = set(rec["skill_ids"])
            per_skill_negs = {
                sid: sample_hard_negatives(sid, gold, groups, leaf_of, HARD_NEGATIVES_N,
                                            args.seed, fallback_ids=all_ids)
                for sid in rec["skill_ids"]
            }
            f.write(json.dumps({"skill_ids": rec["skill_ids"],
                                 "hard_negatives_by_skill": per_skill_negs},
                                sort_keys=True) + "\n")
            n += 1
    print(f"hard negatives: {n} records -> {out_path}")


def cmd_leakage_check(args):
    labelled = _load_labelled_queries(args)
    generated = []
    for path in args.generated_files:
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("queries"):
                generated.extend(rec["queries"])
            if rec.get("query"):
                generated.append(rec["query"])
    violations = leakage_check(generated, labelled)
    report = {"n_generated": len(generated), "n_labelled": len(labelled),
              "n_violations": len(violations), "violations": violations[:50]}
    print(json.dumps(report, indent=2, sort_keys=True))
    if violations:
        raise SystemExit(f"synth_queries: LEAKAGE — {len(violations)} generated queries collide "
                          f"with a labelled query")


def cmd_audit(args):
    """Sample N per-skill query groups for the manual good/repetitive/drifted table, with
    cheap heuristic pre-flags (near-duplicate n-gram overlap within a skill's own 5; zero
    content-word overlap with the skill's own name+description as a drift signal) to speed up
    the manual pass — the classification itself is not automated (no ground truth exists for
    "reads as a real user request")."""
    recs = [json.loads(l) for l in Path(args.generated_file).read_text().splitlines() if l]
    recs = [r for r in recs if r.get("queries")]
    rng = random.Random(args.seed)
    sample = rng.sample(recs, min(args.n, len(recs)))
    skills_by_id = {s["id"]: s for s in _load_skills(args)}
    rows = []
    for rec in sample:
        skill = skills_by_id.get(rec["skill_id"], {})
        name_words = set(normalise(skill.get("name", "")).split())
        desc_words = set(normalise(skill.get("description", "")).split())
        ctx_words = name_words | desc_words
        queries = rec["queries"]
        norm_qs = [normalise(q) for q in queries]
        dup_pairs = sum(1 for i in range(len(norm_qs)) for j in range(i + 1, len(norm_qs))
                         if _token_overlap(norm_qs[i], norm_qs[j]) > 0.6)
        name_copies = sum(1 for q in queries if skill.get("name", "").lower() in q.lower())
        zero_overlap = sum(1 for nq in norm_qs if not (set(nq.split()) & ctx_words))
        rows.append({
            "skill_id": rec["skill_id"], "skill_name": skill.get("name"), "queries": queries,
            "heuristic_dup_pairs": dup_pairs, "heuristic_name_copies": name_copies,
            "heuristic_zero_context_overlap": zero_overlap,
        })
    Path(args.out).write_text(json.dumps(rows, indent=2, sort_keys=True))
    print(f"audit sample: {len(rows)} skills -> {args.out}")
    print(f"  heuristic flags: {sum(r['heuristic_dup_pairs'] for r in rows)} dup-pair hits, "
          f"{sum(r['heuristic_name_copies'] for r in rows)} name-copy hits, "
          f"{sum(r['heuristic_zero_context_overlap'] for r in rows)} zero-context-overlap hits")


def _token_overlap(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ---------------------------------------------------------------------------
# corpus loading helpers
# ---------------------------------------------------------------------------

def _load_skills(args) -> list:
    if getattr(args, "skills_file", None):
        return json.loads(Path(args.skills_file).read_text())
    import corpora
    which = getattr(args, "corpus", "dev")
    if which == "dev":
        return corpora.load_skillret_dev()["skills"]
    if which == "test-a":
        return corpora.load_skillret()["skills"]
    if which == "test-b":
        return corpora.load_skillretbench()["skills"]
    raise SystemExit(f"synth_queries: unknown --corpus {which}")


def _load_labelled_queries(args) -> list:
    if getattr(args, "queries_file", None):
        return json.loads(Path(args.queries_file).read_text())
    import corpora
    out = []
    for which in (args.corpus or "").split(","):
        which = which.strip()
        if not which:
            continue
        if which == "dev":
            out.extend(q["query"] for q in corpora.load_skillret_dev()["queries"])
        elif which == "test-a":
            out.extend(q["query"] for q in corpora.load_skillret()["queries"])
        elif which == "test-b":
            out.extend(q["query"] for q in corpora.load_skillretbench()["queries"])
        else:
            raise SystemExit(f"synth_queries: unknown --corpus entry {which!r}")
    return out


def _write_manifest(out_path: Path, manifest: dict):
    manifest_path = out_path.with_suffix(out_path.suffix + ".manifest.json")
    existing = []
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        if not isinstance(existing, list):
            existing = [existing]
    existing.append({**manifest, "written_at": time.time()})
    manifest_path.write_text(json.dumps(existing, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--corpus", default="dev", choices=["dev", "test-a", "test-b"])
        sp.add_argument("--skills-file", default=None,
                         help="override: JSON list of skill dicts (tests / fixtures)")
        sp.add_argument("--seed", type=int, default=20260905)

    g1 = sub.add_parser("generate-per-skill")
    add_common(g1)
    g1.add_argument("--out", required=True)
    g1.add_argument("--batch-size", type=int, default=24)
    g1.add_argument("--backend", choices=["transformers", "vllm"], default="transformers",
                     help="vllm's continuous batching hits target throughput; a naive "
                          "transformers.generate() batch waits for its slowest sequence")
    g1.add_argument("--max-new-tokens", type=int, default=320)
    g1.add_argument("--temperature", type=float, default=0.8)
    g1.add_argument("--top-p", type=float, default=0.9)
    g1.add_argument("--limit", type=int, default=None)
    g1.add_argument("--force-any-python", action="store_true")
    g1.set_defaults(func=cmd_generate_per_skill)

    g2 = sub.add_parser("generate-composite")
    add_common(g2)
    g2.add_argument("--out", required=True)
    g2.add_argument("--n", type=int, default=None, help="override auto target-fraction count")
    g2.add_argument("--batch-size", type=int, default=24)
    g2.add_argument("--backend", choices=["transformers", "vllm"], default="transformers",
                     help="vllm's continuous batching hits target throughput; a naive "
                          "transformers.generate() batch waits for its slowest sequence")
    g2.add_argument("--max-new-tokens", type=int, default=160)
    g2.add_argument("--temperature", type=float, default=0.8)
    g2.add_argument("--top-p", type=float, default=0.9)
    g2.add_argument("--force-any-python", action="store_true")
    g2.set_defaults(func=cmd_generate_composite)

    g3 = sub.add_parser("hard-negatives")
    add_common(g3)
    g3.add_argument("--per-skill-file", required=True)
    g3.add_argument("--composite-file", default=None)
    g3.add_argument("--out", required=True)
    g3.set_defaults(func=cmd_hard_negatives)

    g4 = sub.add_parser("leakage-check")
    g4.add_argument("--corpus", default="dev")
    g4.add_argument("--queries-file", default=None,
                     help="override: JSON list of query strings (tests / fixtures)")
    g4.add_argument("generated_files", nargs="+")
    g4.set_defaults(func=cmd_leakage_check)

    g5 = sub.add_parser("audit")
    add_common(g5)
    g5.add_argument("--generated-file", required=True)
    g5.add_argument("--n", type=int, default=100)
    g5.add_argument("--out", required=True)
    g5.set_defaults(func=cmd_audit)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
