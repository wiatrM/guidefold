# GPU hybrid service: prospective engineering/DEV protocol v1

Registered before any new GPU service quality evaluation. This does not reopen
spent test-A/test-B budgets or change default T0/T1 admission (DENSE-PROGRAM §4a).

## Fixed implementation

- Unchanged default CLI BM25F, as restored and independently verified in PR #54.
- Opt-in TEI 1.9.3 Rust/Candle FlashQwen3 on RTX 4090, pinned image digest and
  SKILLRET-Embedding-0.6B revision `0e10886e80a0aacc9efddc28282a258e2ab7eae1`.
- FP16, last-token pooling including prompt, L2-normalized 1024 dimensions,
  maximum 8192 tokens. Exact model-card query instruction beginning
  `Instruct: Given a skill search query, ...`.
- Document formatter follows the official `skillret/eval.py build_skill_text`:
  stripped `name | description | skill_md`, with description fallback for empty
  skill_md in the public corpus. The historical card converter uses `body`, so
  benchmark document inputs explicitly use the pinned raw skill_md after checking
  that raw records convert to the exact published cards. This changes the dense
  representation, not the canonical sparse cards, labels or metrics.
- PostgreSQL exact cosine search, policy filtering before ranking; no ANN recall
  loss. Hybrid uses equal RRF k=60, union of each channel's top-50, preserving both
  full channel ranks for union members, then the existing policy and select().
- One GPU owner, two tokenizer workers, dynamic batches <=8192 tokens/16 requests,
  32 TEI requests, eight API slots; one query encode shared across resolved scopes.
  BM25F overlaps encoding. Query embeddings are never cached for latency runs.

## Numerical/performance gates

Numerical audit versus PyTorch FP16, same inputs/prompt/pooling, criterion minimum
cosine >=0.999 over 40 frozen DEV queries, 32 documents and four synthetic inputs.
Audit includes Unicode, mixed lengths and long input. Cross-batch ranking stability
is measured, not assumed bit-exact; only the default sparse path claims tier parity.

Same 200 frozen DEV query texts over 6006 pinned public documents, arms HTTP c1/c4,
fresh process c1 and burst fresh c4. Report all errors, p50/p95/p99, stage times,
client <=400 ms and server <=300 ms, live encode counts and model/vector identities.
Report GPU startup/readiness, memory and explicit worker-down behavior. Loopback
success does not imply WAN/TLS/IAM, production scale or k8s admission.

## Bounded quality evaluation

Use the frozen 1000-query SKILLRET-train DEV set and its 10123-document pool.
Exactly three prespecified arms: F0 reference BM25F, pure dense, and equal-RRF hybrid.
No fusion-weight, top-k, corpus or select() tuning in this protocol. Preserve all
arms and per-query hashes/ranks. Reuse existing metric functions: hit@1, nDCG@10,
all_required@4, coverage, per-k breakdown and paired bootstrap (1000 draws, seed 0).
Compare both API retrieval and final selected cards; no labels reach SEARCH.

These queries were in SKILLRET's training distribution: DEV demonstrates correct
integration and observed behavior, not independent generalization. HSR is undefined
on this dataset and must remain null. No new test-A/test-B quality run is authorized
by this protocol. Independent transfer and harmful-sibling admission require a fresh
preregistered holdout with those labels; missing data cannot be recorded as a pass.
The GPU profile remains explicit and `quality_admitted:false` until then.

Sources: [model card](https://huggingface.co/ThakiCloud/SKILLRET-Embedding-0.6B),
[official formatter](https://github.com/ThakiCloud/SKILLRET/blob/main/skillret/eval.py),
[TEI](https://huggingface.co/docs/text-embeddings-inference/en/index).
## Numerical control registered before DEV quality evaluation

The first 800-request latency run passed both budgets but changed 3/600 selected
card sequences across batching arms (and 67/600 ranked hashes, which also include
integer scores). No new quality labels have been evaluated. Test batch limit 1 as
an engineering control with the same model, prompt and fixed document vectors.
If both latency gates pass and all 600 cross-arm hashes match, offer this profile
for repeatability and retain the batch-16 measurements/profile for throughput.
This is a numerical/performance choice, not a quality-tuned model/fusion variant.

Control outcome before DEV quality: batch=1 passed all four latency gates and
all 600 paired ranked/selected hashes. It is the opt-in GPU overlay default;
batch=16 remains an explicit throughput experiment. Offline document preparation
may use batches of eight under a worker limit of 16. The document vectors are
then immutable and shared by both measured dense/hybrid quality arms. Readiness
verifies the configured worker batch limit as well as model identity.
