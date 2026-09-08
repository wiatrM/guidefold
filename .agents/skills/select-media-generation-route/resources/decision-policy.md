# Media route decision policy

## Route in this order

1. Define the web job from the approved brief and any `Motion Prompt Packet`: placement, visible size, duration, crop set, copy-safe field, motion purpose, loop or resolved ending, interaction, poster, reduced-motion, Save-Data, and asset-failure behavior.
2. Extract hard constraints: protected pixels, reference fidelity, first/last frame, multi-reference, V2V, camera control, people, physical transformation, audio, transparency, latency, privacy, license, and maximum accepted-asset cost.
3. Eliminate unnecessary generation:
   - use source media when licensed and sufficient;
   - use CSS/SVG/Motion/Lottie/shaders for text, logos, UI, geometric systems, exact loops, and scroll-linked state;
   - use a still when motion adds no narrative or conversion value.
4. Prefer a still-first route. Create or approve the key visual, lock the focal region and brand-safe pixels, then animate it with restrained I2V.
5. Choose the cheapest eligible tier:
   - `local-preview`: fast motion sketch or loop proof;
   - `local-final`: organic or atmospheric I2V within the validated RTX 4090 envelope;
   - `managed-economy`: simple I2V, parallax, light/material motion, or first/last-frame loop;
   - `managed-standard`: controlled camera, product motion, people, or higher consistency;
   - `managed-premium`: multi-reference transformation, V2V/motion transfer, multiple timed beats, difficult physics, or a final hero that failed cheaper tiers.
   For hosted Seedance work, draft with Mini/Fast at 480p or 720p. Use Standard
   or 1080p only after the exact motion take is accepted for a final hero slot.
6. Escalate only after a measurable failure. Preserve the same approved keyframe, prompt intent, crop, and acceptance rubric between tiers.
7. Quote immediately before submission. Reject price drift, missing rights/retention evidence, unsupported parameters, or a route outside the approved adapter allowlist.

## Scoring

Score each eligible route from 0 to 5 on:

- capability fit and preservation fidelity, weight 30%;
- expected acceptance rate on the asset class, 25%;
- effective cost per accepted asset, including retries and operator review, 20%;
- automation and operational fit, 10%;
- latency, 5%;
- license, privacy, retention, and provenance confidence, 10%.

Reject instead of scoring when any hard constraint fails. Calculate expected cost as:

`quoted request cost × expected attempts / expected acceptance probability + review cost + post-processing cost`

Do not fabricate acceptance probabilities. Use the Unslopify benchmark ledger; until it exists, mark them `benchmark_required` and prefer the lower-risk route.

## Default routing heuristics

| Asset job | First choice | Escalate when |
| --- | --- | --- |
| Logo, readable UI, diagrams, exact geometry | semantic code, SVG, Motion, Lottie | never to generative video for protected pixels |
| Ambient texture, light, smoke, liquid, material loop | local Wan I2V from approved still | temporal defects persist after two bounded variants |
| Fast preview or motion sketch | local LTX-Video distilled | preview cannot demonstrate the intended motion grammar |
| Simple approved-still animation | managed economy I2V | preservation or camera control fails |
| First/last-frame loop | model with explicit first/last or loop control | seam remains visible after deterministic trim |
| Realistic materials or camera-led hero | Veo Fast, Gen-4.5, or measured equivalent | only if cheaper tiers fail the rubric |
| Multi-reference transformation, V2V, several timed beats | Seedance 2.0 class | use premium only because these capabilities are required |
| Character performance or driving-video transfer | current Kling motion-control class | benchmark provider price and identity stability first |
| Film compositing or HDR/EXR workflow | current Luma Ray high-fidelity class | only when downstream grading needs it |

Model names above describe capability classes, not permanent pins. Read the dated snapshot and verify live schemas.

## Provider role policy

Treat these as operator-owned desired roles, subject to an enabled, healthy,
audited adapter and a live quote:

| Role | Preferred route | Rule |
| --- | --- | --- |
| `primary_final` | ByteDance via Vercel AI Gateway or BytePlus | selected final hero shots only; Standard/1080p requires accepted draft |
| `primary_draft` | Replicate Seedance Mini, then fal Seedance Mini | default hosted 480/720p draft tier |
| `creative_edit` | Runway | edits, recipes, camera-led or controlled creative operations |
| `agentic_manual` | Higgsfield | Soul ID, operator experiments, and the current alpha executable route |
| `fallback_provider` | Replicate | use only after typed primary unavailability or capability mismatch |
| `experimental_low_cost` | WaveSpeed or PiAPI | `audit_required`; never auto-route customer work |

Consumer-account wrappers, scraped sessions, unofficial Seedance domains, and
providers that cannot prove model identity are `forbidden_production`. Never
offer a connect action for them.

## Asset-plan handoff

Express needs through `requiredCapabilities`; never invent a provider model ID in `design/asset-plan.json`. Include observable terms such as:

- `image-to-video`, `first-last-frame`, `multi-image-reference`, `video-reference`, `motion-transfer`, `camera-orbit`, `native-loop`, `silent-output`, `720p`, or `1080p`;
- `protected-elements-composited-after-generation`;
- `poster-required`, `reduced-motion-static`, and `save-data-static`.

For the current schema, use `source`, `imagegen`, `higgsfield`, or `vercel-ai-gateway` only when that route is executable. Vercel AI Gateway is the approved ByteDance video route; Higgsfield covers approved image/video work. An unimplemented local or alternate hosted route remains `mock`. Always provide an aspect-correct placeholder and deterministic fallback.

## Generation discipline

- Generate without audio for autoplay landing media unless audio is explicitly essential.
- Draft in Mini/Fast at 480p or 720p; upscale or invoke Standard only for an
  accepted final motion take.
- Prefer 3–6 seconds and a single readable motion idea over a longer montage.
- Allocate the whole job envelope across 1–10 assets by expected page impact. Compare one polished video with several stills/layers/patterns animated in code; choose the portfolio with the best expected accepted-result quality and latency. Do not search indefinitely.
- Validate duration, dimensions, fps, codec, hashes, first/last frames, crop safety, flicker, protected-element fidelity, file size, and poster.
- Deliver MP4 plus a browser-appropriate alternative when justified; always include poster, reduced-motion, Save-Data, and decoder-failure fallbacks.
