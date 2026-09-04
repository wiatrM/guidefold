# ADR-0019: Publish Guidefold as open source under Apache-2.0; the tool is the distributable unit

**Status:** Accepted · 2026-09-04

## Context

Guidefold was designed and built against one partner monorepo, and the early docs (`SKILL.md`,
`docs/CONVENTIONS.md`, the archived `docs/DESIGN-v0.2.md`) named that partner directly or through
a stand-in publisher name (`meridian`). The MVP (`docs/MVP.md`) is a general-purpose tool — any
organisation running a monorepo has the same problem of routing 2,000+ rules to an agent by
location and task — and the repository is now public at
`https://github.com/wiatrM/guidefold`.

Two kinds of material exist in this tree:

1. **The tool** — the bootstrap skill (`skills/guidefold/`), the CLI, the consumer templates
   (`templates/`), the design docs, ADRs and the "Meridian" fixture (`examples/monorepo/`), which
   is fictional. None of it depends on a specific organisation's data.
2. **Partner-confidential material** — the original partner's real skill content, its actual
   `guidefold.yaml`, any real routing telemetry, and internal competitive/positioning documents.
   None of this was ever fixture data and none of it belongs in a public tree.

## Decision

Publish this repository under the **Apache License 2.0** (`LICENSE`, already the license
declared in `skills/guidefold/SKILL.md`). The distributable unit is what E0.3 makes generic:

- `skills/guidefold/` — the bootstrap skill, the CLI, and the hook templates — is what a
  consumer monorepo copies to `.agents/skills/guidefold/`. It names no organisation; the
  description tag and every URN example use `<publisher>`, the value a consumer sets in their
  own `guidefold.yaml`.
- `templates/` — the consumer CI workflow and the example `guidefold.yaml` — uses a placeholder
  organisation (`acme`), never a real one.
- `docs/`, `examples/monorepo/` (fictional "Meridian") and `docs/adr/` stay in the tree because
  they are the design record and a working fixture, not partner data.

Partner-confidential material — the real organisation's name, its real skill content, real
telemetry, and any competitive-positioning documents written about a named partner — is kept out
of this tree entirely rather than redacted in place. A file that would need redaction to be
public is a file that does not belong in a public repository; it stays in a private
workspace/repo instead.

## Consequences

- `guidefold init` (E0.4, not yet built) is the intended on-ramp for a new adopter: it will write
  a real `publisher` and node map into `guidefold.yaml`, replacing the `<publisher>` /
  `acme` placeholders. Until then, an adopter edits `templates/guidefold.example.yaml` and
  `skills/guidefold/SKILL.md`'s description tag by hand.
- Historical documents that record what was actually verified against the real test registry
  (`docs/ASSESSMENT.md`, `docs/adr/ADR-0008`, `docs/adr/ADR-0010`) keep their original example
  values (e.g. `meridian`, `meridian`) where those are the literal strings a `gcloud` command used
  during testing. Rewriting a verification log to use a placeholder would misrepresent what was
  tested; genericising applies to the *product surface* (bootstrap skill, README, templates,
  CONVENTIONS.md), not to dated verification records or the archived `docs/archive/DESIGN-v0.2.md`.
- New contributors send PRs against `main`; `CONTRIBUTING.md` and
  `.github/PULL_REQUEST_TEMPLATE.md` state the process. No CLA is required for Apache-2.0.
- Nothing in `docs/MVP.md`'s scope, timeline or kill criteria changes; this ADR only concerns how
  the repository presents itself to a reader outside the original partner engagement.
