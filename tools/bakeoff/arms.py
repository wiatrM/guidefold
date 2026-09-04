"""arms.py — the E1.3 bake-off retrieval arms (ROUTER-SPEC-v2.md, "E1.3 bake-off arms").

Every arm has the same shape: `arm(query: str, corpus: list[SkillRecord], limit=50) -> list[str]`,
a ranked list of URNs (highest-relevance first), deduplicated. `ARMS` at the bottom maps the
spec's arm names to these callables so a later evaluation pass (golden set, not built in this
phase) can iterate them uniformly.

  B0   `skills/guidefold/scripts/guidefold`'s own `rank_cards()`, called unmodified.
  B1   field-weighted BM25Okapi over name/description/digest/triggers/body (own implementation,
       weights from docs/DESIGN.md §7: name x3, triggers x2.5, description x2, digest x1.5, body x1;
       k1=1.2, b=0.75, tokenized with `tokenizer.tokenize`).
  B2a  dense, generic teacher: Qwen/Qwen3-Embedding-0.6B, encoded fresh (no static table).
  B2b  dense, generic teacher: BAAI/bge-m3, encoded fresh.
  B3a  dense, skill-tuned teacher: pipizhao/SkillRouter-Embedding-0.6B, encoded fresh.
  B3b  dense, skill-tuned teacher: ThakiCloud/SKILLRET-Embedding-0.6B, encoded fresh.
  B4   dense, the tier-1 STATIC STUDENT TABLE (see distill.py) alone — this is the arm the shipped
       hook actually runs at query time. Built via `distill.distill()` (same tokenizer, same
       table used to build both words.bin and vectors.i8 — the spec's "single most important
       rule"), then scored with the exact int8 dot product / integer |d|^2 the hook will use,
       just without the hook's stdlib-only micro-optimizations (this file is tier 2 and may use
       numpy freely; the ranking produced is bit-for-bit the same order a pure-integer
       cross-multiplying comparator would produce, since both are monotonic in dot/sqrt(d2)).
  B5   B1 + B4 fused by reciprocal rank fusion (k=60) — the candidate shipped configuration.
  B6   B5's top-20 reranked by pipizhao/SkillRouter-Reranker-0.6B's yes/no logit difference (E1.6).

  B1+  NOT IMPLEMENTED IN THIS PHASE. Extension point: BM25 over teacher-generated query
       expansions (ADR-0009 §1 -- "model-generated expansion per skill ... cached by body hash").
       It would slot in next to `arm_b1` as `arm_b1_plus(query, corpus, expansions, ...)`, reusing
       `BM25Index` unchanged and only adding an expansion-lookup step before tokenizing the query.
       Deferred because it needs a CI-time expansion-generation step (an LLM call cached by body
       hash) that is out of scope for a corpus-and-arms-only phase with no golden set to justify it.
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import distill  # noqa: E402
from corpus import SkillRecord, cli, load_corpus  # noqa: E402
from encode import Encoder  # noqa: E402
from tokenizer import tokenize  # noqa: E402

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "examples" / "monorepo"
DEFAULT_NODE = "_root"  # B0 has no cwd in a bake-off; searches from the broadest scope.
DEFAULT_LIMIT = 50
RRF_K = 60

# --------------------------------------------------------------------------------------
# B0 — the current CLI, unmodified
# --------------------------------------------------------------------------------------
def arm_b0(query: str, corpus: list, limit: int = DEFAULT_LIMIT, node: str = DEFAULT_NODE) -> list:
    """`cli.rank_cards()` called exactly as `cmd_find` calls it -- no reimplementation."""
    cfg = cli.load_map(FIXTURE_ROOT)
    reg = cli.registry_for(cfg, FIXTURE_ROOT)
    cards = cli.rank_cards(reg, node, query, limit)
    seen, urns = set(), []
    for c in cards:
        if c["urn"] not in seen:
            seen.add(c["urn"])
            urns.append(c["urn"])
    return urns


# --------------------------------------------------------------------------------------
# B1 — field-weighted BM25
# --------------------------------------------------------------------------------------
FIELD_WEIGHTS = {"name": 3.0, "triggers": 2.5, "description": 2.0, "digest": 1.5, "body": 1.0}
BM25_K1 = 1.2
BM25_B = 0.75


class BM25Index:
    """BM25F-lite: fields are combined into one weighted term-frequency / weighted-length pseudo
    document per skill before the standard Okapi BM25 formula is applied. Weights and k1/b per
    docs/DESIGN.md §7 and ROUTER-SPEC-v2.md ("B1 field-weighted BM25 ... k1=1.2 b=0.75")."""

    def __init__(self, corpus: list, field_weights=None, k1: float = BM25_K1, b: float = BM25_B):
        self.corpus = corpus
        self.field_weights = field_weights or FIELD_WEIGHTS
        self.k1 = k1
        self.b = b
        self.doc_term_freqs: list = []
        self.doc_lens: list = []
        df: Counter = Counter()
        for record in corpus:
            tf: Counter = Counter()
            length = 0.0
            for field_name, text in record.fields_text().items():
                weight = self.field_weights.get(field_name, 1.0)
                words = tokenize(text)
                length += weight * len(words)
                for w in words:
                    tf[w] += weight
            self.doc_term_freqs.append(tf)
            self.doc_lens.append(length)
            for w in tf:
                df[w] += 1
        self.df = df
        self.n = len(corpus)
        self.avgdl = (sum(self.doc_lens) / self.n) if self.n else 0.0

    def _idf(self, term: str) -> float:
        n_t = self.df.get(term, 0)
        return math.log(1 + (self.n - n_t + 0.5) / (n_t + 0.5))

    def scores(self, query_terms: list) -> list:
        out = [0.0] * self.n
        for term in query_terms:
            idf = self._idf(term)
            if idf <= 0:
                continue
            for i in range(self.n):
                tf = self.doc_term_freqs[i].get(term)
                if not tf:
                    continue
                dl = self.doc_lens[i]
                norm = self.k1 * (1 - self.b + self.b * (dl / self.avgdl if self.avgdl else 1.0))
                out[i] += idf * (tf * (self.k1 + 1)) / (tf + norm)
        return out


_BM25_CACHE: dict = {}


def _corpus_key(corpus: list) -> tuple:
    return tuple(r.urn for r in corpus)


def _bm25_index(corpus: list) -> BM25Index:
    key = _corpus_key(corpus)
    idx = _BM25_CACHE.get(key)
    if idx is None:
        idx = BM25Index(corpus)
        _BM25_CACHE[key] = idx
    return idx


def arm_b1(query: str, corpus: list, limit: int = DEFAULT_LIMIT) -> list:
    idx = _bm25_index(corpus)
    scores = idx.scores(tokenize(query))
    ranked = sorted(range(idx.n), key=lambda i: (-scores[i], corpus[i].urn))
    return [corpus[i].urn for i in ranked if scores[i] > 0][:limit]


# --------------------------------------------------------------------------------------
# B2 / B3 — dense with the teacher directly (no static table)
# --------------------------------------------------------------------------------------
_ENCODER_CACHE: dict = {}
_DOC_VECTOR_CACHE: dict = {}


def _encoder(hf_id: str, revision: str) -> Encoder:
    key = (hf_id, revision)
    if key not in _ENCODER_CACHE:
        _ENCODER_CACHE[key] = Encoder(hf_id, revision)
    return _ENCODER_CACHE[key]


def _dense_doc_vectors(hf_id: str, revision: str, corpus: list) -> np.ndarray:
    key = (hf_id, revision, _corpus_key(corpus))
    if key not in _DOC_VECTOR_CACHE:
        enc = _encoder(hf_id, revision)
        _DOC_VECTOR_CACHE[key] = enc.encode([r.concat_text() for r in corpus], is_query=False)
    return _DOC_VECTOR_CACHE[key]


def _dense_rank(hf_id: str, revision: str, query: str, corpus: list, limit: int) -> list:
    doc_vecs = _dense_doc_vectors(hf_id, revision, corpus)
    qvec = _encoder(hf_id, revision).encode([query], is_query=True)[0]
    scores = doc_vecs @ qvec  # both unit-normalised -> dot product == cosine
    order = sorted(range(len(corpus)), key=lambda i: (-scores[i], corpus[i].urn))
    return [corpus[i].urn for i in order[:limit]]


QWEN3_EMBEDDING = ("Qwen/Qwen3-Embedding-0.6B", "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3")
BGE_M3 = ("BAAI/bge-m3", "5617a9f61b028005a4858fdac845db406aefb181")
SKILLROUTER_EMBEDDING = ("pipizhao/SkillRouter-Embedding-0.6B", "c03c9bcee9fce92ab0262bb6dcf54d174a8ba558")
SKILLRET_EMBEDDING = ("ThakiCloud/SKILLRET-Embedding-0.6B", "0e10886e80a0aacc9efddc28282a258e2ab7eae1")
SKILLROUTER_RERANKER = ("pipizhao/SkillRouter-Reranker-0.6B", "78986e1142d12857cfd85b8005e62902cd42d858")


def arm_b2a(query: str, corpus: list, limit: int = DEFAULT_LIMIT) -> list:
    return _dense_rank(*QWEN3_EMBEDDING, query, corpus, limit)


def arm_b2b(query: str, corpus: list, limit: int = DEFAULT_LIMIT) -> list:
    return _dense_rank(*BGE_M3, query, corpus, limit)


def arm_b3a(query: str, corpus: list, limit: int = DEFAULT_LIMIT) -> list:
    return _dense_rank(*SKILLROUTER_EMBEDDING, query, corpus, limit)


def arm_b3b(query: str, corpus: list, limit: int = DEFAULT_LIMIT) -> list:
    return _dense_rank(*SKILLRET_EMBEDDING, query, corpus, limit)


# --------------------------------------------------------------------------------------
# B4 — dense with the static student table ALONE (the one the hook will actually run)
# --------------------------------------------------------------------------------------
DEFAULT_STUDENT_TEACHER = SKILLROUTER_EMBEDDING  # a phase-1 default, NOT the bake-off's chosen
# winner -- ADR-0015's bake-off between SkillRouter-Embedding and SKILLRET-Embedding is a golden-
# set question this phase explicitly does not answer. Override via `teacher=` if needed.

_STUDENT_CACHE: dict = {}


def _student_table(corpus: list, teacher=DEFAULT_STUDENT_TEACHER, dims: int = distill.DEFAULT_DIMS) -> dict:
    key = (teacher, dims, _corpus_key(corpus))
    if key not in _STUDENT_CACHE:
        out_dir = distill.BUILD_ROOT / ("_b4_student__" + teacher[0].replace("/", "__"))
        result = distill.distill(corpus, teacher[0], teacher[1], out_dir, dims=dims, write_teacher=False)
        words = distill.read_words_bin(result["words_bin"])
        vectors = distill.read_vectors_i8(result["vectors_i8"])
        _STUDENT_CACHE[key] = {
            "word_table_i8": words["table"],
            "id_of": {w: i for i, w in enumerate(words["words"])},
            "skill_table_i8": vectors["table"],
            "skill_d2": vectors["d2"],
            "urns": vectors["urns"],
        }
    return _STUDENT_CACHE[key]


def arm_b4(query: str, corpus: list, limit: int = DEFAULT_LIMIT, teacher=DEFAULT_STUDENT_TEACHER) -> list:
    table = _student_table(corpus, teacher)
    dims = table["word_table_i8"].shape[1]
    q = np.zeros(dims, dtype=np.int64)
    for word in tokenize(query):
        wid = table["id_of"].get(word)
        if wid is not None:
            q += table["word_table_i8"][wid].astype(np.int64)
    dots = table["skill_table_i8"].astype(np.int64) @ q  # exact integer dot products
    d2 = table["skill_d2"].astype(np.int64)
    urns = table["urns"]

    def rank_key(i):
        # ranking by dot / sqrt(d2) is the same order the spec's pure-integer cross-multiplying
        # comparator (a.q * |b|^2 vs b.q * |a|^2) produces -- |q|^2 is a positive constant factor
        # shared by every candidate for this query, so it never changes relative order.
        cos = (dots[i] / math.sqrt(d2[i])) if d2[i] > 0 else 0.0
        return (-cos, urns[i])

    order = sorted(range(len(urns)), key=rank_key)
    return [urns[i] for i in order[:limit]]


# --------------------------------------------------------------------------------------
# B5 — B1 + B4 fused by RRF (the candidate shipped configuration)
# --------------------------------------------------------------------------------------
def _rrf_fuse(*ranked_lists, k: int = RRF_K) -> dict:
    scores: dict = {}
    for ranked in ranked_lists:
        for rank, urn in enumerate(ranked, start=1):
            scores[urn] = scores.get(urn, 0.0) + 1.0 / (k + rank)
    return scores


def arm_b5(query: str, corpus: list, limit: int = DEFAULT_LIMIT) -> list:
    b1 = arm_b1(query, corpus, limit=DEFAULT_LIMIT)
    b4 = arm_b4(query, corpus, limit=DEFAULT_LIMIT)
    fused = _rrf_fuse(b1, b4)
    order = sorted(fused, key=lambda u: (-fused[u], u))
    return order[:limit]


# --------------------------------------------------------------------------------------
# B6 — B5 top-20 reranked with SkillRouter-Reranker-0.6B (E1.6)
# --------------------------------------------------------------------------------------
class Reranker:
    """pipizhao/SkillRouter-Reranker-0.6B's own documented prompt template and yes/no logit-
    difference scoring, verbatim from its README "How to Use"."""

    _SYSTEM_PREFIX = (
        '<|im_start|>system\nJudge whether the Document meets the requirements '
        'based on the Query and the Instruct provided. Note that the answer can '
        'only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
    )
    _ASSISTANT_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
    _INSTRUCTION = (
        "Given a task description, judge whether the skill document is relevant "
        "and useful for completing the task"
    )

    def __init__(self, hf_id: str = SKILLROUTER_RERANKER[0], revision: str = SKILLROUTER_RERANKER[1]):
        self.hf_id = hf_id
        self.revision = revision
        self._tokenizer = None
        self._model = None
        self._token_yes = None
        self._token_no = None

    def _ensure_loaded(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(self.hf_id, revision=self.revision, padding_side="left")
        self._model = AutoModelForCausalLM.from_pretrained(self.hf_id, revision=self.revision, dtype=torch.float32)
        self._model.eval().to("cpu")
        self._token_yes = self._tokenizer.convert_tokens_to_ids("yes")
        self._token_no = self._tokenizer.convert_tokens_to_ids("no")

    def score(self, query: str, record: SkillRecord, desc_max: int = 500, body_max: int = 2000,
              max_length: int = 4096) -> float:
        import torch

        self._ensure_loaded()
        doc_text = f"{record.name} | {record.description[:desc_max]} | {record.body[:body_max]}"
        prompt = f"<Instruct>: {self._INSTRUCTION}\n\n<Query>: {query}\n\n<Document>: {doc_text}"
        prefix_tokens = self._tokenizer.encode(self._SYSTEM_PREFIX, add_special_tokens=False)
        suffix_tokens = self._tokenizer.encode(self._ASSISTANT_SUFFIX, add_special_tokens=False)
        body_tokens = self._tokenizer(
            prompt, padding=False, truncation=True,
            max_length=max_length - len(prefix_tokens) - len(suffix_tokens),
            return_attention_mask=False,
        )["input_ids"]
        input_ids = torch.tensor([prefix_tokens + body_tokens + suffix_tokens])
        attention_mask = torch.ones_like(input_ids)
        with torch.no_grad():
            logits = self._model(input_ids=input_ids, attention_mask=attention_mask).logits[:, -1, :]
        return (logits[:, self._token_yes] - logits[:, self._token_no]).item()


_RERANKER: Reranker = None


def _reranker() -> Reranker:
    global _RERANKER
    if _RERANKER is None:
        _RERANKER = Reranker()
    return _RERANKER


def arm_b6(query: str, corpus: list, limit: int = 4) -> list:
    candidates = arm_b5(query, corpus, limit=20)
    by_urn = {r.urn: r for r in corpus}
    reranker = _reranker()
    scored = [(reranker.score(query, by_urn[u]), u) for u in candidates if u in by_urn]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [u for _, u in scored[:limit]]


ARMS = {
    "B0": arm_b0,
    "B1": arm_b1,
    "B2a": arm_b2a,
    "B2b": arm_b2b,
    "B3a": arm_b3a,
    "B3b": arm_b3b,
    "B4": arm_b4,
    "B5": arm_b5,
    "B6": arm_b6,
}


if __name__ == "__main__":
    import time

    query = sys.argv[1] if len(sys.argv) > 1 else "add RBAC"
    corpus = load_corpus()
    print(f"query: {query!r}  ({len(corpus)} skills)\n")
    for name, arm in ARMS.items():
        t0 = time.time()
        ranked = arm(query, corpus)
        elapsed = time.time() - t0
        print(f"{name} ({elapsed:.3f}s):")
        for urn in ranked[:5]:
            print(f"  {urn}")
        print()
