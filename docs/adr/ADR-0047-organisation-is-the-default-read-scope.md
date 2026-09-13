# ADR-0047: The organisation is the default read scope; a repository is a filter

**Status:** Accepted · 2026-09-13 · owner instruction the same day, on seeing the console:
"w OVERVIEW dashboard NIE POWINIEN BYC PER REPOSITORY tylko per cala organizacja i ew dane
powinny sie wyswietlac OGOLNIE albo filtrowane per repository", then "tak samo na innych
zakladkach: Library tez jest per skill, blad myslimy globalnie z mozliwoscia fitlracji repo",
naming Map, Proposals and Usage & quality as well, and "live agenci pracuja globalnie tez, chyba
ze poproszeni sa o repo only".
**Governs:** every `GET {org_base}/…` read introduced by contract 1.11.0
([API-CONTRACT §4.10](../API-CONTRACT.md)), `mgmt.AuthorizeScope`, and the console's Overview,
Library, Map, Skill, Proposals and Usage & quality views.
**Depends on:** [ADR-0033](ADR-0033-api-contract-first-and-mvp-storage.md) (contract before code),
[ADR-0042](ADR-0042-multi-repo-organisation-and-ci-configurator.md) (one organisation, many
repositories), [ADR-0046](ADR-0046-live-agent-on-demand-across-connected-repositories.md) (the
Live Agent already runs over every connected repository).
**Does not change:** any `{repo_base}` route, any mutation, the repository ACL (S15), the import
wizard (an upload needs one repository), or the CLI (which acts on the checkout it runs in).

## Context

The product sells one thing: seeing and managing the whole skill estate of an organisation, across
many repositories and a monorepo (positioning, 2026-09-09). Yet every console view after sign-in
demanded a repository before it showed anything: Overview, Library, Map, Proposals and Usage all
rendered "Choose a repository" when `?repo=` was absent. The API had the same shape — every
catalogue, review, import and telemetry read lived under `/orgs/{org}/repos/{repo}`, even though
the telemetry ledger itself is already organisation-scoped (`gf.events.tenant_id = org_id`) and the
management tables all carry `repo_id` as an ordinary column. The per-repository routes were a
narrowing of organisation data, not the natural unit.

The narrowing had one real justification: repository ACLs. A member may be granted access to some
repositories and not others (`gfm.repo_acl_policies`, `gfm.repo_members`), and that check was
implemented once, in `mgmt.AuthorizeRepo`, for exactly one repository per request. Any
organisation-wide read has to keep that isolation or it leaks.

Two ways were considered to give the console an organisation view:

1. **Fan out in the browser.** Keep the API as is; the UI lists repositories and issues every read
   once per repository, summing counts client-side. Rejected: N × 6 reads per page, numbers computed
   in the client rather than returned by the API (the Overview's rule is "every number a count the
   API returned"), top-skill and queue merges re-implemented in TypeScript, and the previous-window
   deltas would be sums of sums. It also violates the performance budgets for an organisation with
   many repositories.
2. **Organisation-scope routes with an optional repository filter.** Every read gets a twin under
   `{org_base}` whose scope is the set of repositories the caller may read, narrowed by `?repo=`.
   Chosen.

## Decision

1. **Scope is resolved once, in `mgmt`.** `Context.AuthorizeScope(orgParam, repoParam, role)`
   returns the organisation and a `Scope{Repos []string; Repo *Repo}`. A `{repo_base}` route yields
   a scope of one repository, checked exactly as before. An `{org_base}` route yields every
   repository of the organisation the principal may read — all of them for an owner; for a member,
   those with no ACL rows plus those with an explicit grant — or, with `?repo=`, that one repository
   after the same check. The per-repository rule is a private helper both paths call, so the two
   routes cannot disagree.
2. **Handlers are shared, predicates become sets.** The same handler function serves both patterns;
   `repo_id = $n` becomes `repo_id = ANY($n::text[])`. Nothing is copied. The envelope's `repo_id`
   is the repository when the scope is one and `null` when it spans several.
3. **Rows say where they come from.** `SkillSummary`, `ProposalSummary`, `ImportStatus`,
   `QueueItem`, scope nodes and `ModulePage` carry `repo_id`; `UsageSkill.repo_id` is nullable
   because the ledger can observe a skill the catalogue has never seen. Facets accept `field=repo`.
   The usage export gains a trailing `repo_id` column.
4. **Two structures are inherently per repository and are made explicit, not hidden.** The source
   tree gets a virtual root of repositories (`MapChild.kind = repository`, paths prefixed by
   `<repo_id>/`). Scope ids are unique per repository, so an organisation-scope read of one scope
   answers when it exists in exactly one readable repository and fails with `scope_ambiguous` (409)
   when it exists in several, asking for `repo=`. A wrong guess would show a reader another
   repository's module under a familiar name.
5. **Mutations stay per repository.** Decisions, exports, feedback, publication, queue decisions and
   imports keep their `{repo_base}` routes. The console takes `repo_id` from the row it acts on.
6. **The console reads at organisation scope by default.** `?repo=` is a filter carried in the
   address, offered as a repository selector in the shell, and absent by default. No view after
   sign-in demands a repository except Import (an upload needs one) and, for now, the
   repository-specific tabs of Organization.
7. **The Live Agent is already organisation-wide** (ADR-0046, contract 1.6.0: a run always covers
   every connected repository). A repository-only run would be a new request field and is not part
   of this decision.

## Consequences

- The contract grows by seventeen additive GET routes and a handful of additive fields; contract
  1.11.0. Clients of 1.6.x are unaffected.
- The ACL is enforced by the same code on both route families; the tests for the new routes include
  a restricted member to prove the organisation view drops what the member could not read
  per repository.
- The console loses its "Choose a repository" gates on six views and gains one repository selector.
  The Overview's "Largest scopes" panel becomes "Largest repositories" when no repository is chosen.
- The `_index-hierarchy`, `AGENTS.md` cards and the CLI are untouched: they act inside one checkout.
