package identity_test

import (
	"bytes"
	"encoding/json"
	"net/http"
	"sort"
	"strings"
	"testing"

	"github.com/santhosh-tekuri/jsonschema/v6"
	"gopkg.in/yaml.v3"
)

// contract compiles the component schemas of the published OpenAPI document and
// validates real handler responses against them. The point is not that the file
// parses: it is that the document and the running server agree.
type contract struct {
	compiler *jsonschema.Compiler
	document map[string]any
}

const specURI = "https://guidefold.example/openapi/management-v1.yaml"

func loadContract(t *testing.T) *contract {
	t.Helper()
	var parsed any
	if e := yaml.Unmarshal(spec(t), &parsed); e != nil {
		t.Fatalf("the OpenAPI document is not valid YAML: %v", e)
	}
	// Round-trip through JSON so the schema compiler sees the same value types a
	// decoded response has.
	raw, e := json.Marshal(parsed)
	if e != nil {
		t.Fatal(e)
	}
	document, e := jsonschema.UnmarshalJSON(bytes.NewReader(raw))
	if e != nil {
		t.Fatal(e)
	}
	c := jsonschema.NewCompiler()
	if e = c.AddResource(specURI, document); e != nil {
		t.Fatal(e)
	}
	root, _ := document.(map[string]any)
	if root == nil {
		t.Fatal("the OpenAPI document is not an object")
	}
	if root["openapi"] != "3.1.0" {
		t.Fatalf("openapi version %v", root["openapi"])
	}
	return &contract{compiler: c, document: root}
}

func (c *contract) check(t *testing.T, schema string, value map[string]any) {
	t.Helper()
	compiled, e := c.compiler.Compile(specURI + "#/components/schemas/" + schema)
	if e != nil {
		t.Fatalf("compile %s: %v", schema, e)
	}
	// Re-decode so numbers and nulls look exactly as they arrived over HTTP.
	raw, e := json.Marshal(value)
	if e != nil {
		t.Fatal(e)
	}
	decoded, e := jsonschema.UnmarshalJSON(bytes.NewReader(raw))
	if e != nil {
		t.Fatal(e)
	}
	if e = compiled.Validate(decoded); e != nil {
		t.Errorf("%s does not match the contract: %v\npayload: %s", schema, e, raw)
	}
}

func TestResponsesMatchTheOpenAPIComponents(t *testing.T) {
	spec := loadContract(t)
	h := newHarness(t)
	owner := h.signIn(t, "google", "spec-owner", "spec@example.test", "Spec")

	status, providers, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/auth/providers"})
	if status != 200 {
		t.Fatal(status)
	}
	spec.check(t, "Providers", providers)

	spec.check(t, "Me", owner.refresh(t))

	status, created, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "Spec Org", "slug": "spec-org"}, key: "spec-1"})
	if status != 201 {
		t.Fatalf("create org: %d %v", status, created)
	}
	spec.check(t, "OrgCreated", created)

	status, list, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs"})
	if status != 200 {
		t.Fatal(status)
	}
	spec.check(t, "OrgList", list)

	status, detail, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/spec-org"})
	if status != 200 {
		t.Fatal(status)
	}
	spec.check(t, "OrgDetail", detail)

	status, members, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/spec-org/members"})
	if status != 200 {
		t.Fatal(status)
	}
	spec.check(t, "MemberList", members)

	status, invitation, _ := owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/spec-org/invitations",
		body: map[string]any{"email": "guest@example.test", "role": "member"}, key: "spec-2"})
	if status != 201 {
		t.Fatalf("invite: %d %v", status, invitation)
	}
	spec.check(t, "Invitation", invitation)

	guest := h.signIn(t, "github", "spec-guest", "guest@example.test", "Guest")
	status, accepted, _ := guest.call(t, call{method: http.MethodPost,
		path: mustURL(t, invitation["accept_url"].(string)).Path, key: "spec-accept"})
	if status != 200 {
		t.Fatalf("accept: %d %v", status, accepted)
	}
	spec.check(t, "InvitationAccepted", accepted)

	status, role, _ := owner.call(t, call{method: http.MethodPatch,
		path: "/api/v1/orgs/spec-org/members/" + guest.userID(t),
		body: map[string]any{"role": "owner"}, key: "spec-role"})
	if status != 200 {
		t.Fatalf("role: %d %v", status, role)
	}
	spec.check(t, "RoleChanged", role)

	status, removed, _ := owner.call(t, call{method: http.MethodDelete,
		path: "/api/v1/orgs/spec-org/members/" + guest.userID(t), key: "spec-remove"})
	if status != 204 || len(removed) != 0 {
		t.Fatalf("remove: %d %v", status, removed)
	}

	status, installation, _ := owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/spec-org/installations", key: "spec-3",
		body: map[string]any{"name": "Adapter", "repo_id": "mono",
			"scopes": []string{"search", "events"}, "harness": "copilot"}})
	if status != 201 {
		t.Fatalf("installation: %d %v", status, installation)
	}
	spec.check(t, "InstallationCreated", installation)

	status, installations, _ := owner.call(t, call{method: http.MethodGet,
		path: "/api/v1/orgs/spec-org/installations"})
	if status != 200 {
		t.Fatal(status)
	}
	spec.check(t, "InstallationList", installations)

	status, revoked, _ := owner.call(t, call{method: http.MethodDelete,
		path: "/api/v1/orgs/spec-org/installations/" + installation["installation_id"].(string),
		key:  "spec-4"})
	if status != 204 || len(revoked) != 0 {
		t.Fatalf("revoke: %d %v", status, revoked)
	}

	status, audit, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/spec-org/audit"})
	if status != 200 {
		t.Fatal(status)
	}
	spec.check(t, "AuditPage", audit)

	status, out, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/auth/logout"})
	if status != 204 || len(out) != 0 {
		t.Fatalf("logout: %d %v", status, out)
	}
}

func TestDeviceFlowResponsesMatchTheContract(t *testing.T) {
	spec := loadContract(t)
	h := newHarness(t)
	cli := h.newClient()
	status, start, _ := cli.call(t, call{method: http.MethodPost, path: "/api/v1/auth/device"})
	if status != 200 {
		t.Fatal(status)
	}
	spec.check(t, "DeviceAuthorization", start)

	person := h.signIn(t, "google", "spec-device", "device@example.test", "D")
	status, decision, _ := person.call(t, call{method: http.MethodPost,
		path: "/api/v1/auth/device/approve", body: map[string]any{"user_code": start["user_code"]}})
	if status != 200 {
		t.Fatalf("approve: %d %v", status, decision)
	}
	spec.check(t, "DeviceDecision", decision)

	status, token, _ := cli.call(t, call{method: http.MethodPost, path: "/api/v1/auth/device/token",
		body: map[string]any{"device_code": start["device_code"]}})
	if status != 200 {
		t.Fatalf("token: %d %v", status, token)
	}
	spec.check(t, "DeviceToken", token)

	status, linkStarted, _ := person.call(t, call{method: http.MethodPost,
		path: "/api/v1/me/identities/link/start", body: map[string]any{"provider": "github"}})
	if status != 200 {
		t.Fatal(status)
	}
	spec.check(t, "LinkStarted", linkStarted)
}

func TestErrorEnvelopesMatchTheContract(t *testing.T) {
	spec := loadContract(t)
	h := newHarness(t)
	anonymous := h.newClient()
	owner := h.signIn(t, "google", "spec-err", "err@example.test", "E")
	owner.createOrg(t, "err-org", "Err")

	for _, x := range []struct {
		name   string
		client *client
		req    call
		status int
		code   string
	}{
		{"unauthenticated", anonymous, call{method: http.MethodGet, path: "/api/v1/me"}, 401, "unauthenticated"},
		{"not found", owner, call{method: http.MethodGet, path: "/api/v1/nope"}, 404, "not_found"},
		{"forbidden", h.signIn(t, "github", "spec-out", "out@example.test", "O"),
			call{method: http.MethodGet, path: "/api/v1/orgs/err-org"}, 403, "forbidden"},
		{"csrf", owner, call{method: http.MethodPost, path: "/api/v1/orgs",
			body: map[string]any{"name": "X", "slug": "x-org"}, key: "k", csrf: "-"}, 403, "csrf_token_mismatch"},
		{"idempotency", owner, call{method: http.MethodPost, path: "/api/v1/orgs",
			body: map[string]any{"name": "X", "slug": "x-org"}}, 400, "idempotency_key_required"},
		{"validation", owner, call{method: http.MethodPost, path: "/api/v1/orgs",
			body: map[string]any{"name": "X", "slug": "NOT A SLUG"}, key: "k2"}, 400, "invalid_slug"},
		{"device", anonymous, call{method: http.MethodPost, path: "/api/v1/auth/device/token",
			body: map[string]any{"device_code": "unknown"}}, 400, "expired_token"},
	} {
		t.Run(x.name, func(t *testing.T) {
			status, body, header := x.client.call(t, x.req)
			if status != x.status || body["error"] != x.code {
				t.Fatalf("%d %v", status, body)
			}
			if header.Get("X-Request-Id") == "" || body["request_id"] != header.Get("X-Request-Id") {
				t.Fatalf("request id: header %q body %v", header.Get("X-Request-Id"), body["request_id"])
			}
			if header.Get("Cache-Control") != "no-store" {
				t.Fatalf("Cache-Control %q", header.Get("Cache-Control"))
			}
			spec.check(t, "Error", body)
		})
	}
}

// Every implemented route must be documented, and every documented path that is
// not marked planned must be implemented.
func TestDocumentAndServerDescribeTheSameSurface(t *testing.T) {
	spec := loadContract(t)
	h := newHarness(t)

	documented := map[string]bool{}
	planned := map[string]bool{}
	paths, _ := spec.document["paths"].(map[string]any)
	if len(paths) == 0 {
		t.Fatal("the document has no paths")
	}
	for path, raw := range paths {
		item, _ := raw.(map[string]any)
		isPlanned := item["x-status"] == "planned"
		for method, operation := range item {
			if strings.HasPrefix(method, "x-") || method == "parameters" {
				continue
			}
			if _, ok := operation.(map[string]any); !ok {
				continue
			}
			key := strings.ToUpper(method) + " " + path
			if isPlanned {
				planned[key] = true
			} else {
				documented[key] = true
			}
		}
	}
	implemented := map[string]bool{}
	for _, route := range h.router.Routes() {
		implemented[route] = true
	}
	missing, undocumented := []string{}, []string{}
	for key := range documented {
		if !implemented[key] {
			missing = append(missing, key)
		}
	}
	for key := range implemented {
		if !documented[key] {
			undocumented = append(undocumented, key)
		}
	}
	sort.Strings(missing)
	sort.Strings(undocumented)
	if len(missing) > 0 {
		t.Errorf("documented but not implemented (mark x-status: planned or implement): %v", missing)
	}
	if len(undocumented) > 0 {
		t.Errorf("implemented but not documented: %v", undocumented)
	}
	// An empty `planned` set is now the goal, not a defect: every documented
	// path is implemented. What still has to hold is the other direction — a
	// path marked planned must not already be served, or the label is a lie.
	for key := range planned {
		if implemented[key] {
			t.Errorf("%s is implemented but still marked planned", key)
		}
	}
}

func TestSpecIsServedOverHTTP(t *testing.T) {
	h := newHarness(t)
	resp, e := http.Get(h.server.URL + "/api/v1/openapi.yaml")
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("status %d", resp.StatusCode)
	}
	if got := resp.Header.Get("Content-Type"); got != "application/yaml" {
		t.Fatalf("content type %q", got)
	}
	var document map[string]any
	if e = yaml.NewDecoder(resp.Body).Decode(&document); e != nil {
		t.Fatal(e)
	}
	if document["openapi"] != "3.1.0" {
		t.Fatalf("served document %v", document["openapi"])
	}
}
