# Asset inspection and prompting

## Inspect before prompting

For every referenced URL, record final URL, HTTP status, content type, byte size, SHA-256, dimensions, duration, fps, codec, audio, alpha bounds, focal path, copy-safe region, first/last frames, and license evidence. Download only to temporary analysis storage. Do not commit binaries or signed URLs.

If the exact licensed asset already satisfies the packet, use it. Generation is a fallback for a defined missing shot, not a default upgrade.

## Provider-neutral prompt anatomy

Write prompts in this order:

1. fixed subject identity and elements that cannot change;
2. environment, depth planes, materials, weather, and light direction;
3. aspect ratio, framing, lens behavior, camera height, crop-safe region, and text-free area;
4. subject motion and camera motion as separate observable actions;
5. timed beats, end state, and loop or resolve requirement;
6. palette bounds and contrast target;
7. negatives: text, logos, extra subjects, shape drift, anatomy change, flicker, jump cuts, muddy particles, color contamination, and unsafe crops;
8. duration, resolution, fps, codec, audio, poster, and failure fallback.

Adapt that brief through `higgsfield-cinematic-assets`. Do not name a paid model before gateway discovery and approval. The alpha permits one approved Higgsfield slot.

## Corpus-derived shot blueprints

- 005 Wanderful: wide low horizon, lone traveler in a golden field, cyan sky occupying most of frame, heavy atmospheric diffusion, slow lateral human drift, nearly locked camera, no foreground crossing the centered copy field. Ask for a matched start/end pose or a hidden crossfade.
- 006 Foldcraft: black spatial void, one rectangular overhead water portal, narrow cyan light shaft, small orange fish schooling inside it, locked wide camera, slow cyclical school motion, large empty left field for copy, no other luminous objects.
- 007 Securify: low camera near snow surface, one snowboarder crossing the lower frame, white outerwear with a restrained red panel, powder burst, black-blue night background, readable silhouette. Treat it as a resolved action shot; generate a separate loop if repetition is required.
- 003 Nexum: slow forward glide between massive redwood trunks, warm backlight through mist, high vertical lines, quiet forest floor, stable lower copy region and breakpoint crop map. Do not claim a clean loop unless end frames match.
- 002 AI builder: macro architectural array of cobalt vertical fins on black, narrow specular highlights traveling across surfaces, slow lateral camera or rotating light, centered low-detail region for white type, no readable UI or circuit-board clichés.
- 001 Mostar: keep the landmark as licensed photography split into sky, mountains, town, left/right stone foreground, bridge, and river layers. Animate those planes deterministically. If a generated plate is approved, limit it to replaceable atmosphere or water behind the protected bridge geometry.
- 004 Marcus: preserve the portrait as a deterministic transparent cutout and move the marquee behind it. A generated clip is unnecessary unless the brief names a separate background motion problem.

## Acceptance

Reject outputs with unstable subject identity, broken landmark geometry, text-like marks, missing copy-safe area, camera movement that fights object-cover crops, nonmatching loop ends, incoherent middle frames, or a poster that changes the composition.
