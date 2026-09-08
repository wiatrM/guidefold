# Higgsfield cinematic generation workflow

Provenance: user-authored Codex task `019fd853-5cdd-7001-b482-6c0f6806e359`.

## Plan before spending

1. Read the brand thesis, page narrative, crop targets, motion mode, asset policy, and the media section of any approved `Motion Prompt Packet`.
2. Gather only licensed or explicitly approved brand references.
3. Define duration, aspect ratio, resolution, frame rate, codec, audio policy, and delivery format.
4. Write a timestamped beat sheet. A validated ten-second structure is 00:00.350 hook, 00:02.200 intelligence/core reveal, 00:04.400 coordination, 00:07.050 human approval, and 00:09.350 connected-system resolve. Adapt its content, not the need for temporal clarity.
5. Produce an aspect-correct poster/placeholder so frontend construction proceeds concurrently.
6. Record estimated paid usage and require both job approval metadata and `UNSLOPIFY_PAID_ASSET_APPROVED=1` before a generation call.

## Prompt anatomy

Start with the provider-neutral asset brief from `direct-motion-site-prompts` when one
exists. Translate it into Higgsfield parameters only after the route and approval are
fixed. Preserve its subject continuity, camera, copy-safe field, crop set, timing, loop
or resolved ending, and acceptance checks.

Specify:

- subject identity and continuity;
- reference-image role and what must remain unchanged;
- environment, material, light, atmosphere, and brand palette;
- camera path, lens/framing, depth, and crop-safe regions;
- timestamped physical transformations and handoffs;
- final composition and whether it must loop or resolve;
- negative constraints: unwanted text/logos, cuts, flicker, anatomy changes, muddy particles, off-brand color, and incoherent intermediate frames.

Use observable actions rather than vague phrases like cinematic, premium, or high quality. Scroll media needs meaningful intermediate frames and a decisive final state so reverse scrubbing remains coherent.

## Execution boundary

Local interactive exploration may use Higgsfield MCP. Cluster execution calls the internal
Unslopify Media Gateway from a dedicated deterministic media Job. The gateway owns the
official Higgsfield CLI/OAuth adapter; neither the writer nor the media Job receives upstream
credentials. Never let the writer select a paid model or execute generation.

The asset planner records required capabilities rather than inventing a model ID. After
approval the gateway discovers current models, estimates cost, verifies the immutable
capability, submits or resumes the idempotent provider job, and exposes a same-origin delivery.
The media runner downloads, hashes and validates the file. Load [container runtime](./container-runtime.md) for the
exact cluster protocol. Never log access tokens, signed delivery URLs, or raw provider
responses containing credentials.

## Validate delivery

Measure actual duration, dimensions, fps, codec, audio, file size, first/last frames, crop safety, reference fidelity, and rights/provenance. Generate a poster and hash every delivered file. A proven output was exactly 10.000 s, 1920×1080, 24 fps, H.264, and silent; this is evidence, not a universal default.

Hook/virality scores are advisory. Do not regenerate a landing asset that satisfies narrative continuity simply because a social score is modest. Regeneration needs a concrete acceptance failure and renewed budget approval.

## Handoff

Return asset hashes, hosted/local URL, poster, focal region, timing map, prompt/model provenance, approval record, and fallback policy. The frontend gates download for save-data/reduced-motion, handles decoder/CORS errors, cleans pending work, recomputes cover geometry, and works in reverse.
