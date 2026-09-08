# Fixed model-routing policy

## Immutable input

Snapshot these operator-owned values into `JobSpec.modelRouting` at submission:

- `qualityProfile`: `fast`, `balanced`, or `premium`;
- `advisorPolicy`: `auto`, `always`, or `off`;
- `writerProvider`: `codex` or `claude`.

Do not accept model IDs, effort strings, provider keys, or fallback prices from the customer. A later operator setting change applies only to new jobs.

## Routes

| Stack | Advisor | Technical lead | Executor |
| --- | --- | --- | --- |
| GPT | `gpt-5.6-sol`, `ultra` | `gpt-5.6-terra`, `high` | `gpt-5.6-luna`, `medium`; `high` for premium motion or repair |
| Claude | runtime-configured Fable, `high` | `opus`, `high` | `sonnet`, `medium`; `high` for premium motion or repair |

Fable is not an official Anthropic CLI alias in the pinned harness. A Claude advisor route requires an operator-controlled, pinned `UNSLOPIFY_CLAUDE_FABLE_MODEL` that passed bootstrap readiness. Missing or rejected configuration becomes `PROVIDER_MODEL_UNAVAILABLE` before a writer Pod starts. Never probe a guessed alias, substitute a model, or fall back to paid API usage.

PRIME RPC applies its documented maximum `xhigh` when it hosts the SOL advisor. Record `requestedReasoningEffort=ultra` and `reasoningEffort=xhigh`; never claim that PRIME applied `ultra`.

## Advisor gate

- `always`: use the advisor for every job.
- `off`: skip the advisor.
- `auto`: use it only for the explicitly purchased `premium` quality profile.

Skipping the advisor does not skip source research or deterministic QA. Route ordinary research through the technical-lead model.

## Phase ownership

1. PRIME researches and shapes; it never writes site code. For an advised GPT route, SOL writes a validated advisory handoff, then Terra produces the technical direction.
2. The selected writer owns both build and the single repair loop.
3. With `writerProvider=codex`, Luna is the sole writer. With `writerProvider=claude`, configured Fable writes a validated advisory handoff when gated on, Opus writes a validated technical plan, and Sonnet is the sole writer.
4. Claude review always uses Opus as an independent, read-only review after deterministic QA.
5. Deterministic QA blocks publication regardless of model judgment.

`fast` and `balanced` are not aliases: fast uses medium TL reasoning, while balanced uses high TL reasoning. Both keep the executor at medium unless premium motion or the premium profile requires high. Every prelude and main call emits its own duration, usage source, token fields, model, role, and requested/applied reasoning.

Do not run two writers in parallel. Do not switch writer after a failure. An operator must create a new revision to change writer provider.

## Time discipline

- For `fast`, target capture plus research/shaping in 2–5 minutes and hard-bound research at 10 minutes. Do not run the advisor.
- For `balanced` and `premium`, keep research and review at 10 minutes or less each.
- Keep initial build at 30 minutes or less and repair at 15 minutes or less.
- Prefer `medium` executor effort for standard work.
- Raise executor effort to `high` only for premium motion, scroll-scrub, or a preservation-sensitive repair.
- Do not spend advisor time on a simple, well-specified `fast` job.
- Prefer the latest valid phase checkpoint over repeating completed model work after an infrastructure-only failure. If the runtime cannot resume that phase safely, emit the limitation in telemetry rather than hiding the repeated time.
