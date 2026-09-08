# Assessment product implementation

## Build order

1. Read the binding assessmentProduct contract and preservation map before editing source.
2. Build the assessment as one semantic form or fieldset sequence with a visible title, instructions, progress text, labels, validation, previous/next controls, and a reviewable submit action.
3. Keep the landing-page promise, three dimensions, credibility evidence, and one assessment CTA understandable without starting the flow.
4. Render questions from typed local data. Keep scoring, result bands, insight selection, and next-step routing in pure testable functions.
5. Count only the ten best-practice answers in the public score. Use the five qualification answers to select approved result language or next steps, never to fabricate precision.
6. Show the score as text before any decorative meter. Give the result band, three personalized insights, and a useful next step. Do not expose internal sales labels.
7. Preserve answers when navigating backward. Move focus to the new question heading and announce validation and result changes through accessible text.
8. Make the entire flow usable by keyboard and screen reader. Do not encode status by color alone. Respect reduced motion; question transitions must not be required for comprehension.
9. Keep in-browser-only answers in component memory by default. Do not add analytics, local storage, cookies, network requests, IP enrichment, or third-party embeds unless the brief explicitly authorizes them.
10. For an approved handoff, submit only declared fields to the preserved target, retain exact consent/legal copy, handle failure without losing the local result, and never log answers or contact data.

## Truth and safety

- Derive a time estimate from the implemented flow or omit it.
- Label scoring as a self-assessment when methodology is not independently validated.
- Never infer budget from preferred support in user-facing output.
- Never invent research, credentials, statistics, urgency, scarcity, or a booking URL.
- Provide a static, readable result if JavaScript enhancement fails where practical; at minimum keep the offer, methodology summary, and preserved primary path available.

## Verification

Add tests for score boundaries 0, each band edge, and 10; reversed positive answers; deterministic insight priority; fewer than three missed practices; qualification routing; restart/back navigation; required validation; and the selected data mode. Verify no network request occurs in in-browser-only mode.

Record the assessment contract disposition, data mode, protected-form handling, tests, and any omitted time or credibility claims in reports/build-notes.md.
