---
# Consumer bootstrap template. Replace <publisher> with guidefold.yaml's publisher before copying this directory.
name: guidefold
description: "[<publisher>] Discover and load this organization's conventions, procedures and runbooks from its repository or configured service or registry. Use when implementing a task that needs the organization's guidance or when asked to follow team conventions. Do not use for generic language or library questions."
license: Apache-2.0
metadata:
  scope: _root
  owner: platform-engineering
  status: active
---

# Guidefold organizational guidance

Requires Python 3 and PyYAML. Agent Registry access also needs a configured gcloud CLI and registry
permissions. Service search needs a configured URL and bearer token.

Discover a small set of relevant instructions, then read their complete content before applying them.
The scope tree comes from this repository's `guidefold.yaml`; directory depth is not a knowledge layer.

## Start from available context

Read any generated scope card or Guidefold hook result already in context. Cards and hooks are discovery hints;
check loaded source content and revision before acting. They can be older than the current repository.
Run the bundled `scripts/guidefold` from the configured consumer repository (use its installed path).
The CLI finds the nearest ancestor containing `guidefold.yaml`, or uses `GUIDEFOLD_ROOT`.

## Discover and load

1. Run `scripts/guidefold where` to get JSON with the current node, owner and ancestor chain.
   The chain starts with the current node and ends at `_root`; unmatched paths within the repository use `_root`.
2. Run `scripts/guidefold find "<task>" --scope <node>`. By default it prints up to 8 selected cards:
   URN, description, score and node. Scope contributes to relevance; the nearest scope does not always rank first.
   Local results are limited to the requested node's subtree and ancestor chain.
   For distinct task steps, use focused searches and combine relevant skills and their requirements.
3. Load the selected instruction with `scripts/guidefold load <urn>` when using the configured registry backend.
   Read the printed `SKILL.md` path. Load applicable `metadata.requires` dependencies as well.
   Select by task fit and scope; do not preload the entire organization.
4. Apply the relevant instructions and identify the URNs used in the result. An ancestor can add shared
   constraints; a more specific scope alone does not resolve conflicting instructions.

## Service mode

`registry.backend` and `search.backend` are separate settings. The global registry override accepts
`local|agent-registry`; `find --backend local|service` overrides only that search call.
For configured service search use `scripts/guidefold find "<task>" --scope <node> --backend service --limit 4`.
The service accepts budgets 0–4; a larger limit (including the default 8), `--include-deprecated`,
or an unavailable service causes local search fallback.

When effective `search.backend` is `service`, use `scripts/guidefold load <urn>@<revision>`.
The revision must come from an actual service response or harness metadata. Current `find` stdout does
not print revisions; do not guess one or assume a one-call find override changes later load behavior.
Service load verifies the returned checksum, contacts `/v1/use` on each call and has no local fallback.
If a pinned revision is unavailable, report that limitation instead of substituting another version.

## Related skills on a card

A service card may carry a `family` block: the more general skill it refines, the more specific
skills that refine it, and each one's knowledge layer (`atomic`, `task`, `abstract`, or absent).
When the family names a child whose scope matches the scope you are working in, load that child —
it is the version written for your part of the tree. Load an abstract parent only when you need the
rules or constraints that hold everywhere, not the steps. A family lists at most eight children and
looks one level in each direction, so it never proves that a listed skill is the only one, that a
missing one does not exist, or that you now have everything the task needs; it is a pointer to
neighbours, not a dependency list. Use `find` for what else is relevant and the card's own
`requires` for what a skill needs in order to run.

## Sources and cache

`load` prints the path under `${GUIDEFOLD_CACHE:-~/.cache/guidefold}/skills/<encoded-urn>/<revision>/`.
Read that path instead of constructing it. Do not edit cached copies. Improve a skill in its owning
repository and open a PR when requested; the cache is not the source of truth.
If a skill references missing files or flags, report the specific mismatch; do not assume CI has verified it.
If no relevant skill is found, say so and proceed without inventing organizational conventions.
Loading or downloading an instruction does not prove it was applied or helped the task.

For a repository-wide overview, when available, load `urn:skill:<publisher>:_index:hierarchy-index`
using the same backend and revision rules. This generated index describes declared scopes and owners.
