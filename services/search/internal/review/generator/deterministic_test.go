package generator_test

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

func sha(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}

const runbook = `# Rotate the Kafka consumer credentials

## Purpose

Rotate the credentials a consumer group uses without dropping messages.

## When to use

The credential is older than 90 days, or a rotation was requested.

## When not to use

- Do NOT use this for producer credentials.
- Do NOT use during an incident.

## Steps

1. Pause the consumer group with ` + "`kafkactl pause`" + `.
2. Issue a new credential from the vault.
3. Update the deployment secret and roll the pods.
4. Resume the consumer group.

## Verification

Consumer lag returns to zero within five minutes.
`

func extractionRequest() generator.Request {
	return generator.Request{
		Kind: generator.KindExtraction, OrgID: "org", RepoID: "meridian",
		Scope: "atlas.streams", Owner: "team-streams",
		Limits: generator.Limits{MaxProposals: 5, MaxNeighbours: 10},
		Documents: []generator.Document{{Path: "docs/runbooks/kafka-rotation.md",
			SHA256: sha(runbook), Commit: "abc", Body: runbook}},
	}
}

// Every field a candidate carries either points at the exact source lines it
// came from, or says that a person has to confirm it. There is no third state
// (PRODUCT-PIVOT U2 AC2).
func TestExtractionGivesEveryFieldProvenance(t *testing.T) {
	out, cost, e := (&generator.Deterministic{}).Generate(context.Background(), extractionRequest())
	if e != nil {
		t.Fatal(e)
	}
	if cost.Calls != 0 || cost.USDCertain != 0 || cost.USDUncertain != 0 {
		t.Fatalf("the deterministic recipe must cost nothing, got %+v", cost)
	}
	if len(out.Candidates) != 1 {
		t.Fatalf("expected one candidate, got %d", len(out.Candidates))
	}
	c := out.Candidates[0]
	steps := 0
	for _, f := range c.Fields {
		if f.Ref == nil && !f.NeedsConfirmation {
			t.Errorf("field %q has neither a source reference nor needs_confirmation", f.Field)
		}
		if f.Ref != nil {
			if f.Ref.Path != "docs/runbooks/kafka-rotation.md" || f.Ref.SHA256 != sha(runbook) {
				t.Errorf("field %q points at %s@%s", f.Field, f.Ref.Path, f.Ref.SHA256)
			}
			if f.Ref.LineFrom < 1 || f.Ref.LineTo < f.Ref.LineFrom {
				t.Errorf("field %q has line range %d-%d", f.Field, f.Ref.LineFrom, f.Ref.LineTo)
			}
		}
		if strings.HasPrefix(f.Field, "steps[") {
			steps++
			if f.Ref == nil {
				t.Errorf("%s must name the lines it was read from", f.Field)
			}
		}
	}
	if steps != 4 {
		t.Fatalf("expected four steps with provenance, got %d", steps)
	}
	for _, want := range []string{"purpose", "when_to_use", "when_not_to_use", "verification"} {
		if !hasField(c.Fields, want) {
			t.Errorf("no provenance entry for %s", want)
		}
	}
	if !strings.Contains(c.Body, "## Steps") || !strings.Contains(c.Body, "kafkactl pause") {
		t.Errorf("the candidate body lost the procedure:\n%s", c.Body)
	}
	if !strings.HasPrefix(c.Body, "---\n") {
		t.Errorf("the candidate body has no frontmatter:\n%s", c.Body)
	}
	if c.Scope != "atlas.streams" {
		t.Errorf("candidate scope %q, want atlas.streams", c.Scope)
	}
}

// A document that carries no procedure is not a runbook. Producing an empty
// candidate for it would spend an owner's review time on nothing.
func TestExtractionAbstainsWithoutASimpleProcedure(t *testing.T) {
	req := extractionRequest()
	req.Documents[0].Body = "# Notes\n\nSome prose with no steps at all.\n"
	req.Documents[0].SHA256 = sha(req.Documents[0].Body)
	out, _, e := (&generator.Deterministic{}).Generate(context.Background(), req)
	if e != nil {
		t.Fatal(e)
	}
	if len(out.Candidates) != 0 {
		t.Fatalf("expected no candidate, got %d", len(out.Candidates))
	}
	if len(out.Abstentions) != 1 || out.Abstentions[0].Reason != "no_procedure_found" {
		t.Fatalf("expected one no_procedure_found abstention, got %+v", out.Abstentions)
	}
}

func hasField(fields []generator.Field, name string) bool {
	for _, f := range fields {
		if f.Field == name {
			return true
		}
	}
	return false
}

// Enrichment only ever adds inferred metadata, and never rewrites the body a
// person authored (PRODUCT-PIVOT U2 AC3).
func TestEnrichmentIsInferredAndKeepsTheBody(t *testing.T) {
	body := "---\nname: kafka-retry\n---\n\n# Kafka retry\n\nRetry a consumer with backoff.\n\n" +
		"## Steps\n\n1. Configure the `backoff` policy.\n2. Retry the consumer.\n\n" +
		"## When not to use\n\n- Do NOT use for producers.\n"
	req := generator.Request{Kind: generator.KindEnrichment, Scope: "atlas.streams",
		Limits: generator.Limits{MaxProposals: 5, MaxNeighbours: 10},
		Skills: []generator.Skill{{SkillID: "urn:skill:acme:atlas.streams:kafka-retry",
			Path: "streams/.agents/skills/kafka-retry/SKILL.md", SHA256: sha(body),
			Name: "kafka-retry", Description: "retry", Scope: "atlas.streams", Body: body}}}
	out, _, e := (&generator.Deterministic{}).Generate(context.Background(), req)
	if e != nil {
		t.Fatal(e)
	}
	if len(out.Candidates) != 1 {
		t.Fatalf("expected one candidate, got %d (%+v)", len(out.Candidates), out.Abstentions)
	}
	c := out.Candidates[0]
	if c.TargetSkillID != "urn:skill:acme:atlas.streams:kafka-retry" {
		t.Errorf("enrichment must target the skill it read, got %q", c.TargetSkillID)
	}
	for _, f := range c.Fields {
		if f.Origin != generator.OriginInferred {
			t.Errorf("field %q has origin %q, enrichment infers everything", f.Field, f.Origin)
		}
	}
	if !strings.Contains(c.Body, "# Kafka retry") || !strings.Contains(c.Body, "1. Configure") {
		t.Errorf("enrichment rewrote the authored body:\n%s", c.Body)
	}
	if !hasField(c.Fields, "negative_triggers") {
		t.Error("the 'Do NOT use' list did not become negative triggers")
	}
	if !hasField(c.Fields, "example_queries") {
		t.Error("the steps did not produce example queries")
	}
}

// The consolidation fixture of PRODUCT-PIVOT U2 AC5: one marked shared element
// in two runbooks, and three near-misses that must be declined with a reason.
func TestConsolidation(t *testing.T) {
	shared := []string{
		"Pause the consumer group.",
		"Issue a new credential from the vault.",
		"Roll the deployment pods.",
	}
	build := func(id, scope string, steps []string, extra string) generator.Skill {
		body := "---\nname: " + id + "\n---\n\n# " + id + "\n\n## Steps\n\n"
		for i, s := range steps {
			body += string(rune('1'+i)) + ". " + s + "\n"
		}
		body += extra
		return generator.Skill{SkillID: "urn:skill:acme:" + scope + ":" + id,
			Path: scope + "/.agents/skills/" + id + "/SKILL.md", SHA256: sha(body),
			Name: id, Scope: scope, Body: body}
	}
	run := func(skills ...generator.Skill) generator.Output {
		out, _, e := (&generator.Deterministic{}).Generate(context.Background(),
			generator.Request{Kind: generator.KindConsolidation, Scope: "atlas",
				Limits: generator.Limits{MaxProposals: 5, MaxNeighbours: 10}, Skills: skills})
		if e != nil {
			t.Fatal(e)
		}
		return out
	}

	t.Run("marked_shared_element_consolidates_once", func(t *testing.T) {
		out := run(build("rotate-a", "atlas", shared, ""), build("rotate-b", "atlas", shared, ""))
		if len(out.Candidates) != 1 {
			t.Fatalf("expected exactly one consolidation, got %d (%+v)",
				len(out.Candidates), out.Abstentions)
		}
		derived := []string{}
		for _, r := range out.Candidates[0].Relations {
			if r.Type == "derived_from" {
				derived = append(derived, r.To)
			}
		}
		if len(derived) != 2 {
			t.Fatalf("a shared element needs derived_from to both sources, got %v", derived)
		}
	})

	t.Run("different_versions_abstain", func(t *testing.T) {
		a := []string{"Upgrade the broker to 3.6.", shared[1], shared[2]}
		b := []string{"Upgrade the broker to 2.8.", shared[1], shared[2]}
		out := run(build("rotate-a", "atlas", a, ""), build("rotate-b", "atlas", b, ""))
		if len(out.Candidates) != 0 {
			t.Fatalf("version-different procedures must not consolidate, got %d", len(out.Candidates))
		}
		assertAbstention(t, out, "no_shared_procedure", "version_mismatch")
	})

	t.Run("different_conditions_abstain", func(t *testing.T) {
		a := append([]string{"Drain the node if the queue is idle,"}, shared...)
		b := append([]string{"Drain the node unless a rebalance is running,"}, shared...)
		// The shared run is still three steps long, but the run that *includes*
		// the differing first step is the longest; the recipe must notice.
		out := run(build("rotate-a", "atlas", a, ""), build("rotate-b", "atlas", b, ""))
		if len(out.Candidates) == 1 {
			for _, f := range out.Candidates[0].Fields {
				if strings.Contains(f.Value, "if the queue") || strings.Contains(f.Value, "unless a rebalance") {
					t.Fatalf("a conditional step was consolidated: %q", f.Value)
				}
			}
		}
	})

	t.Run("contradictory_steps_abstain", func(t *testing.T) {
		a := append(append([]string{}, shared...), "\n5. Restart the broker.\n")
		b := append(append([]string{}, shared...), "\n5. Do not restart the broker.\n")
		out := run(build("rotate-a", "atlas", a, ""), build("rotate-b", "atlas", b, ""))
		if len(out.Candidates) != 0 {
			t.Fatalf("contradictory procedures must not consolidate, got %d", len(out.Candidates))
		}
		assertAbstention(t, out, "contradictory_steps")
	})

	t.Run("one_procedure_abstains", func(t *testing.T) {
		out := run(build("rotate-a", "atlas", shared, ""))
		if len(out.Candidates) != 0 {
			t.Fatalf("one procedure cannot be a shared element, got %d", len(out.Candidates))
		}
		assertAbstention(t, out, "too_few_procedures")
	})
}

func assertAbstention(t *testing.T, out generator.Output, reasons ...string) {
	t.Helper()
	if len(out.Abstentions) == 0 {
		t.Fatal("declining to consolidate must state a reason, got none")
	}
	for _, want := range reasons {
		for _, a := range out.Abstentions {
			if a.Reason == want {
				if a.Detail == "" {
					t.Errorf("abstention %q carries no detail", want)
				}
				return
			}
		}
	}
	t.Fatalf("expected one of %v, got %+v", reasons, out.Abstentions)
}

// The cache key is what makes "a rejected proposal is never regenerated" true:
// the same inputs under the same recipe must produce the same key, and any
// change to inputs, recipe, model or candidate must change it.
func TestCacheKeyIsStableAndSensitive(t *testing.T) {
	recipe := generator.Recipe{Generator: "deterministic", Version: "det-1"}
	base := generator.CacheKey("org", "extraction", []string{"b", "a"}, recipe, "x")
	if base != generator.CacheKey("org", "extraction", []string{"a", "b"}, recipe, "x") {
		t.Error("input order must not change the key")
	}
	for name, got := range map[string]string{
		"org":      generator.CacheKey("other", "extraction", []string{"a", "b"}, recipe, "x"),
		"kind":     generator.CacheKey("org", "enrichment", []string{"a", "b"}, recipe, "x"),
		"inputs":   generator.CacheKey("org", "extraction", []string{"a", "c"}, recipe, "x"),
		"identity": generator.CacheKey("org", "extraction", []string{"a", "b"}, recipe, "y"),
		"recipe": generator.CacheKey("org", "extraction", []string{"a", "b"},
			generator.Recipe{Version: "det-2"}, "x"),
		"model": generator.CacheKey("org", "extraction", []string{"a", "b"},
			generator.Recipe{Version: "det-1", Model: "m"}, "x"),
	} {
		if got == base {
			t.Errorf("changing the %s did not change the cache key", name)
		}
	}
}

// `none` is a configuration, not a failure: the job is skipped and the import
// keeps whatever the parse already produced (U2.7).
func TestNoneGeneratorReportsNotConfigured(t *testing.T) {
	g, recipe, e := generator.Select(func(string) string { return "none" })
	if e != nil {
		t.Fatal(e)
	}
	if recipe.Generator != generator.NameNone {
		t.Fatalf("recipe %+v", recipe)
	}
	if _, _, e := g.Generate(context.Background(), generator.Request{}); e != generator.ErrNotConfigured {
		t.Fatalf("expected ErrNotConfigured, got %v", e)
	}
}

func TestSelectRefusesAnUnknownGenerator(t *testing.T) {
	if _, _, e := generator.Select(func(string) string { return "gpt-guess" }); e == nil {
		t.Fatal("an unknown generator name must be a configuration error")
	}
}
