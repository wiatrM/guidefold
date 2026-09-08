# Motion prompt contracts

## Motion Prompt Packet

Write this object into `reports/design-brief.json`, matching `/harness/schemas/design-direction.schema.json`. The YAML below is the shape, not the format:

```yaml
motionPromptPacket:
  referenceBasis:
    primaryId: "<corpus ID or inspected reference>"
    secondaryMechanic: "<optional; one job only>"
    borrowedMechanics: ["<observable mechanic>"]
    rejectedMechanics: ["<mechanic and reason>"]
  archetype: "<one archetype>"
  composition:
    layerOrder: ["<back to front>"]
    focalRegion: "<desktop and mobile coordinates>"
    copySafeRegion: "<desktop and mobile bounds>"
    typographyRelation: "<in front, behind cutout, split around subject>"
  motion:
    states: ["<named state>"]
    beats: ["<trigger, interval, transform, easing, terminal state>"]
    interruption: "<resize, reverse, menu, visibility behavior>"
  media:
    route: "<source, deterministic, segmented still, loop, I2V, scroll film>"
    existingEvidence: "<URL/hash/inspection date or none>"
    delivery: "<ratio, duration, resolution, fps, codec, audio>"
    fallback: "<poster/static/layered state>"
  responsive: "<real recomposition>"
  reducedMotion: "<complete static state>"
  saveData: "<no heavy download state>"
  acceptance: ["<observable checks>"]
```

## Shaping-agent prompt

Ask the shaper to select the archetype, extract mechanics, reject conflicts, choose the media route, and write the packet. Do not ask it to implement code, download during a job, or authorize paid generation.

## Writer prompt

Give the writer the approved packet, preservation contract, local asset paths, and stack. Require semantic structure first, one motion state model, stable posters/placeholders, cleanup, responsive composition, reduced motion, and a build-notes disposition for every acceptance item. Do not give it provider credentials or model selection.

## Media-planner prompt

Give the planner only the asset section, reference rights, crop map, beat sheet, negative constraints, delivery contract, and budget state. Require a provider-neutral brief before any Higgsfield adaptation. The planner may estimate; only the media runner may generate after approval.

## Reviewer prompt

Give the reviewer the packet and captured evidence. Ask whether the implemented layer order, focal crop, motion beats, reverse behavior, terminal state, fallbacks, and protected content match. A preference from the corpus is not a defect without an observable acceptance failure.

## Repair prompt

Include only verified failing acceptance items and the original packet. Preserve the archetype and media route. Require the smallest change; do not restart concept selection or regenerate media without a renewed approval record.
