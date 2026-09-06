# Readout and implementation notes (no scientific configuration changes)

The run uses full-bank score construction then the best200 ranked documents for shared product policy/select. The phrase 'candidate union' in the prospective protocol is imprecise; there is no production top50-union restriction. This applies identically to all five new arms, and does not establish production candidate-source feasibility.

The query length counter in the encoding function excludes the instruction prefix; the final independent QA recomputes lengths including that prefix. Document counters are unaffected. Cached name/description counts may be absent, and cache-read times are not encoding benchmarks.

Additional provenance is in provenance.json (library versions, imported helper/CLI, tokenizer/config/weights SHA256, GPU). manifest.json identifies the actual training script and inputs; pretraining-manifest-v1.json retains the interrupted pre-training attempt. The only restart repaired DEV document exposure in training negatives before any learned outcome existed. All six arms, seed, data selection and optimization settings were unchanged.

Heads differ in capacity: flat65parameters, field129, sparse-field81. Both capacity and aggregate encoder token budget are confounders for attributing an effect purely to field semantics. This feasibility result may nominate a follow-up with matched budgets/capacity; no new hyperparameters were selected from DEV.

The root-scope corpus contains no negative triggers, deprecations or dependency edges. Reusing policy_filter/select preserves the API path but does not stress policy conflicts or graph closure. No NO_SKILL admission is possible because labels contain only positive tasks. The five arms explicitly use identical abstention-disabled selection; the shipped reference retains its own behavior.

Independent CTO review checked binary nDCG on100 independent CPU cases and reconciled all3000 selected queries against5785 binary training qrels. A separate raw-output QA recomputes the five final-arm metrics. Baseline replay was checked against P-shipped:1000/1000 top10 rankings and injected sets identical. The replay is historical context, not a simultaneously measured serving comparison.
