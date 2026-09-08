package main

import (
	"context"
	"sort"
)

// The family view of a card: 1.2, additive, and deliberately outside the ranker.
//
// SEARCH answers "which four cards" and USE answers "give me this one". Neither
// can answer the question an agent actually has once it holds an abstraction:
// *is there a more specific version of this for my scope, and is this the
// specific one or the general one?* 1.1 leaves the adapter to guess from names.
//
// `family` says it outright, from the `refines` edges a person approved: the
// parent this card refines, the children that refine it, and the knowledge layer
// each of them sits on. It is a *pointer*, not a promise of completeness — depth
// is one hop and children are capped — because a family that silently truncates
// would be worse than none (P08, PRODUCT-PIVOT §2).
//
// It changes nothing about retrieval. Ranking, selection and the 1.1 response
// are computed and finished before any of this runs, and a 1.1 request never
// sees the field. That is the whole constraint P06–P08 work under: enriched
// metadata may not enter production ranking without its own evaluation
// (PIVOT-BACKLOG, "Zasady prowadzenia").

// familyChildLimit bounds the children a card lists. Eight is enough for a real
// module and small enough that a card stays a card.
const familyChildLimit = 8

// buildFamilyEdges fills the catalog's `refines` projection: one parent per
// card, and the children that name it. It runs once per snapshot inside
// `prepare`, so a request never scans the catalog.
func (c *Catalog) buildFamilyEdges() {
	c.RefinesParent = map[string]string{}
	c.RefinesChildren = map[string][]string{}
	for _, u := range c.Order {
		for _, parent := range stringList(c.Cards[u]["refines"]) {
			if parent == "" || parent == u {
				continue
			}
			if _, ok := c.Cards[parent]; !ok {
				// An edge out of the snapshot is not a family tie. The graph
				// validator refuses these at publication; a reader must not be
				// shown one if it slips through.
				continue
			}
			if _, seen := c.RefinesParent[u]; !seen {
				c.RefinesParent[u] = parent
			}
			c.RefinesChildren[parent] = append(c.RefinesChildren[parent], u)
		}
	}
	for parent := range c.RefinesChildren {
		sort.Strings(c.RefinesChildren[parent])
	}
}

// knowledgeLayers reads the Wiedza axis for a bounded set of skills.
//
// The layer lives in the management catalog, not in the serving snapshot: it is
// a property of the skill an owner approved, and Retrieval reads it rather than
// keeping a second copy that could disagree. A tenant that is not an
// organisation — the legacy operator profile — has no management catalog behind
// it and gets no layers, exactly as it gets no resources.
func (s *Store) knowledgeLayers(ctx context.Context, tenant string, ids []string) map[string]string {
	out := map[string]string{}
	if !isUUID(tenant) || len(ids) == 0 {
		return out
	}
	rows, e := s.Pool.Query(ctx, `SELECT skill_id,knowledge_layer FROM gfm.skills
 WHERE org_id=$1::uuid AND skill_id=ANY($2::text[])`, tenant, ids)
	if e != nil {
		// A layer nobody could read is unknown, not "unclassified" and not an
		// error: 1.2 promises the family, and the layer is a label on it.
		return out
	}
	defer rows.Close()
	for rows.Next() {
		var id, layer string
		if e = rows.Scan(&id, &layer); e != nil {
			return out
		}
		if layer != "" && layer != "unclassified" {
			out[id] = layer
		}
	}
	return out
}

// familyFor builds one card's family from the catalog projection and a layer
// lookup that has already been done.
func (c *Catalog) familyFor(id string, layers map[string]string) M {
	var parent any
	if p, ok := c.RefinesParent[id]; ok {
		parent = M{"skill_id": p, "revision": c.Revisions[p], "layer": nullString(layers[p])}
	}
	children := []M{}
	for _, child := range c.RefinesChildren[id] {
		if len(children) >= familyChildLimit {
			break
		}
		children = append(children, M{"skill_id": child, "revision": c.Revisions[child],
			"scope": str(c.Cards[child]["node"]), "layer": nullString(layers[child])})
	}
	return M{"parent": parent, "children": children, "layer": nullString(layers[id])}
}

// familyIDs is every skill whose layer one response needs: the cards themselves,
// their parents and the children that will be listed.
func (c *Catalog) familyIDs(ids []string) []string {
	seen := map[string]bool{}
	out := []string{}
	add := func(v string) {
		if v == "" || seen[v] {
			return
		}
		seen[v] = true
		out = append(out, v)
	}
	for _, id := range ids {
		add(id)
		if p, ok := c.RefinesParent[id]; ok {
			add(p)
		}
		for i, child := range c.RefinesChildren[id] {
			if i >= familyChildLimit {
				break
			}
			add(child)
		}
	}
	sort.Strings(out)
	return out
}

// decorateFamily12 attaches `family` to every card of a 1.2 SEARCH response.
//
// It runs after ranking, after selection and after `card_context` has been
// rendered and measured, so neither the order of `ranked`/`cards` nor the byte
// budget can move because of it. One query serves the whole response.
func (s *Store) decorateFamily12(ctx context.Context, c *Catalog, groups ...[]M) {
	ids := []string{}
	for _, group := range groups {
		for _, card := range group {
			ids = append(ids, str(card["skill_id"]))
		}
	}
	if len(ids) == 0 {
		return
	}
	layers := s.knowledgeLayers(ctx, c.Tenant, c.familyIDs(ids))
	for _, group := range groups {
		for _, card := range group {
			card["family"] = c.familyFor(str(card["skill_id"]), layers)
		}
	}
}
