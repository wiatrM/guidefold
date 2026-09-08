package generator_test

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// Cross-scope consolidation and the knowledge layer, measured on the planted
// pair in the Meridian fixture (examples/monorepo/docs/runbooks/README.md,
// "Meridian fixture, planted for U2 AC5").
//
// The fixture is a dev/regression fixture, not evidence about recall on real
// repositories (eval-evidence-rules). What it does prove is the rule P08 turns
// on: a shared procedure that spans two sibling scopes becomes one element in
// their parent scope with its sources named, and a lookalike that contradicts it
// is declined out loud rather than merged.

func repoRoot(t *testing.T) string {
	t.Helper()
	root, e := filepath.Abs(filepath.Join("..", "..", "..", "..", ".."))
	if e != nil {
		t.Fatalf("locate repository root: %v", e)
	}
	if _, e := os.Stat(filepath.Join(root, "examples", "monorepo", "guidefold.yaml")); e != nil {
		t.Fatalf("expected the Meridian fixture under %s: %v", root, e)
	}
	return root
}

// plantedSkill reads one planted runbook and presents it as the skill an
// approved extraction would have created from it.
func plantedSkill(t *testing.T, root, rel, id, scope, owner string) generator.Skill {
	t.Helper()
	path := filepath.Join(root, "examples", "monorepo", filepath.FromSlash(rel))
	body, e := os.ReadFile(path)
	if e != nil {
		t.Fatalf("read planted fixture %s: %v", rel, e)
	}
	return generator.Skill{SkillID: id, Path: rel, SHA256: strings.Repeat("0", 64),
		Scope: scope, Owner: owner, Name: filepath.Base(filepath.Dir(rel)), Body: string(body)}
}

func plantedGroup(t *testing.T) []generator.Skill {
	t.Helper()
	root := repoRoot(t)
	return []generator.Skill{
		plantedSkill(t, root, "platforms/atlas/geo/docs/runbooks/rotate-tile-cache.md",
			"urn:skill:meridian:atlas.geo:rotate-tile-cache", "atlas.geo", "geo-team"),
		plantedSkill(t, root, "platforms/atlas/graph/docs/runbooks/rotate-link-cache.md",
			"urn:skill:meridian:atlas.graph:rotate-link-cache", "atlas.graph", "graph-team"),
		plantedSkill(t, root, "platforms/atlas/geo/docs/runbooks/rotate-legacy-tile-cache.md",
			"urn:skill:meridian:atlas.geo:rotate-legacy-tile-cache", "atlas.geo", "geo-team"),
	}
}

func consolidatePlanted(t *testing.T) generator.Output {
	t.Helper()
	engine, _, e := generator.Select(func(string) string { return generator.NameDeterministic })
	if e != nil {
		t.Fatalf("select the deterministic generator: %v", e)
	}
	out, _, e := engine.Generate(context.Background(), generator.Request{
		Kind: generator.KindConsolidation, OrgID: "org", RepoID: "monorepo",
		// The group is the parent scope and its owner, which is what the plan
		// hands the generator for a cross-scope group.
		Scope: "atlas", Owner: "atlas-platform", GroupID: "consolidation:atlas",
		Skills: plantedGroup(t),
		Limits: generator.Limits{MaxProposals: 5, MaxNeighbours: 10},
		// The Meridian fixture's own guidefold.yaml declares `atlas` at
		// `platforms/atlas/**`, not at a literal `atlas/` directory -- the same
		// mismatch generate.go's real caller resolves from gfm.scopes. Wire it
		// here too so this test exercises the resolved path, not the
		// dotted-scope-name fallback (2026-09-08 ACT-01 finding).
		ScopeDirs: map[string]string{"atlas": "platforms/atlas"},
	})
	if e != nil {
		t.Fatalf("consolidate the planted group: %v", e)
	}
	return out
}

func TestConsolidationLiftsOneSharedElementToTheParentScope(t *testing.T) {
	out := consolidatePlanted(t)
	if len(out.Candidates) != 1 {
		paths := []string{}
		for _, c := range out.Candidates {
			paths = append(paths, c.Path)
		}
		t.Fatalf("expected exactly one shared element, got %d: %v", len(out.Candidates), paths)
	}
	c := out.Candidates[0]
	if c.Scope != "atlas" {
		t.Errorf("the shared element of two sibling scopes belongs to their parent, got %q", c.Scope)
	}
	// The raise takes the *target* scope's owner. Keeping either source's owner
	// would put a skill in `atlas` that nobody in `atlas` agreed to.
	if c.Owner != "atlas-platform" {
		t.Errorf("a raised scope carries the target scope's owner, got %q", c.Owner)
	}
	// With ScopeDirs resolved from gfm.scopes (as the real caller in generate.go
	// does), the candidate lands in the scope's REAL on-disk directory, not a
	// dotted-name guess -- this is the exact path the 2026-09-08 ACT-01 run
	// found wrong (`atlas/graph/...` instead of `platforms/atlas/graph/...`).
	if !strings.HasPrefix(c.Path, "platforms/atlas/.agents/skills/") {
		t.Errorf("candidate path %q was not resolved against ScopeDirs (want a platforms/atlas/.agents/skills/ prefix)", c.Path)
	}

	derived, refines := []string{}, []string{}
	for _, r := range c.Relations {
		switch {
		case r.Type == "derived_from" && r.From == "":
			derived = append(derived, r.To)
		case r.Type == "refines" && r.From != "" && r.To == "":
			refines = append(refines, r.From)
		default:
			t.Errorf("unexpected relation %+v", r)
		}
	}
	if len(derived) != 2 {
		t.Errorf("a shared element owes both sources a derived_from, got %v", derived)
	}
	if len(refines) != 2 {
		t.Errorf("each source must be proposed as refining the shared element, got %v", refines)
	}
	for i := range derived {
		if derived[i] != refines[i] {
			t.Errorf("the two directions must name the same sources: %v vs %v", derived, refines)
		}
	}
	if !strings.Contains(strings.Join(derived, " "), "rotate-tile-cache") ||
		!strings.Contains(strings.Join(derived, " "), "rotate-link-cache") {
		t.Errorf("the sources are the planted pair, got %v", derived)
	}
	// The lookalike must not be one of them.
	if strings.Contains(strings.Join(derived, " "), "legacy") {
		t.Errorf("the lookalike was consolidated: %v", derived)
	}
}

func TestConsolidationInfersTheAbstractLayerAndCitesIt(t *testing.T) {
	c := consolidatePlanted(t).Candidates[0]
	meta, _ := c.Frontmatter["metadata"].(map[string]any)
	if meta[generator.FieldKnowledgeLayer] != generator.LayerAbstract {
		t.Errorf("an element consolidated from two scopes is abstract, got %v",
			meta[generator.FieldKnowledgeLayer])
	}
	var field *generator.Field
	for i := range c.Fields {
		if c.Fields[i].Field == generator.FieldKnowledgeLayer {
			field = &c.Fields[i]
		}
	}
	if field == nil {
		t.Fatal("the layer must be a field of its own so a reviewer can reject it alone")
	}
	if field.Origin != generator.OriginInferred {
		t.Errorf("a generator may only infer a layer, got origin %q", field.Origin)
	}
	if field.Ref == nil || field.Ref.Path == "" || field.Ref.LineFrom == 0 {
		t.Errorf("an inferred layer still points at the lines it was read from, got %+v", field.Ref)
	}
}

func TestConsolidationDeclinesTheLookalikeWithAReason(t *testing.T) {
	out := consolidatePlanted(t)
	if len(out.Abstentions) == 0 {
		t.Fatal("the contradicting lookalike must be declined out loud, not dropped")
	}
	found := false
	for _, a := range out.Abstentions {
		joined := strings.Join(a.Skills, " ")
		if !strings.Contains(joined, "legacy") {
			continue
		}
		found = true
		if a.Reason != "contradictory_steps" {
			t.Errorf("expected contradictory_steps for the lookalike, got %q", a.Reason)
		}
		if a.Detail == "" {
			t.Error("an abstention without a detail is not a reason")
		}
		if !strings.Contains(a.Detail, "remove the previous generation") &&
			!strings.Contains(a.Detail, "Remove the previous generation") {
			t.Errorf("the detail must quote the steps that disagree, got %q", a.Detail)
		}
	}
	if !found {
		t.Errorf("no abstention names the lookalike; got %+v", out.Abstentions)
	}
}

func TestConsolidationIsBoundedByMaxNeighbours(t *testing.T) {
	engine, _, _ := generator.Select(func(string) string { return generator.NameDeterministic })
	out, _, e := engine.Generate(context.Background(), generator.Request{
		Kind: generator.KindConsolidation, OrgID: "org", RepoID: "monorepo",
		Scope: "atlas", Owner: "atlas-platform", GroupID: "consolidation:atlas",
		Skills: plantedGroup(t),
		// One neighbour cannot be a pair, whatever the group holds.
		Limits: generator.Limits{MaxProposals: 5, MaxNeighbours: 1},
	})
	if e != nil {
		t.Fatalf("consolidate: %v", e)
	}
	if len(out.Candidates) != 0 {
		t.Errorf("max_neighbours=1 leaves nothing to compare, got %d candidates", len(out.Candidates))
	}
	if len(out.Abstentions) != 1 || out.Abstentions[0].Reason != "too_few_procedures" {
		t.Errorf("expected one too_few_procedures abstention, got %+v", out.Abstentions)
	}
}

func TestInferLayerRuleTable(t *testing.T) {
	cases := []struct {
		name  string
		in    generator.LayerInput
		layer string
		rule  string
	}{
		{"two scopes beat step count", generator.LayerInput{Steps: 4, SourceScopes: 2},
			generator.LayerAbstract, generator.LayerRuleConsolidated},
		{"ordered steps are a task", generator.LayerInput{Steps: 4, SourceScopes: 1},
			generator.LayerTask, generator.LayerRuleOrderedSteps},
		{"one step is atomic", generator.LayerInput{Steps: 1, SourceScopes: 1},
			generator.LayerAtomic, generator.LayerRuleSingleStep},
		{"rules without steps are abstract", generator.LayerInput{Rules: 3, SourceScopes: 1},
			generator.LayerAbstract, generator.LayerRuleRulesOnly},
		{"a bare reference is atomic", generator.LayerInput{SourceScopes: 1},
			generator.LayerAtomic, generator.LayerRuleReference},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			layer, rule := generator.InferLayer(c.in)
			if layer != c.layer || rule != c.rule {
				t.Errorf("got (%s, %s), want (%s, %s)", layer, rule, c.layer, c.rule)
			}
		})
	}
	for _, v := range []string{generator.LayerAtomic, generator.LayerTask, generator.LayerAbstract,
		generator.LayerUnclassified} {
		if !generator.KnownLayer(v) {
			t.Errorf("%q must be a known layer", v)
		}
	}
	// The source axis must never pass for the knowledge axis.
	for _, v := range []string{"team", "platform", "org", "Abstract", ""} {
		if generator.KnownLayer(v) {
			t.Errorf("%q is not a knowledge layer", v)
		}
	}
}

func TestExtractionInfersAKnowledgeLayerForEveryCandidate(t *testing.T) {
	engine, _, _ := generator.Select(func(string) string { return generator.NameDeterministic })
	root := repoRoot(t)
	body, e := os.ReadFile(filepath.Join(root, "examples", "monorepo",
		filepath.FromSlash("platforms/atlas/geo/docs/runbooks/rotate-tile-cache.md")))
	if e != nil {
		t.Fatalf("read the planted runbook: %v", e)
	}
	out, _, e := engine.Generate(context.Background(), generator.Request{
		Kind: generator.KindExtraction, OrgID: "org", RepoID: "monorepo", Scope: "atlas.geo",
		Owner: "geo-team",
		Documents: []generator.Document{{Path: "platforms/atlas/geo/docs/runbooks/rotate-tile-cache.md",
			SHA256: strings.Repeat("0", 64), Scope: "atlas.geo", Owner: "geo-team",
			Body: string(body)}},
		Limits: generator.Limits{MaxProposals: 5, MaxNeighbours: 10},
	})
	if e != nil {
		t.Fatalf("extract: %v", e)
	}
	if len(out.Candidates) != 1 {
		t.Fatalf("expected one extraction candidate, got %d (%+v)", len(out.Candidates), out.Abstentions)
	}
	c := out.Candidates[0]
	meta, _ := c.Frontmatter["metadata"].(map[string]any)
	// Six ordered steps: a procedure, so a task — not abstract, and not atomic.
	if meta[generator.FieldKnowledgeLayer] != generator.LayerTask {
		t.Errorf("a runbook with ordered steps is a task, got %v", meta[generator.FieldKnowledgeLayer])
	}
	// The source axis is untouched; the two must not be collapsed into one key.
	if meta["layer"] == nil {
		t.Error("the source layer key must stay where it was")
	}
	seen := false
	for _, f := range c.Fields {
		if f.Field == generator.FieldKnowledgeLayer {
			seen = true
			if f.Origin != generator.OriginInferred {
				t.Errorf("origin %q", f.Origin)
			}
		}
	}
	if !seen {
		t.Error("the inferred layer must appear in the candidate's provenance")
	}
}
