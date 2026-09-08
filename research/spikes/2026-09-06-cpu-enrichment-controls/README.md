# CPU-only enrichment controls

Frozen, internal follow-up to the partial-coverage query enrichment pilot. No GPU, no new generation and no production edits. All five primary arms and one separately specified full-coverage control completed; both independent QA scripts passed. See the final report linked below.

Read [PROTOCOL.md](PROTOCOL.md), then [related-work.md](related-work.md). The protocol and run script hashes are bound by manifest.json. Arm texts and filter decisions are frozen separately before routing the evaluation queries. Analysis/QA source hashes were recorded before analysis in statistics-code-freeze.json.

## Reproduce

From the project root, using Python with PyYAML and NumPy available:

```sh
python research/spikes/2026-09-06-cpu-enrichment-controls/run.py prepare
python research/spikes/2026-09-06-cpu-enrichment-controls/run.py freeze-arms
nice -n 10 python research/spikes/2026-09-06-cpu-enrichment-controls/run.py evaluate
python research/spikes/2026-09-06-cpu-enrichment-controls/analyze.py
python research/spikes/2026-09-06-cpu-enrichment-controls/qa-independent.py
python research/spikes/2026-09-06-cpu-enrichment-controls/diagnose-candidates.py
```

The first two commands refuse to overwrite their freezes. Do not delete frozen outputs to obtain a better result. Use a new experiment directory/cohort for a new hypothesis. Evaluation resumes only completed, hash-checked arms; an interrupted partial arm requires a recorded interruption and explicit handling before rerunning that same frozen arm.

The environment name used locally contains gpu-venv, but this experiment imports no GPU framework; CUDA_VISIBLE_DEVICES is empty, numerical thread counts are one and evaluation runs at nice 10. The only routing optimization memoizes product integer scores for individual tokens in an immutable, all-visible index. The full policy/candidates/score/select path remains the product code, checked against its unmodified scorer on 64 preselected queries per arm plus 64 generated texts. Timings are not a product-performance claim.

## Artifacts

- manifest.json and evaluation-queries.jsonl: cohort provenance/exclusions.
- item-decisions.json and filter-diagnostics.json: every accepted generated item's source rank and retention.
- arm-texts.json, matched-counts.json, arms-freeze.json: all five intervention texts and controls.
- rankings-*.jsonl.gz: full candidate top 50 and selected cards for each query/arm.
- complete-*.json and execution.json: completion hashes and exact parity checks.
- results.json: prespecified outcome and uncertainty calculations.
- independent-qa.json: independent label/ranking/control/hash validation and statistical reconstruction.
- candidate-diagnostics.json: descriptive oracle bounds, not a proposed algorithm's measured performance.

## Completed follow-up

[Polish final report](../../../docs/research/2026-09-06-agent-skill-scan/cpu-enrichment-controls.md) and [TRAIN label-quality audit](../../../docs/research/2026-09-06-agent-skill-scan/skillret-train-label-audit.md).

The additional F control has its own FULL-COVERAGE-PROTOCOL.md, full-coverage-freeze.json, full-coverage.py, analyze-full.py and qa-full.py. Its results are exploratory and do not change the original four-test family. full-coverage-fragility.json records a post-hoc exact check of its four changed recall outcomes.

For the label audit, run audit-labels.py or inspect label-quality-audit.ipynb. The script checks structure and prepares a 120-query packet, but does not infer semantic relevance. Existing review-packet files are preserved on rerun, including any reviewer judgments subsequently added. The notebook is an unexecuted companion; the script has run. The three illustrative label concerns are not a prevalence estimate or a completed independent annotation study.
