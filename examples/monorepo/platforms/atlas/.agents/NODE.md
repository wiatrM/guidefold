# atlas

Atlas is the analyst workspace of the Meridian platform: the services and APIs analysts use to
explore data that forge has integrated. It has three main components, each its own node: `geo`
(geospatial layers stored in PostGIS with H3 cell indexes, served as vector tiles), `graph`
(link-analysis queries over the ontology's entities and relationships, with strictly bounded
traversals) and `identity` (roles, RBAC policies and the `turnstile` authorization service that
fronts every atlas API). All atlas HTTP services share one contract-first API style defined in
`platforms/atlas/api/openapi.yaml`.

The node is owned by **atlas-platform**, which owns the shared API conventions, the gateway and the
cross-cutting middleware chain. Sub-nodes are owned by geo-team, graph-team and identity-platform
respectively; changes that cross a sub-node boundary (for example a new policy input field used by
graph) need approval from both owners.
