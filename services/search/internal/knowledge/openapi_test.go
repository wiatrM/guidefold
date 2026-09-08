package knowledge_test

import (
	"net/http"
	"net/url"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

// Every knowledge response is validated against the published component
// schemas, over a catalog a real import produced.
func TestKnowledgeResponsesMatchTheOpenAPIComponents(t *testing.T) {
	spec := pivottest.LoadContract(t)
	c := newCatalog(t)

	page := c.mustGet(t, "/skills?limit=5")
	spec.Check(t, "SkillPage", page)
	for _, raw := range page["items"].([]any) {
		spec.Check(t, "SkillSummary", raw.(map[string]any))
	}
	filtered := c.mustGet(t, "/skills?scope=atlas.identity&owner=identity-platform")
	spec.Check(t, "SkillPage", filtered)
	for _, echo := range filtered["filters"].(map[string]any) {
		spec.Check(t, "FilterEcho", echo.(map[string]any))
	}

	spec.Check(t, "Facets", c.mustGet(t, "/skills/facets?field=owner"))
	spec.Check(t, "FacetLookup", c.mustGet(t, "/skills/facets/lookup?field=owner&value=nobody"))

	summary := page["items"].([]any)[0].(map[string]any)
	skillID := summary["skill_id"].(string)
	detail := c.mustGet(t, c.skillPath(skillID))
	spec.Check(t, "SkillDetail", detail)
	for _, raw := range detail["revisions"].([]any) {
		spec.Check(t, "RevisionRef", raw.(map[string]any))
	}

	revisionID := summary["revision_id"].(string)
	revision := c.mustGet(t, c.skillPath(skillID)+"/revisions/"+revisionID)
	spec.Check(t, "Revision", revision)
	for _, raw := range revision["references"].([]any) {
		spec.Check(t, "SkillReference", raw.(map[string]any))
	}

	status, judgment, _ := c.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: c.base + c.skillPath(skillID) + "/revisions/" + revisionID + "/feedback",
		Body: map[string]any{"idempotency_key": "spec", "verdict": "mixed"}, Key: "spec"})
	if status != http.StatusOK {
		t.Fatalf("feedback: %d %v", status, judgment)
	}
	spec.Check(t, "Judgment", judgment)
	rated := c.mustGet(t, c.skillPath(skillID)+"/revisions/"+revisionID)
	for _, raw := range rated["feedback"].([]any) {
		spec.Check(t, "FeedbackEntry", raw.(map[string]any))
	}

	spec.Check(t, "MapRepository", c.mustGet(t, "/map/repository"))
	spec.Check(t, "MapRepository", c.mustGet(t, "/map/repository?path=.agents/skills"))
	scopes := c.mustGet(t, "/map/scopes")
	spec.Check(t, "MapScopes", scopes)
	for _, raw := range scopes["scopes"].([]any) {
		spec.Check(t, "ScopeNode", raw.(map[string]any))
	}
	spec.Check(t, "MapScopes", c.mustGet(t, "/map/scopes?scope=atlas.identity"))
	spec.Check(t, "MapLayers", c.mustGet(t, "/map/layers"))
	relations := c.mustGet(t, "/map/relations")
	spec.Check(t, "Relations", relations)
	for _, raw := range relations["items"].([]any) {
		spec.Check(t, "RelationEdge", raw.(map[string]any))
	}
	spec.Check(t, "ModulePage", c.mustGet(t, "/modules/atlas.identity"))
}

// The knowledge module's errors render the one envelope.
func TestKnowledgeErrorEnvelopesMatchTheContract(t *testing.T) {
	spec := pivottest.LoadContract(t)
	c := newCatalog(t)
	summary, _ := c.firstSkill(t)
	skillID := summary["skill_id"].(string)
	stranger := c.h.SignIn(t, "stranger", "stranger@example.test")

	for _, x := range []struct {
		name   string
		client *pivottest.Client
		call   pivottest.Call
		status int
		code   string
	}{
		{"forbidden", stranger, pivottest.Call{Method: http.MethodGet, Path: c.base + "/skills"},
			http.StatusForbidden, "forbidden"},
		{"skill not found", c.owner, pivottest.Call{Method: http.MethodGet,
			Path: c.base + "/skills/" + url.PathEscape("urn:skill:meridian:_root:nope")},
			http.StatusNotFound, "skill_not_found"},
		{"revision not found", c.owner, pivottest.Call{Method: http.MethodGet,
			Path: c.base + c.skillPath(skillID) + "/revisions/" + strings.Repeat("0", 64)},
			http.StatusNotFound, "revision_not_found"},
		{"invalid facet field", c.owner, pivottest.Call{Method: http.MethodGet,
			Path: c.base + "/skills/facets?field=nope"}, http.StatusBadRequest, "invalid_request"},
		{"invalid cursor", c.owner, pivottest.Call{Method: http.MethodGet,
			Path: c.base + "/skills?cursor=nope"}, http.StatusBadRequest, "invalid_cursor"},
		{"unknown module", c.owner, pivottest.Call{Method: http.MethodGet,
			Path: c.base + "/modules/no.such.scope"}, http.StatusNotFound, "not_found"},
		{"invalid verdict", c.owner, pivottest.Call{Method: http.MethodPost,
			Path: c.base + c.skillPath(skillID) + "/revisions/" + summary["revision_id"].(string) + "/feedback",
			Body: map[string]any{"idempotency_key": "bad", "verdict": "nope"}, Key: "bad"},
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
