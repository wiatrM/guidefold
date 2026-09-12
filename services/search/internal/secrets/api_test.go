package secrets_test

import (
	"bytes"
	"context"
	"net/http"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
)

func TestMain(m *testing.M) { pivottest.Main(m) }

const openRouterKey = "sk-or-v1-0123456789abcdef"

func credentialPath(org string) string {
	return "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderOpenRouter
}

// The invariant this whole module exists to keep: the key goes in and never
// comes back out. Asserted on the raw response bytes, because a decoded map
// would hide a field nobody meant to add.
func TestStoredKeyNeverComesBackOut(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	status, body, _ := owner.Raw(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey, "name": "shared account"}})
	if status != http.StatusOK {
		t.Fatalf("PUT credential: %d %s", status, body)
	}
	if bytes.Contains(body, []byte(openRouterKey)) {
		t.Fatalf("the write response echoed the key: %s", body)
	}
	if !bytes.Contains(body, []byte(`"last4":"cdef"`)) {
		t.Fatalf("the write response has no last4: %s", body)
	}

	status, body, _ = owner.Raw(t, pivottest.Call{Method: http.MethodGet, Path: "/api/v1/orgs/" + org + "/credentials"})
	if status != http.StatusOK {
		t.Fatalf("GET credentials: %d %s", status, body)
	}
	if bytes.Contains(body, []byte(openRouterKey)) {
		t.Fatalf("the list echoed the key: %s", body)
	}
	if !bytes.Contains(body, []byte(`"last4":"cdef"`)) || !bytes.Contains(body, []byte(`"name":"shared account"`)) {
		t.Fatalf("the list lost the metadata: %s", body)
	}

	// The worker's read path is the only one that produces a plaintext.
	plain, e := h.Secrets.OpenFor(context.Background(), org, secrets.ProviderOpenRouter)
	if e != nil {
		t.Fatal(e)
	}
	if plain != openRouterKey {
		t.Fatalf("the worker read %q", plain)
	}
}

// Row-level counterpart to TestOpenRefusesAnotherOrganisation: two tenants, two
// keys, and neither can see or use the other's.
func TestOneOrganisationNeverReadsAnothersKey(t *testing.T) {
	h := pivottest.New(t)
	first := h.SignIn(t, "first", "first@example.test")
	second := h.SignIn(t, "second", "second@example.test")
	orgA := first.CreateOrg(t, "org-a")
	orgB := second.CreateOrg(t, "org-b")

	if status, _, _ := first.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(orgA),
		Body: map[string]any{"api_key": "sk-or-v1-aaaaaaaaaaaa"}}); status != http.StatusOK {
		t.Fatalf("org-a PUT: %d", status)
	}
	if status, _, _ := second.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(orgB),
		Body: map[string]any{"api_key": "sk-or-v1-bbbbbbbbbbbb"}}); status != http.StatusOK {
		t.Fatalf("org-b PUT: %d", status)
	}

	// A member of neither organisation is told nothing about the other.
	if status, _, _ := first.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: "/api/v1/orgs/" + orgB + "/credentials"}); status != http.StatusForbidden {
		t.Fatalf("reading another organisation's credentials answered %d, want 403", status)
	}

	a, e := h.Secrets.OpenFor(context.Background(), orgA, secrets.ProviderOpenRouter)
	if e != nil {
		t.Fatal(e)
	}
	b, e := h.Secrets.OpenFor(context.Background(), orgB, secrets.ProviderOpenRouter)
	if e != nil {
		t.Fatal(e)
	}
	if a == b || a != "sk-or-v1-aaaaaaaaaaaa" || b != "sk-or-v1-bbbbbbbbbbbb" {
		t.Fatalf("keys crossed tenants: %q and %q", a, b)
	}
}

// Storing a key is spending authority: it is the owner's, not a member's.
func TestMemberCannotWriteOrDeleteACredential(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	member := h.SignIn(t, "member", "member@example.test")
	if _, e := h.Pool.Exec(context.Background(),
		`INSERT INTO gfm.memberships(org_id,user_id,role) VALUES($1::uuid,$2::uuid,'member')`,
		org, member.User["id"]); e != nil {
		t.Fatal(e)
	}
	if status, _, _ := member.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusForbidden {
		t.Fatalf("a member's PUT answered %d, want 403", status)
	}
	if status, _, _ := member.Call(t, pivottest.Call{Method: http.MethodDelete,
		Path: credentialPath(org)}); status != http.StatusForbidden {
		t.Fatalf("a member's DELETE answered %d, want 403", status)
	}
	// Reading the metadata is a member's right: they have to be able to see
	// whether the organisation can run the agent at all.
	if status, _, _ := member.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: "/api/v1/orgs/" + org + "/credentials"}); status != http.StatusOK {
		t.Fatalf("a member's GET answered %d, want 200", status)
	}
}

// The audit trail records that a key was set, and records four characters of it.
func TestAuditRecordsOnlyLast4(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusOK {
		t.Fatalf("PUT: %d", status)
	}
	var action, entity, revision string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT action,entity,coalesce(revision,'') FROM gfm.audit
 WHERE org_id=$1::uuid AND action='credential.set' ORDER BY audit_id DESC LIMIT 1`, org).
		Scan(&action, &entity, &revision); e != nil {
		t.Fatalf("no credential.set audit row: %v", e)
	}
	if entity != "credential:"+secrets.ProviderOpenRouter {
		t.Fatalf("audit entity is %q", entity)
	}
	if revision != "cdef" {
		t.Fatalf("audit revision is %q, want the last four characters only", revision)
	}
}

func TestProviderDomainAndRejectedKey(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + org + "/credentials/mistral",
		Body: map[string]any{"api_key": openRouterKey}})
	if status != http.StatusBadRequest || body["error"] != "invalid_provider" {
		t.Fatalf("an unknown provider answered %d %v", status, body)
	}
	// The harness verifier refuses any key containing "-bad".
	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": "sk-or-v1-bad-key"}})
	if status != http.StatusBadRequest || body["error"] != "credential_invalid" {
		t.Fatalf("a key the provider rejects answered %d %v", status, body)
	}
	// Each provider has its own row, so the three can be held at once.
	for _, provider := range secrets.Providers {
		if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut,
			Path: "/api/v1/orgs/" + org + "/credentials/" + provider,
			Body: map[string]any{"api_key": "sk-" + provider + "-0000cafe"}}); status != http.StatusOK {
			t.Fatalf("storing the %s key answered %d", provider, status)
		}
	}
	status, list, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: "/api/v1/orgs/" + org + "/credentials"})
	items, _ := list["items"].([]any)
	if status != http.StatusOK || len(items) != len(secrets.Providers) {
		t.Fatalf("expected one row per provider, got %d (%d %v)", len(items), status, list)
	}
}

func TestDeleteRemovesTheCredential(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusOK {
		t.Fatalf("PUT: %d", status)
	}
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodDelete,
		Path: credentialPath(org)}); status != http.StatusNoContent {
		t.Fatalf("DELETE: %d", status)
	}
	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodDelete, Path: credentialPath(org)})
	if status != http.StatusNotFound || body["error"] != "credential_not_found" {
		t.Fatalf("deleting again answered %d %v", status, body)
	}
	if _, e := h.Secrets.OpenFor(context.Background(), org, secrets.ProviderOpenRouter); e == nil {
		t.Fatal("the worker can still open a deleted credential")
	}
}
