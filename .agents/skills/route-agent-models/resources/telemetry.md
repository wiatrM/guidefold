# Phase telemetry contract

Emit one sanitized `UNSLOPIFY_PHASE_METRICS` record per completed phase. Store it as `job_events.metadata.metrics` while retaining top-level `durationMs` for compatibility.

Required dimensions:

- engine, provider, role, fixed model, applied reasoning effort;
- wall duration;
- `usageSource`: `reported`, `estimated`, or `none`.
- terminal phase outcome, stable failure code, retry class, attempt number, and last valid checkpoint.

Optional reported values are API duration, input/output/reasoning tokens, cache-read/cache-write tokens, provider-reported total tokens, tool calls, turns, and retries. When requested and applied reasoning differ, record both.

Never include prompts, responses, source copy, session IDs, auth material, request IDs, signed URLs, or provider diagnostics. Never label a local estimate as reported.

Do not derive `totalTokens` when provider cache semantics are ambiguous. Prefer the provider total; otherwise leave the total absent and expose components. Do not infer subscription cost from API list prices or present it as an actual charge.

Build ETA ranges only from completed jobs with the same quality, motion, writer, and advisor route. Track capture, research, build, deterministic QA, review, repair, package, media queue, and media generation separately so one slow provider does not distort the entire pipeline. Until enough samples exist, show elapsed time and phase rather than false precision. The user may close the page; terminal and operator-action states are asynchronous notifications.
