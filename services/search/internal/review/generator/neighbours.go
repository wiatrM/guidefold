package generator

import (
	"sort"
	"strings"
)

// Neighbour selection for consolidation.
//
// `max_neighbours` bounds what one scope may contribute to a consolidation
// group (API-CONTRACT §8). The bound is not the problem; *which* skills it
// keeps is. Before this file the plan kept the first `max_neighbours` rows of
// `ORDER BY s.scope,s.skill_id`, and `skill_id` is the URN text, so a flat
// repository handed consolidation the alphabetically first ten of its skills
// and nothing else. Measured on this repository on 2026-09-15: 81 skills in one
// `_root` scope, of which the ten compared were `accessibility-contract` …
// `backlog-prioritisation`, while the only verbatim-shared procedure in the
// tree lives in the nine `higgsfield-*` skills — never presented, never
// reported (docs/reports/bakeoff/CONSOLIDATION-REAL-REPO-2026-09-15.md).
//
// Alphabetical order is not neutral for this job. Skills that share a name
// family share an author, a tool and usually a copied preamble, which is where
// a shared element actually is; so when a scope holds more skills than the
// bound, the family with the most members goes first. The bound itself does not
// move: a scope still contributes at most `max_neighbours` skills and the group
// is still at most `max_neighbours²`.

// FamilyOf is the name family of a skill: the first dashed segment of its name,
// which is how a repository spells "these belong together" without a scope for
// them (`higgsfield-generate`, `higgsfield-soul-id`). The argument may be a URN
// or a bare name.
func FamilyOf(skillID string) string {
	name := skillID
	if i := strings.LastIndex(name, ":"); i >= 0 {
		name = name[i+1:]
	}
	if i := strings.Index(name, "-"); i > 0 {
		return name[:i]
	}
	return name
}

// NeighbourOrder returns the positions of `ids` in the order consolidation
// wants them: the largest name family first, then smaller families, then the
// skills that belong to no family, each block in id order. Families of one are
// not families — a single skill can share nothing with itself.
//
// The order is total and depends only on the ids, so two plans over the same
// catalog present the same group.
func NeighbourOrder(ids []string) []int {
	size := map[string]int{}
	for _, id := range ids {
		size[FamilyOf(id)]++
	}
	order := make([]int, len(ids))
	for i := range order {
		order[i] = i
	}
	sort.SliceStable(order, func(a, b int) bool {
		ia, ib := order[a], order[b]
		fa, fb := FamilyOf(ids[ia]), FamilyOf(ids[ib])
		sa, sb := size[fa], size[fb]
		if sa < 2 {
			sa = 0
		}
		if sb < 2 {
			sb = 0
		}
		if sa != sb {
			return sa > sb
		}
		if sa > 0 && fa != fb {
			return fa < fb
		}
		return ids[ia] < ids[ib]
	})
	return order
}
