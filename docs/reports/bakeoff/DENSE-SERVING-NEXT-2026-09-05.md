# GPU dense serving: next experiment — 2026-09-05

**Recommendation: evaluate SKILLRET in a warm Hugging Face TEI GPU worker before
building more serving machinery.** The current encoder spike does not establish a
hardware limit or prove that dense retrieval cannot earn deployment. Its serial queue
and CPU/GPU dispatch overhead are concrete optimization targets. This is a proposal,
not an implemented GPU path or a reopening of spent quality-test budgets.

## What our measurements establish

The old Python/C++ hybrid measured p95 152 ms at c1 and 444 ms at c4; fresh clients
measured 206/446 ms. Its single encoder lock serializes requests. A separate process
reduces interpreter contention but does not combine four queries into one forward.
A batch-one service time is not a batch-four estimate, and p95 values cannot simply
be added as independent costs. See [E1.1b](E1.1b-service-feasibility-2026-09-05.md).

The [stage profile](validation/e11b-encoder-stages.json) already uses fp16, SDPA and
actual Flash Attention kernels. Tokenization is under 1 ms p95 in the instrumented
sample; the transformer forward dominates. The three-query profiler records 4516
`cudaLaunchKernel` calls. CUDA event spans include idle gaps and are not pure active
GPU time. Instrumentation adds overhead, so these are diagnostic observations, not
an end-to-end SLO result. Moving the HTTP handler to another language cannot by
itself remove these launches or batching constraints.

The final [Go/ParadeDB sparse reference](GO-PARADEDB-2026-09-05.md) has HTTP p95
21/28 ms and whole-fresh-client p95 117/138 ms at c1/c4. This leaves room for a GPU
stage, but measuring sparse alone does not prove hybrid latency under shared load.

## What established systems actually do

| System | Mechanism relevant here | Scope and limitation |
|---|---|---|
| Hugging Face TEI | Token-based dynamic batching; optimized Candle/Flash Attention/cuBLASLt inference; OpenTelemetry and Prometheus | First candidate for a dedicated embedding service. Qwen3-Embedding-0.6B and Ada RTX 4000 hardware are supported; our fine-tuned checkpoint/pooling still need conformance checks. |
| NVIDIA Triton Inference Server | Schedules model instances, dynamic batches, bounded queues and timeouts; can host different optimized backends | Useful serving layer when controlling multiple models/backends. Triton alone does not compile away an inefficient PyTorch forward. |
| TensorRT / CUDA Graphs / torch.compile | Fuse operations, choose efficient kernels, reduce CPU launch overhead; CUDA graphs replay compatible execution shapes | Candidate if launch overhead remains after TEI. Export/support, numerical drift, shape buckets and warmup must be validated on this checkpoint. |
| Ray Serve | Batched Python deployment functions plus resource/replica orchestration | Useful if we need a custom pipeline; another worker alone is not a faster GPU kernel. |

Sources: [TEI features](https://huggingface.co/docs/text-embeddings-inference/en/index),
[TEI models/hardware](https://huggingface.co/docs/text-embeddings-inference/en/supported_models),
[Triton batching](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/batcher.html),
[TensorRT optimization](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/optimization.html),
[CUDA Graphs](https://docs.nvidia.com/dl-cuda-graph/latest/),
[Ray Serve batching](https://docs.ray.io/en/latest/serve/advanced-guides/dyn-req-batch.html).
Checked 2026-09-05. These capabilities support the proposal; they provide no measured
speedup factor for our model. NVIDIA Triton Inference Server is distinct from the
Triton language/compiler used to write GPU kernels.

Uber describes integrating NVIDIA Triton into Michelangelo's Online Prediction
Service, with GPU resource sharing and Kubernetes-based control. It separates online
inference from offline training/feature pipelines, where Ray and Spark are used.
That supports adopting a specialized inference runtime here, not adding Spark to a
single synchronous SEARCH request. [Uber engineering, May 2024](https://www.uber.com/ci/en/blog/from-predictive-to-generative-ai/).

Meta's SilverTorch combines ANN retrieval, eligibility filtering, reranking and
scoring as tensor modules in a shared PyTorch execution graph, using `torch.compile`
and fused kernels. Their example is an 80-million-item recommendation workload.
It shows why graph layout and data movement matter more than the source language;
its speedup factors cannot be applied to our 0.6B query encoder or 6006 skills.
[Meta engineering, May 2026](https://engineering.fb.com/2026/05/26/ml-applications/silvertorch-index-as-model-new-retrieval-paradigm-recommendation-systems/).

Meta's [Faiss](https://engineering.fb.com/2017/03/29/data-infrastructure/faiss-a-library-for-efficient-similarity-search/)
accelerates similarity search over existing vectors. It does not compute the query's
neural embedding. For 6006 vectors of 1024 dimensions, float32 storage is about
23.5 MiB (6006 x 1024 x 4 bytes): first measure exact CPU/pgvector or GPU matrix
search, rather than assuming a distributed ANN platform is necessary.
Kafka/Flink/Spark could support telemetry, feature preparation and offline indexing
later. Inserting a broker/job scheduler into online SEARCH adds another queue and
is not an optimization of the measured encoder forward.

## Proposed shape

The Go API keeps authentication, tenant/repo/snapshot identity, scope checks, revision
consistency and final policy/selection. Start BM25 and query embedding in parallel.
A dedicated warm GPU worker owns the checkpoint and batches requests; stored document
vectors are built at publication time and bound to the exact model/prompt/tokenizer/
normalization revision. After embedding, retrieve vectors from the same snapshot,
combine admissible candidates and apply the shared composition policy.

Keep one model-serving owner per GPU initially, with a token/request cap, deadline
propagation, a short measured batching window and explicit overload behavior.
Try batch sizes 1/4/8 with short/long input buckets and a 0/2/5 ms wait grid on DEV
latency traffic; do not assume batch 4 costs the same as batch 1. More Python worker
processes sharing one GPU can duplicate weights and compete for memory bandwidth.
Additional replicas should be driven by measured queue time and throughput needs.
Pin images and model revisions; readiness requires completed model warmup. In a
future Kubernetes deployment, retain warm capacity instead of scaling latency-critical
encoding to zero. Sparse fallback/shadow labeling must be explicit and evaluated;
the current Go reference does not implement that behavior.

## Correctness before new quality claims

The old encoder uses an instruction starting `a skill search query`; the pinned
model README specifies `Given a skill search query`. Its query cache key also omits
the prompt/configuration. A [40-query DEV audit](validation/go-paradedb-dense-prompt-audit.json)
with ABBA order and no query-cache reuse found changes to top-10 order in 37/40 cases
and membership in 24/40, with stable same-prompt controls. It used no qrels, so this
is proof of ranking sensitivity, not proof that the corrected prompt improves quality.

The checkpoint's pooling configuration is `lasttoken`, dimension 1024, including the
prompt, followed by normalization. A TEI deployment must preserve that processing,
padding/masks and truncation, and compare vectors plus ranking on DEV before any
latency claim about an equivalent model. Record the tokenizer, prompt, maximum length,
pooling, dtype, model revision and document identity in cache/index keys. A prompt
correction is a new semantic version; it must not silently relabel old embeddings or
historical quality numbers. fp16 is the first reference; quantization is a later,
separate quality/performance tradeoff.

## Can dense earn its place?

Historical R1 on test-B reduced HSR@4 by 10.00 pp [−15.67, −4.00] but improved
all_required@4 only 0.67 pp [−1.50, +2.83]. That is a useful signal for distinguishing
confusable skills, not a passed completeness gate. The new ParadeDB reference raises
HSR by 10.67 pp. Combining these systems might help, but their independent deltas
cannot be subtracted to predict a hybrid outcome. Dense ranking also cannot guarantee
that the final four-card selector composes every required skill.

A useful engineering target for the next spike is encoder p95 <=50 ms and hybrid
server p95 <=150 ms at c4, while retaining the existing acceptance budgets (server
<=300 ms; whole fresh client <=400 ms). These are proposed targets, not predictions.
Report tokenizer/queue/batch/forward/vector/policy time, batch distributions, p50/p95/
p99, overload/errors, GPU memory, throughput and both fresh and steady-client runs.
Use the same 200 latency query IDs without qrels; only measured full-path results
can establish whether the target is achievable.

Choose relevance/fusion/composition on DEV. The [programme multiplicity rule](DENSE-PROGRAM.md)
prohibits inventing a post-test combination and repeatedly testing it on the same
holdouts. Any new quality claim needs an already registered family's remaining budget
(such as the specified C/dense reference) or a newly registered evaluation with fresh
held-out evidence. Keep this service in shadow until both quality and latency admission
are established. Faster inference can make dense affordable; it cannot by itself
prove that selected skills are better or complete.
