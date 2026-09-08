# Reanalysis and pilot-design spikes

Run: `python3 research/spikes/2026-09-06-evidence/audit.py` from repository root.
Python stdlib; reads saved rankings and verified pinned corpus files. No retrieval, model, training or network. The two checks are post-hoc audits, not a new frozen test run or a model admission.

- `audit-results.json`:1250 matched queries x2 arms x2 scopes; hashes, paired2000-resample bootstrap, explicit all-query vs both-answered denominators and gold-cardinality strata. Historical reference comparator is shipped F0; flat remains an unadmitted experiment.
- `pilot-power.json`:exact binomial/sign-test design calculations. These are mathematical scenarios, not observed developer outcomes.

Findings: root Hit@1 +8.4pp, completeness+1.12pp CI[-1.12,3.44] over all1250; the old both-answered n1200 gives+0.67pp. HSR declines10pp on300 distractor queries, but their completeness also declines11pp. 215/1250 gold lists exceed4 items; AND-all-gold completeness cannot succeed under K4. Check AND/OR semantics before calling that a benchmark defect. There are no empty-gold cases, hence no NO_SKILL validation here.

For40 independent paired tasks, improve15%/regress5% (net+10pp) gives17.2% power at two-sided alpha.05. Zero harmful flips out of40 still permits7.2% harm at a one-sided95% upper bound. Clustering by developer and skill invalidates independence and can further weaken certainty.

CTO independently reviewed pairing, denominators, exact power and bounds: no blocking numerical issue. Applied corrections: metric_increases/decreases do not imply benefit for harmful exposure; reference F0 is shipped, flat not adopted. Query-bootstrap clustering, multiple comparisons and post-hoc strata remain limitations.
