package review_test

import (
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/review"
)

// The graph cases PRODUCT-PIVOT U2.6 names: a diamond, a shared atom, a
// specialization, a cycle and a wrongful scope widening. The first three are
// legitimate structures that must publish; the last two must not.

func known(nodes []review.Node) map[string]bool {
	out := map[string]bool{}
	for _, n := range nodes {
		out[n.SkillID] = true
	}
	return out
}

func codes(f review.Findings) []string {
	out := []string{}
	for _, x := range f {
		out = append(out, x.Code)
	}
	return out
}

func TestGraphAdmission(t *testing.T) {
	owners := map[string]string{"_root": "platform", "atlas": "atlas-team",
		"atlas.geo": "geo-team", "atlas.graph": "graph-team"}

	t.Run("diamond_publishes", func(t *testing.T) {
		// a requires b and c; both require d. A shared dependency reached by two
		// paths is a normal graph, not a duplicate.
		nodes := []review.Node{
			{SkillID: "a", Scope: "atlas", Requires: []string{"b", "c"}},
			{SkillID: "b", Scope: "atlas", Requires: []string{"d"}},
			{SkillID: "c", Scope: "atlas", Requires: []string{"d"}},
			{SkillID: "d", Scope: "atlas"},
		}
		if f := review.ValidateGraph(nodes, known(nodes), owners); len(f) != 0 {
			t.Fatalf("a diamond must publish, got %v", codes(f))
		}
	})

	t.Run("shared_atom_publishes", func(t *testing.T) {
		// One atom derived from two procedures of two scopes, raised to the
		// scope whose owner is proposing it.
		nodes := []review.Node{
			{SkillID: "geo-rotate", Scope: "atlas.geo"},
			{SkillID: "graph-rotate", Scope: "atlas.graph"},
			{SkillID: "shared-rotate", Scope: "atlas", Owner: "atlas-team",
				DerivedFrom: []string{"geo-rotate", "graph-rotate"}},
		}
		if f := review.ValidateGraph(nodes, known(nodes), owners); len(f) != 0 {
			t.Fatalf("a properly owned shared atom must publish, got %v", codes(f))
		}
	})

	t.Run("specialization_publishes", func(t *testing.T) {
		// A deeper skill refines a shallower one. Refinement points upward and
		// is not a cycle.
		nodes := []review.Node{
			{SkillID: "general", Scope: "atlas"},
			{SkillID: "specific", Scope: "atlas.geo", Refines: []string{"general"}},
		}
		if f := review.ValidateGraph(nodes, known(nodes), owners); len(f) != 0 {
			t.Fatalf("a specialization must publish, got %v", codes(f))
		}
	})

	t.Run("cycle_is_named_with_its_path", func(t *testing.T) {
		nodes := []review.Node{
			{SkillID: "a", Scope: "atlas", Requires: []string{"b"}},
			{SkillID: "b", Scope: "atlas", Requires: []string{"c"}},
			{SkillID: "c", Scope: "atlas", Requires: []string{"a"}},
		}
		f := review.ValidateGraph(nodes, known(nodes), owners)
		if len(f) == 0 || f[0].Code != "graph_cycle" {
			t.Fatalf("expected graph_cycle first, got %v", codes(f))
		}
		if len(f[0].Path) < 3 {
			t.Fatalf("graph_cycle must name the loop, got %v", f[0].Path)
		}
		e := f.Err()
		if !strings.Contains(e.Error(), "graph_cycle") {
			t.Fatalf("the error does not carry the code: %v", e)
		}
	})

	t.Run("similar_and_conflicts_with_may_be_symmetric", func(t *testing.T) {
		// The two symmetric relations are exempt from the cycle rule: "these
		// overlap" is a statement both skills make about each other.
		nodes := []review.Node{
			{SkillID: "a", Scope: "atlas"},
			{SkillID: "b", Scope: "atlas"},
		}
		f := review.ValidateGraph(nodes, known(nodes), owners)
		if len(f) != 0 {
			t.Fatalf("symmetric relations must not fail admission, got %v", codes(f))
		}
	})

	t.Run("missing_dependency_is_not_a_cycle", func(t *testing.T) {
		nodes := []review.Node{{SkillID: "a", Scope: "atlas", Requires: []string{"gone"}}}
		f := review.ValidateGraph(nodes, known(nodes), owners)
		if len(f) != 1 || f[0].Code != "missing_dependency" {
			t.Fatalf("expected missing_dependency, got %v", codes(f))
		}
		if len(f[0].Missing) != 1 || f[0].Missing[0] != "gone" {
			t.Fatalf("the finding must name what is missing, got %v", f[0].Missing)
		}
	})

	t.Run("missing_required_resource_blocks", func(t *testing.T) {
		nodes := []review.Node{{SkillID: "a", Scope: "atlas", Resources: []review.Resource{
			{Path: "a/references/policy.md", Required: true, Available: false},
			{Path: "a/references/optional.md", Required: false, Available: false},
		}}}
		f := review.ValidateGraph(nodes, known(nodes), owners)
		if len(f) != 1 || f[0].Code != "missing_required_resource" {
			t.Fatalf("expected missing_required_resource, got %v", codes(f))
		}
		if f[0].Missing[0] != "a/references/policy.md" {
			t.Fatalf("the wrong resource was blamed: %v", f[0].Missing)
		}
	})

	t.Run("one_source_is_not_a_consolidation", func(t *testing.T) {
		nodes := []review.Node{
			{SkillID: "geo-rotate", Scope: "atlas.geo"},
			{SkillID: "shared", Scope: "atlas", Owner: "atlas-team",
				DerivedFrom: []string{"geo-rotate"}},
		}
		f := review.ValidateGraph(nodes, known(nodes), owners)
		if len(f) != 1 || f[0].Code != "consolidation_sources_insufficient" {
			t.Fatalf("expected consolidation_sources_insufficient, got %v", codes(f))
		}
	})

	t.Run("wrongful_scope_widening_is_refused", func(t *testing.T) {
		// Two sources in the same scope do not justify raising the shared skill
		// above them: several source scopes are what proves a general rule, and
		// there is only one here.
		nodes := []review.Node{
			{SkillID: "geo-a", Scope: "atlas.geo"},
			{SkillID: "geo-b", Scope: "atlas.geo"},
			{SkillID: "shared", Scope: "_root", Owner: "platform",
				DerivedFrom: []string{"geo-a", "geo-b"}},
		}
		f := review.ValidateGraph(nodes, known(nodes), owners)
		if len(f) != 1 || f[0].Code != "scope_widening_not_approved" {
			t.Fatalf("expected scope_widening_not_approved, got %v", codes(f))
		}
	})

	t.Run("scope_widening_needs_the_target_owner", func(t *testing.T) {
		// Two distinct source scopes, but the proposal is owned by one of the
		// sources rather than by the owner of the scope it rises to.
		nodes := []review.Node{
			{SkillID: "geo-a", Scope: "atlas.geo"},
			{SkillID: "graph-b", Scope: "atlas.graph"},
			{SkillID: "shared", Scope: "atlas", Owner: "geo-team",
				DerivedFrom: []string{"geo-a", "graph-b"}},
		}
		f := review.ValidateGraph(nodes, known(nodes), owners)
		if len(f) != 1 || f[0].Code != "scope_widening_not_approved" {
			t.Fatalf("expected scope_widening_not_approved, got %v", codes(f))
		}
	})

	t.Run("a_cycle_is_reported_before_anything_else", func(t *testing.T) {
		nodes := []review.Node{
			{SkillID: "a", Scope: "atlas", Requires: []string{"b", "gone"}},
			{SkillID: "b", Scope: "atlas", Requires: []string{"a"}},
		}
		f := review.ValidateGraph(nodes, known(nodes), owners)
		if len(f) < 2 || f[0].Code != "graph_cycle" {
			t.Fatalf("a cycle makes every other reading unreliable: %v", codes(f))
		}
	})
}
