# Model and provider snapshot

Snapshot date: 2026-08-08. Verify every catalog, price, license, retention rule, and API contract before approval. Marketing benchmarks are not cross-provider evidence.

## Seedance 2.0 access

Normalized public prices below are approximate USD, excluding tax. Input-video charges and regional terms may differ.

| Route | 720p per second | 5 seconds | 8 seconds | Automation | Use |
| --- | ---: | ---: | ---: | --- | --- |
| BytePlus through Vercel AI Gateway | ~$0.151 | ~$0.76 | ~$1.21 | API / AI SDK | lowest verified first-party-like route; legal and retention review required |
| Replicate official model | $0.18 | $0.90 | $1.44 | official MCP, REST, SDK | best first hosted PoC and fallback balance |
| fal Mini | $0.1547 | $0.77 | $1.24 | hosted MCP, REST, SDK | economical Seedance draft |
| fal Fast | $0.2419 | $1.21 | $1.94 | hosted MCP, REST, SDK | faster managed draft/final |
| fal Standard | $0.3034 | $1.52 | $2.43 | hosted MCP, REST, SDK | premium multimodal route |
| Runway Mini | $0.16 | $0.80 | $1.28 | MCP, official skills, REST, SDK | agent-friendly draft |
| Runway Fast | $0.29 | $1.45 | $2.32 | MCP, official skills, REST, SDK | controlled final |
| Runway Standard | $0.36 | $1.80 | $2.88 | MCP, official skills, REST, SDK | higher-cost production workflow |
| Higgsfield Standard example | ~$0.194 | — | ~$1.55 | hosted MCP, CLI, skills | best current Unslopify integration; plan economics vary |

Higgsfield Unlimited generation is UI-only; MCP, CLI, Canvas, and Supercomputer consume credits. Do not price automated jobs as unlimited.

Primary sources: [ByteDance route in Vercel AI Gateway](https://vercel.com/ai-gateway/models/seedance-2.0), [Replicate Seedance 2.0](https://replicate.com/bytedance/seedance-2.0), [fal Seedance 2.0](https://fal.ai/models/bytedance/seedance-2.0/text-to-video), [fal Mini](https://fal.ai/models/bytedance/seedance-2.0/mini/text-to-video), [Runway API pricing](https://docs.dev.runwayml.com/guides/pricing/), [Higgsfield Seedance cost example](https://higgsfield.ai/blog/generating-with-seedance-2-0), [Higgsfield MCP/CLI](https://higgsfield.ai/cli), [fal MCP](https://fal.ai/docs/documentation/setting-up/mcp), [Replicate MCP](https://mcp.replicate.com/), and [Runway skills](https://github.com/runwayml/skills).

## Hosted alternatives

| Model class | Typical public API cost | Strong fit | Avoid as default when |
| --- | ---: | --- | --- |
| Veo 3.1 Lite | $0.05/s 720p | inexpensive restrained background motion | richer reference control is required |
| Veo 3.1 Fast | $0.10/s 720p | strong general cloud candidate, first/last frame | silent simple loops do not need its realism |
| Veo 3.1 | $0.40/s 720/1080p | high realism, light, materials, difficult camera | muted ambient background |
| Runway Gen-4 Turbo | $0.05/s | cheap I2V iteration and approved-still animation | precise multi-reference transformation |
| Runway Gen-4.5 | $0.12/s | camera choreography, motion art, physics | explicit first/last control is mandatory |
| Luma Ray3.2 | about $0.30 per 5 s at 720p | landing atmospherics, materials, VFX/compositing | exact UI or protected text must survive |
| MiniMax Hailuo 2.3 Fast | about $0.19 per 6 s at 768p | low-cost I2V of approved key visuals | text-to-video or complex references are required |
| Kling 3 motion-control class | live quote required | people, performance, driving video, motion transfer | provider price and identity stability are unbenchmarked |

Sources: [Google Veo documentation](https://ai.google.dev/gemini-api/docs/veo), [Google Veo pricing](https://ai.google.dev/gemini-api/docs/pricing), [Runway pricing](https://docs.dev.runwayml.com/guides/pricing/), [Luma API](https://lumalabs.ai/api), [MiniMax video generation](https://platform.minimax.io/docs/guides/video-generation), [MiniMax PAYG](https://platform.minimax.io/docs/guides/pricing-paygo), and [Kling 3 on fal](https://blog.fal.ai/kling-3-0-is-now-available-on-fal/).

## Local candidates

| Candidate | RTX 4090 position | License gate | Route |
| --- | --- | --- | --- |
| Wan2.2 TI2V-5B | official 24 GB / RTX 4090 support, 720p 24 fps; official report says under 9 minutes for 5 s without special optimization | Apache-2.0 repo/model; verify exact weights | local final I2V baseline |
| LTX-Video 0.9.8 2B distilled | lightweight fast preview; benchmark 4090 time locally | code and checkpoint licenses differ | preview baseline |
| LTX-Video 13B distilled FP8/mix | stretch quality test | verify checkpoint license and VRAM | optional benchmark |
| FLUX.2 klein 4B | local still generation/editing with ample 4090 headroom | Apache-2.0 variant | key visual baseline |
| HunyuanVideo 1.5 | technically fits with offload | license excludes EU use; block in Poland | `license_blocked` |
| LTX-2 / 2.3 | official ComfyUI path requires at least 32 GB VRAM | community terms and checkpoint license | not a 4090 baseline |
| CogVideoX / Stable Video Diffusion | older or more constrained | checkpoint-specific terms | control only, not default |

Sources: [Wan2.2](https://github.com/Wan-Video/Wan2.2), [ComfyUI Wan2.2](https://docs.comfy.org/tutorials/video/wan/wan2_2), [LTX-Video](https://github.com/Lightricks/LTX-Video), [LTX model collection](https://huggingface.co/Lightricks/LTX-Video), [FLUX.2](https://github.com/black-forest-labs/flux2), [Qwen-Image](https://github.com/QwenLM/Qwen-Image), [HunyuanVideo 1.5 license](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5/blob/main/LICENSE), and [ComfyUI server routes](https://docs.comfy.org/development/comfyui-server/comms_routes).

## Provider policy notes

Recommended operator registry as of this snapshot:

- `primary_final`: ByteDance through Vercel AI Gateway or BytePlus;
- `primary_draft`: Replicate Seedance Mini, with fal Seedance Mini as the
  alternate economy route;
- `creative_edit`: Runway;
- `agentic_manual`: Higgsfield;
- `fallback_provider`: Replicate;
- `experimental_low_cost`: WaveSpeed and PiAPI only after security, model
  identity, rights, retention, delivery-origin, and quote-schema audit.

WaveSpeed publishes an authenticated read-only model catalog with pricing, but
catalog presence does not prove that a named closed model is the claimed
first-party build. See [official authentication](https://doc.wavespeed.ai/authentication)
and [official list-models API](https://wavespeed.ai/docs/docs-common-api/models).
PiAPI remains `audit_required` until equivalent primary documentation and model
identity evidence are recorded.

- Prefer official or directly contracted routes. Treat consumer-account wrappers and unofficial Seedance-branded domains as production-forbidden.
- Replicate states that this official model's inputs and outputs are not used for training; still verify model-specific terms.
- fal supports storage controls, but default request/response and media retention require explicit configuration and verification.
- Runway exposes mature agent tooling and strong commercial terms, but API credits are separate from web subscriptions.
- BytePlus/Vercel currently needs a focused DPA, retention, and zero-data-retention review before customer assets.
- Subscription credit conversion is an accounting estimate. The authoritative generation gate remains the provider's live quote bound to the approved request.
