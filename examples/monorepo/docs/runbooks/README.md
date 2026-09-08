# Runbooks in the Meridian fixture

Meridian fixture, planted for U2 AC5.

The fixture's own prose files carry no ordered procedure, so the deterministic recipe
(`det-1`) correctly abstains on all of them with `no_procedure_found`. That proves the
abstain-or-cite rule but never exercises the other half of U2 AC5: a shared element that
*should* be consolidated, and a lookalike that should not.

These three documents are planted for that. They are documents, not skills: no `SKILL.md`
and no `guidefold.yaml` node changes, so the router golden set and the Go parity fixtures
are untouched.

| Document | Scope | Role |
|---|---|---|
| `platforms/atlas/geo/docs/runbooks/rotate-tile-cache.md` | `atlas.geo` | source A of the planted shared element |
| `platforms/atlas/graph/docs/runbooks/rotate-link-cache.md` | `atlas.graph` | source B of the planted shared element |
| `platforms/atlas/geo/docs/runbooks/rotate-legacy-tile-cache.md` | `atlas.geo` | the lookalike that must **not** be consolidated |

## Expected outcome

`atlas.geo` and `atlas.graph` are siblings under `atlas` (see `guidefold.yaml`), so
consolidation groups all three under the parent scope `atlas` and compares procedures inside
that one bounded group — never all pairs in the repository.

1. **One consolidation.** A and B carry the same four steps under `## Shared procedure`, in
   the same order, word for word. The shared element is proposed in the parent scope
   `atlas`, owned by `atlas-platform` (the target scope's owner, not either source's), with
   `derived_from` to both sources and a proposed `refines` from each source to it. Its
   inferred `knowledge_layer` is `abstract`, because it was consolidated from two distinct
   scopes.
2. **One stated abstention.** The lookalike repeats steps 1–3 of the same procedure and then
   says the opposite of step 4: *"Do not remove the previous generation once the retention
   window has closed."* It also pins a version the other two do not. It must be declined with
   an explicit reason (`contradictory_steps`), not merged and not silently dropped.

A run that merges the lookalike, or that produces nothing without saying why, is a
regression. Both outcomes are checked by
`services/search/internal/review/generator/consolidation_test.go` and by
`tests/acceptance/test_p08_pyramid.py`.

## The other runbooks

`tests/acceptance/_support.py::add_runbooks` writes two more runbooks into a throwaway copy
of this tree at test time. Those are for extraction, they are never committed here, and they
are unrelated to the planted pair above.
