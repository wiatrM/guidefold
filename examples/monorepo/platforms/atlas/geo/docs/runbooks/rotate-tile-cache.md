# Rotate the geo tile cache

## Purpose

Atlas geo serves map tiles out of a warm generation cache. Whenever the tile pyramid is
rebuilt the cache has to be rotated, so an analyst never reads a tile that no longer matches
the published index.

## When to use

The tile pyramid was rebuilt for one or more zoom levels, or the cache reports a hit ratio
below the floor agreed with the geo team.

## When not to use

Rebuilding the H3 index itself, or replacing the object-storage bucket the tiles live in.
Both are separate procedures with their own owners.

## Shared procedure

1. Announce the rotation in the owning team's channel and record the change ticket id.
2. Take the current generation out of the read path and let in-flight requests drain.
3. Warm the replacement generation and compare its checksum against the published manifest.
4. Remove the previous generation once the retention window has closed.

## Steps

1. Rebuild the affected zoom levels with `atlas-geo tiles rebuild --levels`.
2. Publish the new tile manifest to the shared trust store.

## Verification

`atlas-geo tiles status` reports the new generation id on every serving replica, and no
request is answered from a generation the manifest does not name.
