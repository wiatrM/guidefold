# CTO structural audit: NO_SKILL and full-body hydration

Registered before execution on 2026-09-06. Diagnostic replay of the unchanged product on
synthetic Meridian development fixtures, not a retrieval-quality trial. No configuration
is tuned; no frozen test corpus is queried; no model/API is called.

Questions fixed before execution:

1. How many of the 44 already labelled no-applicable development queries produce an empty
   selection? Compare score distributions with positive cases without choosing a threshold.
2. Does a non-empty lexical match mechanically dominate the default magnitude threshold,
   even for deliberately unrelated sentences containing corpus tokens? Probes are diagnostics.
3. Exact body-byte and heading counts of all 26 cards; how many fit existing conservative USE
   budget semantics at fixed 1024, 4096 and 16384 budgets? No semantic section-retrieval claim.

Run from repository root with Python 3.12 and PyYAML:

    python3 research/spikes/2026-09-06-cto/audit.py

Imports the actual CLI Index/Router and existing development cases, writes results.json
alongside itself, and leaves product artifacts untouched. Do not choose a confidence
threshold from these data. This is an isolated research audit authorized by the current
user request, not a new runtime component or a new neural research family.
