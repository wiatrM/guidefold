"""encode.py — one interface over every teacher encoder used in the bake-off.

Tier 2 only (ROUTER-SPEC-v2.md): this module imports torch/transformers/sentence-
transformers freely. It is never imported by `skills/guidefold/scripts/guidefold`.

    Encoder(hf_id, revision).encode(texts) -> np.ndarray[float32]   # unit-normalised rows

Pooling is whatever each model's own repo declares, not a project-wide choice:
  * `Qwen/Qwen3-Embedding-0.6B`            sentence-transformers, last-token pooling + L2 normalize
                                            (its own `1_Pooling/config.json`: pooling_mode_lasttoken).
  * `BAAI/bge-m3`                          sentence-transformers, CLS pooling + L2 normalize
                                            (its own `1_Pooling/config.json`: pooling_mode_cls_token).
  * `ThakiCloud/SKILLRET-Embedding-0.6B`   sentence-transformers, last-token pooling + L2 normalize
                                            (its own `1_Pooling/config.json`: pooling_mode: lasttoken).
  * `pipizhao/SkillRouter-Embedding-0.6B`  NOT shipped with a sentence-transformers config (no
                                            modules.json/1_Pooling in the repo) -> loaded as a plain
                                            `AutoModel` + the exact last-token pooling + L2-normalize
                                            recipe published in the model's own README "How to Use".

Asymmetric query/document prompts are applied only where the model's own README documents them
(see QUERY_PROMPTS below); `bge-m3`'s README states explicitly it needs no query instruction.

Every encoding is cached to `.bakeoff-cache/<hf_id>__<sha>/<hash>.npy` (hash covers the exact text
and whether it was encoded as a query, since asymmetric models produce a different vector for the
same string encoded as a query vs. as a document) so reruns are cheap and, together with `distill.py`
fixing every other source of nondeterminism, reproducible.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

import numpy as np

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import torch  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

CACHE_ROOT = Path(__file__).resolve().parent / ".bakeoff-cache"

# Models that ship their own sentence-transformers config (modules.json + 1_Pooling) and can be
# loaded directly with SentenceTransformer(). Anything not in this set falls back to a plain
# transformers AutoModel with hand-rolled last-token pooling (pipizhao/SkillRouter-Embedding-0.6B).
_SENTENCE_TRANSFORMERS_MODELS = {
    "Qwen/Qwen3-Embedding-0.6B",
    "BAAI/bge-m3",
    "ThakiCloud/SKILLRET-Embedding-0.6B",
}

# Query-side instruction prefixes, verbatim from each model's own README "How to Use" /
# config_sentence_transformers.json. `None` means the model's own docs say no prefix is needed.
# Never applied to documents/skills — only to `encode(texts, is_query=True)` calls.
QUERY_PROMPTS: dict[str, Optional[str]] = {
    # Qwen3-Embedding-0.6B ships this as its ST "query" prompt (config_sentence_transformers.json).
    "Qwen/Qwen3-Embedding-0.6B": (
        "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:"
    ),
    # bge-m3 README, "Usage" section: "The only difference is that the BGE-M3 model no longer
    # requires adding instructions to the queries."
    "BAAI/bge-m3": None,
    # SKILLRET-Embedding-0.6B README "How to Use" overrides its generic ST default prompt with
    # this skill-retrieval-specific one.
    "ThakiCloud/SKILLRET-Embedding-0.6B": (
        "Instruct: a skill search query, retrieve relevant skills that match the query\nQuery: "
    ),
    # pipizhao/SkillRouter-Embedding-0.6B README "How to Use", QUERY_INSTRUCTION constant.
    "pipizhao/SkillRouter-Embedding-0.6B": (
        "Instruct: Given a task description, retrieve the most relevant skill document that would "
        "help an agent complete the task\nQuery:"
    ),
}


def _cache_dir(hf_id: str, revision: str) -> Path:
    return CACHE_ROOT / f"{hf_id}__{revision}"


def _cache_key(text: str, is_query: bool) -> str:
    payload = json.dumps({"text": text, "is_query": is_query}, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _last_token_pool(last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """Verbatim from pipizhao/SkillRouter-Embedding-0.6B's README (also how Qwen3-Embedding-style
    causal-LM embedders pool without a sentence-transformers wrapper)."""
    left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
    if left_padding:
        return last_hidden_states[:, -1]
    seq_lens = attention_mask.sum(dim=1) - 1
    batch = last_hidden_states.shape[0]
    return last_hidden_states[torch.arange(batch, device=last_hidden_states.device), seq_lens]


class Encoder:
    """Encoder(hf_id, revision).encode(texts, is_query=False) -> np.ndarray[float32], unit rows."""

    def __init__(self, hf_id: str, revision: str, batch_size: int = 8):
        self.hf_id = hf_id
        self.revision = revision
        self.batch_size = batch_size
        self.cache_dir = _cache_dir(hf_id, revision)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._backend = "sentence-transformers" if hf_id in _SENTENCE_TRANSFORMERS_MODELS else "transformers"
        self._model = None
        self._tokenizer = None

    # -- lazy model load: an Encoder can be constructed (e.g. to check the cache) without paying
    #    the torch import + weight-load cost until encode() actually needs the network on a miss.
    def _ensure_loaded(self):
        if self._model is not None:
            return
        torch.set_num_threads(max(1, os.cpu_count() or 1))
        if self._backend == "sentence-transformers":
            self._model = SentenceTransformer(
                self.hf_id, revision=self.revision, device="cpu", trust_remote_code=True
            )
            self._model.eval()
        else:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.hf_id, revision=self.revision, trust_remote_code=True, padding_side="left"
            )
            self._model = AutoModel.from_pretrained(
                self.hf_id, revision=self.revision, trust_remote_code=True, dtype=torch.float32
            )
            self._model.eval().to("cpu")

    def _encode_uncached(self, texts: list[str], is_query: bool) -> np.ndarray:
        self._ensure_loaded()
        prompt = QUERY_PROMPTS.get(self.hf_id) if is_query else None
        if self._backend == "sentence-transformers":
            with torch.no_grad():
                vecs = self._model.encode(
                    texts,
                    batch_size=self.batch_size,
                    prompt=prompt,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
            return np.asarray(vecs, dtype=np.float32)
        # raw transformers path: pipizhao/SkillRouter-Embedding-0.6B
        prefixed = [(prompt + " " + t if prompt else t) for t in texts]
        out_chunks = []
        for i in range(0, len(prefixed), self.batch_size):
            chunk = prefixed[i : i + self.batch_size]
            encoded = self._tokenizer(
                chunk, padding=True, truncation=True, max_length=4096, return_tensors="pt"
            )
            with torch.no_grad():
                outputs = self._model(**encoded)
                pooled = _last_token_pool(outputs.last_hidden_state, encoded["attention_mask"])
                pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            out_chunks.append(pooled.numpy().astype(np.float32))
        return np.concatenate(out_chunks, axis=0) if out_chunks else np.zeros((0, 0), dtype=np.float32)

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        """Returns float32 rows, one per input text, unit-normalised (L2 == 1). Cached on disk."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        keys = [_cache_key(t, is_query) for t in texts]
        paths = [self.cache_dir / f"{k}.npy" for k in keys]
        rows: list[Optional[np.ndarray]] = [None] * len(texts)
        miss_idx = []
        for i, p in enumerate(paths):
            if p.exists():
                rows[i] = np.load(p)
            else:
                miss_idx.append(i)
        if miss_idx:
            fresh = self._encode_uncached([texts[i] for i in miss_idx], is_query)
            for j, i in enumerate(miss_idx):
                rows[i] = fresh[j]
                np.save(paths[i], fresh[j])
        out = np.stack(rows, axis=0).astype(np.float32)
        # Both backends already normalise, but re-normalise explicitly so "unit length" is a
        # guarantee of this interface, not an assumption about upstream library behaviour.
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


if __name__ == "__main__":
    import sys
    import time

    hf_id = sys.argv[1] if len(sys.argv) > 1 else "BAAI/bge-m3"
    revision = sys.argv[2] if len(sys.argv) > 2 else "5617a9f61b028005a4858fdac845db406aefb181"
    enc = Encoder(hf_id, revision)
    t0 = time.time()
    vecs = enc.encode(["migrate a postgres schema safely", "kafka consumer group checkpointing"])
    print(vecs.shape, vecs.dtype, f"{time.time() - t0:.2f}s", "norms:", np.linalg.norm(vecs, axis=1))
