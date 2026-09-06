# Backlog — offline mirror

**The GitHub issues are the source of truth** ([ADR-0027](adr/ADR-0027-product-focus-hard-rules.md)
rule 4). This file is a copy so the repository can answer "what is next" without a network call.
Regenerate it when the issue set changes materially; if the two disagree, the issues win.

Focus and the argument for this shape: [`docs/PRODUCT-FOCUS.md`](PRODUCT-FOCUS.md).
Narrative plan: [`docs/MVP.md`](MVP.md) §4–§5.

**Milestones** (dates relative to 2026-09-06)

| Milestone | Due | Meaning |
|---|---|---|
| M1 — design partner on T0/T1 | 2026-09-20 | One real repo, one real developer, T0 working in Claude Code and Copilot; telemetry proves a session happened |
| M2 — four weeks of real use | 2026-10-18 | Four weeks of real sessions, a weekly per-skill report in a named owner's hands, T1 reachable over a real network |
| M3 — pilot E6.7 decision | 2026-11-15 | Frozen protocol, 3 teams, 20–40 paired tasks, explicit go/no-go for anything beyond T1 |

**Labels.** `epic`, `story`, `research`, `parked`, `blocked-on-owner`; areas `client`, `service`,
`ci`, `authoring`, `telemetry`, `pilot`, `docs`.

Seven epics, forty stories. No story exists without an epic; no research story exists outside #76.

---

## [#71] Epic A — A design partner uses T0 in a real Claude Code and Copilot session
`epic` `client` `docs` · M1 · *ADR-0027 rule 3: "done" means used.*

| # | Story | Size | Depends on | Milestone |
|---|---|---|---|---|
| [#78] | Agree the design partner: repository, developers, data policy · `blocked-on-owner` | S | — | M1 |
| [#79] | T0 must not require a GCP account: fix the bootstrap `SKILL.md` and README | S | — | M1 |
| [#80] | A different operator runs `init` and `doctor` on the partner repo in under 30 minutes, timed | M | #78, #79 | M1 |
| [#81] | Claude Code: prove in a real session that the hook injects the right cards | M | #80 | M1 |
| [#82] | Copilot CLI: prove explicit `find` and `load` in a real session, with honest limits | M | #80 | M1 |
| [#83] | Rebuild the adapter capability matrix from real-session evidence | S | #81, #82 | M1 |
| [#84] | `find` returns relevance order, and the first five onboarding friction items are fixed | S | — (PR #68 open) | M1 |

## [#72] Epic B — The authoring loop a skill owner actually reads before merge
`epic` `authoring` `ci` · M1 · *The value proposition no vendor ships.*

| # | Story | Size | Depends on | Milestone |
|---|---|---|---|---|
| [#85] | Run the authoring report in the partner repo's CI in exposure-only mode | S | #78 | M1 |
| [#86] | F5 trigger and negative-trigger suggestions inside `guidefold validate` | M | — | M1 |
| [#87] | E7.5: the frozen dev set runs on every index build and a regression blocks the snapshot swap | M | #85 | M2 |
| [#88] | Measure whether skill authors actually act on the collision comment | S | #85 | M2 |
| [#89] | `validate` enforces the frontmatter and metadata rules authors actually trip on | S | #78 | M1 |
| [#90] | One page for skill owners: what CI tells you about your skill | S | #85 | M1 |

## [#73] Epic C — The owner sees which skills are exposed, loaded and never used
`epic` `telemetry` · M2

| # | Story | Size | Depends on | Milestone |
|---|---|---|---|---|
| [#91] | Per-skill report from the partner's real ledger: never exposed, exposed unused, used | S | #81, #83 | M2 |
| [#92] | Bounded spool and out-of-hook flush: measured loss and lag, no network in the hook | S | #81 | M2 |
| [#93] | Authenticated telemetry flush replaces the test-only loopback credential adapter | M | #97, #98 | M2 |
| [#94] | Prove events carry no prompt or path text and that 90-day retention deletes | S | #78, #91 | M2 |
| [#95] | A named owner receives the report weekly and records one decision from it · `blocked-on-owner` | S | #91 | M2 |

## [#74] Epic D — T1 for the design partner: a different operator, a real network
`epic` `service` · M2 · *Every number this project has was measured on loopback.*

| # | Story | Size | Depends on | Milestone |
|---|---|---|---|---|
| [#96] | Clean-VM install of T1 by a different operator, timed · `blocked-on-owner` | M | #78 | M2 |
| [#97] | TLS and IAM ingress for T1: the E6 gate that has never been measured | L | #96 | M2 |
| [#98] | An authenticated harness reaches T1 end to end over the real network | M | #97, #81, #82 | M2 |
| [#99] | Keep tier parity at zero mismatches on the structured corpus for every service change | S | — | M2 |
| [#100] | Rehearse snapshot rollback and backup restore on the partner instance | S | #96 | M2 |
| [#101] | `doctor` measures the consumer's own corpus and recommends T0 or T1 | S | — | M1 |

## [#75] Epic E — Pilot E6.7: the go/no-go on developer value
`epic` `pilot` · M3 · *ADR-0027 rule 6: the decision point.*

| # | Story | Size | Depends on | Milestone |
|---|---|---|---|---|
| [#102] | Fill the eight owner placeholders in the E6.7 protocol · `blocked-on-owner` | S | — | M3 |
| [#103] | Freeze and sha-stamp the protocol, and bind `config_version` into the pilot event stream | S | #102 | M3 |
| [#104] | Recruit three pilot teams and confirm access plus labelled tasks · `blocked-on-owner` | M | #102 | M3 |
| [#105] | Dry-run the protocol on five tasks and fix the instrumentation it breaks | M | #103, #104 | M3 |
| [#106] | Run the pilot and publish the `analyze.py` report with its confidence intervals | L | #105 | M3 |
| [#107] | Hands-on usability sessions in the three teams: a failure list, not a score | M | #104 | M3 |

## [#76] Epic F — Research: family E, the one dense track in flight
`epic` `research` · M3 · *ADR-0027 rules 2 and 5. Never a product dependency.*

| # | Story | Size | Depends on | Milestone |
|---|---|---|---|---|
| [#108] | Generate synthetic in-distribution queries over the tenant's own skills, with a leakage check | M | — | M3 |
| [#109] | Family E dev run: at most six configurations, then freeze exactly one arm | M | #108 | M3 |
| [#110] | Test once on both pinned corpora and record every number | S | #109 | M3 |
| [#111] | Close family E in DENSE-PROGRAM §7, pass or fail, with the number | S | #110 | M3 |

## [#77] Epic G — Parked surface: what is frozen, why, and what would reopen it
`epic` `parked` · no milestone — this epic is a register, not a delivery

| # | Story | Size |
|---|---|---|
| [#112] | Park the TEI/GPU shadow worker | S |
| [#113] | Park Kubernetes lifecycle and every deployment target beyond `deploy/t1` | S |
| [#114] | Park index sharding and vector layout (ADR-0021) | S |
| [#115] | Park graph admission scoring, keep graph validation and recovery | S |
| [#116] | KISS review checklist: a PR adding a component names the rule that permits it | S |
| [#117] | One register of parked and dropped MVP scope, with reopening conditions | M |

---

## What was parked or dropped from `docs/MVP.md`, and why

The full register with reopening conditions is #117. Summary:

| MVP scope | Decision | Why |
|---|---|---|
| E0.1–E0.5 foundation | **kept**, folded into epic A | E0.4 (`init`/`doctor`, onboarding ≤ 30 min) is #80; E0.3 portability is #79 |
| E1.1–E1.8 router repairs | **kept as done**, no new stories | Landed across PR #7, #9, #11, #38, #45, #54, #67; the one open defect is #84 (PR #68) |
| E2.1–E2.9 client and distribution | **kept**, split across epics A, C, D | E2.2 → #81/#82, E2.4/E2.7 → #92, E2.6 → #98, E2.8 → #83, E2.9 → #99/#101 |
| E2.3 registry publication | **parked** | The Agent Registry is a downstream mirror, "never required for SEARCH latency or MVP release" (`docs/MVP.md` §2). It keeps working and keeps its tests; it stops being the headline (#79, #117) |
| **E3 promotion vertical** (E3.1–E3.7) | **parked, whole epic** | Promotion is downstream of discovery and no developer has used discovery yet. Reopen when epic C shows an owner making decisions from the report and asking for a proposal workflow |
| E4.1, E4.5, E4.6 governance | **kept** | E4.5 is #89; E4.1 and E4.6 are correctness properties of the frozen surface |
| E4.2 automated probation, E4.3 induction, E4.4 audit export | **parked** | ADR-0027 rule 1; already deferred in `docs/MVP.md` §7 |
| **E5 demo UI** (E5.1) | **parked** | Backstage, Port and Cortex already build portals ([`PRODUCT-FOCUS.md`](PRODUCT-FOCUS.md)); `docs/ui/*` retained as a design record. E5.2 (CLI inspection) and E5.3 (owner report) survive as epic C |
| E6.1–E6.6 service and evidence | **kept**, split across epics C and D | E6.1/E6.6 → #97/#100, E6.2/E6.3 → #98, E6.4 → #93, E6.5 → #91 |
| E6.7 pilot | **kept**, promoted to epic E | It is the decision point (ADR-0027 rule 6) |
| E7.3 composer | **closed** | Ran on dev with no arm frozen (PR #59). Not reopened |
| E7.4 synthetic queries at index time | **merged into** #108 | It is the same generation work, now inside the one research family |
| **E7.1, E7.2, E7.6** flywheel and per-tenant fine-tune | **parked** | They need pilot USE labels that do not exist. ADR-0027 rules 2 and 6 |
| **T2 organisation tier** | **parked** | ADR-0024's tier table stays as target architecture; rule 6 makes the pilot the gate |
| **Codex and Gemini CLI adapters** | **parked** | Claude Code and Copilot are not yet demonstrated (#81, #82). Hook templates stay in `skills/guidefold/hooks/` |
| **TEI/GPU shadow, k8s, sharding, graph admission** | **parked** | ADR-0027 rule 1 surface freeze — #112, #113, #114, #115 |

Nothing was deleted. Every parked item keeps its branch, its flag, its tests and its reports.
