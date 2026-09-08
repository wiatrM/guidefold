# Rotate the link-analysis cache

## Purpose

Atlas graph answers link-analysis queries from a warm generation cache built over the entity
graph. When the graph is re-materialised the cache has to be rotated, so a traversal never
mixes edges from two different builds.

## When to use

The entity graph was re-materialised, or the traversal service reports stale-edge errors on
more than a handful of queries.

## When not to use

Reindexing the full-text entity search, or migrating the graph store itself. Both are
separate procedures with their own owners.

## Shared procedure

1. Announce the rotation in the owning team's channel and record the change ticket id.
2. Take the current generation out of the read path and let in-flight requests drain.
3. Warm the replacement generation and compare its checksum against the published manifest.
4. Remove the previous generation once the retention window has closed.

## Steps

1. Re-materialise the entity graph with `atlas-graph materialize --since`.
2. Publish the new edge manifest to the shared trust store.

## Verification

`atlas-graph cache status` reports the new generation id on every replica, and no traversal
is answered from a generation the manifest does not name.
