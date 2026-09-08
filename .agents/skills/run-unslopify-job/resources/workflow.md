# Unslopify orchestration workflow

## Phase order

Before phase 1, use `route-agent-models` to snapshot `qualityProfile`, `advisorPolicy`, and `writerProvider`. The snapshot is immutable for the revision; a later operator tuning change never changes a running job.

1. `capture`: Playwright capture and sanitizer, no AI auth.
2. `prime`: one read-only Job with ordered research and shaping: `research-redesign-source`, the mandatory `ui-ux-pro-max` evidence pass, conditional `direct-motion-site-prompts` for every motion-led direction, then `shape-premium-direction`, which invokes `select-media-generation-route` before writing generated asset slots. Motion-led briefs contain one `Motion Prompt Packet`. It emits the sanitized research contracts and immutable attempt brief. RLM depth is 1 with at most two children. If PRIME is unavailable, Codex performs the same stages without source writes.
3. The route-selection skill may choose source, deterministic motion, mock/local PoC, or an approved paid portfolio. The private alpha executes operator-funded Vercel AI Gateway video and Higgsfield image/video routes within the immutable entitlement. Approval is automatic when the operator policy and live cumulative quote permit it; customer input is never required for spend inside that envelope. Run `media` and the writer according to the runtime's serial/parallel policy. `media` talks only to the internal MCP gateway with exact plan, asset, provider, request, fence, and budget capabilities; the writer builds final-size placeholders. Pre-submit provider, quote, or capacity failure selects the audited source/code fallback. An uncertain post-submit state enters reconciliation without a duplicate submission and does not block the page build.
4. `media-integrate`: after both checkpoints, atomically promote hash-bound staged assets.
   Skip both media phases for source/mock plans.
5. `codex`: legacy phase name for the selected sole writer, which uses `build-motion-landing`. Codex/Luna is default; Claude/Sonnet is allowed only when the operator snapshot selected Claude before claim.
6. `qa`: deterministic initial `audit-release-quality` gates.
7. `claude`: review-only and returns `review.json`.
8. `codex-repair`: legacy phase name for one repair pass by the same selected writer, containing only verified, in-scope findings.
9. `final-qa`: rerun failures, all release blockers, and smoke regressions.
10. `package`: sanitize and publish preview, ZIP, screenshots, optional motion, `DESIGN.md`, preservation report, QA report, and result manifest.

User-visible states map to `queued → claimed → capturing → researching → shaping → building → qa → reviewing → repairing → qa → packaging → completed`. The researching-to-shaping transition occurs inside the PRIME Job. Exceptional states are `needs_input`, `needs_reauth`, `paused_capacity`, `cancel_requested`, `canceled`, and `failed`.

## Provider execution

Model IDs and efforts come only from `route-agent-models`; customer input cannot override them. Fable requires operator-configured availability and has no silent fallback. PRIME reports its applied `xhigh` ceiling separately from requested SOL `ultra`.

Codex uses `codex exec --json --ephemeral --sandbox workspace-write --ask-for-approval never --output-schema /harness/job-result.schema.json -o /artifacts/result.json -`.

Claude uses `claude -p --output-format stream-json --verbose --max-turns <budget> --permission-mode acceptEdits`, with `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, isolated `CLAUDE_CONFIG_DIR`, updater disabled, explicit tool lists, and no bare/dangerous bypass mode.

PRIME runs `prime-agent --mode rpc`, not `-p`; `autoRefine=false`, trace sharing off, read-only harness, RLM depth 1, at most two children, external timeout, and explicit terminal-event handling.

## Authority and fallback

PRIME researches, the snapshotted provider writes, deterministic tools test, Claude reviews, and the same writer repairs. Codex is the default writer. Claude becomes writer only through the operator-owned pre-claim snapshot or a new revision. Never switch writer mid-job or silently switch to a paid provider.

Proceed automatically after submission. Use `needs_input` only for a real preservation, rights, safety, or scope conflict that the system cannot resolve conservatively. Operator-funded media inside the snapshotted entitlement never pauses the customer. Use `needs_reauth` for required model auth and `paused_capacity` for a required provider's unavailable capacity. Check cancellation before and after external actions.

## Provider skill allowlist

- PRIME: `research-redesign-source`, mandatory `ui-ux-pro-max`, conditional `direct-motion-site-prompts`, `shape-premium-direction`, `select-media-generation-route`, `design-taste-frontend`, `refactoring-ui`, `top-design`, `cloudfloo-visual-system`, and conditional `cloudfloo-cinematic-landing`/`hooked-ux`. No build or refinement skills.
- Selected writer/repair provider: `build-motion-landing`, mandatory `ui-ux-pro-max`, conditional `direct-motion-site-prompts`, `humanizer`, `avoid-ai-writing`, `cloudfloo-visual-system`, conditional cinematic/scroll/brand/Higgsfield skills, and the specific Impeccable commands named by the brief or verified findings.
- Claude reviewer: `audit-release-quality`, `cloudfloo-quality-gate`, `ui-ux-pro-max`, and conditional `direct-motion-site-prompts` evidence/checklists read-only; read-only tools plus structured output.

Claude findings use stable IDs and severity `critical|high|medium|low`, with category, file/evidence, reproduction, preservation impact, and proposed remediation. The selected writer marks each repair finding `applied|rejected|not_reproducible` with evidence; only critical/high verified findings are mandatory, and no change may violate preservation.

## Completion

Every completed phase emits sanitized wall time, route dimensions, and provider-reported usage when available. Also record the first failing deterministic command, stable error code, retry class, and checkpoint reached; never include source copy or provider diagnostics. Missing usage stays `none`; estimates stay `estimated`; cache semantics never justify an invented total or subscription charge.

Completion needs a current fence, valid packaging `result.json`, passing final QA, secret-scan pass, private artifact upload, and preview metadata with an opaque token, separate origin, CSP, `noindex`, iframe sandbox policy, and 14-day expiry. ZIP download uses a short-lived signed URL. A stale worker terminates without checkpoint or upload. Partial artifacts never produce `completed`.
