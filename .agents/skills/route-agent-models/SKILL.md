---
name: route-agent-models
description: Select a fixed advisor, technical-lead, executor, and reviewer route for an Unslopify job while bounding reasoning, wall time, token reporting, writer ownership, and provider fallback. Use before agent phases or when tuning fast, balanced, or premium runtime profiles.
---

# Route Agent Models

Resolve one immutable model-routing snapshot before starting any authenticated phase. Never accept model IDs from customer input and never change writer provider mid-job.

## Resource routing

- Always load [routing policy](./resources/policy.md) to choose roles, models, reasoning, advisor gates, and phase budgets.
- Load [telemetry contract](./resources/telemetry.md) when emitting usage, duration, retry, ETA, or optimization evidence.

Keep exactly one writer. If a required fixed model is unavailable, enter the typed operator state; do not buy capacity or silently substitute another model.
