# Versioning of shared libraries

Every library under `libs/` (`db`, `classification`, `auth-sdk`) is released independently with strict
semantic versioning. Tags are `libs/<name>/vX.Y.Z`; the Go module path is `meridian.example/libs/<name>`
and the Python distribution is `meridian-<name>` with the same version number.

## What bumps what

| Change | Bump |
|--------|------|
| Removed or renamed exported symbol, changed signature, changed default timeout or env var | major |
| New exported symbol, new optional config field, new error value | minor |
| Bug fix with unchanged public behaviour, doc or test-only change | patch |

Build tags, environment variables the library reads and default timeouts are part of the public API.
Exported error values and sentinel constants are frozen once released.

## Deprecation window

A major bump keeps the previous API available for two platform release trains, annotated with
`// Deprecated:` (Go) or `DeprecationWarning` (Python). Supported majors are the current and previous one;
older majors receive security patches only.

## Compatibility matrix

| Library | Latest | Supported majors | Notes |
|---------|--------|------------------|-------|
| db | 2.3.1 | v2, v1 | v1 security-only |
| classification | 1.4.0 | v1 | enum is closed |
| auth-sdk | 3.0.2 | v3, v2 | v3 introduced delegated outbound tokens |
