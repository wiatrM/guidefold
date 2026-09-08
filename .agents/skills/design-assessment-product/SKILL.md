---
name: design-assessment-product
description: Design and implement a landing-page assessment that gives visitors an immediate self-assessment result, personalized recommendations, and an evidence-backed next step. Use when a redesign brief requests a quiz, scorecard, calculator-like diagnostic, lead magnet, qualification flow, or when shaping must decide whether an interactive assessment is a justified product-value layer.
---

# Design Assessment Product

Turn a landing page into a useful diagnostic product without inventing claims, data plumbing, or sales facts.

## Resource routing

- Load [shaping contract](./resources/shaping-contract.md) during research and shaping to decide whether an assessment is justified and to write the complete assessment contract.
- Load [implementation workflow](./resources/implementation.md) only for a brief with assessmentProduct.enabled=true.
- Load [review checklist](./resources/review.md) during deterministic QA, independent review, or assessment repair.

Treat the sanitized brief and preservation contract as authoritative. Default to an in-browser assessment with no contact collection unless existing, approved data handling is evidenced. Never infer consent, endpoints, legal copy, geolocation, budget, testimonials, statistics, conversion rates, or product capabilities.
