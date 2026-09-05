# ADR-0021: Shard the index by node; ship the word table as a language artifact, not a corpus artifact

**Status:** Proposed · 2026-09-05
**Amends:** [ADR-0020](ADR-0020-two-tier-dense-retrieval.md) — corrects its vocabulary-headroom
estimate and its gate wording.
**Informs:** MVP story E2.3, which already names `index/<shard>/<sha>/` but does not say how to shard.

## Context

E1.4 ships a **single** index artifact per commit, capped at 15 MB for 2 000 skills. That cap was
set against a synthetic corpus. Measuring against a real one changes the picture.

### What was measured

889 real `SKILL.md` files (`benjaminasterA/antigravity-awesome-skills`, MIT), tokenised with the
shipped tokenizer and serialised through the shipped `_serialize_artifact_files()`:

| skills | distinct terms | tokens | build + serialise | sparse artifact |
|---|---|---|---|---|
| 100 | 7 914 | 78 659 | 0.20 s | 377 937 B |
| 200 | 11 209 | 155 482 | 0.41 s | 634 858 B |
| 400 | 16 523 | 326 547 | 1.08 s | 1 115 600 B |
| 889 | 26 489 | 757 089 | 2.16 s | 2 207 701 B |

Fitting Heaps' law to those points gives **V = 620.2 · n^0.553**. The exponent sits squarely in the
natural-language range (0.4–0.6), which is the evidence that the corpus behaves like real prose
rather than like the synthetic filler the earlier estimate used. Per skill: 852 tokens, 2.4 ms of
build time, 2 483 B of sparse artifact.

Extrapolating on those measured per-skill constants, with an int8 word table at 256 dims:

| skills | terms (Heaps) | CI build | sparse | + word table | total | of 15 MB |
|---|---|---|---|---|---|---|
| 2 000 | 41 473 | 4.9 s | 4.97 MB | 11.46 MB | 16.43 MB | **104 %** |
| 10 000 | 100 982 | 24.3 s | 24.83 MB | 29.22 MB | 54.05 MB | **344 %** |
| 30 000 | 185 376 | 72.8 s | 74.50 MB | 56.62 MB | 131.12 MB | **834 %** |

### What that says

**Build time is a non-issue.** 73 seconds at 30 000 skills, growing linearly because it is
counting words. It is an unremarkable CI step and needs no optimisation. Critically, it runs
**per merge to `main` and executes no model** — the neural work (distillation, bake-off) is
triggered by a vocabulary or teacher change, which Heaps' law says arrives on a scale of weeks,
not per merge.

**Artifact size is the constraint, and it binds sooner than ADR-0020 claimed.** ADR-0020 stated the
15 MB cap "closes … leaving room for a ~40k-word table at 256 dims". On real text that is wrong:
at 2 000 skills a full Heaps vocabulary is 41 473 words and the total reaches **104 %** of the cap.
The synthetic estimate was optimistic because its documents were 120 tokens where real ones are 803,
and its term distribution was uniform where real text is Zipfian.

**A single artifact cannot serve 30 000 skills.** 131 MB is not something a hook downloads.

## Decision

**1. The distilled word table is an artifact of the *language*, not of the corpus.**

At 30 000 skills the vocabulary is ~185 000 words, and the overwhelming majority are ordinary
English shared by every team. There is no reason for those bytes to travel with one team's skills,
and no reason for them to be rebuilt when a skill merges.

So `words.bin` / `words.idx` are keyed by **the teacher's HF commit sha and the distillation
parameters**, not by the corpus sha. Consequences: it is downloaded **once** and cached
indefinitely; a merge never invalidates it; and two monorepos on the same teacher share the same
file. It changes only when someone deliberately changes the teacher — an ADR-level act.

**2. Postings and cards shard by top-level node.**

`postings.bin`, `postings.idx`, `terms.bin`, `cards.jsonl` and `graph.json` are built per shard,
where a shard is a top-level node of `guidefold.yaml`. At 30 000 skills across ~25 top-level nodes
that is ~1 200 skills and **~3 MB** per shard.

`nodes.json` and the manifest stay global and tiny — the hook needs the whole hierarchy to resolve
`cwd → node` before it knows which shards to want.

**3. The hook fetches only the shards on its ancestor chain**, which is typically two or three.
Cold cost becomes the one-time word table plus ~9 MB; a merge costs one ~3 MB shard.

**4. Correct ADR-0020's vocabulary guidance.** The distilled vocabulary is capped by document
frequency at **~34 000 words** at 256 dims, not ~40 000. At 34k the projected 2 000-skill artifact
is 13.13 MB (83.5 % of budget); at 40k it is 14.71 MB (93.5 %); at 60k it is 19.99 MB and over.
The cap is load-bearing, not advisory.

**5. Correct ADR-0020's gate wording, which could not detect the regression it was written to catch.**

ADR-0020 says: ship `w_dense > 0` only if the fused arm beats the better BM25 arm by ≥ 3 pp
Recall@8 **"with no regression on the sibling-ambiguity or no-applicable strata"**. The E1.3
bake-off found that on `sibling_ambiguity` both arms score Recall@8 = 1.0000 — the metric is
saturated there — while the fused arm regresses **hit@1 by 16.67 pp** and **nDCG@10 by 7.40 pp**.
A gate phrased against a saturated metric is not a gate. The regression clause must therefore name
**hit@1 and nDCG@10 per stratum**, which are the metrics that still discriminate at this corpus size.

(The gate failed anyway, on its headline clause: +1.24 pp Recall@8 against a 3 pp bar. `w_dense = 0`
ships. But it failed for the right reason only by luck, and that is worth fixing before the pilot
corpus makes the headline clause passable.)

## Consequences

**Good.** The design scales to 30 000 skills without the hook ever downloading more than about
9 MB of corpus data. The word table stops being rebuilt for changes that cannot affect it. Shards
give per-team cache locality: a team touching `atlas` never re-downloads `forge`. And the 15 MB
budget becomes a per-shard budget, which is a far easier thing to hold as a corpus grows.

**Bad.** More moving parts: two cache lifetimes (teacher-keyed and corpus-keyed) instead of one, and
a hook that may need several shards before it can answer. Cross-shard `requires` edges need the
global graph or a shard fetch, so `graph.json` may have to stay global — that is unresolved below.
Sharding by top-level node is also uneven: a monorepo with one enormous platform and twenty small
ones gets one enormous shard.

**Neutral.** None of this is needed for the MVP fixture (26 skills) or the pilot (~200). It becomes
necessary somewhere between 2 000 and 10 000 skills, and the measurements above say where.

## Open questions

1. **Cross-shard `requires` closure.** Selection follows `requires` edges up to depth 2, and those
   edges cross shards. Either `graph.json` stays global (small: 406 KB at 889 skills, so ~14 MB at
   30 000 — itself over budget) or the closure fetches shards on demand, which costs latency. Neither
   is obviously right; needs measuring.
2. **Uneven shards.** Should sharding be by top-level node (simple, uneven) or by a size-balanced
   partition (even, but a skill's shard is then not derivable from its path without a lookup)?
3. **Does IDF stay global?** BM25's IDF is corpus-wide. Computing it per shard makes scores
   incomparable across shards; computing it globally means a merge in `forge` perturbs `atlas`
   scores. The determinism claim is per index sha either way, but the second option makes shard
   caching much less effective.
4. **Vocabulary pruning changes retrieval, not just size.** Dropping df=1 terms removes exactly the
   rarest words, which are the highest-IDF and often the most discriminating. The ~34k cap needs a
   quality measurement, not only a byte measurement.
