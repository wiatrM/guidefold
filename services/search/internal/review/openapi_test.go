package review_test

import (
	"net/http"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// Every review response is validated against the published component schemas,
// over proposals a real generation run produced. The point is not that the
// document parses: it is that the document and the running server agree, so a
// response that quietly grows or loses a field fails here rather than in a
// client.
func TestReviewResponsesMatchTheOpenAPIComponents(t *testing.T) {
	spec := pivottest.LoadContract(t)
	e := setup(t)

	status, plan, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/imports/" + e.importID + "/plan"})
	if status != 200 {
		t.Fatalf("plan: %d %v", status, plan)
	}
	spec.Check(t, "ImportPlan", plan)
	for _, raw := range plan["groups"].([]any) {
		spec.Check(t, "GenerationGroup", raw.(map[string]any))
	}
	spec.Check(t, "GenerationLimits", plan["limits"].(map[string]any))
	spec.Check(t, "GeneratorRecipe", plan["generator"].(map[string]any))

	status, accepted, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/imports/" + e.importID + "/proposals:generate",
		Body: map[string]any{"idempotency_key": "spec-gen"}, Key: "spec-gen"})
	if status != 200 {
		t.Fatalf("generate: %d %v", status, accepted)
	}
	spec.Check(t, "GenerateAccepted", accepted)
	e.h.RunGenerate(t, &generator.Deterministic{},
		generator.Recipe{Generator: generator.NameDeterministic, Version: generator.RecipeVersion})

	status, page, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/proposals?limit=50"})
	if status != 200 {
		t.Fatalf("proposals: %d %v", status, page)
	}
	spec.Check(t, "ProposalList", page)
	items := page["items"].([]any)
	if len(items) == 0 {
		t.Fatal("no proposals to validate")
	}
	for _, raw := range items {
		spec.Check(t, "ProposalSummary", raw.(map[string]any))
	}

	id := pick(t, e, generator.KindExtraction, "rotate-an-auth-sdk-signing-key")
	detail := get(t, e, id)
	spec.Check(t, "ProposalDetail", detail)
	for _, raw := range detail["provenance"].([]any) {
		spec.Check(t, "ProvenanceEntry", raw.(map[string]any))
	}

	status, decision, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/decision",
		Body: map[string]any{"idempotency_key": "spec-d", "decision": "approve",
			"reason": "matches the runbook", "expected_revision": detail["expected_revision"]},
		Key: "spec-d"})
	if status != 200 {
		t.Fatalf("decision: %d %v", status, decision)
	}
	spec.Check(t, "DecisionResult", decision)

	status, export, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/proposals/" + id + "/export",
		Body: map[string]any{"idempotency_key": "spec-x"}, Key: "spec-x"})
	if status != 200 {
		t.Fatalf("export: %d %v", status, export)
	}
	spec.Check(t, "Export", export)
	exportID := export["export_id"].(string)
	status, stored, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/exports/" + exportID})
	if status != 200 {
		t.Fatalf("export read: %d %v", status, stored)
	}
	spec.Check(t, "Export", stored)

	status, publication, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/proposals/" + id + "/publication"})
	if status != 200 {
		t.Fatalf("publication: %d %v", status, publication)
	}
	spec.Check(t, "Publication", publication)

	status, snapshots, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/snapshots"})
	if status != 200 {
		t.Fatalf("snapshots: %d %v", status, snapshots)
	}
	spec.Check(t, "SnapshotList", snapshots)

	status, queued, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/publish",
		Body: map[string]any{"idempotency_key": "spec-p", "import_id": e.importID}, Key: "spec-p"})
	if status != 200 {
		t.Fatalf("publish: %d %v", status, queued)
	}
	spec.Check(t, "PublishAccepted", queued)
	status, job, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/publications/" + queued["job_id"].(string)})
	if status != 200 {
		t.Fatalf("publications/{job_id}: %d %v", status, job)
	}
	spec.Check(t, "PublicationJob", job)

	// Every error this module can answer with is the one envelope, and every
	// code is one the contract lists.
	stranger := e.h.SignIn(t, "spec-stranger", "spec-stranger@example.test")
	for _, x := range []struct {
		name   string
		client *pivottest.Client
		call   pivottest.Call
		status int
		code   string
	}{
		{"forbidden", stranger, pivottest.Call{Method: http.MethodGet, Path: e.base + "/proposals"},
			http.StatusForbidden, "forbidden"},
		{"proposal not found", e.owner, pivottest.Call{Method: http.MethodGet,
			Path: e.base + "/proposals/00000000-0000-4000-8000-000000000000"},
			http.StatusNotFound, "proposal_not_found"},
		{"export not found", e.owner, pivottest.Call{Method: http.MethodGet,
			Path: e.base + "/exports/00000000-0000-4000-8000-000000000000"},
			http.StatusNotFound, "export_not_found"},
		{"import not found", e.owner, pivottest.Call{Method: http.MethodGet,
			Path: e.base + "/imports/00000000-0000-4000-8000-000000000000/plan"},
			http.StatusNotFound, "import_not_found"},
		{"snapshot not found", e.owner, pivottest.Call{Method: http.MethodPost,
			Path: e.base + "/snapshots/repository:nope/activate",
			Body: map[string]any{"idempotency_key": "spec-a", "reason": "rolling back"},
			Key:  "spec-a"}, http.StatusNotFound, "not_found"},
		{"decision on an exported proposal", e.owner, pivottest.Call{Method: http.MethodPost,
			Path: e.base + "/proposals/" + id + "/decision",
			Body: map[string]any{"idempotency_key": "spec-d2", "decision": "reject",
				"reason": "changed my mind"}, Key: "spec-d2"},
			http.StatusConflict, "proposal_state_invalid"},
		{"invalid filter", e.owner, pivottest.Call{Method: http.MethodGet,
			Path: e.base + "/proposals?state=nope"}, http.StatusBadRequest, "invalid_filter_value"},
		{"invalid cursor", e.owner, pivottest.Call{Method: http.MethodGet,
			Path: e.base + "/proposals?cursor=nope"}, http.StatusBadRequest, "invalid_cursor"},
		{"activate without a reason", e.owner, pivottest.Call{Method: http.MethodPost,
			Path: e.base + "/snapshots/repository:nope/activate",
			Body: map[string]any{"idempotency_key": "spec-a2"}, Key: "spec-a2"},
			http.StatusBadRequest, "invalid_request"},
	} {
		t.Run(x.name, func(t *testing.T) {
			status, body, header := x.client.Call(t, x.call)
			if status != x.status || body["error"] != x.code {
				t.Fatalf("%d %v", status, body)
			}
			if header.Get("X-Request-Id") == "" || body["request_id"] != header.Get("X-Request-Id") {
				t.Fatalf("request id: header %q body %v", header.Get("X-Request-Id"), body["request_id"])
			}
			spec.Check(t, "Error", body)
		})
	}
}

// The document and the router describe the same surface: every review route the
// server registers is published, and every published one is registered.
func TestReviewRoutesArePublished(t *testing.T) {
	spec := pivottest.LoadContract(t)
	h := pivottest.New(t)
	paths, _ := spec.Document["paths"].(map[string]any)
	if paths == nil {
		t.Fatal("the OpenAPI document has no paths")
	}
	published := map[string]bool{}
	for path, raw := range paths {
		entry, _ := raw.(map[string]any)
		if entry["x-status"] == "planned" {
			continue
		}
		for method := range entry {
			switch method {
			case "get", "post", "put", "patch", "delete":
				published[strings.ToUpper(method)+" "+path] = true
			}
		}
	}
	review := func(route string) bool {
		for _, marker := range []string{"/proposals", "/exports/", "/publish", "/snapshots",
			"/publications/", "/plan"} {
			if strings.Contains(route, marker) {
				return true
			}
		}
		return false
	}
	for _, route := range h.Router.Routes() {
		if !review(route) {
			continue
		}
		if !published[route] {
			t.Errorf("the server serves %s, the OpenAPI document does not publish it", route)
		}
	}
	for route := range published {
		if !review(route) {
			continue
		}
		found := false
		for _, registered := range h.Router.Routes() {
			if registered == route {
				found = true
			}
		}
		if !found {
			t.Errorf("the OpenAPI document publishes %s, the server does not serve it", route)
		}
	}
}
