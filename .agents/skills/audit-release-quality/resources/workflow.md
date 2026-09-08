# Release quality workflow

## Deterministic gate order

1. Lockfile consistency, dependency vulnerability policy, typecheck, lint when configured, tests, and production build.
2. Serve the production build; record console errors, failed requests, and runtime exceptions.
3. Capture screenshots at 360×800, 390×844, 768×1024, and 1440×900.
4. Verify responsive flow, overflow, clipping, long text, broken images, navigation, forms, and primary CTA.
5. Verify keyboard order, visible focus, landmarks, labels, contrast, alt text, and automated accessibility findings.
6. Verify `prefers-reduced-motion`, save-data, autoplay policy, reverse scroll, resize, refresh mid-page, and media fallback.
7. Check layout shifts, image/video size, main-thread work, font loading, and declared performance budgets.
8. Load `cloudfloo-quality-gate` and run deterministic checks. Evaluate the concerns represented by Impeccable `adapt`, `harden`, `optimize`, `critique`, `audit`, and `polish`, but do not invoke mutating skill commands or edit source in the QA pod. Emit findings for Codex repair.
9. Diff implementation against the preservation contract.
10. Secret-scan source, `dist`, ZIP listing and contents, reports, logs, and screenshot metadata.
11. On a deterministic tool crash, persist the exact failing command category, exit/signal, bounded stderr tail after redaction, elapsed time, and completed checks before returning the stable failure code. Do not collapse actionable tool failures into a generic process error.

## Design audits

- Em/en-dash audit when required by the active taste profile.
- Pre-flight checklist with pass/fail and one-line evidence for every item.
- Section-layout repetition: list each section's layout family.
- Hero discipline: headline lines, subtext word count, CTA visibility, proof density.
- Anti-slop: gradients, arbitrary pills/cards/glass/glow, weak hierarchy, generic copy, repeated layouts, and decorative motion.
- Brand fidelity: accent roles, type stack, logo treatment, imagery, and voice.
- Preservation: enumerate every changed URL, nav label, field, anchor, protected heading, logo, and legal string; the list must be empty unless approved.

## Cinematic checks

Inspect representative bright and dark frames. Contrast material may be present; verify it keeps copy readable without hiding the film. Disable or delay JavaScript initialization and confirm every row remains visible. Test forward/reverse scroll, exact final marker, decoder failure, poster fallback, resize geometry, save-data, and reduced motion.

## Outputs

- `reports/qa-report.json`
- `reports/qa-report.md`
- required viewport screenshots
- optional motion recording for significant motion

Each check is `pass`, `fail`, or `not_applicable`, with evidence and remediation. Build, security, critical accessibility, preservation, required artifact, or secret failures block release. Any active-profile pre-flight failure also blocks completion.

Run independent checks concurrently only when they do not contend for the preview server or mutate outputs. Fail fast on build, secret, fence, or preservation blockers, but always flush the redacted diagnostic record so a retry does not repeat blind work.

Validate `reports/qa-report.json` with `/harness/schemas/qa-report.schema.json` and the preservation report with `/harness/schemas/preservation-report.schema.json`.
