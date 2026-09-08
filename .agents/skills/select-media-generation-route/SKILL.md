---
name: select-media-generation-route
description: Select the lowest-cost media production route that can meet a landing-page asset's visual, motion, preservation, licensing, privacy, and delivery requirements. Use while shaping image or video asset plans, comparing local RTX 4090 generation with managed APIs, choosing Seedance or an alternative model class, or deciding that CSS, SVG, Motion, source media, or a static image is the better solution.
---

# Select Media Generation Route

Choose the production method before choosing a provider or model. Optimize for accepted web assets per dollar and minute, not headline benchmark rank or raw request price.

## Resource routing

- Always load [decision policy](./resources/decision-policy.md) for the routing sequence, scoring, escalation, and asset-plan handoff.
- Load [model and provider snapshot](./resources/model-provider-snapshot.md) only when comparing current hosted or local candidates. Treat every price and catalog entry as dated evidence; verify the live provider schema and quote before spend.
- Load [RTX 4090 PoC](./resources/rtx4090-poc.md) when planning, running, or assessing the local synthetic benchmark.
- Load no other resource for this skill.

## Hard boundaries

- Prefer existing licensed media, semantic HTML, CSS, SVG, canvas, shaders, Lottie, or Motion whenever they can preserve the required logo, text, UI, geometry, loop seam, or interaction exactly.
- Prefer still-first image-to-video over unconstrained text-to-video for landing assets.
- Never place readable UI, legal copy, logos, or irreplaceable product details inside generated pixels. Composite protected elements afterward.
- Never assume native alpha. Plan segmentation or compositing as a separate deterministic step.
- Never choose a model from marketing claims alone. Require a capability match, current quote, rights/retention check, and an acceptance fallback.
- Never expose provider credentials to PRIME, the writer, or an ephemeral media job. Keep estimate, approval, fencing, idempotency, and delivery inside the Media Gateway boundary.
- Never execute customer jobs on the local RTX 4090. Local PoC inputs must be synthetic or redacted.
- Never route production work through consumer-account wrappers or unofficial
  Seedance-branded domains. Experimental resellers require an explicit completed
  audit state in the operator registry.

## Alpha execution rule

The current private alpha can execute operator-pinned Higgsfield image/video and ByteDance video through Vercel AI Gateway, always behind the internal Media Gateway. The provider registry does not grant generation authority by itself: require an enabled adapter, exact capability, live quote, immutable entitlement, fence, idempotency, and delivery contract. If a route is unavailable before submission, select the source/code fallback and keep the redesign autonomous.
