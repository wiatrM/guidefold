# End-to-end telemetry replay

`tools/pilot/telemetry_report.py` is the independent scorecard replay for the
E6.7 task harness. It accepts JSONL, a JSON event list, or an exported object
with an `events`/`rows` list:

```text
python3 tools/pilot/telemetry_report.py \
  --events path/to/run.jsonl \
  --json-out path/to/report.json
```

The report contains task success/failure/unknown, harness errors,
SEARCH/USE/ASK counts, token totals, tool calls and latency. `success_rate`
uses all finished tasks; `known_success_rate` is shown separately for the
success/failure subset. A missing cost or latency field produces `null` and an
observation flag, never zero.

This tool counts event occurrences. It does not deduplicate retries, infer
that a loaded skill helped, or pair experimental conditions. Use the durable
telemetry ledger for deduplication and `tools/pilot/analyze.py` for the frozen
paired-task contrasts. Keep the raw event log, protocol hash, model/router
versions and repository snapshot beside every report so an independent replay
can reproduce it.

The implementation and tests are regression tooling. A real E6.7 result still
requires frozen tasks, a hidden verifier or independent evaluators, and explicit
unknown coverage.

