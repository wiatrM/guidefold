---
name: adr-process
description: "[meridian] How Meridian records architecture decisions as ADRs under docs/adr: numbering, template sections, status lifecycle and who must approve. Use when a change affects more than one platform, introduces a new datastore, protocol or external dependency, or when a reviewer asks for an ADR. Do not use for routine refactors, bug fixes or per-team runbooks."
license: Apache-2.0
compatibility: "Only needs a text editor and a pull request; no special tooling."
metadata:
  scope: _root
  owner: platform-engineering
  references: "docs/adr/README.md"
  status: active
  since: "2026-09-04"
  digest: >-
    Cross-cutting technical decisions in Meridian are captured as numbered Markdown ADRs in docs/adr,
    reviewed in the same PR as the code they justify. ADRs move through proposed, accepted, deprecated and
    superseded states and are never rewritten once accepted.
---

# ADR process

## When to use / when NOT to use
Write an ADR when a change:
- crosses a platform boundary (forge, atlas, relay, security, libs) or changes a shared interface;
- introduces or removes a datastore, message broker, serialization format or external dependency;
- changes how software is built, released or deployed (Bazel rules, bundle format, Helm layout);
- would be expensive to reverse in six months, or a reviewer explicitly asks for one.

Skip the ADR for bug fixes, refactors that keep interfaces stable, team-local tooling and operational
runbooks (those belong in the owning node's skills).

## Steps
1. Copy the template block from `docs/adr/README.md` into `docs/adr/NNNN-short-kebab-title.md`, where
   `NNNN` is the next free number listed in the index. Numbers are never reused.
2. Fill the sections in order: Context, Decision, Alternatives considered, Consequences, Status. Keep
   Context factual; put opinions in Decision.
3. Set `Status: proposed` and add the row to the index table in `docs/adr/README.md`, bumping the
   "next free number" line.
4. Open the PR with the ADR and, where possible, the first implementation slice together. Title it
   `adr: NNNN <title>`.
5. Request review from the owners of every node the decision touches, plus `@meridian/platform-engineering`
   for anything under `libs/` or the build system.
6. On approval flip the status to `accepted` in the same PR. Approval means two owner approvals and no
   unresolved blocking comment after five working days.
7. To change an accepted decision, write a new ADR that says `Supersedes: NNNN` and mark the old one
   `superseded by NNNN`. Never edit the body of an accepted ADR beyond the status line.

## Conventions specific to this scope
- One decision per file; if a proposal contains two independent choices, split it.
- File name and H1 must match: `0005-h3-as-geo-index.md` starts with `# 0005: H3 as geo index`.
- Alternatives considered lists at least two options with a sentence on why each lost.
- Consequences include the migration plan and the rollback path, not only the benefits.
- Link code with paths relative to the repo root (`platforms/atlas/geo/src/index/h3_index.go`), never
  absolute paths or branch URLs.
- Diagrams are Mermaid fenced blocks inside the ADR; no binary images in `docs/adr/`.
- Deprecated ADRs keep their number and file; the index marks them so search still finds the history.
- Air-gap note: every ADR that adds an external dependency states how it is mirrored into the offline
  release bundle.

## Verify
```bash
ls docs/adr | sort | tail -3                                   # next number is unused
grep -n "^| 00" docs/adr/README.md | tail -3                    # index row added
grep -En "^Status: (proposed|accepted|deprecated|superseded by [0-9]{4})$" docs/adr/[0-9]*.md
head -1 docs/adr/NNNN-*.md                                     # H1 matches the file name
```
Reviewers also check that the ADR names every touched node owner and that the PR description links it.

## See also
- urn:skill:meridian:_root:monorepo-conventions
- urn:skill:meridian:forge.ontology:object-type-migrations
