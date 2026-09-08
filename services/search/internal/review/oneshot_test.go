package review

import (
	"fmt"
	"reflect"
	"testing"
)

// The two decisions that make a one-shot pyramid run possible, tested without a
// database because neither of them touches one: which skills end up compared
// with which, and which ceiling a profile moves.

func TestConsolidationGroupsSiblingsUnderTheirParent(t *testing.T) {
	in := map[string][]Input{
		"atlas.geo":      {{SkillID: "geo-1"}, {SkillID: "geo-2"}},
		"atlas.graph":    {{SkillID: "graph-1"}},
		"atlas":          {{SkillID: "atlas-1"}},
		"forge.ontology": {{SkillID: "forge-1"}},
		"_root":          {{SkillID: "root-1"}},
	}
	out := consolidationGroups(in, Limits{MaxNeighbours: 10})

	ids := func(scope string) []string {
		got := []string{}
		for _, i := range out[scope] {
			got = append(got, i.SkillID)
		}
		return got
	}
	// Two sibling scopes meet under `atlas`; that is the whole point.
	if got := ids("atlas"); !reflect.DeepEqual(got, []string{"geo-1", "geo-2", "graph-1"}) {
		t.Errorf("atlas group is %v, want the geo and graph skills", got)
	}
	if got := ids("forge"); !reflect.DeepEqual(got, []string{"forge-1"}) {
		t.Errorf("forge group is %v", got)
	}
	// A top-level scope's own skills group with the root's, so nothing is
	// dropped out of the plan for having no parent.
	// Scope order, not insertion order: the same catalog must produce the same
	// group whichever order the rows came back in.
	if got := ids("_root"); !reflect.DeepEqual(got, []string{"root-1", "atlas-1"}) {
		t.Errorf("root group is %v, want the root's own skills and atlas's", got)
	}
	// Every skill appears exactly once: a shared element proposed under two
	// different ancestors would be two proposals with two cache keys for one
	// piece of knowledge.
	seen := map[string]int{}
	for _, inputs := range out {
		for _, i := range inputs {
			seen[i.SkillID]++
		}
	}
	for id, n := range seen {
		if n != 1 {
			t.Errorf("%s is in %d groups", id, n)
		}
	}
	if len(seen) != 6 {
		t.Errorf("expected all six skills to be grouped, got %d", len(seen))
	}
}

func TestConsolidationGroupsAreBoundedByMaxNeighbours(t *testing.T) {
	// `max_neighbours` bounds how many scopes contribute; `skillsByScope` bounds
	// what each one contributes. A group is therefore at most max_neighbours²
	// skills, and the pairwise scan inside it stays a constant.
	in := map[string][]Input{}
	for _, scope := range []string{"atlas.a", "atlas.b", "atlas.c", "atlas.d"} {
		in[scope] = []Input{{SkillID: scope + "-1", Scope: scope},
			{SkillID: scope + "-2", Scope: scope}}
	}
	out := consolidationGroups(in, Limits{MaxNeighbours: 3})
	scopes := map[string]bool{}
	for _, i := range out["atlas"] {
		scopes[i.Scope] = true
	}
	if len(scopes) != 3 {
		t.Errorf("at most 3 scopes may contribute, got %d (%v)", len(scopes), scopes)
	}
	if len(out["atlas"]) != 6 {
		t.Errorf("each contributing scope keeps its own skills, got %d", len(out["atlas"]))
	}
}

func TestTheBoundIsNotSpentOnTheFirstSibling(t *testing.T) {
	// Four children of five skills each. Truncating a concatenated list at
	// `max_neighbours` would fill the group from the first two scopes in name
	// order and never compare the other two against anything — a silent loss of
	// exactly the pairs consolidation exists to find, and of pairs the older
	// per-scope grouping did compare.
	in := map[string][]Input{}
	for _, scope := range []string{"atlas.a", "atlas.b", "atlas.c", "atlas.d"} {
		for i := 1; i <= 5; i++ {
			in[scope] = append(in[scope], Input{SkillID: fmt.Sprintf("%s-%d", scope, i),
				Scope: scope})
		}
	}
	out := consolidationGroups(in, Limits{MaxNeighbours: 10})
	seen := map[string]int{}
	for _, i := range out["atlas"] {
		seen[i.Scope]++
	}
	if len(seen) != 4 {
		t.Fatalf("only %d of 4 sibling scopes reached the group: %v", len(seen), seen)
	}
	for scope, n := range seen {
		if n != 5 {
			t.Errorf("%s contributed %d of its 5 skills", scope, n)
		}
	}
	// And a same-scope pair is never pushed out by a sibling: everything a
	// per-scope group would have compared is still in the parent group.
	for _, id := range []string{"atlas.a-1", "atlas.a-5", "atlas.d-1", "atlas.d-5"} {
		found := false
		for _, i := range out["atlas"] {
			if i.SkillID == id {
				found = true
			}
		}
		if !found {
			t.Errorf("%s was dropped from the group", id)
		}
	}
}

func TestParentScope(t *testing.T) {
	cases := map[string]string{
		"atlas.geo":                 "atlas",
		"forge.pipelines.streaming": "forge.pipelines",
		"atlas":                     "_root",
		"_root":                     "_root",
		"":                          "_root",
	}
	for in, want := range cases {
		if got := parentScope(in); got != want {
			t.Errorf("parentScope(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestOneShotRaisesOnlyTheGroupCeiling(t *testing.T) {
	base := DefaultLimits()
	planned := withProfile(base, ProfileOneShot)
	if planned.MaxGroups <= base.MaxGroups {
		t.Errorf("one_shot must plan past the default %d groups, got %d",
			base.MaxGroups, planned.MaxGroups)
	}
	// The money ceilings are the deployment's and do not move with a profile.
	if planned.MaxUSD != base.MaxUSD || planned.MaxCalls != base.MaxCalls ||
		planned.MaxTokens != base.MaxTokens || planned.MaxNeighbours != base.MaxNeighbours {
		t.Errorf("one_shot moved a budget: %+v vs %+v", planned, base)
	}
	if got := withProfile(base, ProfileDefault); got.MaxGroups != base.MaxGroups {
		t.Errorf("the default profile changes nothing, got %d", got.MaxGroups)
	}
}

func TestOneShotReportsTheGroupsItWillActuallyRun(t *testing.T) {
	groups := []Group{
		{Kind: "extraction", Scope: "a"}, {Kind: "extraction", Scope: "b"},
		{Kind: "extraction", Scope: "c"}, {Kind: "consolidation", Scope: "_root"},
	}
	got := fitGroups(withProfile(DefaultLimits(), ProfileOneShot), groups, ProfileOneShot)
	// Three of one kind is the number an owner has to approve, not the 1000-group
	// ceiling that let them through.
	if got.MaxGroups != 3 {
		t.Errorf("max_groups after planning is %d, want 3", got.MaxGroups)
	}
	if same := fitGroups(DefaultLimits(), groups, ProfileDefault); same.MaxGroups != 5 {
		t.Errorf("the default profile keeps its ceiling, got %d", same.MaxGroups)
	}
	if empty := fitGroups(withProfile(DefaultLimits(), ProfileOneShot), nil,
		ProfileOneShot); empty.MaxGroups != 1 {
		t.Errorf("an empty plan still reports a usable limit, got %d", empty.MaxGroups)
	}
}

func TestProfileNamesAreClosed(t *testing.T) {
	for _, ok := range []string{"", "default", "one_shot"} {
		if _, e := parseProfile(ok); e != nil {
			t.Errorf("profile %q must be accepted: %v", ok, e)
		}
	}
	for _, bad := range []string{"oneshot", "ONE_SHOT", "full", "all"} {
		if _, e := parseProfile(bad); e == nil {
			t.Errorf("profile %q must be refused", bad)
		}
	}
	if profileName(ProfileDefault) != "default" || profileName(ProfileOneShot) != "one_shot" {
		t.Error("a client must be able to tell the default from an unknown field")
	}
}
