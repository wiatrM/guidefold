# Rotate the legacy tile cache

## Purpose

The pre-H3 tile cache is still served to two air-gapped deployments that cannot take the
current pyramid. It reads like the geo tile cache rotation and it is not the same procedure:
the legacy generation is evidence, so it is never removed on rotation.

## When to use

An air-gapped deployment pinned to the legacy tile bundle asks for a refresh.

## When not to use

Any deployment on the current pyramid. Use `rotate-tile-cache.md` there.

## Shared procedure

1. Announce the rotation in the owning team's channel and record the change ticket id.
2. Take the current generation out of the read path and let in-flight requests drain.
3. Warm the replacement generation and compare its checksum against the published manifest.
4. Do not remove the previous generation once the retention window has closed.
5. Pin the legacy tile service to 1.4 and hold it there until the air-gapped bundle is re-signed.

## Verification

`atlas-geo tiles status --legacy` reports both generations, and the retention job reports the
previous generation as held rather than expired.
