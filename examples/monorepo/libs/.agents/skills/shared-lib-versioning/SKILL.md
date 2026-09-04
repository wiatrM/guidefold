---
name: shared-lib-versioning
description: "[shared] Semantic versioning, tagging and compatibility rules for the shared libraries under libs (db, classification, auth-sdk): when to bump major, minor or patch, how to tag libs/<name>/vX.Y.Z, deprecation windows and the consumer upgrade policy. Use when you change a public API in libs, cut a library release or decide whether a change is breaking. Do not use for the platform release train or for application code inside platforms."
license: Apache-2.0
compatibility: "Needs Go 1.22+ with gorelease or apidiff, Python 3.11+ with griffe for the Python packages, and tag rights on main."
metadata:
  scope: shared
  owner: shared-libs
  references: "libs/VERSIONING.md"
  status: active
  since: "2026-09-04"
  kind: ways-of-working
  layer: platform
  triggers: "semver bump, libs tag vX.Y.Z, deprecation window, gorelease apidiff, breaking API change, CHANGELOG Unreleased"
  negative_triggers: "platform release train"
  digest: >-
    Shared libraries in libs are versioned independently with strict semver and tagged as libs/<name>/vX.Y.Z.
    Breaking changes require a major bump, a deprecation window of two platform trains and a migration note in
    the changelog, so every platform can upgrade on its own schedule.
---

# Shared library versioning

## When to use / when NOT to use
Use when you:
- change an exported Go symbol or public Python module in `libs/db`, `libs/classification` or `libs/auth-sdk`;
- cut a new library tag or decide which semver component to bump;
- deprecate an API and need to know how long consumers get;
- bump a shared library inside a platform and want the upgrade policy.

Do not use for the platform-wide release train (`_root:release-process`) or for helpers under
`platforms/*` that are not consumed across platforms.

## Steps
1. Classify the change with the table in `libs/VERSIONING.md`: removed or changed signature is major, new
   exported symbol or option is minor, behaviour-preserving fix is patch.
2. For Go run `gorelease -base=libs/<name>/vX.Y.Z` (or `apidiff`) and paste the summary into the PR. For
   Python run `griffe check meridian_<name> --against libs/<name>/vX.Y.Z`.
3. Update `libs/<name>/CHANGELOG.md` under `## Unreleased`; every major bump also gets a `### Migration` note.
4. If major: keep the old API for two platform trains, mark it `// Deprecated:` (Go) or
   `warnings.warn(..., DeprecationWarning)` (Python) pointing at the replacement.
5. Merge to `main`, then tag: `git tag -s libs/<name>/vX.Y.Z -m "libs/<name> vX.Y.Z"` and push the tag.
   The tag prefix must equal the directory so Go module resolution works.
6. Open follow-up PRs in each consuming platform bumping the version; consumers must be on a supported
   major before the next train freezes.
7. Record the release in the compatibility matrix at the bottom of `libs/VERSIONING.md`.

## Conventions specific to this scope
- Each library is its own Go module (`meridian.example/libs/<name>`) and Python distribution
  (`meridian-<name>`) with the same version number in both ecosystems.
- Pre-1.0 is not an excuse: everything in `libs/` is treated as 1.x or higher.
- Major versions of Go modules use the `/v2` import path suffix; do not fork the directory.
- Only `libs/` may be imported across platforms; a helper copied into two platforms is a signal to promote
  it here with a minor release.
- Supported majors: current and previous. Older majors receive security patches only.
- Build tags, environment variables read by the library and default timeouts are part of the public API.
- Exported error values and sentinel constants are frozen once released; add new ones instead.
- The version string is exposed as `Version` (Go) and `__version__` (Python) and reported by service
  `/version` endpoints.

## Verify
```bash
gorelease -base=$(git describe --tags --match 'libs/db/v*' --abbrev=0)   # suggested bump matches your choice
go mod tidy && git diff --exit-code go.mod go.sum                          # no unpinned drift
grep -n "Migration" libs/<name>/CHANGELOG.md                                # present for majors
git tag -l 'libs/<name>/v*' | sort -V | tail -1                             # last tag is the one you expect
```

## See also
- urn:skill:meridian:_root:release-process
- urn:skill:meridian:shared.auth-sdk:auth-sdk-usage
