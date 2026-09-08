---
name: run-unslopify-job
description: Orchestrate a complete queued Unslopify job through capture, PRIME research, shaping, Codex build, deterministic QA, Claude review, one repair, final QA, and packaging.
---

# Run Unslopify Job

Use this as the top-level private-alpha workflow. It is a fenced state machine with one writer, autonomous operator-funded media within the entitlement, and typed source/code fallback before an uncertain charge.

## Resource routing

- Always load [orchestration workflow](./resources/workflow.md) for phase order, fallbacks, automatic gates, and completion behavior.
- Load [phase contract](./resources/phase-contract.md) when executing, resuming, retrying, checkpointing, canceling, or packaging a job.

Never publish from a stale fence. Runtime jobs may propose a HarnessCandidate but cannot mutate the active harness.
