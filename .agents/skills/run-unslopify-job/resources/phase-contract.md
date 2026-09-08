# Phase contract

Each phase validates `jobId`, attempt, lease, and numeric fence, writes through a temporary path, then atomically promotes a checkpoint. Heartbeat extends queue visibility. Before every checkpoint, upload, or state transition, revalidate the current fence.

| Phase | Source writes | Required checkpoint |
|---|---:|---|
| capture | no | `capture/manifest.json`, sanitized inputs, screenshots |
| prime | no | research packet, source/slop audits, preservation contract, immutable design brief, page/asset plans |
| media | staging only | gateway generation ID, cost and hash-bound delivery manifest |
| codex | yes, Codex only | runnable source, build notes, preservation implementation |
| media-integrate | declared generated paths only | verified integration report |
| qa | reports only | `reports/qa-report.json` plus evidence |
| claude | `review.json` only | structured verified findings |
| codex-repair | yes, Codex only | `reports/repair-log.json`, updated source |
| final-qa | reports only | final `reports/qa-report.json` plus regression evidence |
| package | package output only | `result.json`, ZIP, dist, artifact manifest |

Provider credentials mount only in the matching phase. Capture, QA, and package receive no AI auth. Runtime pods receive no Kubernetes ServiceAccount token and no Supabase/controller secrets. Codex and PRIME auth are separate PVCs; Claude uses a dedicated `CLAUDE_CODE_OAUTH_TOKEN` Secret.

At most two attempts are allowed. An expired lease may be reclaimed with a new attempt and fence. The old controller/pod cannot cancel, delete, checkpoint, complete, or publish the newer attempt. Cancellation is cooperative first and exact-fence cleanup second.

A PRIME brief with `outcome: needs_input` does not checkpoint or start the writer. It
emits the non-retryable `JOB_NEEDS_INPUT` code and releases the lease. An operator
resolution is reintroduced into the next sanitized research context with the
`[OPERATOR_DECISION]` prefix. Provider reauthentication, capacity pauses, and operator
input pauses do not consume an execution retry when explicitly resumed.

Package success requires all required artifacts, current fence, final QA, signed upload URLs, preview expiry, and secret scan. Runtime may emit a redacted HarnessCandidate but cannot edit the read-only HarnessRelease.

Machine handoffs must validate against the corresponding files in `/harness/schemas`; prose-only handoffs are invalid.
