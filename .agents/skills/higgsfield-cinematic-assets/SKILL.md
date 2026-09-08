---
name: higgsfield-cinematic-assets
description: Plan and generate approved Higgsfield hero images or videos with references, timed beats, prompt structure, paid-call approval, delivery validation, and scroll-ready fallbacks.
---

# Higgsfield Cinematic Assets

Use only when the approved asset plan requests AI-generated cinematic media. Frontend work continues in parallel with aspect-correct placeholders.

## Resource routing

- Load [generation workflow](./resources/workflow.md) for reference curation, beat sheets, prompt anatomy, validation, provenance, and frontend handoff.
- Load [container runtime](./resources/container-runtime.md) only when preparing or executing an operator-approved cluster media job.
- Load no other resource for this skill.

The build agent plans media but never spends credits. Only the dedicated media runner may
call the internal Media Gateway, using a short-lived capability whose job, fence, phase,
request digest, tools and budget match the immutable asset plan.
For the private alpha the plan may contain exactly one Higgsfield slot. Stop at
`needs_input` if a brief requires more; do not merge multiple requests into one prompt.
