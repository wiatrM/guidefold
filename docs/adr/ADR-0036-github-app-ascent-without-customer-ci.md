# ADR-0036: Knowledge ascent for a customer who installed the GitHub App, without editing their CI

**Status:** Proposed · 2026-09-08 · amended 2026-09-12 by owner instruction ("uruchamia się w PR a
nie w CI", behaves like a coverage bot, reports a missing or exhausted model key): decision point 1
is replaced, 1a and 4a are added. The amendment supersedes only this ADR's own earlier point 1.
Original text · owner intent stated the same day ("a customer installs the GitHub
App and it wires itself into CI"). Contract entries are in place (API-CONTRACT 1.2.0 §3, §4.7, §5,
§7, §8); code is not. Becomes Accepted when a registered GitHub App, the worker image change and
the network policy change below exist and the acceptance test in §Consequences passes.
**Amends:** [ADR-0035](ADR-0035-knowledge-ascent-in-ci.md) (its "no new runtime component" line:
this adds a webhook route, a job kind and a GitHub adapter, all inside existing modules and images),
[ADR-0034](ADR-0034-github-app-oauth-and-chrome-extension.md) (the App this ADR relies on; its
point 2 — a least-privilege GitHub adapter for the worker — is the shared prerequisite).
**Governs:** `POST /api/v1/github/webhook`, `gfm.github_installations`, job `ascend.run`, the
worker image and its egress policy.

## Context

ADR-0035 ships knowledge ascent as a job in the *customer's* CI (`templates/ci.yml`). That requires
the customer to copy a workflow, add a model key as a repository secret and keep the tooling ref
pinned. The owner wants the hosted product to do this for a customer who installed the Guidefold
GitHub App: no workflow file, no secret in their repository, the same separate-PR-for-the-parent-
owner gate.

What exists today, verified 2026-09-08: no GitHub App code in the service (no JWT signing, no
installation-token exchange, no webhook, no HMAC check, no `gfm.github_*` table, no GitHub content
adapter); "github" is only an OAuth provider name passed to WorkOS. The worker image has Python,
PyYAML and the trusted CLI file, but **no `git`**, and its NetworkPolicy allows egress to DNS and the
database only. The job queue, leasing, fencing, checkpoints and the `exec` pattern for running the
trusted builder (`importer.PythonBuilder`) all exist and are the shape to reuse.

## Decision

1. **Trigger: every pull request, not only the ones that touch a skill.** Owner instruction,
   2026-09-12: the App behaves like a coverage bot. It runs on the pull request rather than in the
   customer's CI, it says something on every pull request, and it promotes what it learns into a
   separate pull request of its own.

   GitHub sends `pull_request` (`opened`, `synchronize`, `reopened`) to
   `POST /api/v1/github/webhook`. The handler verifies `X-Hub-Signature-256` against
   `GITHUB_WEBHOOK_SECRET_FILE`, is idempotent on `X-GitHub-Delivery`, maps `installation.id` and
   `repository.full_name` to `gfm.github_installations` and `gfm.repos`, and enqueues one
   `pr.report` job (idempotency key `pr:<installation_id>:<pr_number>:<head_sha>`). Anything
   unmatched is `202 {accepted:false}` with a reason; GitHub never sees a 4xx for an installation
   this organisation has not linked. `installation` `created`/`deleted` events maintain the table.
   Linking a GitHub repository to a Guidefold `repo_id` is the owner's act in the UI from
   ADR-0034's "Connect GitHub" flow.

   The previous rule enqueued work only for a pull request that changed
   `**/.agents/skills/**/SKILL.md`. It is replaced because a `pull_request` payload does not carry
   the changed files, so deciding that in the handler would need a GitHub call the handler must not
   make, and because an App that is silent on the pull requests of every team that has not started
   writing skills never shows those teams why they should. `pr.report` fetches the changed files
   with the installation token and enqueues `ascend.run` itself when skill files are among them.

1a. **What the comment says, and what it proposes.** `pr.report` upserts one sticky comment,
   rewritten on each push rather than added to. It names the organisation's rules that apply to the
   paths this pull request touches, resolved from the published catalog, and — this part costs a
   model call — whether the diff appears to contradict one of them. Reading the diff of ordinary
   source code is in scope; **proposing a change to that source code is not**. Every change this App
   proposes is a skill file, in a pull request of its own. Guidefold sells the organisation's
   knowledge, not code review, and a bot that edits application code would be judged against tools
   built for exactly that. An owner of a scope can rule on a proposed rule in a minute; a proposed
   patch to somebody's feature branch needs the whole task in their head, so it would go unread.
2. **The job does exactly what CI does.** `ascend.run` in the worker obtains an installation token
   (RS256 JWT from `GITHUB_APP_PRIVATE_KEY_FILE` → `POST /app/installations/{id}/access_tokens`,
   one hour, held in memory only), clones `head_sha` into `/work`, runs the trusted CLI file from
   the worker image — `skills/guidefold/scripts/guidefold ascend --since <base_ref> --json --summary-md`
   — with `GUIDEFOLD_ASCEND_API_KEY_FILE`, pushes any written files to `guidefold/ascend-pr-<n>`,
   and opens a PR to `base_ref` with the summary as body. Reviewers are the CODEOWNERS of the
   directories written into; nothing is pushed to the customer's PR branch. Checkpoint is the last
   completed scope level; `result` carries `pr_url`, `written[]`, `levels[]`, `calls`.
3. **Never executes the customer's code.** The clone is data. The only executable is the CLI file
   baked into the image (already true for `import.parse`). `guidefold ascend` itself runs `git diff`
   and `validate`, both over files, never hooks or scripts from the repository.
4. **Secrets and ownership.** All three secrets use the `*_FILE` pattern the generator already
   uses. The webhook route and installation table live in a new thin `github` module (inbound
   provider callback, like `identity`'s auth callback); the job lives in `review` (generation from
   existing skills gated by an owner, where ADR-0035 already points the hosted variant); the
   GitHub HTTP client is an outbound port under `importer` (ADR-0034 point 2), used by both.
4a. **No key, or no credit left, is reported — never swallowed.** The model key belongs to the
   organisation (ADR-0045). Two states have to reach a human rather than disappear into a job log:

   - the organisation has stored no key for the configured provider. `pr.report` still writes the
     deterministic half of the comment, and says in it that the promotion half did not run because
     no model key is configured, with a link to the console screen that stores one. The job
     terminates `skipped` with `model_credential_missing`.
   - the provider refuses the call because the account is out of credit or over its quota (HTTP
     402, or 429 that the provider marks as quota rather than rate). The comment says the key is
     out of budget and names the provider. The job terminates `failed` with
     `model_quota_exhausted`, and `gfm.live_runs.error` carries the same value for a run started
     from the console.

   Both are stated in the comment and on the console, because the person who can fix either one is
   usually not the person watching the pull request. A quota failure is never retried on a backoff:
   attempts against an exhausted account produce charges on someone else's bill and no output.

5. **Image and network.** `Dockerfile.worker` adds `git` (a pinned apt package, and
   `tests/test_worker_image.py` extended to allow exactly that). The worker NetworkPolicy adds
   egress to `api.github.com`, `github.com` (443) and the configured model endpoint. Until both
   ship, the job terminates `skipped` with `github_app_not_configured`; the webhook still answers
   `202 {accepted:false, reason:"github_app_not_configured"}`.
6. **Customer CI stays supported.** ADR-0035's template remains the path for customers who do not
   install the App or who want the model key in their own secret store.

## Consequences

- Prerequisites outside this repository: a registered GitHub App with `contents: write`,
  `pull_requests: write`, `metadata: read` and the `pull_request` + `installation` events; its
  private key and webhook secret mounted at the worker and API respectively.
- Acceptance test (to be written under `tests/acceptance/`): against a running stack with a fake
  GitHub API (`httptest`, same pattern as `generator/remote_test.go`), a signed `pull_request`
  webhook for a linked repository whose PR changed a leaf skill produces one `ascend.run` job, one
  clone, one CLI run against the stub model, one branch push and one PR creation call with the
  parent directory in its diff — and a second identical delivery produces nothing.
- Cost: one model call per ancestor level per PR, as in CI; plus two GitHub API calls per job.
- Not decided here: whether the hosted review UI should show ascent PRs. The PR is the review
  surface, by design.

## References

API-CONTRACT 1.2.0 (§3, §4.7, §5 `GitHubInstallation`, §7 `gfm.github_installations`, §8
`ascend.run`), `templates/ci.yml` (`ascend`), `services/search/Dockerfile.worker`,
`deploy/k8s/chart/templates/worker.yaml`, `services/search/internal/importer/builder.go`
(trusted-exec pattern), `services/search/internal/review/generator/remote.go` (`*_FILE` secrets).
