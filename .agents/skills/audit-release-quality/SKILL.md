---
name: audit-release-quality
description: Run release-blocking QA for a generated redesign. Use after build and repair to verify technical health, responsive visuals, accessibility, performance, motion, preservation, artifacts, and secret safety.
---

# Audit Release Quality

Quality gates produce evidence; they are not taste votes. A critical failure blocks publishing.

## Resource routing

- Load [quality workflow](./resources/workflow.md) for gate order, required viewports, cinematic checks, result format, and blockers.
- Load no other resource for this skill.

Claude review may recommend changes, but it cannot waive deterministic, security, accessibility, or preservation failures.
