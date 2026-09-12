# README copy and architecture review
Status: reviewed locally; GitHub publication tracked separately.
Date: 2026-09-08.
Purpose: owner-requested README rewrite, demo, existing logo and technical architecture images.
Scope: documentation only; no product requirement, runtime or pricing change. Supports developer onboarding (U8/P10).
Inputs: README, services/search/README.md, HARNESS-SERVICE-CONTRACT, SEARCH-USE-TELEMETRY and the owner's demo URL.
Replaces: previous README prose. Does not replace the API contract or architecture decisions.
Index: [README](../../../README.md).

Related: [worktree integration and checks](integration-20260908.md).

## Copy audit
Humanizer first pass and avoid-ai-writing second pass applied to README.
Protected: product name, existing logo, demo URL, commands, paths, endpoint names and Apache-2.0 license.
Editable: introduction, problem, architecture explanation, setup guidance and feedback request.
Removed: blanket integration claims and any implication that paid hosting has shipped.
Deliberate exception: "harness" is the technical component name explicitly requested by the owner, including --harness and contract links.
No fabricated customer results or performance claims. Fixture examples are labelled.
No runtime behavior changed; Go, UI and end-to-end production tests are outside this docs-only change.

## Verification
Windows Python, fictional Meridian fixture: validate returned 26 skills and 0 errors; where, find and load exited 0. All relative README links and image paths exist. git diff --check passed. No forbidden promotional vocabulary found. The Docker deployment and real harness delivery were not retested for this documentation change.

## Images
Built-in imagegen, not CLI/API fallback. Existing logo copied unchanged from prototypes/pipeline-hifi/public/assets/guidefold-mark.png.
Final project assets:
- [Logo](../../assets/readme/guidefold-mark.png)
- [Harness integration](../../assets/readme/harness-integration.png)
- [Go service](../../assets/readme/go-service.png)

Visual review corrected invented slogans, request/response arrowheads and the Go process boundary around Postgres.
The repeated database in the second image is explicitly the same database; horizontal arrows mean database access.
Diagrams simplify the linked contracts and are not evidence of identical vendor integration support.

## Generation prompts
### Image 1

Use case: infographic-diagram. Create a professional C4-style software architecture diagram for Guidefold README, landscape 1800x1100 feel, white background, dark navy typography, disciplined grid, crisp orthogonal connectors with explicit arrowheads, restrained orange accent. No illustration, maps, decorative textures, gradients, 3D or mascots. Title "Guidefold · harness integration". Left boundary "Developer workstation": boxes "Coding harness" with small "Claude Code / Codex / Copilot"; connected to "Guidefold CLI / adapter" with small "task · cwd · target paths". Bottom within workstation "Local sparse router" connected to adapter, label "local mode". Right boundary "SEARCH / USE service": box "Go HTTP API" above cylinder "Postgres" with bidirectional arrow. Between adapter and API two horizontal exchanges clearly numbered: "1  SEARCH → scoped skill cards + revisions" and "2  USE → exact body + SHA-256". A final workstation box "Agent context" receives adapter arrow labeled "verified instruction delivery". Bottom separate authoring lane: "Git: SKILL.md + guidefold.yaml" → "Validate / build snapshot" → "Go publisher" → Postgres, label last edge "atomic activation". Footer: "Adapter support depends on the coding harness. Delivery is not proof of use." Technical documentation quality, large readable labels, ample margins, explicit system boundaries. Do not imply native vendor integration or LLM in retrieval.

Correction:
Correct this technical diagram. Remove both invented slogans in top-right and bottom-right entirely. Remove /search /use /health labels inside Go API. Make both horizontal SEARCH and USE connectors bidirectional with arrowheads on both ends (requests and responses). Expand Developer workstation boundary to include Agent context box. Keep all other content and professional style unchanged. No new text or decorative additions.

### Image 2

Use case: infographic-diagram. Professional implementation-level architecture diagram, landscape, clean white background, dark navy text, muted orange highlights, C4/engineering documentation style. Title "Guidefold · native Go service". Main large boundary labeled "Static Go executable · API request path". Inside vertical flow with exactly these boxes: "HTTP + bearer authentication" → "Schema validation + admission" → "Resolve repository scope" → "Policy + integer BM25F" → "Dependency graph + selection" → "SEARCH: cards + exact revisions". Beside this flow an independent branch from scope box → "USE: revision + visibility check" → "Full body + SHA-256". Right side Postgres cylinder labeled "Postgres" with sublabels "Active snapshot", "Canonical postings", "Immutable skill bodies"; connect scope, scoring and USE to storage, noncrossing orthogonal lines. Bottom outside API boundary, lane "Committed Git snapshot" → "Go publisher" → Postgres labeled "validate + atomic activation". Small factual notes at bottom: "Default: router_bm25f_v1" and "No Python or LLM on the default API request path". No React, WorkOS, model provider, Redis, Kubernetes, speculative components or performance numbers. Large legible exact text; all arrows unambiguous. Give endpoints readable labels "POST /v1/search" and "POST /v1/use" near respective outputs. Professional accurate schematic, not marketing art.

Correction:
Correct this technical architecture diagram. Postgres must be OUTSIDE the Static Go executable boundary: redraw that boundary enclosing only the Go processing boxes, ending before the Postgres cylinder. Label lower repeated database 'Same Postgres' so it cannot be interpreted as a second database. Keep all remaining exact text and design unchanged. No new slogan or content.

## Landing v2 JS budget

Date: 2026-09-11. Pre-change baseline captured on unchanged code (before the Landing v2 tokens
and evidence-mirror change), via `pnpm build`.

Chunk: `dist/assets/landing-P09dfzH_.js` — 76,889 bytes raw, 25,216 bytes gzipped
(`gzip -c dist/assets/landing-P09dfzH_.js | wc -c`).

Budget: +34 KB gzipped (DESIGN.md v2 §5).

After (2026-09-12, landing v2 QA gate, task 13). Production build at HEAD plus this task's
`index.html` and radius fixes; the baseline above was not recreated with `git stash`.

| Artefact | Before (2026-09-11) | After (2026-09-12) | Delta |
|---|---|---|---|
| Landing route chunk, raw | 76,889 B | 109,935 B | +33,046 B |
| Landing route chunk, gzip | 25,216 B | 36,242 B | **+11,026 B (+10.77 KB)** |
| Landing route CSS, gzip | not captured at task 1 | 7,678 B | no baseline |

After the LCP follow-up wave (2026-09-12). The route's own code is now two chunks: `landing`
keeps the shell, header, film, hero and footer, and `BelowHero` carries the eight sections
under the hero, so the budget is read against their sum. The baseline for this wave was
recreated by reverting the eleven changed source files and rebuilding, then restoring them.

| Artefact | Task 1 baseline | Task 13 | This wave | Delta vs task 1 |
|---|---|---|---|---|
| Landing route code, raw | 76,889 B | 109,935 B | 103,004 B (32,438 + 70,566) | +26,115 B |
| Landing route code, gzip | 25,216 B | 36,242 B | 35,131 B (11,051 + 24,080) | **+9,915 B (+9.68 KB)** |
| Landing route CSS, gzip | not captured | 7,678 B | 6,150 B (1,612 + 4,538) | no baseline |
| Entry chunk, gzip | not captured | 82.77 kB (vite display) | 60,620 B = 59.20 kB | −23.57 kB |
| First-paint payload at `/`, gzip | not captured | 224.61 KB | **108.61 KB** | −116.00 KB |

`gzip -c dist/assets/<file> | wc -c` for the byte columns, except the task 13 entry-chunk cell, which is vite's own rounded display — that build's `dist/` was not kept; the first-paint payload sums the
gzip figures `vite build` prints for the entry chunk, the route chunk, every chunk they share
and both stylesheets — that is, everything the browser must have before the hero can paint.
Verdict: **inside the +34 KB budget**, 29% of the allowance used, and the first-paint payload
is now less than half what it was. The demo dialog (`DemoDialog`, 1,850 B raw / 940 B gzip,
plus a 50,426 B / 17,010 B @base-ui chunk) and the management shell (`management`, 50,360 B /
17,120 B) are outside it in both directions: neither is requested on `/`.

`gzip -c dist/assets/landing-<hash>.js | wc -c`, run on `dist/` from `pnpm build`.
Verdict: **inside the +34 KB budget**, 32% of the allowance used. The allowance covers the
bento grid and bento card, the number ticker with `lib/ease.ts`, the anchor map and the
entrance layer.

The lazily imported `bar-chart` chunk (358,590 B raw, 103,400 B gzip, Recharts) is **not**
part of this delta: `ResearchEvidence.tsx` already imported it with `lazy()` at the task 1
baseline, so it sits outside the route chunk before and after. It is the only long task
measured during a full scroll pass; see the task 13 gate record.

