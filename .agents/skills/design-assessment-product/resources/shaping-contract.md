# Assessment product shaping contract

## Selection gate

Evaluate the assessment pattern on every shaping pass. Set assessmentProduct.enabled=false with a concise rationale unless all of these are true:

- The customer explicitly requests a quiz, scorecard, diagnostic, calculator-like flow, or lead-qualification experience; or verified offer evidence shows that a self-assessment is the clearest useful product preview.
- The offer has three evidence-backed dimensions that a visitor can assess through observable behavior.
- The result can give three useful actions before asking for a sale.
- The interaction does not replace or rename protected routes, navigation, anchors, fields, legal copy, or the primary conversion path.
- The page can provide a truthful result without claiming a professional diagnosis or fabricated precision.

Do not enable an assessment merely to increase section count, time on page, or lead volume. For medical, legal, financial, employment, housing, insurance, or similarly consequential decisions, avoid diagnostic or eligibility claims and require authoritative customer-supplied methodology before scoring.

## Assessment architecture

When enabled, write the complete assessmentProduct object in reports/design-brief.json:

1. Choose one hook:
   - frustration: name a verified gap between effort and outcome without shaming the visitor.
   - outcome: ask whether the visitor wants a verified, attainable result.
2. State what the assessment measures, what the visitor receives, and the real interaction cost. Do not claim a duration until the final question copy can support it.
3. Define exactly three dimensions. Make them distinct, actionable, and grounded in the sanitized offer evidence.
4. Define ten binary best-practice questions. Each question must test one behavior, map to one dimension, state which answer earns a point, and carry one useful recommendation for a missed practice.
5. Define the five qualification questions in this exact purpose order: current situation, 90-day goal, primary obstacle, preferred support, and optional open context.
6. Use qualification answers only to tailor the result and next step. Do not disguise a financial, health, demographic, or other sensitive inference as qualification.
7. Define three non-pejorative result bands with contiguous score ranges covering 0 through 10. Give every band a useful summary and next step. Never show visitors sales labels such as cold, warm, or hot.
8. Generate the three result insights from the highest-priority missed practices, with a neutral fallback when fewer than three practices are missed.

## Data mode

Choose the least-privileged mode:

- in-browser-only: default. Calculate locally, store nothing remotely, and route the final action to a preserved route, anchor, or educational result.
- preserved-form-handoff: pass only explicitly approved values into an existing preserved form. Keep its names, consent, action, and legal copy unchanged.
- approved-lead-capture: use only when sanitized evidence supplies the endpoint or integration owner, exact approved fields, consent and privacy copy, retention/handling expectations, and a preserved fallback.

Never collect location from IP. Keep phone optional when it is explicitly approved. If the customer requires remote lead capture but the approved data contract is missing, return needs_input; do not invent a service such as ScoreApp or a new backend.

## Copy and evidence

Use source claims only when present in sanitized evidence and allowed by preservation. Treat statements such as "free," "three minutes," "instant," "20-40% conversion," research citations, or authority claims as unverified until evidenced. Prefer concrete utility over hype: what is measured, what is returned, and what action becomes easier.
