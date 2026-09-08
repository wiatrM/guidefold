# RTX 4090 media PoC

## Objective and boundary

Determine whether one RTX 4090 24 GB worker can produce accepted landing-page stills, previews, and 3–5 second motion assets cheaply enough to reduce hosted generation. Use only synthetic or redacted evidence. Do not run customer jobs from WSL or the desktop PoC.

## Baseline stack

- Key visual: FLUX.2 klein 4B versus Qwen-Image.
- Fast preview: LTX-Video 0.9.8 2B distilled.
- Local final: Wan2.2 TI2V-5B, still-first I2V, 1280×704 or portrait counterpart, 24 fps.
- Stretch only: LTX-Video 13B distilled FP8/mix if the exact checkpoint fits and its license passes review.
- Exclude HunyuanVideo 1.5 in Poland because its license does not authorize EU use. Exclude LTX-2 as a baseline because the official ComfyUI path requires at least 32 GB VRAM.

## Host and automation

Use a dedicated Windows or Linux GPU worker with pinned ComfyUI and workflow JSON, at least 64 GB system RAM, preferably 96–128 GB, fast NVMe, and roughly 250 GB free. Preload allowlisted weights outside authenticated job phases; record SHA-256 and separate code and weights licenses.

Use ComfyUI's API directly instead of requiring MCP:

1. submit versioned workflow JSON to `POST /prompt`;
2. observe progress and errors on `/ws`;
3. read `/history/{prompt_id}` and download through `/view`;
4. inventory nodes and hardware through `/object_info` and `/system_stats`.

Wrap it behind the same Media Gateway domain contract before any future production use. Keep provider/local worker credentials in the durable gateway, not in agent jobs.

## Benchmark set

Create twelve synthetic shots covering:

- ambient abstract loop;
- macro material and light;
- product-object orbit;
- still parallax;
- device or UI mockup I2V with UI composited afterward;
- first-to-last transformation.

Use three fixed seeds per shot. Start at 832×480 or 960×544 for previews and 3–5 seconds at the final Wan profile. Generate protected text and logos only as deterministic overlays.

## Measurements

Record workflow hash, model and weights hash, seed, dimensions, duration, wall time, peak VRAM, peak RAM, watt-hours, OOM/error rate, file size, and post-processing time. Blind-score 1–5:

- prompt match;
- temporal consistency;
- source preservation;
- restrained useful motion;
- loop seam;
- crop safety;
- landing-page usefulness.

Hard reject flicker, deformed brand/UI/text, uncontrolled camera movement, missing poster, or missing reduced-motion/Save-Data fallback.

## Gate

Proceed to a gateway adapter only if the Wan final baseline reaches median 4/5 and at least 70% accepted outputs without manual pixel repair. Compare marginal electricity plus review time per accepted asset against hosted quotes. If it misses the gate, keep the 4090 route for stills and previews and send final video to a managed API.

## Productionization sequence

1. Pin ComfyUI, nodes, workflow JSON, weights, and licenses.
2. Add a typed request containing intent, dimensions, duration, seed, source hash, preservation constraints, route class, and budget tier.
3. Add a single-GPU queue, timeout, cancellation, at most one safe retry, and unknown-submission quarantine.
4. Emit a manifest with every hash, license, timing, energy estimate, and generated file.
5. Normalize delivery with ffmpeg to web-safe MP4, optional WebM/AV1, poster, and size budget.
6. Implement a Media Gateway adapter only after the offline gate; retain estimate, approval, fencing, idempotency, same-origin delivery, and secret-scan rules.