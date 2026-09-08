package review

import (
	"sort"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// The one-shot profile, and the grouping that makes a pyramid possible.
//
// Both exist for the same request: "point this at my repository and give me back
// the instructions in it, arranged". Default limits are built for a careful
// first run — five groups, a small budget — and that is right when a person is
// deciding whether to spend anything. It is wrong when the answer is already
// yes, because it silently leaves most of the repository unplanned, and
// `groups_skipped` is a number nobody reads twice.
//
// `profile=one_shot` raises `max_groups` to cover every group the plan found and
// nothing else. The money ceilings stay exactly where they were: `max_usd` and
// `max_calls` still stop the run, the job still checkpoints per group, and the
// plan still shows every number before anything is enqueued (U2.7).

// ProfileDefault and ProfileOneShot are the two run profiles.
const (
	ProfileDefault = ""
	ProfileOneShot = "one_shot"
)

// oneShotCeiling is the hard bound a one-shot run still cannot cross. It is not
// a budget — `max_usd` is — but a catalog with thousands of scopes must not turn
// one request into thousands of enqueued groups without anybody choosing that.
const oneShotCeiling = 1000

// parseProfile validates the requested profile.
func parseProfile(raw string) (string, error) {
	switch strings.TrimSpace(raw) {
	case ProfileDefault, "default":
		return ProfileDefault, nil
	case ProfileOneShot:
		return ProfileOneShot, nil
	}
	return "", mgmt.Invalid("invalid_request", "profile must be one_shot when present.")
}

// withProfile returns the limits a profile plans under, before the caller's own
// clamping. Only `max_groups` moves; every other ceiling is the deployment's.
func withProfile(limits Limits, profile string) Limits {
	if profile == ProfileOneShot {
		limits.MaxGroups = oneShotCeiling
	}
	return limits
}

// fitGroups lowers `max_groups` back to what the plan actually found, so the
// number an owner sees before starting is the number of groups that will run —
// not the ceiling that let them all through.
func fitGroups(limits Limits, groups []Group, profile string) Limits {
	if profile != ProfileOneShot {
		return limits
	}
	perKind := map[string]int{}
	most := 0
	for _, g := range groups {
		perKind[g.Kind]++
		if perKind[g.Kind] > most {
			most = perKind[g.Kind]
		}
	}
	if most == 0 {
		most = 1
	}
	limits.MaxGroups = most
	return limits
}

// consolidationGroups regroups one scope-keyed map so that consolidation
// compares siblings.
//
// A shared procedure almost never lives twice inside one scope; it lives once in
// `atlas.geo` and once in `atlas.graph`, and the element it wants to become
// belongs to `atlas`. Grouping consolidation by scope, as extraction and
// enrichment are grouped, can therefore never find the thing consolidation
// exists to find.
//
// So consolidation groups by *parent* scope: each scope's skills go into the
// group of the scope that contains it, and the parent's own skills go into their
// grandparent's. Every skill lands in exactly one group, which is what keeps a
// shared element from being proposed twice under two different ancestors with
// two different cache keys.
//
// The group, not the catalog, is the unit of comparison, and it is bounded by
// `max_neighbours` — so the pairwise scan inside a group is quadratic in a small
// constant and never in the size of the repository (API-CONTRACT §8).
func consolidationGroups(byScope map[string][]Input, limits Limits) map[string][]Input {
	scopes := make([]string, 0, len(byScope))
	for scope := range byScope {
		scopes = append(scopes, scope)
	}
	sort.Strings(scopes)
	members := map[string][][]Input{}
	for _, scope := range scopes {
		parent := parentScope(scope)
		members[parent] = append(members[parent], byScope[scope])
	}
	out := map[string][]Input{}
	for parent, children := range members {
		out[parent] = combine(children, limits.MaxNeighbours)
	}
	return out
}

// combine builds one group out of the scopes that contribute to it.
//
// `max_neighbours` bounds a scope's contribution, which is where
// `skillsByScope` already applies it, and it bounds how many scopes may
// contribute. A group therefore holds at most `max_neighbours²` skills — 100 at
// the default — and the pairwise scan inside it stays bounded by a constant
// rather than by the catalog.
//
// The bound is deliberately not applied to the concatenation. Truncating a
// concatenated list would let the first scope in name order spend the whole
// budget and leave its siblings uncompared, which is exactly the pair
// consolidation exists to find; and it would drop skills that the previous
// per-scope grouping did compare, so P08 would lose ground P06 had already
// taken. When a parent has more children than the bound, the scopes are taken
// in name order and the ones left out are the group's own tail, not a random
// half of everyone's.
func combine(children [][]Input, limit int) []Input {
	if limit > 0 && len(children) > limit {
		children = children[:limit]
	}
	total := 0
	for _, c := range children {
		total += len(c)
	}
	out := make([]Input, 0, total)
	for _, c := range children {
		out = append(out, c...)
	}
	return out
}

// parentScope is the dotted parent of a scope; the root is its own parent, so a
// top-level scope's skills group with the root's rather than falling out of the
// plan.
func parentScope(scope string) string {
	if scope == "" || scope == "_root" {
		return "_root"
	}
	if i := strings.LastIndex(scope, "."); i > 0 {
		return scope[:i]
	}
	return "_root"
}
