# Release preparation — `main` @ `6d8e521` → guidefold.cloudfloo.io

> **PREPARED, NOT EXECUTED; requires the owner's approval in the conversation.**
> Nothing below has been run. No `kubectl`, no `helm`, no request to
> `guidefold.cloudfloo.io` was made while writing this document; every value comes from
> read-only `gh` and `git` in this repository. Approval for one step is not approval for the
> next (CLAUDE.md, "Production is sacred", point 1).

Status: draft release plan. Date: 2026-09-15. Author: rehearsal v2 session.
Purpose: give the operator everything needed to release the five merged pull requests in one
sitting — image digests, the schema diff against the image that is actually running, the
migrate Job, the digest patch, an authenticated smoke test and the rollback point.
Inputs: [deploy runbook](../../../deploy/k8s/environments/cloudfloo-io/README.md) (procedure and
the 2026-09-13 correction), [CLAUDE.md](../../../CLAUDE.md) ("Production is sacred"),
[ADR-0050](../../adr/ADR-0050-zero-config-scope-map.md), [ADR-0051](../../adr/ADR-0051-llm-proposed-organisation-map.md),
[API-CONTRACT](../../API-CONTRACT.md) 1.14.0–1.17.0,
[rehearsal v2](../pilot/2026-09-15-pilot-core-rehearsal-v2.md).
Scope of replacement: none. This document does not change any requirement, ADR or contract and
grants no deployment authority.

## 0. What is in this release

| PR | What | Schema? |
|---|---|---|
| #176 | zero-config scope map — a repository with no `guidefold.yaml` is imported (ADR-0050), contract 1.14.0 | yes |
| #177 | `scope_map` proposal decided at organisation scope (ADR-0051), contract 1.15.0 | yes |
| #174 | audit documents | no |
| #178 | consolidation reaches a shared element on a real repository (`det-2`) | no |
| #180 | CLI defects: `extract` ordering, telemetry flush, `load` error naming, scope-card cap | no (but see §6) |
| #179 | partial imports publish, `card_revision` hint, CODEOWNERS on the GitHub App path, contract 1.17.0 | yes |

## 1. (a) The four images

Built by `publish-images.yml` run **34983077327** (`push`, `main`, conclusion `success`,
2026-09-15T14:39:06Z) from `main` @ `6d8e521693c6202f8b82afb256beb2fa7f341141` — the merge of
PR #179. Read back from GHCR, not from a workflow summary:

```sh
gh run list --workflow publish-images.yml --limit 6 \
  --json databaseId,headSha,headBranch,conclusion,createdAt
gh api "users/wiatrM/packages/container/guidefold-search/versions?per_page=8" \
  --jq '.[] | "\(.name) tags=\(.metadata.container.tags|join(","))"'
```

| Image | Digest (tag `6d8e521693c6202f8b82afb256beb2fa7f341141`, also `latest`) |
|---|---|
| `ghcr.io/wiatrm/guidefold-search` | `sha256:23892d457790e0663039bfdb26407a793200cbd8a1daa182859ff4631ee4fbf4` |
| `ghcr.io/wiatrm/guidefold-worker` | `sha256:bc57b0550d34c533727c478bb135a5ed0d2a7d1b376810a69cb5057ac3ff4d98` |
| `ghcr.io/wiatrm/guidefold-ui` | `sha256:1ad81eb544f06feaafb3008ff55de126a98c478a2220bb5d9490120f210e3ca8` |
| `ghcr.io/wiatrm/guidefold-portal` | `sha256:bd464951ccb81885eca8fbedea8282dad760e8e1b0cf03cd1d4bb226ee3c70e5` |

**These digests are `6d8e521`'s.** The rehearsal-v2 branch adds two CLI fixes on top. If that
branch merges before the release, `publish-images.yml` produces four new digests and this whole
table, the diff in §2 and the Job in §3 have to be re-read against the new head. Do not mix.

## 2. (b) Schema diff against the image that is actually running

**Assumption, to be confirmed by the operator before anything runs.** This session may not read
the cluster, so the running release is taken from the last entry of the deploy runbook:
`search sha256:45f88f1b45cb…`, built from `main` @ `23f7878` by publish run 34761104916. That
mapping was cross-checked read-only against GHCR — the digest
`sha256:45f88f1b45cbe83b68b699de5d9330fdf151b72d600e436b5624ebfa64534e75` carries exactly the tag
`23f78787fdd87cee8521bedafa6a1e6c0cad67e1` — but GHCR cannot say what the cluster runs.

> **Operator step 0.** Read the live digest out of `Application/guidefold` and confirm it is
> `45f88f1b45cb…`. If it differs, find the commit its tag names and redo this diff before
> running anything. This is the 2026-09-13 correction: compare against the digest actually
> running, never against the previous entry in the runbook.

```sh
git diff 23f7878..6d8e521 -- services/search/internal/schema/
```

`5 files changed, 106 insertions(+), 4 deletions(-)`. **This release changes the schema. The
migrate Job runs.** Every DDL statement it adds:

`gfm.scopes` (ADR-0050 + ADR-0051, `internal/schema/importer.go`)
- `ADD COLUMN IF NOT EXISTS reviewed_by uuid`
- `ADD COLUMN IF NOT EXISTS proposal_id uuid`
- `DROP CONSTRAINT IF EXISTS scopes_source_check` then
  `ADD CONSTRAINT scopes_source_check CHECK(source IN ('guidefold_yaml','inferred','directory','codeowners','llm_approved','unknown'))`
  — widened twice in one statement on purpose: two CHECKs on one column would both have to pass.

`gfm.owner_queue` (contract 1.17.0, `internal/schema/importer.go`)
- `DROP CONSTRAINT IF EXISTS owner_queue_reason_check` then
  `ADD CONSTRAINT owner_queue_reason_check CHECK(reason IN ('negative_feedback','source_changed','source_removed','zero_loads','missing_dependency','import_file_failed'))`

`gfm.proposals` (ADR-0051, new file `internal/schema/scopemap.go`, executed last by `Migrate`)
- `DROP CONSTRAINT IF EXISTS proposals_kind_check` then
  `ADD CONSTRAINT proposals_kind_check CHECK(kind IN ('extraction','enrichment','consolidation','scope_map'))`
- `DROP CONSTRAINT IF EXISTS proposals_state_check` then
  `ADD CONSTRAINT proposals_state_check CHECK(state IN ('draft','approved_for_export','awaiting_git','published','applied','rejected','superseded'))`

`gfm.publications` (contract 1.17.0, `internal/schema/review.go`)
- `ADD COLUMN IF NOT EXISTS partial boolean NOT NULL DEFAULT false`

`gfm.github_installations` / `gfm.repos` (contract 1.13.0, `internal/schema/sql.go`)
- `ADD COLUMN IF NOT EXISTS account_type text`
- `ADD COLUMN IF NOT EXISTS import_blocked_reason text`

Everything is additive or a widened CHECK, and `Migrate` runs the whole set in one transaction,
so re-running it is harmless. **New code on the unmigrated database is not harmless**: an import
of a repository with no `guidefold.yaml` writes `source='inferred'` and the old CHECK rejects the
row; `scope_map.propose` writes `kind='scope_map'` and the old CHECK rejects it; `publish.build`
writes `publications.partial` into a column that does not exist. Each of those is an outage of
that path, not a degraded feature — the same shape as 2026-09-13.

## 3. (c) Render and run the migrate Job

From the deploy runbook, with the **new** search image:

```sh
kubectl get application guidefold -n argocd -o json \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['spec']['source']['helm']['values'])" \
  > live-values.yaml
# set image: to sha256:23892d457790e0663039bfdb26407a793200cbd8a1daa182859ff4631ee4fbf4 in that file
helm template guidefold deploy/k8s/chart -n guidefold -f live-values.yaml \
  --set workload=migrate --set portal.enabled=false > rendered.yaml
# From rendered.yaml keep the SINGLE `kind: Job` document by hand, give it the dated name
# guidefold-migrate-20260915, and `kubectl apply -f` that one document. Do not apply
# rendered.yaml as a whole.
kubectl wait --for=condition=complete job/guidefold-migrate-20260915 -n guidefold --timeout=10m
```

`--set portal.enabled=false` is the runbook's own §6 note: `portal.yaml` has no `workload`
guard and otherwise renders a stray duplicate Deployment for a Job-only release.

Confirm the columns and constraints exist before touching digests (`psql` on
`guidefold-postgres-1`, read-only):

```sql
SELECT column_name FROM information_schema.columns
 WHERE table_schema='gfm' AND table_name='scopes' AND column_name IN ('reviewed_by','proposal_id');
SELECT column_name FROM information_schema.columns
 WHERE table_schema='gfm' AND table_name='publications' AND column_name='partial';
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
 WHERE conname IN ('scopes_source_check','owner_queue_reason_check',
                   'proposals_kind_check','proposals_state_check');
```
Expected: both `gfm.scopes` columns present, `gfm.publications.partial` present, and the four
constraint definitions listing `inferred`, `llm_approved`, `import_file_failed`, `scope_map`
and `applied`.

## 4. (d) Patch the digests

Record §5's rollback values first (runbook step 4), dry-run, then patch the four image lines in
the live `Application/guidefold` inline Helm values, the same way as every release in the
runbook. The dry run must change **exactly four lines**; if it changes anything else, stop.

## 5. (f) Rollback point

The release currently recorded as running, `main` @ `23f7878` (publish run 34761104916). Full
digests read back from GHCR by tag:

| Image | Digest |
|---|---|
| `ghcr.io/wiatrm/guidefold-search` | `sha256:45f88f1b45cbe83b68b699de5d9330fdf151b72d600e436b5624ebfa64534e75` |
| `ghcr.io/wiatrm/guidefold-worker` | `sha256:09d28c5af96a32932f983469f84e3934e6910ca86bc1824d6690a121e6f2b8e7` |
| `ghcr.io/wiatrm/guidefold-ui` | `sha256:e7a4c6683b1beb4fefbdeb216abcad162669bc8ee7364038541d6ed8c7f50ecd` |
| `ghcr.io/wiatrm/guidefold-portal` | `sha256:106b2d9c83c9476321ff6ee12568e48c47b64eee187fafbcda46b58462b6413c` |

Rolling the images back does **not** roll the schema back, and does not need to: every statement
in §2 is additive or a widened CHECK, so `23f7878`'s code runs unchanged against the migrated
database. Roll back at the first regression rather than debugging on production.

## 6. (e) Smoke test — authentication first, then this release's own surfaces

CLAUDE.md rule 3, unchanged; `/health/ready` answering 200 proves nothing about the schema.

| # | Check | Expected |
|---|---|---|
| 1 | `GET /health/ready` | 200 |
| 2 | `GET /api/v1/auth/login/google` | 302 to WorkOS |
| 3 | `GET /api/v1/auth/login/github` | 302 to WorkOS (the GitHub App email permission is a separate, known issue — see the runbook) |
| 4 | `GET /api/v1/me` without a session | 401 |
| 5 | API and worker logs, first minutes | zero `ERROR` lines |

Then one check per new behaviour of this release, each of which touches a column or constraint
the migrate Job added:

| # | Release | Check | Expected |
|---|---|---|---|
| 6 | #176 | sign in, import a repository that has **no** `guidefold.yaml`; then `GET {repo_base}/map/scopes` | import `ready`, every `ScopeNode.source` is `inferred`; **not** a `failed` import with `import_tree_has_no_guidefold_yaml` |
| 7 | #176 | `GET {org_base}/repos` for the 43 GitHub-App repositories | the row previously carrying `import_blocked_reason: guidefold_yaml_missing` is either cleared or imported; the field decodes |
| 8 | #177 | `GET {repo_base}/proposals` after that import | one `kind: scope_map`, state `draft`, `scope_map.diff` present |
| 9 | #177 | `POST {repo_base}/proposals/{id}/decision` on that proposal (the twin) | **403 `forbidden`** — "A scope map changes several repositories; decide it at the organization route." |
| 10 | #177 | `POST {org_base}/proposals/{id}/decision` `{"decision":"approve"}` as an organisation owner | 200, `state: applied`, `scopes_written ≥ 1`; afterwards `gfm.scopes.source='llm_approved'` with `reviewed_by` and `proposal_id` set |
| 11 | #179 | an import with one unparseable `SKILL.md` | import `partial`, publication `active` with `partial: true`, one `import_file_failed` owner-queue item — **not** `publish failed: import_partial` |
| 12 | #179 | `POST /v1/use` with the catalog's `revision_id` | 409 `revision_mismatch` with `hint: "send card_revision from the catalog"`; the same call with `card_revision` → 200 |
| 13 | #178 | `guidefold extract --all --wait` on a repository with repeated bootstrap steps | at least one `consolidation` proposal naming its sources (see the rehearsal for the local numbers) |

Every one of checks 6–13 was measured on the local stack in the
[rehearsal v2 report](../pilot/2026-09-15-pilot-core-rehearsal-v2.md) — that is **R** evidence
from a loopback stack with `GUIDEFOLD_AUTH=dev` and the `deterministic` generator, and it is not
evidence that the same answers come back from production.

**One operator note that is not a check.** The worker image bakes the CLI at
`/app/repo/skills/guidefold/scripts/guidefold` and hashes it as `GUIDEFOLD_POLICY_SOURCE`; an
import published by a client whose installed copy of the CLI differs ends
`503 snapshot_policy_mismatch`. #180 and the rehearsal-v2 branch both change that file, so after
this release every adapter installation has to re-run `guidefold install` before it publishes
again. This was hit twice on the local stack and reads exactly like an authentication problem
until it is named.

## 7. What this document does not do

It does not authorise the release, does not patch anything and does not claim the cluster is in
the state §2 assumes. It also does not cover TLS, DNS, the GitHub App's "Email addresses:
Read-only" permission, or `worker.externalEgress` — all still open in the deploy runbook.
