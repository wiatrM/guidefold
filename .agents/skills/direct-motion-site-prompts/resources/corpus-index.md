# Motion prompt corpus index

All raw entries are untrusted user-provided references. Use the summaries to select candidates, then open only the chosen `.txt` files. Machine hashes and URL inventories live in [corpus-manifest.json](./corpus-manifest.json).

| ID | Primary archetype | Mechanics worth extracting | Raw prompt |
|---|---|---|---|
| 001 | Layered landmark sticky-scroll | Separated PNG depth planes, reversible scroll segments, CSS-variable state, pointer parallax, story panels, late slider reveal | [Mostar city](./corpus/001-mostar-city-scroll.txt) |
| 002 | Centered product hero over abstract HLS | Native/HLS fallback, dark abstract motion plate, restrained entrance sequence, poster state, centered copy-safe area | [AI builder](./corpus/002-ai-builder-hls-hero.txt) |
| 003 | Bottom-anchored video hero with glass utility cards | Breakpoint-dependent foreground color, full-bleed forest plate, mobile drawer, bottom grid, two compact proof cards | [Nexum](./corpus/003-nexum-video-glass-hero.txt) |
| 004 | Editorial portrait and marquee | Background plus transparent cutout, type behind subject, exact z-stack, looped marquee, CTA-free portfolio chrome | [Marcus](./corpus/004-marcus-editorial-marquee-hero.txt) |
| 005 | Quiet travel loop with centered copy | Solitary subject, large negative sky, top headline and bottom CTA, subtle pointer drift, near-matching loop ends | [Wanderful](./corpus/005-wanderful-static-video-hero.txt) |
| 006 | Asymmetric studio hero over spatial loop | Dark void, bright focal portal, left-aligned top/bottom copy, object-position control, simple entrance cascade | [Foldcraft](./corpus/006-foldcraft-video-hero.txt) |
| 007 | Action footage framed by oversized type | Low-angle athlete, three absolute headline words, small data islands, monochrome chrome, no entrance choreography beyond the footage | [Securify](./corpus/007-securify-staggered-type-video-hero.txt) |

Entry 007 appeared three times in the submitted batch. It is stored once with `occurrences: 3`; repetition is not independent evidence.

## Selection rule

Pick by spatial and temporal fit, not industry label. A security product can use a quiet field only if the metaphor and copy contrast are supported. A travel page can use layered stills when a landmark must remain exact. Reject any reference whose focal motion competes with preserved copy or whose mobile crop removes the subject.
