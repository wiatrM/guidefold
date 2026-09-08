# ADR-0035: Knowledge ascent — a model writes abstract skills up the scope tree, gated, as a PR

**Status:** Accepted · 2026-09-08 · owner decisions of the same day: runs in CI on a PR; result is a
separate PR requiring the parent scope's owner; provider is OpenRouter (model chosen per repository);
promotion in the UI is a recommendation the owner clicks, never automatic.
**Amends:** [ADR-0016](ADR-0016-knowledge-lifecycle-gates-and-layers.md) (G6 "lift" is now a
concrete, shipped mechanism at card granularity), [ADR-0031](ADR-0031-monorepo-to-managed-skill-library.md)
§7 (unchanged: no automatic promotion from load counts).
**Governs:** `guidefold ascend`, the `ascend` job in `templates/ci.yml`, `docs/DESIGN.md` §11,
`docs/CONVENTIONS.md` §6.

## Context

The product's stated differentiator is knowledge extracted general-to-specific: a rule true for a
whole platform should live once at the platform scope and teach every team under it, not be
copied into each team's skill. Until today the only implementation of "consolidation upward" was
the deterministic `det-1` recipe in `services/search/internal/review/generator`, which lifts a
shared procedure only when at least three normalised steps are literally identical across two
sibling skills. That finds the planted Meridian pair and essentially nothing in a real repository,
where the same convention is phrased differently by every team. The LLM generator path had no
consolidation-specific prompt, no scope raising and no `refines`/`derived_from` output.

SkillPyramid (arXiv 2606.03692) shows what makes the mechanism work and what breaks it: abstract
skills induced *from* specific ones are the transfer mechanism to unseen tasks (removing them cost
5.2 points on unseen ALFWorld while barely moving seen tasks), and skills generated without
grounding in existing ones score *below* a flat library (64.3 vs 75.7). Today's own evidence in
`docs/reports/market/2026-09-07-progressive-disclosure-evidence.md` shows an agent can act on a
skill's card (name, description, digest) and correctly asks for the body when it needs it 97% of
the time — so cards are the right unit of context to abstract from.

## Decision

1. **Two kinds of abstract skill, both `knowledge_layer: abstract`.** A **map** states what lives in
   a scope — its child scopes and skills, what each is for, who owns it, how they relate — for an
   agent that lands anywhere below and must know what else exists around it. A **convention**
   states what every child does the same way, only when at least two children genuinely share it.
   SkillPyramid abstracts procedures; a monorepo also needs the structural kind.
2. **Bottom-up climb with a delta.** A changed leaf skill seeds its direct parent scope. At each
   level the model sees the target node (owner, children), the abstract skill already there (to
   edit, never to duplicate), the cards of every skill in every descendant scope, and the full body
   of only the changed skill. A level that writes something seeds the next ancestor with what it
   wrote; a level that writes nothing ends the climb. Ascent outputs never trigger ascent by
   themselves.
3. **Grounding and digest-only gates before any write.** Every claim cites source URNs present in
   the context. A body that names a skill not in the context, contains a fenced code block or a
   numbered procedure, or repeats three consecutive lines of any child body verbatim is rejected
   with the reason recorded. Files are capped at 80 lines. `guidefold validate` must pass with the
   new file or it is reverted. These gates are the answer to SkillPyramid's scratch-generation
   ablation: an abstract skill that is not grounded is worse than none.
4. **Idempotency without a model call.** The written file records `ascend_fingerprint` (a hash of
   the child cards and changed bodies it was derived from) and `ascend_kinds_decided`. An unchanged
   fingerprint at a level makes no call and no diff.
5. **Human gate = the parent scope's owner, as a PR.** The CI job never commits to the triggering
   branch. It opens a separate PR against the base whose reviewers are the CODEOWNERS of the
   directories written into — the same rule the API contract enforces as
   `scope_widening_not_approved`. ADR-0012 stands: nothing generated is committed without a human.
6. **Provider.** Any OpenAI-compatible endpoint; OpenRouter by default so the model is a repository
   variable (`GUIDEFOLD_ASCEND_MODEL`), not a code change. The CLI stays a single stdlib+PyYAML file;
   the HTTP call uses `urllib`. The key never enters logs, spool or output.
7. **Utility before belief (next step, not yet gated).** The research harness in
   `research/progressive-disclosure-execution-2026-09-07/` is the template for a paired sibling
   test: an agent in a sibling scope answers a question the new parent card answers, with and
   without it. A card that changes no sibling answer is noise. This becomes a CI gate once it has
   run on a real repository, not before.

## Consequences

- `docs/DESIGN.md` §11's per-unit classifier (segment → classify → match → decide) is not what
  shipped; it stays as the refinement path. Card-level ascent is coarser but grounded in the
  progressive-disclosure evidence and cheaper by an order of magnitude.
- The deterministic `det-1` consolidation in the service remains the offline/test path; the model
  path for consolidation now exists in the CLI, not in the Go generator. Wiring the same prompt into
  `proposal.generate kind: consolidation` for the hosted review is a follow-up under the API contract.
- No new runtime component (ADR-0029): a CLI subcommand and a CI job template.
- Costs: one model call per ancestor level per PR that changes a skill, none when the subtree's
  fingerprint is unchanged.
- Not proven: that an ascended map or convention improves a sibling agent's task outcome. That is
  the paired test in point 7 and the pilot rubric in `docs/pilot/PIVOT-RUBRIC.md`; until it runs,
  ascent is a reviewed proposal mechanism, not a measured product claim.

## References

`skills/guidefold/scripts/guidefold` (`cmd_ascend`), `tests/test_ascend.py`, `templates/ci.yml`
(`ascend`), `docs/CONVENTIONS.md` §6, `docs/DESIGN.md` §11, `docs/API-CONTRACT.md` §4.2/§5.4/§8
(consolidation contract), `docs/reports/market/2026-09-07-progressive-disclosure-evidence.md`,
arXiv 2606.03692 (SkillPyramid).
