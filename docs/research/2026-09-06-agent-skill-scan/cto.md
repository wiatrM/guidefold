# CTO decision memo — 2026-09-06

## Decision

Close the user-test MVP around the existing Go SEARCH/USE service, the existing sparse BM25F
profile, explicit revision hydration, the authoring CI loop, and exposure/load/feedback events.
Use the local T0 tier where it meets its measured size budget. Keep GPU/dense shadow optional,
parked and outside pilot availability requirements. Do not add a reranker, learned composer,
section retriever, new model, worker or database to the production path before the user pilot.

The remote Go architecture is feasible. The claim that the current hook is a thin remote client
with a verified whole-hook p95 <=300 ms is not established by the code or the existing timing
reports. The highest-priority work is a real adapter/harness path and honest delivery measurement.

This memo is a code/evidence audit plus one isolated structural spike authorized by the current
user request. It does not create a new runtime surface, reopen a frozen test, tune weights, or
admit a new research family. Product scope remains consistent with ADR-0029. External literature
comparison belongs to the coordinating research memo; no algorithmic novelty claim is made here.

## Evidence basis and chronology

Inspected HEAD `dfe9e4d4d6eb1536d35ef89493aa2725215a25f1`. The diagnostic captured CLI SHA-256
`7fae2cba8c54db6e1abacba21d38690cb053dfcfc2d6d142c770e9ee6faf41cb` in its JSON.

Governing documents: `CLAUDE.md`, `docs/DESIGN.md`, `docs/CONVENTIONS.md`, `docs/MVP.md`,
`docs/PRODUCT-FOCUS.md`, `docs/adr/ADR-0029-product-focus-hard-rules.md`. No root AGENTS.md
was returned by the repository file inventory; the prototype-specific AGENTS.md is outside
this work. Older design/research documents contain superseded local-heavy plans. Current source
and newer accepted decisions take precedence when describing what actually runs.

| Capability | Evidence in current source | Assessment |
|---|---|---|
| Native remote SEARCH/USE | `services/search/main.go`, `routing.go`, `bm25f.go`, `store.go` | Built: one Go executable; integer BM25F with Postgres postings; no Python in the API image. |
| Field-aware sparse retrieval | `Index.FIELDS` and `DEFAULT_WEIGHTS` at `skills/guidefold/scripts/guidefold:511`; Go `bm25f.go` | Built: name/description/digest/triggers/body with shipped weights 6/4/3/5/2. A semantic schema is not a learned field-fusion model. |
| Dense/hybrid | `services/search/dense.go`, `shadow.go`, main.go:665 | Built behind flags; shadow requires sparse responses, starts after delivery, stores comparisons by search_id. Not admitted foreground ranking. |
| Scope/status policy | `routing.go`; `useResponse` in main.go:276 | Both retrieval and USE enforce current eligibility; exact revision mismatch fails. Operator-configured tenant identity is not production tenant IAM. |
| NO_SKILL | `routing.go:435`; CLI `select` and defaults | Empty response exists, but default magnitude gate is not calibrated confidence. Diagnostic below reproduces the limitation. |
| Full-body hydration | `main.go:276-343` | Built: exact revision, status/scope checks, body/checksum, explicit `execution_observed:false`. Returns 413 on byte-proxy budget overflow; no section retrieval. |
| Thin remote adapter | CLI `search_with_backend`, `cmd_find`, hook | Incomplete relative to the target: every service SEARCH still computes local retrieval, and hook/find load/build a local index first. |
| Measured task benefit | `docs/pilot/E6.7-PROTOCOL.md`; PRODUCT-FOCUS | Protocol exists; no real developer outcome evidence found in the reviewed repository reports. |

## What measured results support

All figures in this section are historical committed reports, not reruns in this audit.

* `docs/reports/bakeoff/ROUTER-BM25F-PARITY-2026-09-05.md`: 0/1000 HTTP/CLI mismatches
  on DEV at 10,123 documents; exact scores, ordered selection and revisions. At 6,006 documents,
  loopback fresh-process p95 115.811 ms (c1) /135.636 ms (burst c4), 800/800 HTTP successes
  across four timing arms. This demonstrates feasible remote serving on that host, not WAN/TLS/IAM
  or real hook performance.
* `R4b-lazy-terms-postings-2026-09-05.md`: whole local hook p95 113.3 ms at 500 skills,
  261.7 ms at 4,000, 320.5 ms at 6,006 (rerun 347.5). Local T300 fails at 6,006.
* `HTTP-ADMISSION-2026-09-06.md`: 97 checks, 27 failures before and zero after; capacity
  reserved before body parsing. `GRAPH-ADMISSION-2026-09-06.md`: 446 E2E assertions,
  2,100 concurrent consistent old/new snapshot responses. These are operational invariants.
* `T1-LEDGER-SHADOW-2026-09-05.md`: 210 event insertions, replay returns 210 duplicates,
  zero duplicate insertions; 32 ledger/report cases on SQLite and HTTP/Postgres. The report
  itself distinguishes test-only credential transport from completed adapter integration.
* `FROZEN-sparse-flat-2026-09-05.md`: uniform field weights improved test-A all_required@4
  by 4.99 pp and test-B by 2.92 pp, but test-B distractor exposure worsened 4.67 pp; NOT ADOPTED.
  Do not silently replace shipped field weights with flat weights because nDCG improved.
* `SkillRetBench-R1-encoder-2026-09-05.md` and `DENSE-PROGRAM.md`: full encoder test-B
  hit@1 +8.33 pp [5.75,11.25], all_required@4 +0.67 pp [-1.50,2.83], distractor exposure
  -10.00 pp [-15.67,-4.00]. Dense fails the predeclared conjunction, but is not universally bad.
  Composition and statistical-power caveats remain; they do not waive admission rules.
* `DEV-C-composer-2026-09-05.md` and `DEV-D-decomposition-2026-09-05.md`: no variant frozen.
  Deterministic composition regressed; best model composition is inconclusive on n=150.
  Decomposition improved completeness but violated hit@1 guardrails and added substantial latency.

## Critical adapter timing boundary

`search_with_backend` at CLI:2243 starts a remote thread, then computes `_local_selected` on
its calling thread at 2308. It only inspects the remote result at 2317. If local work has used the
budget, `remaining <= 0` discards a remote response even if that response already completed.
The timeout does not interrupt the local computation. The hook loads its index at 3130 before
this timer begins; `cmd_find` builds an index at 2346 before the call. These are code-inspection
findings, not newly measured latency numbers.

Consequences:

1. The service can be fast while the real hook still exceeds 300 ms.
2. A configured 300 ms SEARCH deadline is not currently a whole-hook 300 ms bound.
3. A large local corpus can prevent the fast service from being used successfully.
4. The daemon network race provides outage fallback but does not yet deliver a genuinely thin
   remote path. Readiness still depends on having the local artifact for the hook.

MVP completion should prioritize measuring the actual `hook -> service -> context -> load -> event`
cycle, then decoupling foreground remote success from completion of full local scoring using the
existing client/runtime. A bounded cached fallback is consistent with the architecture; adding a
persistent daemon just to fix this is not needed for the MVP. Preserve parity checks in CI/offline.
Do not advertise target-network p95 <=300 ms before measuring actual adapters with TLS/auth,
process startup, index handling, response validation and context delivery included.

## Executed structural spike

Files: `research/spikes/2026-09-06-cto/README.md` (questions registered before execution),
`audit.py` (real CLI/router import), `results.json` (all rows and source hashes).
Environment: WSL Ubuntu 24.04, Python 3.12.3, PyYAML 6.0.1. Command:

```sh
wsl -d Ubuntu-24.04 --cd /home/mike/projects/guidefold -- python3 research/spikes/2026-09-06-cto/audit.py
```

The command exited 0. It runs the unchanged default against all 220 synthetic development
cases and five fixed illustrative probes. No GPU, external API, corpus download or quality-test
query was used. The result file is the only generated output.

### NO_SKILL result

All 44 existing labelled `no_applicable` fixture cases selected skills: abstention recall on
this synthetic diagnostic is 0/44. Top scores 17250-17447 overlap the positive groups. Every
non-empty result on all 220 cases exceeds the default 1200 magnitude threshold.

This is explained by the implementation: a single active lexical leg assigns rank 1 the RRF
score `floor(2^20 / (60+1)) = 17189` before nonnegative scope/graph bonuses. Relative rank
cannot carry the original evidence magnitude. This is a structural issue, not a threshold value
we should tune on Meridian. The existing tuning report already found a margin alternative weak
and non-transferable; this spike does not reopen that experiment.

A pure OOV probe returns an empty set. Adding only `api` or `deployment` produces four cards.
Two explicitly unrelated poetry queries also produce four cards. These examples demonstrate
mechanics, not an estimated production false-positive rate.

For MVP, describe results as candidate guidance and let explicit agent/user use remain optional;
record rejected/not-applicable feedback. Include no-applicable tasks in the prospective pilot.
Do not claim trustworthy calibrated NO_SKILL or mandatory automatic full-body injection.

### Hydration result

The 26 fixture bodies contain 2246-5540 UTF-8 bytes; median 4658, p95 5170. All have 6 ATX headings.
Under the implemented conservative `remaining_skill_tokens` byte proxy:

| Hint/cap | Full bodies fitting |
|---:|---:|
| 1024 | 0/26 |
| 4096 | 1/26 |
| 16384 | 26/26 |

This is a conditional API-budget observation, not a claim that current CLI loads all fail: the
current `_use_via_service` helper does not send that optional token hint. The semantic contract
intentionally treats bytes as an upper-bound proxy and asks the adapter to count final tokens.
A caller that assumes 4096 here means 4096 actual model tokens could see avoidable 413 responses.

For the pilot, make byte budgets and actual harness token accounting explicit. Preserve whole
approved revisions first. Section hydration is a plausible later experiment if real body sizes
and load budgets justify it, but heading counts alone establish neither correct section selection
nor safe omission of prerequisites/constraints. No token-saving or utility claim follows here.

## Feasibility and priority

| Work | Feasibility | MVP decision |
|---|---|---|
| Existing remote Go sparse service | High; measured parity and local latency | Keep. Validate actual harness + deployment network. |
| Thin service client and bounded fallback | High within existing single-file client; current coupling needs work | P0 before a <=300 ms whole-hook claim. Rough estimate 1-3 engineering days plus environment access, not a commitment. |
| Real SEARCH/USE/event cycle in one harness | High; constituent contracts exist | P0. A named non-author developer and actual repo are acceptance dependencies. |
| Field-aware BM25F | Already shipped | Freeze current profile; do not retune test corpora. |
| Reliable automatic NO_SKILL | Technically feasible but no calibrated real-domain evidence | Do not block explicit-find pilot; block claims of reliable automatic abstention. Collect labels first. |
| Exact body hydration + budgets | Already shipped; adapter semantics need checking | P0 body/revision/checksum/context accounting. |
| Section hydration | Moderate implementation, high validation uncertainty | Park; offline only until pilot data demonstrate need. |
| GPU/hybrid shadow | Engineering feasible and implemented; quality/ops burden remains | Optional research flag, no pilot dependency. |
| New fusion model/reranker/composer/evolution | Unproven incremental user value | Exclude from MVP. |

## Publication judgement

Current evidence supports a reproducible systems/evaluation technical report, potentially a
workshop submission after primary-source related work and artifact review. It does not yet
support a claim that Guidefold improves developer tasks, generalizes to arbitrary enterprises,
or provides a novel state-of-the-art retrieval algorithm.

The strongest candidate story is evaluation/admission mismatch: retrieval ranking improvements
can coexist with harmful exposure or unchanged bundle completeness; rank-fusion confidence can
be uninformative; a fast service can still leave the real adapter slow. The new spike supplies
transparent structural evidence for the latter two mechanisms, but synthetic development
results are not independent generalization evidence. A publication-quality next step needs a
fresh locked task/domain sample, paired no-skill controls, and final adapter latency measurements.
The coordinating agent's paired-artifact audit should decide whether existing statistical claims
remain valid before writing an empirical conclusion. Do not train a model merely to create a paper.



## Independent review of coordinating evidence audit

Reviewed `research/spikes/2026-09-06-evidence/audit.py`, `audit-results.json` and
`pilot-power.json`. Paired all-query denominator1250, both-answered denominator1200,
labelled-distractor denominator300, exact binomial/McNemar power, and the one-sided zero-event
upper bounds are mathematically consistent with their stated assumptions. No blocking numeric
issue found by code/output inspection. Requested two clarity corrections: current shipped sparse
is still F0 (flat is an unadmitted variant), and positive flips of a harmful-exposure metric mean
increased harm. These notes were sent to the coordinating agent; this review did not edit its code.

The finding that215/1250 tasks have more than4 annotated gold entries diagnoses a cardinality
mismatch only under the historical adapter's AND interpretation. Before a paper treats them as
impossible tasks, verify whether25-entry gold lists represent required companions or acceptable
alternatives. The audit's explicit caveat and separate post-hoc feasible stratum are appropriate;
they do not replace semantic validation. Neither conditioned nor all-query results independently
establish developer utility. Bootstrap CIs ignore shared-skill clustering, and the power table
is a design calculation for independent pairs rather than measured evidence.

## Later user steering: field-aware small-model experiment

The user subsequently explicitly requested field-aware research and a small trained model.
That authorizes the coordinator's bounded DEV-only offline spike; the production recommendation
above does not prohibit that research. Reviewed proposed design: generic pinned Qwen encoder,
fixed hash-selected training split excluding DEV gold skills, full10123-card DEV pool, flat and
three-field lexical/dense features, fixed shallow heads, no model choice from DEV results.

Conditions for interpreting that experiment honestly: fit feature normalization on train only;
report known query/skill overlap and unmeasured near-duplicate risk; treat unlabelled negatives
as potentially false negatives; keep identical selection/policy or label the experiment as a
ranking-only study. With1024 tokens for each of three fields versus1024 for a flat document, the
comparison also changes encoder/context budget and cannot isolate field semantics alone.
Generic Qwen reduces known SKILLRET fine-tuning overlap but does not prove zero pretraining
contamination. A sparse-only trained head helps separate learned lexical fusion from dense gains.
Six fixed arms are exploratory feasibility evidence, not model admission or a new SOTA claim.
