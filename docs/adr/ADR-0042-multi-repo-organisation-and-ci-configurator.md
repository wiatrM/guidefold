# ADR-0042: Multi-repository organisations, a CI configurator, and per-organisation generator settings

**Status:** Proposed · 2026-09-12 · owner intent stated the same day: "support MULTI REPOSITORY
organization (not monorepo) and CI CONFIGURATOR - to be able to configure CI worker to extract
knowledge also NOT IN CODE but ONLY in skill repository for other repositories also"; "in CI
settings each organization can setup their MODEL LLM for doing pyramid extraction, api keys etc,
then GITHUB APP installed will use those settings." Contract entries are design-only (this ADR's
companion spec, §5); no code, migration or endpoint exists. Becomes Accepted when the owner
authorizes it against PIVOT-BACKLOG and the acceptance tests in Consequences pass.
**Relies on:** [ADR-0036](ADR-0036-github-app-ascent-without-customer-ci.md) (the GitHub App and
its installation-token repo-clone path, which this ADR's new `extract.run` job reuses — still
Proposed itself; `extract.run` is a distinct job kind, not `ascend.run` — companion spec §9 Q5),
[ADR-0035](ADR-0035-knowledge-ascent-in-ci.md) (`templates/*.yml`, the `customer_ci` mode's base),
[ADR-0038](ADR-0038-subscription-byok-and-metered-ai.md) (BYOK default, 10% managed-AI margin,
metering/reconciliation rules this ADR's budgets must obey).
**Governs:** `gfm.repo_links`, `gfm.org_generator_settings`, `gfm.proposals.target_repo_id`,
`gfm.exports.target_repo_id`, the Organization › CI screen, and the worker's generator-selection
precedence.

## Context

Today `gfm.repos` already has primary key `(org_id, repo_id)` — an organisation can register more
than one repository (`POST {org_base}/repos`, repeatable). What does **not** exist: which
registered repository is the *skills repository* proposals should land in; a route for a proposal
generated from one repo's import to export into another repo; a CI configurator screen; per-org
generator settings. `gfm.jobs.payload` and `generator.Select` (`services/search/internal/review/
generator/generator.go`) read `GUIDEFOLD_GENERATOR`/`GUIDEFOLD_GENERATOR_MODEL`/`*_API_KEY_FILE`
from the worker's own environment — one model, one key, per deployment, not per organisation.

**Rozbieżność 1:** the owner's "multi repository organization" request runs against PRODUCT-PIVOT
§4, literally titled "U1 — skan i synchronizacja **monorepo**", and PRODUCT-FOCUS's customer
definition (a platform team on one monorepo). Decision in this ADR: document the multi-repo
capability as a Proposed extension of U1 per the owner's current instruction, without editing
PRODUCT-PIVOT's text in this change. Document to update once accepted: PRODUCT-PIVOT §4, PIVOT-
BACKLOG. Consequence: U1's R/Q/P evidence still runs on the single-repo Meridian fixture; multi-
repo has no R evidence yet. Left to the owner: whether to accept this ADR into the backlog with an
implementation slot.

**Rozbieżność 2:** `generator.Select`'s own comment says `GUIDEFOLD_GENERATOR` "is operator
configuration and never a request field: which model a deployment pays for is not something a
caller may choose" — the owner now wants per-organisation model choice. Decision in this ADR:
generator settings become an **organisation-level** setting (set once by the org's owner in the
UI, not chosen per request by a caller), so the "never a request field" rule holds literally; only
who "the operator" is widens from "the deployment" to "the deployment, or the paying organisation
when it configured its own key." `GUIDEFOLD_GENERATOR*` stays the deployment-wide fallback.

## Decision

1. **Designation, not a role enum.** A new table `gfm.repo_links` (one row per `org_id`) carries
   `skills_repo_id` (FK into that org's `gfm.repos`) and the CI configurator's own settings
   (`source_repo_ids[]`, `kinds[]`, `schedule_cron`, `ci_mode`). Rejected: a `gfm.repos.role`
   column (nothing enforces exactly one `role='skills'` row per org under concurrent writes) and
   `skills_repo_id` on `gfm.orgs` (Identity owns that table's writes; Import would be writing into
   another module's row). A repo can be both a source and the skills repo at once simply by
   appearing in both `skills_repo_id` and `source_repo_ids` — this is exactly today's single-repo
   organisation once it gets a `repo_links` row (§Consequences, migration).
2. **Proposals and exports gain an optional target, nothing existing changes meaning.**
   `gfm.proposals.repo_id` keeps meaning "the repo whose import produced this group." A new
   nullable `target_repo_id` (also added to `gfm.exports`) is `null` for every proposal that exists
   today and for every monorepo organisation going forward — byte-identical behaviour. When an
   organisation has configured `repo_links`, extraction/enrichment jobs set `target_repo_id =
   skills_repo_id`; `approve` then writes `gfm.skills` under `repo_id = target_repo_id ??
   proposal.repo_id`. `consolidation` always runs directly against the skills repo's own catalog
   (`repo_id = skills_repo_id`, `target_repo_id: null`) — it compares siblings already landed
   there, never reaches across repos itself.
3. **The CI configurator (Organization › CI) generates one of two things**, never both: a
   workflow file for the skills repo (`customer_ci`, built on `templates/github-workflows-
   skills.yml`, extended with a `proposals:generate` step per configured source repo) plus a
   minimal import-only workflow per source repo and one CI token per source repo (`gfm.tokens.
   repo_id` is a single column — one token cannot bind to several repos), scope `validate import
   generate`, never `publish`; or, when the org has a linked GitHub App installation, a
   server-side schedule (`ci.schedule.tick`) the worker runs with no customer CI file at all,
   dispatching one **`extract.run`** (new, proposed job kind — companion spec §9 Q5) per source
   repo — never `proposal.generate`, which needs an already-finalized `gfm.imports` row that no
   upload ever creates in this mode, and never ADR-0036's `ascend.run`, which cannot do this job:
   it triggers only on a PR that changed an existing `**/.agents/skills/**/SKILL.md` (ADR-0036
   point 1), its resulting PR goes back into `base_ref` of the *same* repo it cloned — no
   cross-repo publish exists — and it runs `git diff`/`validate` over already-existing skills
   (ADR-0036 point 3), not extraction from plain source, which is what a source repo usually is
   (§3: source repos usually have no `.agents/skills/**`). `extract.run` reuses only ADR-0036
   point 2's installation-token clone path, then runs pyramid extraction under the organisation's
   generator settings (§4) and opens a PR in the skills repo (or files a `gfm.proposals` entry,
   depending on `ci_mode`). `github_app` is only selectable once `GET {org_base}/github/
   installations` returns a row.
4. **Central, non-code knowledge is not a new mechanism.** The owner's "extract knowledge also NOT
   IN CODE but ONLY in skill repository for other repositories also" is covered by letting
   `source_repo_ids` include `skills_repo_id` itself — the skills repo's own documents (runbooks
   that live nowhere else) become an ordinary source, self-targeting (`target_repo_id: null`),
   available to the same consolidation pass as every other source repo's approved output.
5. **Generator settings are per-organisation, encrypted, never echoed.** `gfm.
   org_generator_settings` (one row per org): `provider ∈ {none, openai, anthropic, azure}`,
   `model`, `api_key_ciphertext` (AES-GCM, KEK from `GUIDEFOLD_GENERATOR_KEK_FILE`, versioned for
   rotation), `use_managed_key`, `max_usd_per_run`, `max_usd_per_month`. The raw key exists only in
   the write request body; no response — not even the creating one — ever returns it, which is
   stricter than the existing token convention ("shown once in the creating response") because a
   provider key is a third-party secret with a larger blast radius than a `gf_…` token
   (security-baseline). `generator.Select` tries the calling job's organisation settings first,
   then falls back to `GUIDEFOLD_GENERATOR*`. `Recipe{Generator,Version,Model}` — already the basis
   of `CacheKey` — must carry the organisation's provider/model when used, or changing an org's
   model would silently replay proposals cached under the old one. `ImportPlan.generator` shows the
   organisation's configured provider before spend (U2.7), not the deployment default, whenever one
   is set.
6. **Budgets are metering, not billing.** `max_usd_per_run` narrows a job's `Limits.MaxUSD`, never
   above the deployment ceiling. `max_usd_per_month` is checked before enqueue against the sum of
   `JobCost.usd_certain` for the organisation this month; `usd_uncertain` is neither billed nor
   counted as zero (ADR-0038 §4) — it forces reconciliation. When `use_managed_key`, the customer
   charge is `provider_cost / (1 − 0.10)` (ADR-0038 §3 — not `× 1.10`, which would understate
   margin). This ADR adds no checkout, invoicing or top-up flow (PRODUCT-PIVOT §14 "Poza MVP").

## Consequences

- Existing single-repo organisations are unaffected until their owner opens Organization › CI and
  saves once; that first save materializes `skills_repo_id = source_repo_ids = [their one repo]`.
  No backfill migration, no data rewrite — every `target_repo_id` before and after that save is
  `null`, so `{repo_base}/proposals*` output for them is byte-identical to today.
- Acceptance test (to be written under `tests/acceptance/`, mirroring ADR-0036's pattern): an
  organisation with two source repos and one skills repo runs extraction against each source repo
  and one consolidation pass against the skills repo's combined catalog; every approved candidate
  lands in `gfm.skills` under the skills repo regardless of which source repo it came from. A
  second, single-repo organisation fixture proves zero regression (`target_repo_id` stays null,
  `gfm.proposals`/`gfm.exports` shape unchanged).
- Cost: one CI token per source repo instead of one per org (more tokens to issue and revoke, but
  each stays least-privilege — no org-wide token spanning repos it wasn't scoped to).
- Not decided here: the exact source-path → skills-repo scope mapping UI (companion spec §9 Q1),
  whether `azure` ships now or stays reserved (§9 Q4), and the reciprocal `Amended by` note this ADR
  owes ADR-0036/ADR-0038 once one of them is edited in a change that also touches this file — until
  then this ADR carries the one-directional "Relies on" line above.
- Companion design document: [multi-repo CI configurator
  spec](../superpowers/specs/2026-09-12-multi-repo-ci-configurator-design.md) (full DTOs, error
  codes, wireframe, open questions, acceptance criteria — none applied to `docs/API-CONTRACT.md`
  yet).

## Alternatives considered

- **`gfm.repos.role` enum** for skills-vs-source — rejected (Decision 1): a second source of truth
  that concurrent writes could leave at 0 or 2 "skills" rows per org, when `approve`/`export` need
  exactly one, deterministically.
- **`skills_repo_id` on `gfm.orgs`** — rejected as a *location* only (Decision 1): correct idea,
  wrong module ownership; Identity already owns writes to `gfm.orgs`, and Import needs to write
  this value from the CI configurator screen it owns.
- **A many-to-many `gfm.repo_links`** (several skills repos per org) — rejected: the owner's own
  wording is "one designated skills repository." A many-to-many table would model a relationship
  that does not exist yet; a future multi-skills-repo requirement is a new ADR, not a YAGNI
  pre-build here.
- **Cross-repo consolidation groups** (comparing not-yet-approved candidates across source repos
  directly, before any of them land in the skills repo) — rejected for this ADR: consolidation
  stays scoped to the skills repo's own catalog (Decision 2), so a `Document`/`Skill` never needs a
  `repo_id` distinct from its request's repo — the smallest change that still satisfies "N sources
  → one skills repo."

## References

Companion spec: `docs/superpowers/specs/2026-09-12-multi-repo-ci-configurator-design.md`.
`docs/API-CONTRACT.md` §2 (token scopes), §4.2 (import/proposals routes), §4.7 (GitHub App), §5.4
(`ProposalDetail`/`Export`), §7 (`gfm.repos`, `gfm.proposals`, `gfm.exports`, `gfm.tokens`), §8
(job-kind table, generator env). `services/search/internal/review/generator/{generator.go,
remote.go}` (`Select`, `Recipe`, `CacheKey`, `*_API_KEY_FILE` pattern). `templates/ci.yml`,
`templates/github-workflows-skills.yml`. `.agents/skills/security-baseline/SKILL.md` ("Nie trzymaj
sekretów tam, gdzie ich nie ma").
