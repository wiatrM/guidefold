# Pinned asset observations

Inspection date: 2026-08-08. Files were downloaded from public URLs into temporary storage, hashed, probed, and sampled. They are not stored in Git. Availability and rights must be checked again before use.

| Reference | Technical evidence | Visual and motion observation | Loop warning |
|---|---|---|---|
| 005 Wanderful | H.264, 1664×1244, 24 fps, 12.042 s, 9,647,747 B, SHA `333c0a6a787991f579268ddc64e7be70bc5905fed1f3accca79bbd2cfe67d63f` | Solitary person in a hazy golden field under a cyan sky; slow lateral drift and large empty upper field | First/last RGB difference 0.0323; visually close, still inspect the seam |
| 006 Foldcraft | H.264, 1920×1080, 24 fps, 8.042 s, 7,611,846 B, SHA `75856a0709d530e479618e4c130a2f577f50963cdbf12532ed4ec87d6a94fbb8` | Rectangular water opening above a dark void; fish move inside a narrow cyan light shaft | Difference 0.0268; strongest loop candidate in this batch |
| 007 Securify | H.264, 1928×1072, 24 fps, 7.042 s, 22,896,688 B, SHA `02c017e81205e252d81d99f81ed0544c135fc6ea41db61a798fed8f80a392542` | Low-angle snowboarder, powder burst, dark background, rapid pose changes | Difference 0.2239; hard loop will jump |
| 003 Nexum | H.264, 1920×1080, 24 fps, 10.042 s, 14,669,473 B, SHA `674eee818fcca27050d2fb6ceb0ef69d399467443ad458ee891fd1029d68b577` | Slow glide through redwood trunks with warm volumetric backlight | Difference 0.1681; use a crossfade or a resolved play-once mode |
| 002 AI builder | HLS, 20.02 s, H.264 variants 640×360 to 1920×1080 at 29.97 fps, AAC present | Cobalt vertical architectural fins on black with moving highlights | Sample seam score is not valid for the full 20 s stream |

## Still and layer evidence

Mostar uses 3840×2160 sky, mountain/glow, and town layers plus 2880×1620 left/right foreground and bridge cutouts. The resulting scene is a stone bridge framing turquoise water and the town. Preserve the photographed bridge geometry; the value comes from deterministic depth separation.

The Marcus background resolved to 1280×714 WebP, while its portrait is a 3840×2160 RGBA cutout with occupied alpha bounds `(1170,143)–(2575,2160)`. The subject is suited to type-behind-portrait compositing. The AI builder poster is 1080×720 and shows a blue neural filament on black; it is a fallback, not evidence for generated product UI.

## Interpretation limits

Pixel-difference scores measure frame mismatch, not perceived motion continuity. Contact sheets sampled only a few frames. Reinspect the full asset for a production decision, verify ownership, and use the Media Gateway quote and provider schema only after operator approval.
