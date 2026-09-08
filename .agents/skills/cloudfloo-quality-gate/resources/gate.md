# Cloudfloo-derived quality gate

Provenance: condensed from Cloudfloo quality-gate source at commit `ce8517ed2e0fe375d45fe97319db859c6cebb405` and adapted to machine-readable release evidence.

## Sequence

1. Typecheck, lint when configured, tests, production build, and dependency policy.
2. Serve the production bundle and record console/network errors.
3. Capture 360×800, 390×844, 768×1024, and 1440×900.
4. Inspect first-viewport hierarchy, CTA, every section at rest and transition, overflow, clipping, long copy, and broken assets.
5. Test forward/reverse scroll, refresh at mid-page, resize, rotation, media error, save-data, and reduced motion.
6. Test keyboard order, focus, landmarks, labels, contrast, and touch targets.
7. Inspect layout shifts, oversized media, main-thread cost, and exact final chapter state.
8. Compare protected routes/copy/forms/logo/legal details and scan all outputs for secrets.

For variable film, sample bright and dark frames. A light contrast underlay may remain; it should keep text readable without hiding the film. Disable or delay animation initialization and confirm rows are still visible.

Each check records `pass`, `fail`, or `not_applicable`, evidence, and remediation. Build, security, critical accessibility, preservation, artifact, or secret failure blocks publishing.
