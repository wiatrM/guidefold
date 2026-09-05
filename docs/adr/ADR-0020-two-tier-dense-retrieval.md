# ADR-0020: Two-tier dense retrieval — a distilled static table in the artifact, neural models in CI only

**Status:** Accepted · 2026-09-04
**Amends:** [ADR-0015](ADR-0015-self-hosted-skill-tuned-models.md) — the winning encoder no longer
serves hook queries from a GPU endpoint; it serves CI and `find --experimental` only.
**Builds on:** [ADR-0009](ADR-0009-hybrid-retrieval-client-side.md) (hybrid retrieval, client side),
[ADR-0003](ADR-0003-bootstrap-skill-cli-not-mcp.md) (CLI, not MCP).

> **Literature check:** [`docs/RESEARCH.md`](../RESEARCH.md) places this decision against BEIR,
> DPR, SkillRet and SkillRouter. Short version: the `w_dense = 0` outcome **agrees** with the
> on-task literature — SkillRet's own leaderboard puts BM25 above a 118M dense encoder on skill
> retrieval — and the one paper pointing the other way (DPR) measures an in-domain QA regime.

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
percentage points Recall@8 with no regression in hit@1 or nDCG@10 on the sibling-ambiguity or
no-applicable strata**. Otherwise the artifact ships `w_dense = 0` and the report says so.

> **Amended by [ADR-0021](ADR-0021-index-sharding-and-a-global-word-table.md).** The regression
> clause originally read "no regression on the sibling-ambiguity or no-applicable strata" without
> naming a metric, which in practice meant Recall@8 — and the E1.3 bake-off found Recall@8 is
> **saturated at 1.0000 on `sibling_ambiguity` for both arms** while the fused arm regressed hit@1
> by 16.67 pp and nDCG@10 by 7.40 pp there. A gate phrased against a saturated metric cannot fail,
> so the clause now names the metrics that still discriminate at this corpus size.

> **Gate retired, 2026-09-05 (peer review, P1).** Both forms of the Recall@8 gate above were
> unreachable: B1's Recall@8 is 0.9799, so "+3 pp over the better BM25 arm" required 1.0099. A
> gate that cannot be passed is not evidence when it fails. The replacement, written *before* the
> next run and recorded in [`E1-closure-plan.md`](../reports/bakeoff/E1-closure-plan.md) §3:
> the dense channel is enabled only if, on **policy-filtered candidates at the shipped 4-card
> budget**, it is non-inferior on `all_required@4` and non-worsening on HSR@4, with warm p95
> inside the hook budget — measured on the frozen pilot set, not the dev fixture.
>
> Also fixed the same day: `_dense_rank` compared `dot/normsq`, not cosine — the sqrt-free
> comparison this ADR prescribes is `(a·q)²·|b|² ⋛ (b·q)²·|a|²` with sign, and the spec had
> written it wrongly. Latent while `w_dense = 0`; a blocker for ever turning it on.

**Outcome, E1.3 (2026-09-05):** the gate **failed** — +1.24 pp Recall@8 against the 3 pp bar, plus
the regression above. The artifact ships `w_dense = 0`. The distilled table is still built and
shipped, because it costs nothing at query time and may earn its weight on a larger corpus. Of the
four teachers, SKILLRET-Embedding-0.6B leads on hit@1 and nDCG@10 and is the pick if a bigger corpus
later justifies switching the channel on.

## Consequences

**Good.** The shipped CLI keeps its stdlib-only constraint and its 300 ms budget with room to spare
(measured budget at 256 dims: ~210 ms including interpreter start-up). Routing is bit-reproducible
across operating systems and Python versions. The teacher can be replaced without touching the CLI —
a new index artifact is the whole migration. The 15 MB cap at 2k skills closes, but only with a
**capped vocabulary of ~34 000 words** at 256 dims — see
[ADR-0021](ADR-0021-index-sharding-and-a-global-word-table.md), which corrects the estimate this
paragraph originally carried. Measured against a real 889-skill corpus rather than synthetic filler:
sparse is ~4.97 MB at 2k skills, and a full Heaps vocabulary (41 473 words) would take the total to
**104 % of budget**. At 34k words it is 83.5 %. The cap is load-bearing, not advisory.

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

**Resolved by E1 config selection** (`docs/reports/tuning/E1-config-selection.md`): the decayed
closure (`_decayed_closure`, `weights["ppr_mode"]="closure"`) was implemented behind a flag
alongside the existing reverse-PPR (`weights["ppr_mode"]="pagerank"`) and measured head-to-head on
the 220-case golden set, split into a stratified tune/holdout pair. Result: **byte-identical on
every metric, on both halves independently, and unchanged (only the recorded git SHA moved) when
`docs/reports/golden/baseline.json` was regenerated over the full 220 cases.** Mechanistically,
`w_ppr`'s own sweep (0/100/250/500, same report) showed PPR's contribution to the final score is
three-plus orders of magnitude smaller than the RRF/scope gaps between candidates on this graph, so
whichever algorithm computes that already-negligible quantity cannot show up in the outcome.
`ppr_mode` now **defaults to `"closure"`** — the simpler, exactly hand-verifiable implementation
(a fixed fraction of mass per `requires`-hop, no power iteration) — since it is measurably free on
every case tried. `_reverse_ppr` stays in the code, selectable via `weights: {ppr_mode: pagerank}`;
this equivalence was demonstrated on a shallow, sparse graph (out-degree ≈ 0.6) and should be
re-measured if a monorepo's `requires` graph grows deep or dense enough for out-degree
normalisation to plausibly matter, or once model-derived `similar` edges exist as noted above.
