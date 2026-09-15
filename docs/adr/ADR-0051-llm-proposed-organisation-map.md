# ADR-0051: A model may propose the organisation's scope map; only the owner may apply it

**Status:** Accepted · 2026-09-15 · owner instruction the same day, verbatim: "pamiętajmy że LLM
może 'wymyślić' jak zmapować wiele repo do organizacji, CODEOWNERS też daje dużo info, możemy użyć
LLM w guidefold import żeby seedować strukturalnie poprawne dane organizacji".
**Governs:** the proposal kind `scope_map`, the worker job `scope_map.propose`, the route
`POST {org_base}/proposals/{proposal_id}/decision`, the `gfm.scopes` source value `llm_approved`,
and what an import is allowed to show a model ([API-CONTRACT](../API-CONTRACT.md) §4.2, §4.4, §4.10
point 10, §5.4, §6, §7, §8, contract 1.15.0).
**Depends on:** [ADR-0050](ADR-0050-zero-config-scope-map.md) (the
deterministic inferred map and the precedence `guidefold.yaml` > approved proposal > inferred —
this ADR builds the middle term on top of it,
[ADR-0042](ADR-0042-multi-repo-organisation-and-ci-configurator.md) (one organisation, many
repositories; still Proposed, so its `gfm.repo_links` designation is read here as intent, not as
existing behaviour), [ADR-0045](ADR-0045-org-provider-credentials-encrypted-at-rest.md) (the model
key belongs to the organisation), [ADR-0041](ADR-0041-training-signal-storage-and-dataset-boundaries.md)
(what may leave the repository), [ADR-0008](ADR-0008-skill-identity-resource-id-not-urn.md)
(node names must survive the registry id mapping).
**Amends:** [ADR-0047](ADR-0047-organisation-is-the-default-read-scope.md) decision 5, "Mutations
stay per repository", with exactly one named exception — see decision 5 below.
**Does not change:** retrieval or ranking (P06–P08 rule, [PIVOT-BACKLOG](../PIVOT-BACKLOG.md)
lines 39 and 50), the import state machine, the CLI's own `load_map`, `tools/worker/build_tree.py`,
or any existing proposal kind.

## Context

[PRODUCT-PIVOT](../PRODUCT-PIVOT.md) §4 (U1) line 69 is the requirement this decision serves,
verbatim: "guidefold.yaml ma pierwszeństwo w mapowaniu scope. Katalogi i CODEOWNERS dostarczają
propozycji, jeśli mapy brak. Niepewna hierarchia/owner są widoczne i nie stają się samoczynnie
polityką."

The platform team we sell to has thousands of skills spread over many repositories, each team
writing its own, and nobody holding the whole picture. Somebody has to say that
`platforms/atlas/geo` in one repository and `services/atlas-graph` in another are two children of
the same `atlas` node, owned by the same team. Today that answer exists only in a hand-written
`guidefold.yaml`, and an organisation that has not written one gets `_root` and a flat list.

Three facts make a model a reasonable proposer of that answer, and none of them make it a
reasonable decider. Directory layout, the set of directories that actually contain a `SKILL.md`,
and CODEOWNERS together carry most of the structure — CODEOWNERS in particular is the only place
where a real team name is attached to a real path, and [CONVENTIONS](../CONVENTIONS.md) line 34
already requires a scope `owner` to be a GitHub team present in CODEOWNERS for the same path.
Grouping those signals into a hierarchy is a shape-matching task a model does well and a
deterministic rule does badly, because the shape differs per organisation. And the result is
cheap to check: a scope map is a small typed structure whose correctness is mechanically
decidable, unlike a paragraph of prose.

What makes it dangerous is the same thing that makes it useful. A wrong parent silently moves
skills between owners; a wrong path assignment silently changes which skills an agent is offered
at a given location. So the question this ADR answers is not "may a model guess the map" — it is
"what has to be true before a guess is allowed to become the organisation's data".

## Decision

**1. A model's map is a proposal, never data.** The structure a model returns is written to
`gfm.proposals` with `kind = scope_map`, state `draft`. Nothing reaches `gfm.scopes` until an
owner approves it; the approval writes the rows with `source = 'llm_approved'`, `reviewed_by` and
`proposal_id`, so every row can name the person who accepted it and the proposal it came from.
This is the literal reading of PRODUCT-PIVOT line 69: an uncertain hierarchy is visible and does
not become policy on its own.

**2. Precedence is fixed and the proposal sits in the middle.** `guidefold.yaml` wins, an
approved proposal is next, an inferred map is last (ADR-0050). A later import that carries a
`guidefold.yaml` overwrites a row written by an approval; an approval never overwrites a row the
file declared. Approval also never deletes: a scope the map omits keeps its row, because a node
disappearing without a decision would take skills out of view with nobody having chosen that.

**3. What the model sees is a closed list.** Per repository of the organisation: `repo_id`, the
list of directories containing a `SKILL.md`, the existing `gfm.scopes` nodes (name, parent, owner,
paths), the imported CODEOWNERS rules, `guidefold.yaml` if the repository has one, and the first
400 characters of the root `README.md` and `AGENTS.md`. Never repository code, never a `SKILL.md`
body, never a file outside that list. This follows ADR-0041 decision 2, which forbids raw prompt,
body and source text from leaving as a record, and SEARCH-USE-TELEMETRY §5, which allows only
allowlisted fields. The rule is not a budget concession: the question is how directories group
into an organisation, and the contents of the files are not evidence for it.

**4. The model returns typed JSON, and it is validated before it is stored.** One object:
`nodes[]`, each with `scope`, `parent`, `owner`, `paths[]` (each path carrying its `repo_id`),
`confidence` in `[0,1]` and a one-line `reason`. Five checks run before a proposal row exists,
and again at approval because the repositories may have changed in between:

- every `scope` is a dotted node path whose segments are kebab-case and contain no `--`
  (ADR-0008 decision 1 uses `--` as the registry id separator, so a segment containing one stops
  being reversible), or exactly `_root`;
- `parent` is either absent or names another node of the same map;
- the parent graph is acyclic, and a cycle is reported by naming the loop, not by a boolean;
- every path is assigned to exactly one most-specific node **within its own repository** — the
  containment is computed per `(repo_id, path)`, because a scope identifier is unique per
  repository and not per organisation (ADR-0047 decision 4, API-CONTRACT §4.10 point 6);
- every non-null `owner` is a name that repository can vouch for: a team its CODEOWNERS lists, or
  an owner its own scopes already declare. An owner a repository wrote into `guidefold.yaml` is
  not invented, and rejecting it would fail every map that simply keeps the hierarchy the
  repository already declared; a name from neither source is refused rather than written down as
  a plausible-looking team.

A map that fails produces no proposal and a permanent job failure with the findings named:
retrying the same call cannot repair a structure the model could not build. A failure at approval
is `422 scope_map_invalid` and changes nothing.

`confidence` is shown, never enforced. A threshold would turn a number the model made up into a
gate, which is the automatic policy this ADR exists to prevent.

**5. The decision is taken at organisation scope, by an organisation owner.**
`POST {org_base}/proposals/{proposal_id}/decision` is added, and it is the only mutation in
`{org_base}`. ADR-0047 decision 5 said mutations stay per repository, and that stays true for
exports, feedback, publication, queue decisions and imports. It cannot hold here, and the reason is
a permission, not a convenience: the proposal's `repo_id` is the repository whose import produced
it, but approving writes `gfm.scopes` rows in the organisation's *other* repositories too.
Authorising that as the anchor repository's reviewer would let the reviewer of the smallest
repository move every repository's scopes. So this route requires an organisation owner, and the
`{repo_base}` twin **refuses** a `scope_map` decision with `403 forbidden` rather than accepting it
under the weaker permission — otherwise the twin would be the bypass. For the other three kinds the
organisation route applies exactly the reviewer rule of the repository in the proposal's row, and
`{repo_base}` is unchanged. Any further request for an `{org_base}` mutation needs its own entry in
API-CONTRACT §4.10 point 10.

**6. Approving is applying, and `scope_map` has its own terminal state.** Approval writes
`gfm.scopes` and moves the proposal to `applied`, a state added for this kind alone. It does not
reuse `published`: `published` means a candidate's bytes reached git and a snapshot activated, and
a scope map has no bytes and no snapshot, so reusing the word would make
`GET …/proposals/{id}/publication` answer for something that was never published. `edit` is
`invalid_candidate_change` — the candidate is a typed structure, not prose to correct — and
`export` is `proposal_state_invalid`. An owner who wants a different map rejects this one and
writes `guidefold.yaml`, which outranks every proposal.

**7. The flow runs without a model.** `scope_map.propose` resolves its generator exactly as
`proposal.generate` does (the organisation's preferred credential first, the deployment's
generator second). With `deterministic`, the job proposes the **inferred** map itself — the same
structure ADR-0050 computes from directories and CODEOWNERS — carrying `origin: inferred`. With
`none`, it ends `worker.Skipped("llm_not_configured")` and the import stays useful, the same rule
`proposal.generate` already follows (U2.7; a repository imports without a model key, #146, #167).
This is not a convenience for tests: the deterministic branch is what makes the review, diff,
approval and `gfm.scopes` write provable end to end without a provider, so the only thing a model
adds to the path is the quality of one structure.

**8. Cost is bounded at one call.** `max_calls` is 1 and `max_usd` is 0.50 per job. The input is
structure, so a second call would be the same question asked again; a job that needs more than one
call is a job whose prompt is wrong.

## Consequences

- An organisation with no `guidefold.yaml` gets a reviewable hierarchy after its first import
  instead of a flat `_root`, and the first thing the owner sees is a diff against what they have.
- `gfm.scopes` rows stop being anonymous: `source`, `reviewed_by` and `proposal_id` distinguish
  "the file says so" from "someone accepted a proposal", and `MapScopes` shows it.
- Schema change: `gfm.scopes` gains `reviewed_by` and `proposal_id` and widens its `source` check;
  `gfm.proposals` widens its `kind` and `state` checks. **Production needs the `migrate` Job run
  and verified before the new image digests** (CLAUDE.md, "Production is sacred", point 2).
- Evidence level is R: the two-repository Meridian fixture proves the contract, the validation and
  the write. It does not prove that a model produces a good map for a real organisation — that is
  a P-level claim and needs a real repository set and an owner's judgment. ADR-0042's Rozbieżność 1
  applies unchanged: U1's evidence still runs on a single-repository fixture.
- The `ScopeMapDiff` is computed at read time, so a proposal left in the queue for a week shows
  what approving it would do today, not what it would have done when the job ran. A proposal whose
  inputs changed can therefore stop validating; that is reported, not hidden.
- Nothing here touches retrieval. The map changes which scope a skill is filed under, which is
  already what `guidefold.yaml` does; no ranking input, corpus or score changes, so the P06–P08
  rule holds.
