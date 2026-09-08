# Pricing copy audit

Status: scoped checks passed; full site build not run. Date: 2026-09-08.
Purpose: scoped verification of the public pricing section governed by [ADR-0038](../../adr/ADR-0038-subscription-byok-and-metered-ai.md).
Inputs: owner-approved cost scenario and commercial decision. No product redesign or live deployment.

## Copy scope

Edited `portal/content/index.md`, the public portal home shared by MkDocs and Mintlify. Existing navigation, other copy, links and layout are preserved. The hosted application is not this public home page.

The humanizer pass and the avoid-ai-writing second pass cover only the new pricing section. Copy separates available OSS from planned SaaS, spells out BYOK, gives a concrete margin example, and asks one feedback question. No invented customer outcomes, urgency, testimonials or implementation claims were added. No high-confidence AI-writing pattern remains in the new copy. Existing technical vocabulary outside this section was preserved; it was not re-audited or rewritten.

## Verification

Windows bundled Python: loaded `tests/test_portal.py` with `runpy.run_path` and invoked all six `test_*` functions directly: six passed. Pytest is absent from that runtime, so this is not reported as a pytest run. Markdown-it rendered the changed page; checks passed for the pricing heading, planned-availability notice, feedback URL and formula. Decimal arithmetic verified all three AI scenarios and the $9-to-$10 example. Scoped `git diff --check` passed for PRODUCT-PIVOT, the ADR index and portal home.

Full MkDocs build and browser visual review were not completed: MkDocs is absent from the Windows runtime, and WSL invocations did not return output. No dependency installation or unrelated file changes were made. Pricing arithmetic is illustrative, not a production measurement. No billing integration or live deployment is claimed.
