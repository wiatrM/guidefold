# GPU serving and frozen DEV quality — 2026-09-05

TEI resolves the measured GPU serving bottleneck on the local RTX 4090. Both pure
dense and BM25F+dense pass the 400 ms whole-client / 300 ms server p95 gates, including
four fresh concurrent clients. Pure dense improves frozen DEV complete-skill retrieval
from 30.0% to 47.0%; equal-RRF hybrid reaches 37.5%. These are training-distribution
DEV results, not independent transfer or HSR admission. Default Router parity remains
unchanged. The owner's subsequent T1 priorities require encoder results in **shadow**;
these direct-output endpoints were used only to measure the engineering experiment.

## Latency

The existing frozen 200-query workload, 6006 public skills, four arms, 800 requests per
profile; no query cache. HTTP starts a new connection per request. Fresh timing includes
Python process startup, token-file read, HTTP, parse and exit. Loopback is WSL2 / Docker
Desktop on a shared, unisolated host with RTX 4090 (24 GiB), driver 591.86. The runs
were sequential, not a randomized causal comparison of small latency differences.

| Profile | HTTP c1 p95 | HTTP c4 p95 | Fresh c1 p95 | Burst fresh c4 p95 | HTTP OK |
|---|---:|---:|---:|---:|---:|
| Exact BM25F, PR #54 | 21.6 ms | 29.1 ms | 115.8 ms | 135.6 ms | 800/800 |
| Hybrid, TEI batch=16 | 83.5 ms | 108.5 ms | 177.1 ms | 306.2 ms | 800/800 |
| Hybrid, TEI batch=1 | 95.2 ms | 129.2 ms | 207.9 ms | 332.3 ms | 800/800 |
| Dense, TEI batch=1 | 87.6 ms | 132.9 ms | 205.1 ms | 288.1 ms | 800/800 |

Every profile's server p95 is below 300 ms in each arm. All GPU client requests are
below 400 ms; some exceed 300 ms (the whole-client gate is 400). Full p50/p95/p99,
stages, sample IDs, errors, per-response hashes, source/image hashes and denominators
are in the artifacts. This does not imply WAN/TLS/IAM, actual harness startup, HA or
production fleet capacity. The historical Python/C++ hybrid c4 444/446 ms measurements
are retained under their own implementation and protocol.

The first batched run changed 67/600 ranked hashes (which include integer scores) and
3/600 selected sequences across arms. Batch=1's registered control passed all 600
ranked/selected comparisons for hybrid. It trades throughput for observed repeatability,
not a universal GPU bit-exact guarantee. Each latency run's counters increased by 810
encodes (10 warmups + 800 measured). The model stays resident; model-load count is null
because TEI does not supply that counter. The first post-run GPU memory sample was
4159 MiB total device use, not an isolated process peak.

## Numerical and input audit

Pinned SKILLRET-Embedding-0.6B revision `0e10886e80a0aacc9efddc28282a258e2ab7eae1`,
weights SHA `f73118cac018ffa7ebb5a1ffbdf82034490dfb7f2559558f1e79277f1e8de172`.
TEI image and adapted config/tokenizer hashes are in `gpu-encoder-manifest.json`;
encoder ID `d9c94fd282392d544f376ce2e90760f4252c4747ff480391e66631357ffdd23f`.
TEI 1.9.3 uses Rust/Candle FlashQwen3, FP16, last-token pooling and normalized 1024-d
vectors. Exact pgvector cosine avoids ANN recall loss; BM25F and encoding overlap.

TEI vs PyTorch FP16 on 40 DEV queries, 32 documents and four synthetic Unicode/long
inputs: minimum cosine **0.999985695**, mean **0.999995887**, max absolute component
error **0.000691070**. The preregistered minimum-cosine criterion was 0.999.

The new path uses the model's exact `Instruct: Given a skill search query, ...`
instruction and the official stripped `name | description | skill_md` document format.
Historical `encode.py` omitted `Given`; historical corpus card conversion reads
`body`, not `skill_md`. New document preparation verifies raw pinned records convert
to exactly the published sparse cards before using full skill_md as the dense input.
No sparse cards, corpus labels, metric functions or old evidence are rewritten.
These changes were combined with the serving improvement; this experiment does not
identify their separate causal contributions.

## Quality: all 1000 DEV attempts

Protocol committed at `17220fd4498675c6d20bb9a31928dcb45e96a94e`, with the numerical
batch control recorded before quality. Exactly three fixed arms, 10123 documents,
same CLI snapshot, labels withheld from SEARCH, no parameter tuning. The unchanged
CLI F0 reference was recomputed and saved. One hybrid request timed out at 268 ms;
it was retained without retry and counts as an empty ranking in this table. The
existing answered-only tables and full-denominator diagnostics are both preserved.

| Metric | CLI BM25F | Hybrid | Dense |
|---|---:|---:|---:|
| Hit@1 | 71.3% | 83.9% | 88.7% |
| nDCG@10 | 0.6104 | 0.7270 | 0.7890 |
| All required skills @4 | 30.0% | 37.5% | 47.0% |
| HTTP success | reference in process | 999/1000 | 1000/1000 |
| HSR@4 | unknown | unknown | unknown |

Paired bootstrap, 1000 draws, seed 0, full 1000-attempt denominator:

- Hybrid completeness delta **+7.5 pp**, 95% CI **[+5.9, +9.2]**.
- Dense completeness delta **+17.0 pp**, 95% CI **[+14.5, +19.5]**.
- Hybrid hit@1 delta +12.6 pp [10.3, 14.7]; dense +17.4 pp [14.4, 20.7].

Dense's complete-selection rates for k=1/2/3 are 97.87%, 36.64%, 7.96%. The remaining
multi-skill gap is substantial; a good top hit is not complete composition. Equal
RRF loses to pure dense on this DEV, so the paper's general hybrid motivation is not
a guarantee that equal fusion wins for this trained model and these queries.

SKILLRET-train DEV is in the model's training distribution. This is evidence for a
working integration and observed DEV benefit; it is not independent validation.
No test-A/test-B quality run was repeated. HSR is null because harmful labels are
absent. No family reopening, default-profile change or production admission follows.

## Functional validation and next integration

Go race tests and vet passed; full Python tests passed (the existing watchdog test
emits resource-tracker warnings). A real worker outage returned 503/504 from SEARCH
without sparse fallback, while USE returned the same checked body. Worker restart
restored ranking after 15.8 seconds. Complete publication is idempotent; partial
vectors and a changed prompt were rejected with the previous head intact. A later
schema-validating smoke run is recorded separately when available.

Next T1 work follows the owner's priorities: required `compose-service` parity check,
Postgres event ingest using the reference ledger contract, background GPU shadow joined
by search_id, and a reproducible T1 runbook. No encoder goes into the default response.
The 300/400 ms budgets and harness API 1.1 remain fixed.

## Evidence

All paths below are in [validation](validation/); compressed rows contain public
query/skill IDs, ranks, scores and hashes, without raw query or skill text.

- `gpu-hybrid-batch16-latency.json` / `gpu-hybrid-batch1-latency.json` and `*-rows.jsonl.gz`.
- `gpu-dense-batch1-latency.json` and its `*-rows.jsonl.gz`.
- `gpu-numerical.json`, `gpu-smoke.json`, `gpu-encoder-manifest.json`.
- `gpu-dev-hybrid.json`, `gpu-dev-dense.json`, corresponding `*-rows.jsonl.gz`, `gpu-dev-f0.json.gz`.

[TEI](https://huggingface.co/docs/text-embeddings-inference/en/index),
[model card](https://huggingface.co/ThakiCloud/SKILLRET-Embedding-0.6B),
[official formatter](https://github.com/ThakiCloud/SKILLRET/blob/main/skillret/eval.py).
