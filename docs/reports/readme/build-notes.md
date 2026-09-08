# README copy and architecture review
Status: reviewed locally; GitHub publication tracked separately.
Date: 2026-09-08.
Purpose: owner-requested README rewrite, demo, existing logo and technical architecture images.
Scope: documentation only; no product requirement, runtime or pricing change. Supports developer onboarding (U8/P10).
Inputs: README, services/search/README.md, HARNESS-SERVICE-CONTRACT, SEARCH-USE-TELEMETRY and the owner's demo URL.
Replaces: previous README prose. Does not replace the API contract or architecture decisions.
Index: [README](../../../README.md).

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
