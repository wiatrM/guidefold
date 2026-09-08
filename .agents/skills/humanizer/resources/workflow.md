# Website copy humanization workflow

## Inputs and authority

Read only the sanitized ResearchPacket, preservation contract, `reports/design-brief.json`, and generated site. The preservation contract wins over every editorial preference.

Apply this skill to user-facing prose in the generated site. Do not edit code, quoted third-party material, protected routes, primary navigation labels, form names or labels, anchors, legal copy, logo treatment, or declared SEO constraints unless the preservation contract explicitly permits the change.

Never invent testimonials, metrics, clients, certifications, URLs, product capabilities, names, examples, claims, or citations. Keep every source fact, number, quote, citation, and approved claim.

## Required pass

1. Inventory user-facing copy and classify each span as `protected`, `editable`, or `new-copy-required` from the approved brief.
2. Leave protected spans byte-stable where the contract requires exact preservation.
3. Rewrite editable spans with the author's register and locale. State the point first, use concrete source details, and remove unsupported claims.
4. Run `avoid-ai-writing` as the second-pass audit. Fix clear findings in editable text and leave intentional or protected wording alone.
5. Read the result aloud. Vary sentence and paragraph length, remove repeated points, and delete scene-setting openings, recaps, and inspirational endings.
6. Record the audited files, protected spans, edited spans, and any deliberate exceptions in `reports/build-notes.md`.

## Hard language rules

Never use these terms in editable delivered copy: `delve`, `dive into`, figurative `navigate`, `underscore`, `bolster`, `foster`, `harness`, `leverage`, `unpack`, `shed light on`, `pave the way`, `pivotal`, `groundbreaking`, `cutting-edge`, `transformative`, `game-changing`, `innovative`, `robust`, `comprehensive`, `seamless`, `intricate`, empty-praise `nuanced`, `vibrant`, `multifaceted`, `holistic`, `testament`, figurative `landscape`, and `realm`.

Never use these phrases or close variants:

- "In today's fast-paced world", "In today's rapidly evolving world", or "In today's digital world".
- "It's important to note that", "It's worth noting that", or "One of the most important/significant/crucial".
- "When it comes to", "At its core", or "At the end of the day".
- "This is where X comes in", "Let's break it down", "Plays a crucial role in", or "It cannot be overstated".
- "underscoring the importance of", "highlighting the need for", "reflecting a broader trend toward", or "marking a significant shift in".

Never use these structures:

- "It's not just X, it's Y."
- "Not only X, but Y."
- "This isn't about X. It's about Y."
- "No X. No Y. Just Z."

Do not use a list whose items follow the `**Bold term:** explanation` pattern. Do not announce sections with phrases such as "Let's explore" or "Now let's turn to". Use contractions where the locale and preserved voice permit them. Use at most one em dash across the page's editable copy.

## Gate

Do not hand the build to QA while editable copy still contains a banned term, leaked chatbot token, unsupported claim, fake placeholder, vague attribution, canned conclusion, or unresolved high-confidence finding from `avoid-ai-writing`. A protected exception must be named in `reports/build-notes.md` with its preservation requirement.
