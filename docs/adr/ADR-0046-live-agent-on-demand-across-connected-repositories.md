# ADR-0046: Live Agent — an on-demand run across every connected repository, watched as it happens

**Status:** Proposed · 2026-09-12 · owner instruction the same day: a mode in the UI that runs a
"Live Agent" over ALL connected GitHub repositories, with live output from a real model agent
using keys the organisation supplied — "taki live refetch, nie w CI".
**Governs:** `gfm.live_runs`, `gfm.live_run_targets`, `gfm.live_run_events`, job kinds `live.plan`
and `live.repo`, `{org_base}/live/*`, and the console's Live Agent view.
**Depends on:** [ADR-0045](ADR-0045-org-provider-credentials-encrypted-at-rest.md) (the key),
[ADR-0036](ADR-0036-github-app-ascent-without-customer-ci.md) (installations and the least-privilege
GitHub adapter), [ADR-0032](ADR-0032-engineering-principles-and-hexagonal-architecture.md).
**Does not change:** [ADR-0035](ADR-0035-knowledge-ascent-in-ci.md) and ADR-0036. Ascent in CI and
on pull requests stays exactly as decided; this is a different trigger with a different output.

## Context

Everything Guidefold's agent does today is reactive and gated: ascent runs in the customer's CI
(ADR-0035) or on a pull request through the GitHub App (ADR-0036), and its output is a proposal a
human reviews. Both are the right shape for changing a repository. Neither answers the question an
owner actually asks when they open the console: *what does my skill estimate look like right now,
across all of it?* Waiting for the next pull request in each of thirty repositories is not an
answer, and a CI job the owner cannot watch is not an answer either.

Verified on 2026-09-12: the service has a job queue with leasing, fencing and checkpoints; a remote
model generator with a per-request cost ceiling; and an API contract whose §3 assumes a JSON
envelope with no streaming transport anywhere. The GitHub App code from ADR-0036 does not exist
yet; its contract entries (§4.7) do.

## Decision

1. **On demand, not on a schedule and not in CI.** An organisation owner starts a run from the
   console; members can read a run and its events but cannot start or cancel one, because starting
   one spends the organisation's money. There is
   no cron, no webhook trigger and no CI workflow involved. A run is a read of the current state of
   the organisation's repositories, so re-running it is the whole point — "live refetch" is the
   feature, not a side effect.

2. **The run reads; it does not write to the customer's repositories.** `live.repo` fetches only
   `AGENTS.md` and `**/.agents/skills/**/SKILL.md` through the GitHub contents API with an
   installation token, using the same least-privilege adapter ADR-0036 introduces. It clones
   nothing, executes nothing from the repository, opens no branch and no pull request. Anything the
   agent proposes changing goes to the existing review flow as a proposal, through the path
   ADR-0035 already governs. Keeping the live run read-only is what makes it safe to run at will.

3. **Fan-out is two job kinds, one per repository.** `live.plan` resolves which repositories the run
   covers, writes one `gfm.live_run_targets` row each, and enqueues one `live.repo` per target.
   Repositories are processed by the existing worker pool with the existing leasing and fencing, so
   one slow or failing repository never blocks the rest and a lost worker is recovered the same way
   every other job is. A target that fails leaves the run in state `partial`, naming which
   repositories did not finish. A run over "all connected repositories" that silently covered
   twenty-eight of thirty would be worse than one that failed.

4. **Live output is an append-only event log the UI polls with a cursor.** `gfm.live_run_events`
   holds `(org_id, run_id, seq)` with a type from a closed domain — `run.started`, `repo.started`,
   `model.delta`, `finding`, `repo.finished`, `run.finished`, `error` — and a JSON payload.
   `GET {org_base}/live/runs/{run_id}/events?after=<seq>` returns the next page inside the ordinary
   response envelope, with the ordinary auth, pagination and error codes. No new transport, no
   long-lived connection through the ingress, no second authorization path.
   The log is also the record: a reload, a second viewer, or an owner who opens the run tomorrow
   sees the same thing the first viewer saw live. Streaming without a log would show the first
   viewer something nobody can reproduce. The cost is latency measured in seconds rather than
   milliseconds, which for a run that takes minutes is not a cost anyone feels.
   The worker batches model deltas — one event per ~500 ms or ~2 KB of text — so a chatty model
   cannot turn one run into a hundred thousand rows.

5. **The organisation's key, and a ceiling.** The credential comes from ADR-0045, opened in the
   worker for the duration of one job. Every run carries a hard ceiling: maximum repositories,
   maximum input tokens per repository, and a maximum spend in USD. Spend is counted from the
   usage the provider reports on each response, and from a token estimate only for a response that
   carried no usage; a run whose spend had to be estimated says so on the run record rather than
   presenting a guess as a measurement. When a ceiling is
   reached the run stops and terminates `partial` with `live_run_budget_exhausted`, having written
   every event produced so far. Because the customer's own provider account is charged (ADR-0038
   §2), Guidefold meters nothing and bills nothing — but an agent that can loop is an agent that can
   spend someone else's money, so the ceiling is not optional.

6. **One run at a time per organisation.** A second start while a run is active answers `409
   live_run_already_active` with the active run's id, and the console opens that run instead. This
   is a concurrency limit, not a queue: two simultaneous full sweeps of thirty repositories would
   double the spend for an answer that is the same both times.

7. **Cancellation is real.** `POST {org_base}/live/runs/{run_id}/cancel` marks the run cancelled;
   every target not yet leased is dropped, and a running `live.repo` stops at its next checkpoint
   rather than at the end of the repository. An owner watching money being spent must be able to
   stop it within seconds.

8. **The view leads with the run, not with a table.** The console's Live Agent route follows the
   shadcn console rules (owner instruction 2026-09-12): a large `IconTile`, a composer for the
   prompt, model and repository scope, then a transcript that fills as events arrive and a
   per-repository status list beside it. States are honest: `queued`, `running`, `partial`,
   `cancelled` and `failed` each read as themselves, and "no events yet" is never rendered as
   success. When no credential is configured, the view says so and links to the credential screen
   instead of offering a start button that would fail.

## Consequences

- The service gains its first long-running, owner-initiated, money-spending operation. Everything
  above — the ceiling, the single active run, real cancellation, the honest `partial` state — exists
  because of that, not because of the model.
- The event log grows fastest of any table in `gfm`. Events are deleted with their run after 30
  days, and one run's log is capped at 20,000 events: past that the worker stops appending
  `model.delta`, writes one `error` event with `live_run_log_truncated`, and keeps writing the
  structured events. The run continues and the console says the transcript is truncated. Dropping
  transcript lines quietly would look exactly like an agent that went silent.
- ADR-0036's GitHub adapter and installation tokens become a prerequisite for a second feature. If
  it slips, the live run degrades honestly: repositories with no installation are reported
  `github_app_not_configured` per target rather than skipped quietly.
- The worker's NetworkPolicy needs egress to the OpenRouter endpoint in addition to GitHub. Until
  that exists, `live.repo` terminates `skipped` with a named reason.
- This ADR is Proposed. It becomes Accepted when the tables, the two job kinds, the five endpoints,
  the worker handler and the console view exist, and an acceptance run over the Meridian fixture
  produces a complete event log, a `partial` run when one repository is unreachable, and a
  cancellation that stops work within one poll interval.

## References

- [API-CONTRACT](../API-CONTRACT.md) §3 (envelope, pagination, idempotency), §4.7 (GitHub App),
  §7 (`gfm`), §8 (API–worker contract) — the entries for this decision land there before the code.
- [PRODUCT-PIVOT](../PRODUCT-PIVOT.md) U4, U6.
- [ADR-0045](ADR-0045-org-provider-credentials-encrypted-at-rest.md), [ADR-0036](ADR-0036-github-app-ascent-without-customer-ci.md), [ADR-0038](ADR-0038-subscription-byok-and-metered-ai.md) §2, §5.
