# ADR-0016: Knowledge lifecycle with gates G0–G7 and SkillPyramid layers

**Status:** Accepted · 2026-09-04 (approved: SkillPyramid mechanics with owner acceptance replacing reward) · [ADR-0023](ADR-0023-search-use-service-and-measured-utility.md) proposes an amendment; the status here is unchanged. **Proposed amendment:** [ADR-0031](ADR-0031-monorepo-to-managed-skill-library.md); historical status unchanged.

## Context
Source correction, 2026-09-06: [SkillPyramid v1](https://arxiv.org/html/2606.03692v1) reports +38% reward and −27.7% steps against ReAct without skills, not the flat-library baseline. Its Table 1 gives mean reward 73.7 vs 65.8 and steps 14.6 vs 17.7 against ReAct+Skills. These environment results do not establish monorepo utility. The historical decision below is unchanged.

## Decision
Skills carry a `layer` (`atomic` / `task` / `abstract`) and a state machine `candidate → proposed → in_review → probationary → active → deprecated → archived` with gates: G0 capture (contributor approval, security scan), G1 structure (`validate`), G2 novelty (cosine ≥ 0.85 and trigram Jaccard ≥ 0.4 fails; > 0.70 becomes amend), G3 verification (golden delta, verifier for executable kinds, ≥ 2 distinct-user episodes for agent origins), G4 ownership (CODEOWNERS approve; council for governance kinds), G5 probation (η = (pass+1)/(trial+2) ≥ 0.6 after ≥ 3 loads, origin scope only), G6 lift (SkillPyramid's coarse grouping → screen → fine analysis → grounded build, ≥ 3 skills from ≥ 2 teams, ≤ 5 units), G7 retire (η ≤ 0.2, zero loads 90/180 d, failing anchors, expired programs). Owner acceptance, golden delta and probation replace environment reward. Induction halts for a node below 10 % acceptance.

## Consequences
- Nothing induced or agent-proposed is served outside its origin scope before human acceptance and probation.
- Rejection memory (90 d) and per-node proposal budgets bound reviewer load.
