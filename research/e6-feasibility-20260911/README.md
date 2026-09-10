# E6 feasibility replay — 2026-09-11

**Status:** exploratory end-to-end evidence; not a publication result.  
**Purpose:** verify that the Pi runner executes hidden-verifier tasks and records the
SEARCH/USE/ASK and delivery boundary for a candidate and a flat legacy control.

## Frozen inputs

The task bank contains four isolated file-edit tasks and is shared by both arms.
The hidden verifier is outside every Pi workspace. The runner records the following
task-bank hash:

```text
6829608759a735d241d69e3592eb8adc54661d38446df31ca92488c2708484a0
```

The evaluator file hash is `7de52ae37846b5404f244c58c74bfb6c4e10852d8511beaadb8c339244b1fea6`.
The Guidefold skill, bridge and nodes are fingerprinted in each arm's
`run-manifest.json`.

The retained `artifacts/` directory contains both arm result files, manifests, compact bridge
traces and the quality-gate JSON. It contains no bearer token or full skill body.

## Paired replay

| Arm | Success | SEARCH | USE | ASK | Delivered body chars | Harness errors | Wall time |
|---|---:|---:|---:|---:|---:|---:|---:|
| `map+gate+evolution` / `top_down` / `proof_gated` | 3/4 (75%) | 12 | 16 | 16 | 0 | 0 | 150,782 ms |
| `flat` / `flat` / `legacy` | 3/4 (75%) | 4 | 17 | 0 | 457,275 | 0 | 185,857 ms |

The same task (`t01`) failed in both arms because the agent omitted the final period
from the required exact line. Tasks `t02`–`t04` passed in both arms. The corrected
fixture was replayed with the full shared task-bank hash; no single-task rerun was
silently mixed into this table.

The candidate made three times as many SEARCH calls and received an `ASK` for every
USE because the live cards lacked `source-proof-v1`. The legacy arm exposed 457,275
body characters. This is direct evidence that the gate changes delivery behavior
while preserving task success on this tiny feasibility bank. It is not evidence that
the candidate improves task success: paired delta is 0 pp, and useful-delivery and
harmful-load labels are still unknown.

## Reproduction

```bash
python3 tools/pilot/run_agent_tasks.py \
  --tasks research/e6-feasibility-20260911/task-bank.json \
  --workspace-root research/e6-feasibility-20260911/workspaces \
  --evaluator-root research/e6-feasibility-20260911/evaluator \
  --output <run-output> --arm map+gate+evolution --strategy top_down \
  --delivery-policy proof_gated ...
```

Use a separate output directory for each arm and retain the manifests and traces.
The quality gate must remain `inconclusive` until E2 conflict/revision rows and
useful/harmful observations are supplied. The next real run is the frozen E6.7 bank,
not another hand-written four-task bank.

An independent replay of the retained candidate rows is:

```bash
python3 tools/pilot/quality_gate.py \
  --tasks research/e6-feasibility-20260911/artifacts/candidate/agent-results.jsonl
```

The command intentionally exits `inconclusive` when E2 decisions or useful-delivery labels are
absent; that is the expected state of this feasibility run.
