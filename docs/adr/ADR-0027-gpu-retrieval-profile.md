# ADR-0027: Explicit GPU retrieval profile with a pinned TEI worker

**Status:** Proposed · 2026-09-05. Implements the owner's GPU optimization request;
this proposal does not admit a new default ranker or supersede ADR-0024 parity.
**Related:** ADR-0025 API contract and ADR-0026 Go/Postgres hosting.

## Context

The former Python GPU path serialized approximately 86 ms encodes and missed the
four-client loopback budget. Faster HTTP or a different lexical scorer cannot fix
that bottleneck. PR #54 restored the reference CLI BM25F default and its independent
1,000-query HTTP parity gate. GPU serving must build on that correction.

The SKILLRET model's official query instruction and full document representation
also matter. Historical tooling omitted the word `Given` from its query instruction
and the corpus-to-card conversion read `body`, while the model's evaluation uses
stripped `name | description | skill_md`. New measurements identify the corrected
representation separately; historical results and test-family budgets stay intact.

## Decision

Provide an opt-in `compose.gpu.yaml` deployment with a static Go API, the existing
Postgres distribution and a dedicated TEI Rust/Candle worker owning the GPU. Pin the
container digest, checkpoint revision and weights hash. Use FP16, last-token pooling,
L2-normalized 1024-dimensional vectors and the model's exact query instruction.
A content-addressed encoder manifest binds weights, adapted tokenizer/config files,
prompt, document formatter, dimensions and runtime image.

Publish cards and canonical BM25F postings as a staged snapshot. Publish complete
vectors, skill revisions and encoder identity in one transaction that activates the
head. Reject partial vectors, changed model identity and changes to an immutable
embedding set. Document vectors may be cached by exact input and encoder ID; query
vectors are live. The embedding bundle digest binds the actual stored vectors.

Run BM25F and one query encode concurrently. Share that vector across resolved
scopes; filter admissibility before each channel's ranking. PostgreSQL computes
exact cosine distances, with no ANN recall loss at the measured 6k/10k sizes.
The explicit hybrid uses equal integer RRF, k=60, each channel's top-50 union and
full channel ranks for union members, followed by the existing policy/closure/select.
The pure-dense mode is a separately reported ablation. Neither claims CLI tier parity.

Use one request per online forward by default: the registered control passed both
latency budgets and all 600 cross-arm ranked/selected hashes. Batch=16 remains an
explicit throughput experiment; its first run changed 3/600 selected sequences under
FP16. This observation is not a universal guarantee of deterministic GPU arithmetic.
Readiness verifies both model identity and configured batch limit. TEI's queue,
concurrency, token budget, Go slots, HTTP connections and encoder deadlines are bounded.
Bulk document indexing must not share an online SLO measurement window.

The default `compose.yaml` remains sparse BM25F and requires no GPU. GPU profile
responses expose model, retrieval mode, batch limit and `quality_admitted:false`.
API 1.1, scope/path interpretation, loaded-skill handling, budgets and exact USE
hydration remain shared. A worker outage fails SEARCH explicitly; it does not change
the ranker silently. USE can still read the database. No harness or CLI code changes.

## Validation and admission

[Registered protocol](../reports/bakeoff/GPU-HYBRID-PROTOCOL-v1.md): numerical
agreement against PyTorch, 800-request loopback latency, worker recovery, transactional
publication and exactly three DEV quality arms. Test-A/test-B are not reopened.
SKILLRET-train DEV is not an independent generalization sample, and lacks harmful
labels: HSR stays null. A separate fresh harmful-label holdout and target-network /
harness evaluation are necessary before any default-profile or production admission.

## Consequences

The GPU deployment has a separate dependency and failure mode, model storage and
index-publication lifecycle. The Go API remains model-free; no Python runs on its
request path. This release establishes a reproducible Compose implementation, not
HA, Kubernetes, durable telemetry, IAM or production scale. Kubernetes work should
separate GPU serving and indexing capacity and retain these identities and gates.

[Runbook](../../services/search/GPU.md). Primary references:
[TEI](https://huggingface.co/docs/text-embeddings-inference/en/index),
[SKILLRET model](https://huggingface.co/ThakiCloud/SKILLRET-Embedding-0.6B),
[official document formatter](https://github.com/ThakiCloud/SKILLRET/blob/main/skillret/eval.py).
