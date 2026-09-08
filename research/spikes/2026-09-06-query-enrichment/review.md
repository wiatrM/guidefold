# Independent enrichment review: final verified readout

The frozen advancement gate passes. The measured benefit is small and fragile: C improves recall@10 for five of 2,048 queries and produces three additional complete selections, all on single-skill queries. There is no observed improvement in complete multi-skill selections. This supports another bounded research step, while the current sparse MVP recommendation remains unchanged.

## Verified result

Independent CPU QA reproduced all 6,144 saved per-query metric rows, means for all seven strata, and all 84 paired metric cells including the original 2,000-replicate query-bootstrap intervals and increase/decrease counts. Original dataset files, model config/tokenizer config, generator inputs, run, protocol and output hashes matched. Large model-weight digests remain as recorded by the generation freeze; independent QA did not reread the weight shards. The primary gate was recomputed without modification. Commands:

```text
/home/mike/.cache/guidefold/gpu-venv/bin/python research/spikes/2026-09-06-query-enrichment/qa-independent.py generation
/home/mike/.cache/guidefold/gpu-venv/bin/python research/spikes/2026-09-06-query-enrichment/qa-independent.py verify
```

These use CPU only despite the environment directory name. Evidence: independent-qa.json, generation-independent-qa.json and qa-independent.py.

| Arm | Recall@10 | Binary nDCG@10 | All gold selected@4 |
|---|---:|---:|---:|
| A: original BM25F | 57.4219% | 57.4962% | 29.0527% |
| B: metadata | 57.4382% | 57.5327% | 29.0527% |
| C: metadata + pseudoqueries | 57.5846% | 57.6612% | 29.1992% |

C-A recall@10 is **+0.162760 percentage points**, query-bootstrap 95% interval **[+0.024414, +0.358073]**. The preregistered shared-gold component bootstrap gives **[+0.032191, +0.343146]**; its conclusion about excluding zero agrees. Components were fixed before outcomes: 1,341 groups, largest 18 queries. This check captures shared positive labels, not all source/corpus dependence.

C-A completeness is +0.146484 points, query interval [0, +0.341797] and component interval [0, +0.336381]. The no-assigned-gold guard also passes, with recall +0.054289 points. Its two improved queries demonstrate why the full-cohort result includes global ranking/statistical effects and cannot be reduced to performance on directly enriched gold documents.

## Post-hoc fragility check

The following sensitivity was requested after the primary result and does not alter the preregistered gate. Exact two-sided sign flips were enumerated over the nonzero paired differences, and separately over full-cohort connected components. The statistic is the absolute sum of metric differences; the fixed original-query denominator cancels.

| Metric | Improved / worse / unchanged queries | Distinct nonzero components | Exact query p | Exact component p |
|---|---:|---:|---:|---:|
| Recall@10 | 5 / 0 / 2,043 | 5 | 0.0625 (2/32) | 0.0625 (2/32) |
| All gold selected@4 | 3 / 0 / 2,045 | 3 | 0.25 (2/8) | 0.25 (2/8) |

The recall improvements comprise two k=1, two k=2 and one k=3 queries. All three complete-selection improvements are k=1; completeness changes are exactly zero in both multi-skill strata (k=2 n=725; k=3 n=674). Exact sign flips assume paired arm-label exchangeability or a symmetric sign null; this is an observational comparison of deterministic retrieval systems, not a randomized treatment trial. The checks show inferential sensitivity with very few changed queries. They neither prove no effect nor establish a broad improvement. See posthoc-fragility.json for the independently reconstructed query/component counts; posthoc-fragility.py is the CPU-only reproducible exact-enumeration script.

## Interpretation and feasibility

The generator and mechanical filters produced 869 intents and 734 pseudoqueries; 58 of 512 assigned documents have no accepted addition. The blind fixed-sample semantic review was completed before retrieval: 26 supported and 18 weak/generic items among 44 accepted items, zero unsupported items in this small reviewed sample, and one empty sampled document. Scope omissions recur. A source quotation is insufficient evidence of retrieval usefulness or underlying skill quality.

Only 512 of 10,123 documents were assigned enrichment. Do not scale the +0.163-point effect linearly to full coverage: global statistics and competition among enriched documents change. Metadata alone changes recall for one query; C-B includes additional text volume and normalization changes, so it does not isolate the causal value of question phrasing.

Generation took 1,155.9 seconds of batch computation and 1,200.4 seconds for the measured process. A simple same-throughput projection is about 6.35 hours for 10,123 documents or 18.81 hours for 30,000, before corpus preparation and QA; differing document lengths can invalidate that projection. This is an offline cost. The 94.65 MB versus 94.71 MB serialized-card measure is not the full inverted-index or serving-memory footprint.

Local search p95 values were A 182.4 ms, B 197.9 ms and C 168.0 ms. Some evaluation overlapped a separate generation experiment, so load varied between arms. These are descriptive warm Python timings, not controlled evidence of an arm speedup and not a remote Go/network/complete-hook SLA.

CTO recommendation: preserve the current sparse MVP and treat this as a small positive internal signal. Prioritize scope retention and a cheap, matched prospective follow-up before committing to full-corpus generation. The proposed round-trip filter requires an original, unexpanded index and a matched random-removal control; filtering can preferentially retain familiar vocabulary and sacrifice recall. See followup-filter-proposal.md and followup-filter-related-work.md. This single partial-coverage result is insufficient for a paper claiming a general retrieval breakthrough or improved multi-skill completeness.

---

# Retained pre-outcome review

Reviewed `PROTOCOL.md` and `run.py` after preparation and before ranking outcomes. The reviewer
ran only CPU checks of cohort construction and labels; no GPU, generator, model training or
retrieval arm was executed. Source under review is the manifest-pinned run.py SHA-256
`5c9b5a1c141b6f62f8dfafe655eb0d6e40da565806c586a4fde679380115c259`, protocol SHA-256
`72dbef0ff2a659a2883c57a5c6593c721681ec44e03f3b32495116c4b18608d1`.

## Verdict

No blocking leakage, qrels or matched-product defect found in the prepared experiment. A/B/C
use the actual unchanged BM25F/policy/candidates/score/select pipeline with the shipped weights;
only trigger text differs. This is a cleaner product-path comparison than the earlier learned
fusion prototype. It remains a partial-coverage, same-source feasibility study, not admission.

## Independently verified before outcomes

`pre-evaluation-qa.json` records the CPU check:

* All512 document IDs exactly reproduce the prescribed document-hash ordering, independent of
  query labels. All2,048 query IDs reproduce their separate eligible-query hash ordering.
* Zero prior3,000 query-ID overlaps and zero normalized text overlaps with those queries.
  No exact normalized text duplicate groups occur within the new2,048-query sample.
* All2,048 gold sets exactly match positive qrels;4,121 relevant rows all have binary relevance1.
* The manifest assigns206 queries to any_gold_selected,1,842 to no_gold_selected and40 to
  all_gold_selected. The whole sample has649/725/674 queries for k1/k2/k3. These are frozen
  cohorts based on original512 assignment, including generation failures.

No public test file was needed for these checks. Internal freshness is relative to known,
recorded exposure; external/model-pretraining exposure remains unknown as the protocol states.

## Generation and data boundaries

The generation phase opens selected document data but not evaluation query text or qrels. Its
prompt contains only document-derived name, description and body excerpts. The preparation phase
uses labels only to summarize the independently selected evaluation cohort; they do not choose
which documents are enriched or enter the generator prompt.

Mechanical acceptance checks JSON shape, bounded word counts, normalized quote substring
membership and duplicate text. They do not establish that an evidence quote actually entails
the generated intent/query. This limitation is appropriately explicit in the protocol. JSON
parsing tolerates code fences and ignores extra keys/items rather than enforcing a strict schema;
report that behavior as a mechanical parser, not a formal strict-JSON-schema guarantee.

The planned blinded semantic spot audit is not programmatically required by `evaluate()`.
Complete it before ranking results, with no post-audit output repair or replacement. I froze a
16-document sample by SHA256('enrichment-audit-v1'+skill_id), recorded in `pre-evaluation-qa.json`.
Review source, accepted items and evidence only; do not use queries/ranks to select examples.
Count semantic problems descriptively and retain all outputs unchanged under the frozen filter.

## Product comparison and metric correctness

`dev_sparse.corpus_to_cards` initially supplies empty triggers, so assigning extra triggers does
not destroy authored originals in this dataset. A_original receives no added text; B receives
intent texts; C receives exactly those intents plus accepted query texts. Corpus bodies,
descriptions, scope, status, dependencies and default weights are unchanged. The helper would
need append semantics if applied later to a corpus with existing authored triggers.

All arms use root scope, top50 candidates and real selection k4, with admissibility passed to
selection. Retrieval top10 and actual injected selections are measured separately. Binary
nDCG uses the correct binary ideal DCG; recall divides by full gold cardinality. Empty retrieval
has Hit@1/Recall/nDCG0 rather than dropping its query. The qrel match confirms these binary labels
are the appropriate convention for this sample. No no-applicable examples exist.

Trigger enrichment changes global field length normalization and possibly document-frequency
statistics as well as direct token matches. Thus even a document receiving no extra trigger can
move in ranking. These are legitimate effects of the fixed index treatment; C-B is the effect
of adding pseudoquery text to an already changed trigger field, not a pure isolated semantic
quality or independent-score contribution. The no_gold_selected group captures collateral effects.

Paired bootstrap denominators are stable within each declared stratum. Overall C-A is the fixed
advance gate, with B-A/C-B diagnostic; there is no winner switching. The gate checks overall
Recall lower CI>0, nonnegative completeness point change, and no_gold Recall point change>=-0.5 pp.
It is a feasibility screen, not statistical proof of noninferiority on all guardrails. Shared-skill
clusters, multiple comparisons and40-query all-gold uncertainty remain explicit limitations.

## Nonblocking implementation/operations checks for final QA

* Before evaluation, verify exactly one raw and sidecar record for each of the512 assigned IDs,
  with matching order/IDs and no extras. Current resume verifies raw IDs and final sidecar count;
  it does not independently protect against every raw/sidecar partial-write mismatch.
* Verify source, raw, input, sidecar, run and protocol hashes against manifest/freeze. The evaluation
  function checks the important source and sidecar hashes but not every recorded hash itself.
* Confirm failed/empty generations remain in the assigned cohort. They must not change any/no/all
  group membership or be replaced by more convenient documents.
* Model-weight hashes are recorded after generation. Capture model/tokenizer/library versions in
  the final evidence; a directory name is not itself an integrity check. Greedy sampling is not a
  guarantee of numerical equivalence across GPU/runtime/batch changes.
* Local search timing repeats policy filtering both explicitly and inside candidates. It is useful
  as this harness's relative timing, not whole-hook or Go-service latency. `card_json_bytes` is a
  serialized-card proxy, not the complete postings/index-on-disk size.
* Generation runtime is bounded per process and resumes only identical frozen inputs. Report total
  accumulated cost across retries/restarts, not only the last process's wall time. Batched timings
  divided by8 are valid for this exactly divisible512-document run; do not reuse that formula for
  an arbitrary incomplete last batch without correcting its denominator.

Final numerical QA should recompute all6,144 arm/query rows, verify IDs and ranked/selected caps,
recompute binary metrics/strata and compare saved means. The semantic audit and saved outputs can
then support a bounded conclusion regardless of whether the primary gate passes.


## Before-outcome addendum: field normalization and dependency sensitivity

The BM25 field average length is computed over nonempty field lengths, not all 10,123 documents. A 512-document treatment therefore does not imply a 20-fold average-length dilution. Generated trigger terms can still change field document frequencies and term weighting, and B-to-C changes both per-document trigger lengths and the average over nonempty trigger fields. The full-package retrieval comparison includes those effects. It is not an isolated comparison of semantic paraphrase quality.

A supplementary component-bootstrap protocol was registered at 2026-09-06 09:45:38 UTC while results.json and rankings.jsonl.gz were absent. The primary query-bootstrap gate remains unchanged. Components formed by shared positive gold skills give 1,341 clusters among 2,048 queries, including 992 singletons; the largest contains 18 queries (0.879%) and the effective component count is about 777.9. This handles one observable dependence mechanism, not all dependencies induced by a shared corpus or related source repositories. See cluster-sensitivity-protocol.md and gold-sharing-components.json.

The final blind semantic audit covers all 16 fixed sampled documents before retrieval evaluation: 44 accepted items, 26 supported and 18 weak/generic, with no unsupported item in this reviewed sample. One sampled document is empty after filtering. Lost applicability scope is the recurring issue, such as removing Dafthunk, BTDP, Tailwind/frontend scope or repository-specific Express/globalAsyncHandler conventions. These descriptive, single-reviewer labels add no new numeric gate and do not change the frozen generator, filter, outputs, or admission criterion. Retrieval usefulness cannot be inferred from citation validity or semantic labels alone. See semantic-audit.json/md; the partial-v1 JSON is retained for provenance.

Independent generation QA passed for all 512 documents before retrieval: unique ordered IDs match the frozen manifest, all source/raw/side/freeze hashes match, and a separate implementation exactly reproduces the mechanical accepted items and rejection counters. It confirms 869 intents, 734 pseudoqueries, and 58 documents with no accepted enrichment (409 with intents, 365 with pseudoqueries). Empty outputs remain assigned to treatment for all reporting strata. See generation-independent-qa.json.
