package review_test

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// P08 at the API: the pyramid, the one-shot run, and what shows on the maps.
//
// The bodies come from the planted pair in the Meridian fixture
// (examples/monorepo/docs/runbooks/README.md, "Meridian fixture, planted for
// U2 AC5"). They are mounted here as skills in two sibling scopes, which is the
// state an approved extraction leaves behind, so this file measures the
// consolidation half without also re-measuring extraction.

// p08Env is a repository with the planted procedures living in two sibling
// scopes, `atlas.geo` and `atlas.graph`, and a lookalike beside one of them.
type p08Env struct {
	h        *pivottest.Harness
	owner    *pivottest.Client
	orgID    string
	base     string
	importID string
}

func p08Setup(t *testing.T) *p08Env {
	t.Helper()
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	orgID := owner.CreateOrg(t, "pyramid")
	owner.CreateRepo(t, orgID, "meridian", "https://git.example.test/pyramid/meridian")

	tree := pivottest.Monorepo(t)
	mount := func(scope, dir, source, owner string) {
		body := p08Planted(t, source)
		path := filepath.Join(tree, filepath.FromSlash(scope+"/.agents/skills/"+dir+"/SKILL.md"))
		if e := os.MkdirAll(filepath.Dir(path), 0o755); e != nil {
			t.Fatal(e)
		}
		frontmatter := "---\nname: " + dir + "\ndescription: \"[meridian] Planted " + dir +
			" procedure.\"\nmetadata:\n  owner: " + owner +
			"\n  status: active\n  kind: engineering\n  layer: team\n---\n\n"
		if e := os.WriteFile(path, []byte(frontmatter+body), 0o644); e != nil {
			t.Fatal(e)
		}
	}
	mount("platforms/atlas/geo", "rotate-tile-cache",
		"platforms/atlas/geo/docs/runbooks/rotate-tile-cache.md", "geo-team")
	mount("platforms/atlas/graph", "rotate-link-cache",
		"platforms/atlas/graph/docs/runbooks/rotate-link-cache.md", "graph-team")
	mount("platforms/atlas/geo", "rotate-legacy-tile-cache",
		"platforms/atlas/geo/docs/runbooks/rotate-legacy-tile-cache.md", "geo-team")

	manifest := pivottest.Manifest(t, tree, "pyramid", "meridian", true)
	importID := pivottest.Push(t, owner, orgID, "meridian", tree, manifest, "p08-import")
	if n := h.RunParse(t, pivottest.Scratch(t, "p08-parse")); n == 0 {
		t.Fatal("the parse worker ran nothing")
	}
	return &p08Env{h: h, owner: owner, orgID: orgID,
		base: pivottest.RepoBase(orgID, "meridian"), importID: importID}
}

// p08Planted reads one committed fixture document and strips its title line, so
// the skill body starts at the first section the recipe reads.
func p08Planted(t *testing.T, rel string) string {
	t.Helper()
	root := pivottest.Root(t)
	raw, e := os.ReadFile(filepath.Join(root, "examples", "monorepo", filepath.FromSlash(rel)))
	if e != nil {
		t.Fatalf("read the planted fixture %s: %v", rel, e)
	}
	return string(raw)
}

func p08Proposals(t *testing.T, e *p08Env, kind string) []map[string]any {
	t.Helper()
	path := e.base + "/proposals"
	if kind != "" {
		path += "?kind=" + kind
	}
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: path})
	if status != 200 {
		t.Fatalf("list proposals: %d %v", status, body)
	}
	items, _ := body["items"].([]any)
	out := []map[string]any{}
	for _, raw := range items {
		v, _ := raw.(map[string]any)
		out = append(out, v)
	}
	return out
}

func p08Detail(t *testing.T, e *p08Env, id string) map[string]any {
	t.Helper()
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/proposals/" + id})
	if status != 200 {
		t.Fatalf("proposal %s: %d %v", id, status, body)
	}
	return body
}

// p08OneShot runs the whole import in one request, the way `guidefold extract`
// does, and returns the plan the server answered with.
func p08OneShot(t *testing.T, e *p08Env) map[string]any {
	t.Helper()
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/imports/" + e.importID + "/proposals:generate",
		Body: map[string]any{"idempotency_key": "p08-one-shot", "profile": "one_shot",
			"kinds": []string{generator.KindExtraction, generator.KindEnrichment,
				generator.KindConsolidation}},
		Key: "p08-one-shot"})
	if status != 200 {
		t.Fatalf("one-shot generate: %d %v", status, body)
	}
	e.h.RunGenerate(t, &generator.Deterministic{},
		generator.Recipe{Generator: generator.NameDeterministic, Version: generator.RecipeVersion})
	return body
}

// U2.7 / P08: the one-shot plan covers every group and still shows every limit
// before a single call is made.
func TestOneShotPlanCoversEveryGroupAndShowsItsCost(t *testing.T) {
	e := p08Setup(t)
	status, bounded, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/imports/" + e.importID + "/plan"})
	if status != 200 {
		t.Fatalf("default plan: %d %v", status, bounded)
	}
	status, full, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/imports/" + e.importID + "/plan?profile=one_shot"})
	if status != 200 {
		t.Fatalf("one-shot plan: %d %v", status, full)
	}
	if full["profile"] != "one_shot" || bounded["profile"] != "default" {
		t.Errorf("the plan must name the profile it ran under: %v / %v",
			bounded["profile"], full["profile"])
	}
	boundedGroups, _ := bounded["groups"].([]any)
	fullGroups, _ := full["groups"].([]any)
	if len(fullGroups) <= len(boundedGroups) {
		t.Fatalf("one_shot planned %d groups, the default planned %d: nothing was covered",
			len(fullGroups), len(boundedGroups))
	}
	// Nothing is left behind unnamed.
	skipped, _ := full["groups_skipped"].(map[string]any)
	for kind, n := range skipped {
		if v, _ := n.(float64); v != 0 {
			t.Errorf("one_shot still skipped %v %s groups", v, kind)
		}
	}
	limits, _ := full["limits"].(map[string]any)
	for _, key := range []string{"max_files", "max_bytes", "max_tokens", "max_groups",
		"max_proposals_per_group", "max_neighbours", "max_calls", "max_usd"} {
		if _, ok := limits[key]; !ok {
			t.Errorf("the one-shot plan hides the limit %s: %v", key, limits)
		}
	}
	// `max_groups` is the number of groups that will run, not a ceiling nobody
	// can reason about.
	perKind := map[string]int{}
	most := 0
	for _, raw := range fullGroups {
		g, _ := raw.(map[string]any)
		perKind[g["kind"].(string)]++
		if perKind[g["kind"].(string)] > most {
			most = perKind[g["kind"].(string)]
		}
	}
	if int(limits["max_groups"].(float64)) != most {
		t.Errorf("max_groups is %v, the largest kind has %d groups", limits["max_groups"], most)
	}
	// The money ceilings did not move.
	boundedLimits, _ := bounded["limits"].(map[string]any)
	for _, key := range []string{"max_usd", "max_calls", "max_tokens", "max_neighbours"} {
		if limits[key] != boundedLimits[key] {
			t.Errorf("one_shot moved %s: %v -> %v", key, boundedLimits[key], limits[key])
		}
	}
	if _, ok := full["estimated_usd_max"]; !ok {
		t.Error("the plan must show the cost before start")
	}
}

func TestOneShotRefusesAnUnknownProfile(t *testing.T) {
	e := p08Setup(t)
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/imports/" + e.importID + "/plan?profile=everything"})
	if status != 400 {
		t.Fatalf("an unknown profile must be refused, got %d %v", status, body)
	}
}

// P08: one shared element in the parent scope, both sources named in both
// directions, and the lookalike declined with a reason.
func TestOneShotLiftsTheSharedProcedureIntoTheParentScope(t *testing.T) {
	e := p08Setup(t)
	p08OneShot(t, e)

	shared := []map[string]any{}
	for _, p := range p08Proposals(t, e, generator.KindConsolidation) {
		detail := p08Detail(t, e, p["proposal_id"].(string))
		relations, _ := detail["relations"].([]any)
		derived, refines := []string{}, []string{}
		for _, raw := range relations {
			r, _ := raw.(map[string]any)
			switch r["type"] {
			case "derived_from":
				derived = append(derived, str(r["to"]))
			case "refines":
				if from := str(r["from"]); from != "" {
					refines = append(refines, from)
				}
			}
		}
		joined := strings.Join(derived, " ")
		if !strings.Contains(joined, "rotate-tile-cache") ||
			!strings.Contains(joined, "rotate-link-cache") {
			continue
		}
		if strings.Contains(joined, "legacy") {
			t.Errorf("the lookalike was consolidated: %v", derived)
		}
		if len(derived) != 2 {
			t.Errorf("a shared element names both sources, got %v", derived)
		}
		if len(refines) != 2 {
			t.Errorf("each source must be proposed as refining the element, got %v", refines)
		}
		if detail["scope"] != "atlas" {
			t.Errorf("the shared element of two siblings belongs to atlas, got %v", detail["scope"])
		}
		if detail["owner"] != "atlas-platform" {
			t.Errorf("a raised scope carries the target scope's owner, got %v", detail["owner"])
		}
		shared = append(shared, detail)
	}
	if len(shared) != 1 {
		t.Fatalf("expected exactly one consolidation of the planted pair, got %d", len(shared))
	}
	// The layer is inferred, not asserted, and it says so.
	layer := ""
	for _, raw := range shared[0]["provenance"].([]any) {
		f, _ := raw.(map[string]any)
		if f["field"] == generator.FieldKnowledgeLayer {
			layer = "seen"
			if f["origin"] != generator.OriginInferred {
				t.Errorf("a generated layer is inferred, got %v", f["origin"])
			}
			if f["source_ref"] == nil && f["needs_confirmation"] != true {
				t.Error("an inferred layer needs a source or an explicit needs_confirmation")
			}
		}
	}
	if layer == "" {
		t.Error("the shared element carries no knowledge_layer field")
	}
	candidate, _ := shared[0]["candidate"].(map[string]any)
	if body, _ := candidate["body"].(string); !strings.Contains(body, "knowledge_layer: abstract") {
		t.Errorf("an element consolidated from two scopes is abstract:\n%s", body)
	}
}

func TestOneShotRecordsWhyTheLookalikeWasNotMerged(t *testing.T) {
	e := p08Setup(t)
	p08OneShot(t, e)
	reasons := map[string]int{}
	for _, j := range e.h.Jobs(t, review.KindGenerate) {
		var result map[string]any
		_ = json.Unmarshal(j.Result, &result)
		list, _ := result["abstentions"].([]any)
		for _, raw := range list {
			a, _ := raw.(map[string]any)
			skills := []string{}
			for _, s := range a["skills"].([]any) {
				skills = append(skills, str(s))
			}
			if strings.Contains(strings.Join(skills, " "), "legacy") {
				reasons[str(a["reason"])]++
			}
		}
	}
	if reasons["contradictory_steps"] == 0 {
		t.Fatalf("the lookalike must be declined with a stated reason, got %v", reasons)
	}
}

// U2.3 at one-shot scale: a worker that dies mid-run resumes at the next group
// and the finished groups produce nothing new.
func TestOneShotResumesFromItsCheckpointWithoutDuplicating(t *testing.T) {
	e := p08Setup(t)
	p08OneShot(t, e)
	before := len(p08Proposals(t, e, ""))
	if before == 0 {
		t.Fatal("the one-shot run produced nothing to resume from")
	}
	checkpointed := 0
	for _, j := range e.h.Jobs(t, review.KindGenerate) {
		var cp map[string]any
		if len(j.Checkpoint) > 0 {
			_ = json.Unmarshal(j.Checkpoint, &cp)
		}
		if n, _ := cp["groups_done"].(float64); n > 0 {
			checkpointed++
		}
	}
	if checkpointed == 0 {
		t.Fatal("no job recorded a per-group checkpoint")
	}
	// Requeue every generate job with its checkpoint intact: the restart must
	// resume, not restart, and must not write a second copy of anything.
	if _, err := e.h.Pool.Exec(t.Context(), `UPDATE gfm.jobs
 SET state='queued',worker_id=NULL,lease_until=NULL,finished_at=NULL,result=NULL
 WHERE org_id=$1::uuid AND kind=$2`, e.orgID, review.KindGenerate); err != nil {
		t.Fatal(err)
	}
	e.h.RunGenerate(t, &generator.Deterministic{},
		generator.Recipe{Generator: generator.NameDeterministic, Version: generator.RecipeVersion})
	if after := len(p08Proposals(t, e, "")); after != before {
		t.Fatalf("a resumed run produced %d proposals, was %d", after, before)
	}
}

// P08 (c): the maps show what the run inferred, once an owner has approved it.
func TestApprovedLayersAndRelationsShowOnTheMaps(t *testing.T) {
	e := p08Setup(t)
	p08OneShot(t, e)

	var id string
	for _, p := range p08Proposals(t, e, generator.KindConsolidation) {
		detail := p08Detail(t, e, p["proposal_id"].(string))
		if detail["scope"] == "atlas" {
			id = p["proposal_id"].(string)
			break
		}
	}
	if id == "" {
		t.Fatal("no consolidation to approve")
	}
	detail := p08Detail(t, e, id)
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "p08-approve", "decision": "approve",
			"reason":            "the two runbooks perform the same four steps",
			"expected_revision": detail["expected_revision"]}, Key: "p08-approve"})
	if status != 200 {
		t.Fatalf("approve the shared element: %d %v", status, body)
	}

	status, layers, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/map/layers"})
	if status != 200 {
		t.Fatalf("map/layers: %d %v", status, layers)
	}
	counts := map[string]float64{}
	for _, raw := range layers["layers"].([]any) {
		row, _ := raw.(map[string]any)
		counts[str(row["layer"])] = row["count"].(float64)
	}
	if counts[generator.LayerAbstract] < 1 {
		t.Errorf("the approved abstraction does not show on the layer map: %v", counts)
	}
	if counts["unclassified"] == 0 {
		t.Error("skills nobody classified must still be counted as unclassified")
	}

	status, relations, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/map/relations?type=refines"})
	if status != 200 {
		t.Fatalf("map/relations: %d %v", status, relations)
	}
	up := 0
	for _, raw := range relations["items"].([]any) {
		edge, _ := raw.(map[string]any)
		if strings.Contains(str(edge["to"]), "shared") &&
			(strings.Contains(str(edge["from"]), "rotate-tile-cache") ||
				strings.Contains(str(edge["from"]), "rotate-link-cache")) {
			up++
		}
	}
	if up != 2 {
		t.Errorf("expected both sources to refine the shared element on the map, got %d", up)
	}
	status, derived, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/map/relations?type=derived_from"})
	if status != 200 {
		t.Fatalf("map/relations derived_from: %d %v", status, derived)
	}
	down := 0
	for _, raw := range derived["items"].([]any) {
		edge, _ := raw.(map[string]any)
		if strings.Contains(str(edge["from"]), "shared") {
			down++
		}
	}
	if down != 2 {
		t.Errorf("expected the shared element to name both sources, got %d", down)
	}
}

func str(v any) string {
	s, _ := v.(string)
	return s
}
