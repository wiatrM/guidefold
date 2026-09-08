# Website copy AI-pattern audit

## Scope

Audit user-facing prose in the generated site after `humanizer` runs. Skip source code, code examples, quoted third-party material, and protected text. Do not infer that a person used AI from one word or punctuation mark; look for repeated or clustered patterns.

## Severity

Fix before QA:

- Leaked chatbot framing, internal citation tokens, fake placeholders, AI-tool URL parameters, cutoff disclaimers, or invented sourcing.
- Banned terms and structures declared by `humanizer`.
- Unsupported notability claims, vague attributions, routine-event hype, promotional filler, or facts not present in sanitized inputs.
- Repeated template openings, stock transitions, synonym cycling, inline-header lists, title-case headings, decorative bold, emoji headings, or excessive em dashes.

Fix when the change does not damage the approved voice:

- Repeated groups of three, uniform sentence length, uniform paragraph length, stiff verbs, generic conclusions, false ranges, and superficial `-ing` clauses.

Leave a finding alone when it is protected, quoted, technically required, natural in context, or supported by the approved voice. Record the reason in `reports/build-notes.md`.

## Second-pass procedure

1. List each clear finding with file and exact span.
2. Apply the smallest local edit that removes the pattern without deleting a fact.
3. Re-read the changed paragraph in context and restore any lost connection to adjacent paragraphs.
4. Search again for banned terms, leaked tokens, placeholders, repeated templates, and unsupported claims.
5. Read the page aloud and correct robotic cadence without adding fake personality, slang, errors, or new claims.
6. Add a short audit record to `reports/build-notes.md`. Include edited files, resolved findings, and protected exceptions.

The audit passes when no high-confidence finding remains in editable copy and every exception maps to a preservation requirement or approved voice decision.
