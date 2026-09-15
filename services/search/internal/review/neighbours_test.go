package review

import "testing"

// The plan's own half of the fix: `max_neighbours` still bounds what one scope
// contributes, but a flat repository must not spend that budget on whichever
// skills sort first. Measured on this repository on 2026-09-15: 81 skills in
// one `_root` scope, the ten compared were `accessibility-contract` …
// `backlog-prioritisation`, and the tree's only verbatim shared procedure lives
// in its nine `higgsfield-*` skills
// (docs/reports/bakeoff/CONSOLIDATION-REAL-REPO-2026-09-15.md).

func TestPickNeighboursKeepsTheLargestFamilyNotTheAlphabet(t *testing.T) {
	in := []Input{}
	for _, name := range []string{"accessibility-contract", "adr-writing", "animate",
		"api-contract", "backlog-prioritisation",
		"toolc-audio", "toolc-images", "toolc-video", "toolc-websites"} {
		in = append(in, Input{Kind: "skill", Scope: "_root",
			SkillID: "urn:skill:acme:_root:" + name})
	}
	out := pickNeighbours(in, 5)
	if len(out) != 5 {
		t.Fatalf("the cut must still be max_neighbours, got %d", len(out))
	}
	family := 0
	for _, i := range out {
		if len(i.SkillID) > 4 && i.SkillID[len(i.SkillID)-1:] != "" &&
			containsFamily(i.SkillID, "toolc-") {
			family++
		}
	}
	if family != 4 {
		t.Errorf("all four skills of the largest family must survive the cut, got %d: %v",
			family, ids(out))
	}
	// The group handed on is still sorted by skill id, like every other plan
	// output, so two plans over the same catalog are byte-identical.
	for i := 1; i < len(out); i++ {
		if out[i-1].SkillID > out[i].SkillID {
			t.Fatalf("the chosen group is not sorted by skill id: %v", ids(out))
		}
	}
}

func TestPickNeighboursLeavesASmallScopeAlone(t *testing.T) {
	in := []Input{
		{Kind: "skill", Scope: "_root", SkillID: "urn:skill:acme:_root:b"},
		{Kind: "skill", Scope: "_root", SkillID: "urn:skill:acme:_root:a"},
	}
	out := pickNeighbours(in, 10)
	if len(out) != 2 || out[0].SkillID != in[0].SkillID {
		t.Errorf("a scope under the bound must be handed on untouched, got %v", ids(out))
	}
}

func containsFamily(id, prefix string) bool {
	for i := 0; i+len(prefix) <= len(id); i++ {
		if id[i:i+len(prefix)] == prefix {
			return true
		}
	}
	return false
}

func ids(in []Input) []string {
	out := make([]string, 0, len(in))
	for _, i := range in {
		out = append(out, i.SkillID)
	}
	return out
}
