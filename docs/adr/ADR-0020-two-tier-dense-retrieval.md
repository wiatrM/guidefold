# ADR-0020: Two-tier dense retrieval — a distilled static table in the artifact, neural models in CI only

**Status:** Accepted · 2026-09-04
**Amends:** [ADR-0015](ADR-0015-self-hosted-skill-tuned-models.md) — the winning encoder no longer
serves hook queries from a GPU endpoint; it serves CI and `find --experimental` only.
**Builds on:** [ADR-0009](ADR-0009-hybrid-retrieval-client-side.md) (hybrid retrieval, client side),
[ADR-0003](ADR-0003-bootstrap-skill-cli-not-mcp.md) (CLI, not MCP).

## Context

Three requirements collide.

1. `skills/guidefold/scripts/guidefold` ships inside the skill ZIP, so it is a single file with
   **stdlib + PyYAML only**. No torch, no onnxruntime, no numpy.
2. MVP story E1.5 requires the hook pipeline to run **BM25 + dense (local)** within **300 ms warm**,
   and to produce **identical output for identical `(prompt, cwd, sha)`**.
3. MVP story E1.3 selects a **0.6B** encoder (Qwen3-Embedding-0.6B, bge-m3, SkillRouter-Embedding-0.6B,
   SKILLRET-Embedding-0.6B) as the index embedder.

A hook invocation is a **fresh process**: there is no resident model and no warm state beyond the OS
page cache. A single 0.6B forward pass on a laptop CPU costs 300–500 ms on its own, before process
start-up. Requirements 1 and 3 cannot both be met at query time.

Options considered:

- **Sidecar daemon** (ADR-0015's laptop fallback). Rejected: routing output would depend on whether
  the daemon happens to be running, which destroys requirement 2's determinism claim, and it puts
  torch plus 1.2 GB of weights on every engineer's laptop.
- **Optional onnxruntime dependency.** Rejected: still misses the 300 ms budget in a cold process,
  and an optional dependency that changes results makes the same commit route differently on two machines.
- **BM25 only.** Honest and simple, but abandons the local dense leg that ADR-0009 §1 and E1.5 commit to.

## Decision

**Two tiers.**

**Tier 1 — a distilled static table, shipped inside the index artifact.** In CI, the teacher encoder
chosen by the bake-off embeds each word of the corpus vocabulary; the result is reduced with PCA to
**256 dimensions**, Zipf-weighted, and quantised to **int8** as `words.bin`. At query time the CLI
tokenises the prompt and sums the corresponding int8 word vectors. This is real dense retrieval —
vocabulary mismatch ("outage" ≈ "incident", "RBAC" ≈ "authorization") is handled — in pure-Python
integer arithmetic, in microseconds, with no model present.

**The skill vectors in `vectors.i8` are produced by the same static table and the same tokenizer the
hook uses.** Embedding documents with the teacher while embedding queries with the student would put
the two sides in different vector spaces; RRF would mask the resulting noise behind BM25, and the
bake-off — which evaluates the teacher — would never detect it. Teacher-space vectors, when kept, live
in a separate `teacher.f16` file that the hook never opens.

**Tier 2 — the teacher encoder and the cross-encoder reranker.** Used in CI (distillation, index
build, bake-off) and behind `find --experimental` in shadow mode (E1.6). Lives under `tools/`, may
depend on torch, and is never imported by the shipped CLI.

**Determinism is achieved with integers, not with rounding.** BM25 IDF and field weights are
precomputed in CI as scaled integers, because `math.log` is libm-dependent and differs by 1 ulp
between glibc, musl and macOS. int8·int8 dot products are exact in Python integers; cosine is
scale-invariant, so candidates are compared by cross-multiplication rather than by dividing by a
float norm. One tokenizer — NFC, ASCII-only lowercase, `[a-z0-9]+` — is shared by CI and hook, since
stdlib `re` has no `\p{L}` classes and `str.lower()` shifts with the Unicode database between Python
releases. `cwd → node` resolves from the artifact's `nodes.json`, never from the working-tree
`guidefold.yaml`, so an uncommitted edit cannot silently change routing.

**The dense channel is on probation.** `w_dense` is a weight in the index manifest, and the bake-off
must earn it: ship `w_dense > 0` only if BM25 + static dense beats the better BM25 arm by **≥ 3
percentage points Recall@8 with no regression on the sibling-ambiguity or no-applicable strata**.
Otherwise the artifact ships `w_dense = 0` and the report says so.

## Consequences

**Good.** The shipped CLI keeps its stdlib-only constraint and its 300 ms budget with room to spare
(measured budget at 256 dims: ~210 ms including interpreter start-up). Routing is bit-reproducible
across operating systems and Python versions. The teacher can be replaced without touching the CLI —
a new index artifact is the whole migration. The 15 MB cap at 2k skills closes: ~4.7 MB for postings,
cards, graph and skill vectors, leaving room for a ~40k-word table at 256 dims.

**Bad.** Three models to reason about (teacher, distilled student, reranker), and E1.3 measures a
teacher the hook never runs — so the bake-off must carry an explicit static-student arm or it
measures the wrong thing. Static mean-pooled vectors are weakest exactly where the golden set is
heaviest (sibling ambiguity, multi-skill), which is why the probation gate above exists. Distillation
is per-word rather than per-BPE-token, so multi-word technical phrases are not represented directly;
BM25 carries them.

**Consequently.** ADR-0015's GPU-endpoint serving path is amended to `--experimental` only. The index
artifact format (E1.4) becomes the contract between CI and the hook, and `index --check` in CI is what
keeps them honest.

## Rejected alternative worth recording

Reverse personalised PageRank is required by E1.5 and is implemented, but review found that on the
current graph (out-degree ≈ 0.6; `refines`/`replaces` edges were near-absent when this was written —
the fixture has since grown 8 `refines` and 1 `replaces` edge, still outweighed by `requires` at
`edge.requires=100` vs `edge.refines=60`, and `similar` remains at zero) it is close to
indistinguishable from a decayed two-hop `requires` closure, splits mass by out-degree — the wrong
prior for a prerequisite relation — and is hard to explain in the Probe UI. It is therefore shipped
with `w_ppr` as a manifest weight and a `w_ppr = 0` arm in the bake-off. It is expected to earn its
place once model-derived `similar` edges exist, which is the setting it was designed for.
