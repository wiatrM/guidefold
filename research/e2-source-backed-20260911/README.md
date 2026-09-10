# Source-backed E2 delivery matrix — 2026-09-11

## Status

This is a deterministic R/Q evaluator for the proof-gated delivery policy. It is not a
human semantic evaluation, a model benchmark, or evidence that an agent completed a user
task. The matrix is deliberately kept separate from task-level rows so a safety result
cannot be inflated by pooling incompatible evidence.

## Frozen inputs

- Manifest: `docs/reports/bakeoff/SOURCE-DISJOINT-URCT-MANIFEST-2026-09-10.json`
- Snapshot replay: `/tmp/guidefold-urct-replay-next`
- Manifest SHA-256: `47a145923f1fb256a2d6c03f9a117fbbde9fe99a6ec1d0d419bc9b0c7fa1f3ec`
- Targets: engineering C/C′ and documentation C/C′, fetched from the pinned public A/B/C/C′ corpus.
- Source integrity: the runner checks every target snapshot against the manifest digest before emitting a row.

## Protocol

Each target contributes 19 harmful mutations (conflict, deprecated, out-of-scope,
stale revision, tampered body, incomplete closure, and sibling transfer, cycled) and one
safe complete-proof LOAD. The candidate applies the gate and must return `ASK` for every
harmful mutation. The flat control exposes the same source body for every case. Candidate
and control JSONL files are emitted separately.

Command:

```text
python3 tools/pilot/real_e2_matrix.py \
  --manifest docs/reports/bakeoff/SOURCE-DISJOINT-URCT-MANIFEST-2026-09-10.json \
  --snapshots /tmp/guidefold-urct-replay-next \
  --output-dir /tmp/guidefold-real-e2-next
```

## Result

| Arm | Rows | Harmful cases | Harmful LOADs | Safe LOADs |
|---|---:|---:|---:|---:|
| `map+gate+evolution` | 80 | 76 | 0 | 4 |
| `flat` control | 80 | 76 | 76 | 4 |

The quality gate reports 76/76 correct `ASK` decisions. The one-sided Wilson 95% upper
bound for harmful delivery is **4.81%**, below the pre-registered 5% safety threshold;
stale/conflicting body delivery is zero. This supports the deterministic policy boundary
on these source-backed mutations. It does not establish semantic correctness, transfer
across natural hierarchies, or task success.

The same scorecard combines this E2 result with the four-task Pi feasibility replay. That
overall verdict remains `inconclusive`: both arms achieved 3/4 task success, useful-delivery
labels are missing, and the task bank is intentionally small. Human annotation and a larger,
source-owner-disjoint task bank remain required for the publication gate.

## Reproduction artifacts

- `candidate-e2.jsonl` — proof-gated rows, separate from control.
- `flat-e2.jsonl` — flat exposure control rows.
- `summary.json` — row counts and safety totals.
- `quality-gate.json` — combined scorecard output, including the explicit missing-evidence list.
- Runner: [`tools/pilot/real_e2_matrix.py`](../../tools/pilot/real_e2_matrix.py).
