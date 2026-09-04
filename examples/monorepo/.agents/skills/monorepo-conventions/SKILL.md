---
name: monorepo-conventions
description: "[meridian] Layout, ownership and build conventions for the Meridian monorepo: directory structure per platform, Bazel targets and visibility, CODEOWNERS alignment with guidefold.yaml, trunk-based branching and PR rules. Use when adding a new package, service or node, moving code between platforms, or editing WORKSPACE, BUILD files or CODEOWNERS. Do not use for release tagging, ADR authoring or platform-specific coding style, which have their own skills."
license: Apache-2.0
compatibility: "Needs a Bazel 7+ toolchain (bazelisk) and read access to guidefold.yaml and .github/CODEOWNERS."
metadata:
  scope: _root
  owner: platform-engineering
  references: "WORKSPACE, .github/CODEOWNERS"
  status: active
  since: "2026-09-04"
  kind: engineering
  layer: org
  triggers: "new package or service, BUILD.bazel target, CODEOWNERS line, guidefold.yaml node, Bazel visibility, WORKSPACE dependency"
  negative_triggers: "release tagging, ADR authoring"
  digest: >-
    Meridian is a single Bazel monorepo split into platforms (forge, atlas), infra (relay), security and
    shared libs, each owned by a team listed in guidefold.yaml and mirrored in CODEOWNERS. Code lands on
    main through short-lived branches, and every directory belongs to exactly one owning node.
---

# Monorepo conventions

## When to use / when NOT to use
Use this skill when you:
- create a new package, service or library anywhere under `platforms/`, `infra/`, `libs/` or `security/`;
- add or rename a node in `guidefold.yaml` (this always needs a matching `.github/CODEOWNERS` line);
- change `WORKSPACE`, `.bazelrc` or a `BUILD.bazel` visibility rule;
- move code between platforms or promote a helper into `libs/`.

Do NOT use it for cutting releases (`release-process`), recording design decisions (`adr-process`) or
language style inside a platform; those live in the platform's own skills.

## Steps
1. Pick the owning node. Every directory sits under exactly one `guidefold.yaml` node; the most specific
   path glob wins. If no node fits, propose one in the same PR and get the parent node owner's review.
2. Create the directory with a `BUILD.bazel` next to the code. Targets are named after the directory
   (`//libs/db:db`, `//platforms/atlas/geo/tiles:tiles`). Never `glob(["**"])` across package boundaries.
3. Set `visibility` explicitly. Default is `//visibility:private`; export to the platform with
   `//platforms/forge:__subpackages__`, and to everyone only from `libs/`.
4. Add the CODEOWNERS line. Format is `<path>/  @meridian/<owner>` (two spaces); the owner must equal the
   node `owner` (or a listed subteam) in `guidefold.yaml`.
5. Register external dependencies in `WORKSPACE` (or `MODULE.bazel` once the bzlmod migration lands) with
   a pinned version and sha256. No `latest`, no floating branches.
6. Open a PR from a short-lived branch named `<team>/<topic>` (under three days old). Squash-merge to
   `main`; rebase rather than merge-commit when refreshing.
7. Run `bazel test` for the affected platform before requesting review; CI runs the full graph.

## Conventions specific to this scope
- Directory layout: `platforms/<platform>/<component>/{src,tests,deploy,config}`; `infra/relay/<area>`;
  `libs/<lib>`; `security/<area>`. Tooling that is not shipped lives in `tools/`.
- Go: one `go.mod` at the repo root; import path prefix `meridian.example/`.
- Python: one `requirements.lock` per platform resolved with `pip-compile`; packages are named
  `meridian_<platform>_<component>`.
- Generated files (`AGENTS.md`, `CLAUDE.md`, `.github/instructions/*.instructions.md`) are committed but
  never hand-edited; regenerate with `guidefold materialize`.
- Cross-platform imports go through `libs/` only. `platforms/atlas` must not import `platforms/forge`.
- Commit messages: `<node>: <imperative summary>` (`atlas.geo: add H3 index sharding`); the body says why.
- Feature flags over long-lived branches. Anything behind a flag defaults off and has an owner and a
  removal date.

## Verify
```bash
bazel build //...                                   # whole graph builds
bazel test //platforms/forge/...                    # scoped tests for the platform you touched
guidefold validate                                  # every skill dir maps to one node; owners match CODEOWNERS
for p in $(grep -o '"[a-z/]*/\*\*"' guidefold.yaml | tr -d '"*'); do \
  grep -q "^/$p" .github/CODEOWNERS || echo "missing CODEOWNERS line for $p"; done
git log --oneline -5                                # commit prefixes match node names
```

## See also
- urn:skill:meridian:_root:adr-process
- urn:skill:meridian:_root:release-process
- urn:skill:meridian:shared:shared-lib-versioning
