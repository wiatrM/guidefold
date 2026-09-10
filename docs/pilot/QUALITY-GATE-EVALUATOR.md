# End-to-end quality-gate evaluator

`tools/pilot/run_verifiers.py` runs evaluator-only hidden verifiers and emits task-level replay
rows. `tools/pilot/quality_gate.py` is the mechanical pre-check for the proof-gated hierarchy
experiment. It consumes those rows and, separately, E2 delivery decisions. It does
not turn a retrieval hit into a task success and it never turns `unknown` into either success or
failure.

## Input

The task file may be JSONL, a JSON list, or `{ "rows": [...] }`. Each row represents one complete
`(task_id, arm)` attempt and should contain:

```json
{"task_id":"repo-c-017", "arm":"map+gate+evolution", "outcome":"success",
 "useful_delivery":true, "harmful_load":false}
```

Allowed outcomes are `success`, `failure` and `unknown`. The evaluator reports unknown coverage
separately and marks the overall result `inconclusive` when the candidate has unknown outcomes or
the required baseline/E2 evidence is absent.

The optional E2 file has one row per designed trigger. `harmful:true` marks a conflict, stale,
or out-of-scope case; `actual_action` is `LOAD` or `ASK`; `expected_action` is normally `ASK`.
Loading a harmful row is counted as a harmful delivery even when the task itself would otherwise
pass.

## Report and decision rule

The report contains per-arm task success, unknowns, harmful-load Wilson upper bound, useful
coverage, the best non-gated baseline and the paired success delta. It also reports the number of
E2 trigger cases, correct `ASK`s, harmful loads and stale/conflict deliveries.
When task rows carry execution telemetry (directly or under `telemetry`), the same per-arm report
also aggregates harness errors, SEARCH/USE/ASK counts, input/output tokens, tool calls and elapsed
time. An unobserved metric is `null`; an observed zero remains zero.

The reported checks are deliberately the pre-registered publication gate:

* candidate task success is no more than five percentage points below the best non-gated arm;
* useful coverage is at least 90% of that baseline;
* the two-sided 95% Wilson upper bound for harmful E2 loads is at most 5%;
* no designed stale or conflicting case delivered a body.

The command exits `0` only for `pass`; `fail` and `inconclusive` exit `2`, so CI cannot mistake
missing evidence for a passing experiment.

```bash
python3 tools/pilot/run_verifiers.py \
  --tasks path/to/evaluator-task-bank.json \
  --workspace-root path/to/workspaces \
  --arm map+gate+evolution \
  --output path/to/task-replay.jsonl

python3 tools/pilot/quality_gate.py \
  --tasks path/to/task-replay.jsonl \
  --e2 path/to/e2-decisions.jsonl
```

This evaluator is an analysis guard, not a substitute for the frozen protocol, hidden verifiers,
or two independent human judgements where deterministic acceptance is impossible. Freeze the task
bank, repository snapshots, model, harness, prompts, map, policy and seeds before collecting rows.

## Human annotation packet gate

The source-disjoint C/C′ corpus has a separate blind packet. Before any model call, verify its
integrity and blank state:

```bash
python3 tools/pilot/verify_annotation_packet.py \
  --packet .guidefold/checks/source-disjoint-urct-2026-09-10/annotation_packet \
  --mode blank
```

After two reviewers independently complete every field, run the same command with
`--mode annotated`. It checks allowed labels, immutable source hashes and line-bounded evidence,
then reports raw agreement and disagreements. `ANNOTATION_READY_FOR_ADJUDICATION` is not a gold
label or a task result; disagreements require a separately recorded adjudication before E2 rows
can be scored. The verifier deliberately rejects incomplete or out-of-range forms and keeps
model calls disabled throughout annotation.

The hidden-verifier runner leaves useful-delivery and task-level harmful-load fields unknown,
because a verifier cannot observe delivery usefulness or E2 safety. Those fields must come from
telemetry or E2 labels; the quality gate preserves null for missing observations.

## Pi execution runner

For an end-to-end agent trial, use `tools/pilot/run_agent_tasks.py`. It copies each source workspace
to a temporary directory, enables Pi's `read,bash,edit,write,ls` tools, and runs the verifier from a
separate evaluator root after Pi exits. The task bank is never sent to Pi. Verifier argv entries may
contain the literal `{workspace}`, which is replaced with the isolated workspace path; keep verifier
files outside the source workspace so they remain hidden.

```bash
python3 tools/pilot/run_agent_tasks.py \
  --tasks evaluator/task-bank.jsonl \
  --workspace-root evaluator/workspaces \
  --evaluator-root evaluator/verifiers \
  --output .guidefold/checks/pilot-map-gate \
  --arm 'map+gate' \
  --bridge tools/pilot/bridge.py \
  --nodes-file evaluator/nodes.json \
  --guidefold-skill skills/guidefold/SKILL.md \
  --token-file .guidefold/compose/secrets/api_token \
  --delivery-policy proof_gated
```

The emitted `agent-results.jsonl` can be passed to `quality_gate.py`. Agent failures, verifier
timeouts and malformed output become `unknown` with `harness_error`; a non-zero verifier exit is a
task `failure`. SEARCH/USE/ASK counts come from the redacted Go bridge trace and are never inferred
from the final answer.
