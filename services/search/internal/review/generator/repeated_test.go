package generator_test

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// The rule this file measures: two identical steps between two skills are a
// coincidence, the same two steps verbatim in three skills are copy-paste.
//
// It is planted, not fixture data: each test writes its own tree under
// t.TempDir() so the numbers it asserts belong to the rule and not to whatever
// somebody last committed. The measurement on a real repository lives in
// docs/reports/bakeoff/CONSOLIDATION-REAL-REPO-2026-09-15.md and in
// TestRealTreeConsolidation, which reads a checkout and is skipped without one.

// bootstrapSkill is the shape the duplication really takes in the wild: a short
// section whose heading says "Step 0 — Bootstrap", two numbered steps, and a
// fenced command inside the first one.
const bootstrapSkill = `# %TITLE%

## Step 0 — Bootstrap

Before any other command:

1. If ` + "`toolc`" + ` is not on ` + "`$PATH`" + `, install it:

` + "```bash" + `
curl -fsSL https://example.test/install.sh | sh
` + "```" + `

2. Run ` + "`toolc auth login`" + ` and wait.

## %OWN%

1. %OWNSTEP%
`

func plantSkill(t *testing.T, dir, name, own, ownStep string) generator.Skill {
	t.Helper()
	body := strings.NewReplacer("%TITLE%", name, "%OWN%", own, "%OWNSTEP%", ownStep).
		Replace(bootstrapSkill)
	path := filepath.Join(dir, name, "SKILL.md")
	if e := os.MkdirAll(filepath.Dir(path), 0o755); e != nil {
		t.Fatalf("plant %s: %v", name, e)
	}
	if e := os.WriteFile(path, []byte(body), 0o644); e != nil {
		t.Fatalf("plant %s: %v", name, e)
	}
	sum := sha256.Sum256([]byte(body))
	return generator.Skill{SkillID: "urn:skill:acme:_root:" + name,
		Path: filepath.Join(name, "SKILL.md"), SHA256: hex.EncodeToString(sum[:]),
		Name: name, Description: name, Scope: "_root", Body: body}
}

func consolidate(t *testing.T, skills []generator.Skill) generator.Output {
	t.Helper()
	engine, _, e := generator.Select(func(string) string { return generator.NameDeterministic })
	if e != nil {
		t.Fatalf("select the deterministic generator: %v", e)
	}
	out, _, e := engine.Generate(context.Background(), generator.Request{
		Kind: generator.KindConsolidation, OrgID: "org", RepoID: "repo",
		Scope: "_root", Owner: "platform", GroupID: "consolidation:_root",
		Skills: skills,
		Limits: generator.Limits{MaxProposals: 5, MaxNeighbours: 10},
	})
	if e != nil {
		t.Fatalf("consolidate: %v", e)
	}
	return out
}

func TestTwoStepsInTwoSkillsAreACoincidence(t *testing.T) {
	dir := t.TempDir()
	out := consolidate(t, []generator.Skill{
		plantSkill(t, dir, "toolc-images", "Images", "Pick a model."),
		plantSkill(t, dir, "toolc-video", "Video", "Pick an aspect ratio."),
	})
	if len(out.Candidates) != 0 {
		t.Fatalf("two skills sharing two steps must not become a shared element, got %d", len(out.Candidates))
	}
	if len(out.Abstentions) != 1 || out.Abstentions[0].Reason != "no_shared_procedure" {
		t.Fatalf("expected one no_shared_procedure, got %+v", out.Abstentions)
	}
	if !strings.Contains(out.Abstentions[0].Detail, "3") {
		t.Errorf("the detail must state the source count the short run would need, got %q",
			out.Abstentions[0].Detail)
	}
}

func TestTwoStepsInThreeSkillsAreASharedElement(t *testing.T) {
	dir := t.TempDir()
	out := consolidate(t, []generator.Skill{
		plantSkill(t, dir, "toolc-images", "Images", "Pick a model."),
		plantSkill(t, dir, "toolc-video", "Video", "Pick an aspect ratio."),
		plantSkill(t, dir, "toolc-audio", "Audio", "Pick a voice."),
	})
	if len(out.Candidates) != 1 {
		t.Fatalf("expected exactly one shared element, got %d (%+v)", len(out.Candidates), out.Abstentions)
	}
	c := out.Candidates[0]
	// Every skill that carries the duplicate is a source. Naming two of three
	// would leave the third copy in place after the proposal is approved.
	if len(c.Sources) != 3 {
		t.Errorf("a shared element owes a source to every skill that carries it, got %d: %+v",
			len(c.Sources), c.Sources)
	}
	derived, refines := 0, 0
	for _, r := range c.Relations {
		switch {
		case r.Type == "derived_from" && r.To != "" && r.From == "":
			derived++
		case r.Type == "refines" && r.From != "" && r.To == "":
			refines++
		default:
			t.Errorf("unexpected relation %+v", r)
		}
	}
	if derived != 3 || refines != 3 {
		t.Errorf("expected 3 derived_from and 3 refines, got %d and %d", derived, refines)
	}
	// A shared element that says "install it:" without the command is not a
	// skill an agent can follow. The candidate carries what its SourceRef points
	// at, fenced block included.
	if !strings.Contains(c.Body, "curl -fsSL https://example.test/install.sh | sh") {
		t.Errorf("the shared element dropped the command inside its first step:\n%s", c.Body)
	}
	// Each source keeps its own second section; only the shared run is lifted.
	if strings.Contains(c.Body, "Pick a model.") {
		t.Errorf("a step only one source performs must not enter the shared element:\n%s", c.Body)
	}
	for _, f := range c.Fields {
		if strings.HasPrefix(f.Field, "steps[") {
			if f.Origin != generator.OriginParsed {
				t.Errorf("a lifted step is parsed, not inferred: %+v", f)
			}
			if f.Ref == nil || f.Ref.LineFrom == 0 || f.Ref.SHA256 == "" {
				t.Errorf("a lifted step must point at the lines it came from: %+v", f)
			}
		}
	}
}

func TestAThirdSkillThatContradictsIsNotASource(t *testing.T) {
	dir := t.TempDir()
	lookalike := plantSkill(t, dir, "toolc-legacy", "Legacy", "Pick a model.")
	// Same two steps, but this one forbids what the others require.
	lookalike.Body = strings.Replace(lookalike.Body,
		"2. Run `toolc auth login` and wait.",
		"2. Run `toolc auth login` and wait.\n3. Never run `toolc auth login` and wait.", 1)
	skills := []generator.Skill{
		plantSkill(t, dir, "toolc-images", "Images", "Pick a model."),
		plantSkill(t, dir, "toolc-video", "Video", "Pick an aspect ratio."),
		plantSkill(t, dir, "toolc-audio", "Audio", "Pick a voice."),
		lookalike,
	}
	// The lookalike must not silently join the sources of the shared element.
	out := consolidate(t, skills)
	if len(out.Candidates) != 1 {
		t.Fatalf("expected one shared element, got %d (%+v)", len(out.Candidates), out.Abstentions)
	}
	for _, s := range out.Candidates[0].Sources {
		if strings.Contains(s.Path, "legacy") {
			t.Errorf("a contradicting skill became a source: %+v", out.Candidates[0].Sources)
		}
	}
	found := false
	for _, a := range out.Abstentions {
		if a.Reason == "contradictory_steps" && strings.Contains(strings.Join(a.Skills, " "), "legacy") {
			found = true
			if a.Detail == "" {
				t.Error("an abstention without a detail is not a reason")
			}
		}
	}
	if !found {
		t.Errorf("the contradicting lookalike must be declined out loud, got %+v", out.Abstentions)
	}
}

func TestRoleOfRecognisesTheHeadingsRealSkillsUse(t *testing.T) {
	for _, h := range []string{"Steps", "Step 0 — Bootstrap", "Bootstrap", "Procedure"} {
		if got := generator.RoleOf(h); got != generator.RoleSteps {
			t.Errorf("RoleOf(%q) = %q, want %q", h, got, generator.RoleSteps)
		}
	}
	// The words that were not measured stay out; "verify" still wins over a
	// heading that names both.
	for h, want := range map[string]generator.Role{
		"Bootstrap verification": generator.RoleVerification,
		"Overview":               generator.RolePurpose,
		"Anything else":          generator.RoleOther,
	} {
		if got := generator.RoleOf(h); got != want {
			t.Errorf("RoleOf(%q) = %q, want %q", h, got, want)
		}
	}
}

func TestNeighbourOrderPrefersTheLargestNameFamily(t *testing.T) {
	ids := []string{
		"urn:skill:acme:_root:alpha-one",
		"urn:skill:acme:_root:beta",
		"urn:skill:acme:_root:toolc-audio",
		"urn:skill:acme:_root:toolc-images",
		"urn:skill:acme:_root:toolc-video",
		"urn:skill:acme:_root:alpha-two",
	}
	order := generator.NeighbourOrder(ids)
	got := []string{}
	for _, i := range order {
		got = append(got, generator.FamilyOf(ids[i]))
	}
	want := []string{"toolc", "toolc", "toolc", "alpha", "alpha", "beta"}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("neighbour order %v, want families %v", got, want)
		}
	}
	// A cut of three must keep the whole family that can share something, not
	// the alphabetically first three ids.
	for _, i := range order[:3] {
		if !strings.Contains(ids[i], "toolc-") {
			t.Errorf("the cut kept %q instead of the largest family", ids[i])
		}
	}
}
