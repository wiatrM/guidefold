# ADR-0038: Subscription with BYOK and a 10% gross margin on managed AI usage

**Status:** Accepted · 2026-09-08 · product owner: "APPROVED, dodaj 10% marzy i zamykaj jako ADR, dodaj do landing page".
**Governs:** [PRODUCT-PIVOT §12a](../PRODUCT-PIVOT.md#12a-plan-badań-koszt-i-dowody) and [public pricing copy](../../portal/content/index.md#planned-hosted-pricing).
**Purpose:** approve the commercial model, not launch billing or declare SaaS generally available.
**Inputs:** owner's approved cost scenarios, current CI ascent design, and the sources below. No earlier technical ADR is superseded.

## Context

Guidefold is available as open source. The hosted subscription is planned. Model usage varies with changed scope, context, retries and model choice; an unlimited AI allowance would leave costs unbounded. BYOK moves model charges to the customer's provider account but does not remove runner costs.

Rozbieżność: PRODUCT-PIVOT §12a previously deferred prices until interviews and cost measurements.
Decyzja w tej pracy: record and publish the owner's approved price, with planned availability and no claim of validated willingness to pay.
Dokument zastępowany: only the offer paragraph in PRODUCT-PIVOT §12a; research and evidence gates remain.
Konsekwencje: pricing copy changes; billing, checkout, deployment and hosted-agent implementation are outside this change.
Do decyzji właściciela: no further approval needed for this scope; seat/repository quotas and single-buy prices remain unspecified, not unlimited.

## Decision

1. The planned hosted subscription is **USD 99 per organisation per month**, excluding taxes. It pays for the shared library, review and revision controls. There is no base per-skill or per-SEARCH/USE charge. Enterprise SSO is not included. Publish this as planned pricing, not an available checkout.
2. **BYOK is the starting option.** For the CI agent, prefer the customer's runner and secrets: the customer pays their model provider and CI provider directly. Guidefold adds no AI usage charge to that route. The agent proposes changes for human review; it does not merge them.
3. Without BYOK, charge the same subscription plus a **separate prepaid, capped AI budget**. The approved 10% means gross margin on AI revenue, not markup: `price = attributable provider cost / (1 - 0.10)`. Thus USD 9 in provider cost uses USD 10 of customer budget; multiplying cost by 1.10 would give only 9.09% margin. This is margin before payment fees, runner costs, support and taxes, not 10% net profit.
4. Cost means actual attributable model-provider charges, including billed retries and provider fees, net of applicable discounts/cache savings. Do not bill hypothetical retry reserves or estimate missing usage as zero. Aggregate usage at full precision and round the billing total once to cents. Display provider, model, usage, cost basis and customer charge. Infrastructure failures require reconciliation rather than an unverified debit or automatic rerun charge.
5. Before enabling managed AI billing, reserve budget before dispatch, enforce concurrency-safe hard spend and execution limits, reconcile actual usage idempotently, and stop new work when the budget cannot cover it. No automatic top-up or overage without an explicit customer setting. If cost cannot be bounded or reconciled, do not enable paid execution. Runner costs need a measured allowance or a separately disclosed price before that hosted route is sold.
6. Single buy may cover a scoped setup service or a paid self-hosted addition with defined support. No perpetual hosted service, unlimited AI or perpetual support is included. No single-buy price is approved; the earlier USD 499 lifetime example was a risk illustration, not an offer.

### Cost scenarios, not production measurements

The owner's approved example used USD 3 per million input tokens and USD 15 per million output tokens, with a 20% planning reserve for retries. These are illustrative Sonnet 4.5 assumptions, not a promise to use that model or bill reserves. CI ascent uses a configurable model through OpenRouter by default ([ADR-0035](ADR-0035-knowledge-ascent-in-ci.md)); the separate Go generator's default is not proof of CI usage.

| Total input / output per run | Estimated provider cost incl. reserve | Customer AI budget at 10% margin | Budget for 100 such runs |
|---|---:|---:|---:|
| 20,000 / 2,000 | $0.108 | $0.12 | $12 |
| 200,000 / 20,000 | $1.08 | $1.20 | $120 |
| 2,000,000 / 200,000 | $10.80 | $12.00 | $1,200 |

The largest scenario exceeds the separate generator's current default USD 5 limit; it is hypothetical. None includes CI runner charges. At the illustrative USD 22 monthly non-AI cost per organisation and 3% payment fee, the USD 99 subscription leaves USD 74.03 before development, marketing and taxes. Neither cost nor fee is a measured invoice. A USD 120 AI charge covering USD 108 provider cost leaves USD 12 gross, or USD 8.40 after the illustrative 3% payment fee, before runner/support costs. This narrow margin requires measurement.

## Consequences

- OSS remains available; the paid plan does not change its licence.
- Subscription revenue is separated from variable model spend. BYOK is the default commercial route, not a claim that hosted execution is free.
- The hosted GitHub App route remains **Proposed** in [ADR-0036](ADR-0036-github-app-ascent-without-customer-ci.md). This approval does not accept or implement that design.
- Before paid managed execution, measure 20–30 representative runs: input/output tokens, retries, runtime, provider fees and cost per accepted change. Record missing data as unknown. Validate demand separately; owner approval is not customer evidence.
- Public copy states planned availability. No checkout, payments, new quotas or billing API are implemented by this ADR.

## References

- [PRODUCT-PIVOT §12a](../PRODUCT-PIVOT.md#12a-plan-badań-koszt-i-dowody): canonical commercial requirements and evidence gates.
- [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), checked 2026-09-08 for the illustrative scenario; actual selected-provider rates govern metering.
- [WorkOS pricing](https://workos.com/pricing), checked 2026-09-08; enterprise SSO is outside the base plan.
- [Copy audit and verification](../reports/pricing/build-notes.md).
