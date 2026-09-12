package secrets_test

import (
	"bytes"
	"context"
	"errors"
	"net/http"
	"strings"
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

// preferredCount asserts the invariant against the database, not a response
// body that only ever describes one row: an organisation with credentials has
// exactly one preferred (§4.8).
func preferredCount(t *testing.T, h *pivottest.Harness, org string) int {
	t.Helper()
	var n int
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.org_credentials WHERE org_id=$1::uuid AND preferred`, org).Scan(&n); e != nil {
		t.Fatal(e)
	}
	return n
}

// The first credential an organisation stores becomes preferred with nothing
// asked; a second one leaves it alone (§4.8, §5.5a).
func TestFirstCredentialIsPreferredImplicitly(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}})
	if status != http.StatusOK {
		t.Fatalf("PUT: %d %v", status, body)
	}
	if preferred, _ := body["preferred"].(bool); !preferred {
		t.Fatalf("the first credential answered preferred=%v, want true", body["preferred"])
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows after the first credential = %d, want 1", n)
	}

	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderAnthropic,
		Body: map[string]any{"api_key": "sk-anthropic-cafe0000"}})
	if status != http.StatusOK {
		t.Fatalf("PUT second: %d %v", status, body)
	}
	if preferred, _ := body["preferred"].(bool); preferred {
		t.Fatal("a second credential came back preferred without being asked to")
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows after a second credential = %d, want 1", n)
	}
}

// preferred:true moves the mark to the new row and clears every other row of
// the same organisation in the same transaction (§4.8).
func TestPreferredTrueMovesTheMarkAndLeavesExactlyOne(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusOK {
		t.Fatalf("PUT openrouter: %d", status)
	}
	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderAnthropic,
		Body: map[string]any{"api_key": "sk-anthropic-cafe0000", "preferred": true}})
	if status != http.StatusOK {
		t.Fatalf("PUT anthropic preferred: %d %v", status, body)
	}
	if preferred, _ := body["preferred"].(bool); !preferred {
		t.Fatalf("preferred:true answered preferred=%v, want true", body["preferred"])
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows after moving the mark = %d, want 1", n)
	}
	var provider string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT provider FROM gfm.org_credentials WHERE org_id=$1::uuid AND preferred`, org).Scan(&provider); e != nil {
		t.Fatal(e)
	}
	if provider != secrets.ProviderAnthropic {
		t.Fatalf("preferred provider is %q, want anthropic", provider)
	}

	// Re-storing the openrouter row (rotating its key, flag omitted) must not
	// reclaim the mark, and re-storing the currently preferred row without the
	// flag must not drop it either.
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": "sk-or-v1-rotated00000"}}); status != http.StatusOK {
		t.Fatalf("re-PUT openrouter: %d", status)
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows after rotating a non-preferred row = %d, want 1", n)
	}
	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderAnthropic,
		Body: map[string]any{"api_key": "sk-anthropic-rotated00"}})
	if status != http.StatusOK {
		t.Fatalf("re-PUT anthropic: %d %v", status, body)
	}
	if preferred, _ := body["preferred"].(bool); !preferred {
		t.Fatal("re-storing the preferred row without the flag dropped it")
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows after re-storing the preferred row = %d, want 1", n)
	}
}

// Deleting the preferred credential promotes another one deterministically
// (oldest created_at, then provider), and deleting the last credential leaves
// none — there is no organisation with credentials and no preferred one
// (§4.8).
func TestDeletePromotesAnotherPreferredCredential(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	// openrouter first (becomes preferred implicitly), then anthropic.
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusOK {
		t.Fatalf("PUT openrouter: %d", status)
	}
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderAnthropic,
		Body: map[string]any{"api_key": "sk-anthropic-cafe0000"}}); status != http.StatusOK {
		t.Fatalf("PUT anthropic: %d", status)
	}

	// Deleting the preferred (openrouter) promotes the remaining row.
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodDelete,
		Path: credentialPath(org)}); status != http.StatusNoContent {
		t.Fatalf("DELETE openrouter: %d", status)
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows after deleting the preferred credential = %d, want 1", n)
	}
	var provider string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT provider FROM gfm.org_credentials WHERE org_id=$1::uuid AND preferred`, org).Scan(&provider); e != nil {
		t.Fatal(e)
	}
	if provider != secrets.ProviderAnthropic {
		t.Fatalf("promoted provider is %q, want anthropic (the only one left)", provider)
	}

	// Deleting the last remaining credential leaves the organisation with none.
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodDelete,
		Path: "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderAnthropic}); status != http.StatusNoContent {
		t.Fatalf("DELETE anthropic: %d", status)
	}
	if n := preferredCount(t, h, org); n != 0 {
		t.Fatalf("preferred rows after deleting the last credential = %d, want 0", n)
	}
	var remaining int
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.org_credentials WHERE org_id=$1::uuid`, org).Scan(&remaining); e != nil {
		t.Fatal(e)
	}
	if remaining != 0 {
		t.Fatalf("credentials remaining = %d, want 0", remaining)
	}
}

// model is shape-checked only (§4.8): no whitespace, at most 120 characters,
// `^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,119}$`. A failing shape is invalid_model and
// stores nothing; an empty or omitted model means the provider's default and is
// stored as an empty string; a well-formed model round-trips on GET and PUT.
func TestModelShapeValidation(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey, "model": "this has spaces"}})
	if status != http.StatusBadRequest || body["error"] != "invalid_model" {
		t.Fatalf("a model with whitespace answered %d %v, want 400 invalid_model", status, body)
	}
	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey, "model": strings.Repeat("a", 121)}})
	if status != http.StatusBadRequest || body["error"] != "invalid_model" {
		t.Fatalf("a 121-character model answered %d %v, want 400 invalid_model", status, body)
	}
	var stored int
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.org_credentials WHERE org_id=$1::uuid`, org).Scan(&stored); e != nil {
		t.Fatal(e)
	}
	if stored != 0 {
		t.Fatalf("an invalid model stored %d rows, want 0", stored)
	}

	// Omitted model means the provider's default, stored as ''.
	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}})
	if status != http.StatusOK || body["model"] != "" {
		t.Fatalf("an omitted model answered %d %v, want model=''", status, body)
	}

	// A well-formed model with the characters the shape allows round-trips.
	const wantModel = "openrouter/anthropic/claude-3.5-sonnet:beta"
	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey, "model": wantModel}})
	if status != http.StatusOK || body["model"] != wantModel {
		t.Fatalf("PUT with a well-formed model answered %d %v", status, body)
	}
	status, list, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: "/api/v1/orgs/" + org + "/credentials"})
	items, _ := list["items"].([]any)
	if status != http.StatusOK || len(items) != 1 {
		t.Fatalf("GET answered %d %v", status, list)
	}
	row, _ := items[0].(map[string]any)
	if row["model"] != wantModel {
		t.Fatalf("GET's model = %v, want %q", row["model"], wantModel)
	}
	if preferred, _ := row["preferred"].(bool); !preferred {
		t.Fatal("GET lost preferred=true for the only credential")
	}
}

// rawCredential reads the raw stored row so a test can assert the ciphertext
// and last4 were untouched by an operation that has no business touching them.
func rawCredential(t *testing.T, h *pivottest.Harness, org, provider string) (nonce, ciphertext []byte, last4 string) {
	t.Helper()
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT nonce,ciphertext,last4 FROM gfm.org_credentials WHERE org_id=$1::uuid AND provider=$2`,
		org, provider).Scan(&nonce, &ciphertext, &last4); e != nil {
		t.Fatal(e)
	}
	return nonce, ciphertext, last4
}

// PATCH changes the model, or moves the preferred mark, without the key
// (§4.8): a model change must leave the ciphertext and last4 exactly as PUT
// left them, and the model must round-trip on GET afterwards.
func TestPatchChangesModelWithoutTouchingTheKey(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusOK {
		t.Fatalf("PUT: %d", status)
	}
	beforeNonce, beforeCipher, beforeLast4 := rawCredential(t, h, org, secrets.ProviderOpenRouter)

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPatch, Path: credentialPath(org),
		Body: map[string]any{"model": "openrouter/auto"}})
	if status != http.StatusOK {
		t.Fatalf("PATCH: %d %v", status, body)
	}
	if body["model"] != "openrouter/auto" {
		t.Fatalf("PATCH answered model=%v, want openrouter/auto", body["model"])
	}
	afterNonce, afterCipher, afterLast4 := rawCredential(t, h, org, secrets.ProviderOpenRouter)
	if !bytes.Equal(beforeNonce, afterNonce) || !bytes.Equal(beforeCipher, afterCipher) || beforeLast4 != afterLast4 {
		t.Fatal("PATCH changing the model touched the sealed key or last4")
	}

	status, list, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: "/api/v1/orgs/" + org + "/credentials"})
	items, _ := list["items"].([]any)
	if status != http.StatusOK || len(items) != 1 {
		t.Fatalf("GET: %d %v", status, list)
	}
	row, _ := items[0].(map[string]any)
	if row["model"] != "openrouter/auto" {
		t.Fatalf("GET's model = %v after PATCH, want openrouter/auto", row["model"])
	}

	// api_key is not accepted here at all: patchCredential has no such field, so
	// mgmt.Context.Decode's DisallowUnknownFields refuses it the same way any
	// other route refuses an unknown field, with invalid_json rather than one
	// of PATCH's own domain codes (invalid_provider/invalid_model/invalid_body/
	// credential_not_found) — still a 400, and the key is never read.
	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPatch, Path: credentialPath(org),
		Body: map[string]any{"api_key": "sk-or-v1-should-not-be-accepted", "model": "x"}})
	if status != http.StatusBadRequest || body["error"] != "invalid_json" {
		t.Fatalf("PATCH with api_key answered %d %v, want 400 invalid_json", status, body)
	}
}

// preferred:true on PATCH moves the mark exactly as PUT does, leaving exactly
// one preferred row, without needing the key.
func TestPatchMovesThePreferredMark(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusOK {
		t.Fatalf("PUT openrouter: %d", status)
	}
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderAnthropic,
		Body: map[string]any{"api_key": "sk-anthropic-cafe0000"}}); status != http.StatusOK {
		t.Fatalf("PUT anthropic: %d", status)
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows before PATCH = %d, want 1", n)
	}

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPatch,
		Path: "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderAnthropic,
		Body: map[string]any{"preferred": true}})
	if status != http.StatusOK {
		t.Fatalf("PATCH preferred:true: %d %v", status, body)
	}
	if preferred, _ := body["preferred"].(bool); !preferred {
		t.Fatal("PATCH preferred:true did not answer preferred=true")
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows after PATCH = %d, want 1", n)
	}
	var provider string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT provider FROM gfm.org_credentials WHERE org_id=$1::uuid AND preferred`, org).Scan(&provider); e != nil {
		t.Fatal(e)
	}
	if provider != secrets.ProviderAnthropic {
		t.Fatalf("preferred provider is %q, want anthropic", provider)
	}
}

// An empty PATCH body is refused: at least one field must be present.
func TestPatchEmptyBodyIsRefused(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusOK {
		t.Fatalf("PUT: %d", status)
	}
	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPatch, Path: credentialPath(org),
		Body: map[string]any{}})
	if status != http.StatusBadRequest || body["error"] != "invalid_body" {
		t.Fatalf("an empty PATCH body answered %d %v, want 400 invalid_body", status, body)
	}
}

// preferred:false on the organisation's only preferred row is refused, and
// leaves the organisation exactly as it was: there is no legitimate way to
// reach zero preferred credentials except deleting the last one.
func TestPatchCannotClearTheOnlyPreferredRow(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey, "model": "openrouter/auto"}}); status != http.StatusOK {
		t.Fatalf("PUT: %d", status)
	}
	beforeNonce, beforeCipher, beforeLast4 := rawCredential(t, h, org, secrets.ProviderOpenRouter)

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPatch, Path: credentialPath(org),
		Body: map[string]any{"preferred": false}})
	if status != http.StatusBadRequest || body["error"] != "invalid_body" {
		t.Fatalf("clearing the only preferred row answered %d %v, want 400 invalid_body", status, body)
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows after the refused PATCH = %d, want 1 (unchanged)", n)
	}
	afterNonce, afterCipher, afterLast4 := rawCredential(t, h, org, secrets.ProviderOpenRouter)
	if !bytes.Equal(beforeNonce, afterNonce) || !bytes.Equal(beforeCipher, afterCipher) || beforeLast4 != afterLast4 {
		t.Fatal("a refused PATCH still touched the stored row")
	}
	var model string
	var preferred bool
	if e := h.Pool.QueryRow(context.Background(), `SELECT model,preferred FROM gfm.org_credentials
 WHERE org_id=$1::uuid AND provider=$2`, org, secrets.ProviderOpenRouter).Scan(&model, &preferred); e != nil {
		t.Fatal(e)
	}
	if model != "openrouter/auto" || !preferred {
		t.Fatalf("the row changed despite the refusal: model=%q preferred=%v", model, preferred)
	}
}

// preferred:false on a row that is not the preferred one is a legitimate
// no-op: it must not be refused, and the mark must stay exactly where it was.
func TestPatchPreferredFalseOnANonPreferredRowIsANoop(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusOK {
		t.Fatalf("PUT openrouter: %d", status)
	}
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderAnthropic,
		Body: map[string]any{"api_key": "sk-anthropic-cafe0000"}}); status != http.StatusOK {
		t.Fatalf("PUT anthropic: %d", status)
	}
	// openrouter is preferred (stored first); anthropic is not.
	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPatch,
		Path: "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderAnthropic,
		Body: map[string]any{"preferred": false}})
	if status != http.StatusOK {
		t.Fatalf("PATCH preferred:false on a non-preferred row answered %d %v, want 200", status, body)
	}
	if preferred, _ := body["preferred"].(bool); preferred {
		t.Fatal("PATCH preferred:false answered preferred=true")
	}
	if n := preferredCount(t, h, org); n != 1 {
		t.Fatalf("preferred rows after the no-op PATCH = %d, want 1", n)
	}
	var provider string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT provider FROM gfm.org_credentials WHERE org_id=$1::uuid AND preferred`, org).Scan(&provider); e != nil {
		t.Fatal(e)
	}
	if provider != secrets.ProviderOpenRouter {
		t.Fatalf("the mark moved to %q, want it to stay on openrouter", provider)
	}
}

// Unknown provider and a provider with no stored row answer the documented
// codes.
func TestPatchProviderDomainAndMissingRow(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPatch,
		Path: "/api/v1/orgs/" + org + "/credentials/mistral", Body: map[string]any{"model": "x"}})
	if status != http.StatusBadRequest || body["error"] != "invalid_provider" {
		t.Fatalf("PATCH on an unknown provider answered %d %v, want 400 invalid_provider", status, body)
	}
	status, body, _ = owner.Call(t, pivottest.Call{Method: http.MethodPatch, Path: credentialPath(org),
		Body: map[string]any{"model": "x"}})
	if status != http.StatusNotFound || body["error"] != "credential_not_found" {
		t.Fatalf("PATCH on a provider with no stored row answered %d %v, want 404 credential_not_found", status, body)
	}
}

// An invalid model shape on PATCH is refused and leaves the row untouched.
func TestPatchInvalidModelShape(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey, "model": "openrouter/auto"}}); status != http.StatusOK {
		t.Fatalf("PUT: %d", status)
	}
	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPatch, Path: credentialPath(org),
		Body: map[string]any{"model": "this has spaces"}})
	if status != http.StatusBadRequest || body["error"] != "invalid_model" {
		t.Fatalf("PATCH with a bad model shape answered %d %v, want 400 invalid_model", status, body)
	}
	var model string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT model FROM gfm.org_credentials WHERE org_id=$1::uuid AND provider=$2`,
		org, secrets.ProviderOpenRouter).Scan(&model); e != nil {
		t.Fatal(e)
	}
	if model != "openrouter/auto" {
		t.Fatalf("model changed to %q despite the refusal", model)
	}
}

// A member cannot PATCH; only the owner can.
func TestMemberCannotPatchACredential(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	member := h.SignIn(t, "member", "member@example.test")
	if _, e := h.Pool.Exec(context.Background(),
		`INSERT INTO gfm.memberships(org_id,user_id,role) VALUES($1::uuid,$2::uuid,'member')`,
		org, member.User["id"]); e != nil {
		t.Fatal(e)
	}
	if status, _, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey}}); status != http.StatusOK {
		t.Fatalf("PUT: %d", status)
	}
	if status, _, _ := member.Call(t, pivottest.Call{Method: http.MethodPatch, Path: credentialPath(org),
		Body: map[string]any{"model": "x"}}); status != http.StatusForbidden {
		t.Fatalf("a member's PATCH answered %d, want 403", status)
	}
}

// The key never appears in any response body, on any route, in any field.
func TestKeyNeverAppearsInAnyResponseBody(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")

	status, body, _ := owner.Raw(t, pivottest.Call{Method: http.MethodPut, Path: credentialPath(org),
		Body: map[string]any{"api_key": openRouterKey, "model": "openrouter/auto", "preferred": true}})
	if status != http.StatusOK {
		t.Fatalf("PUT: %d %s", status, body)
	}
	if bytes.Contains(body, []byte(openRouterKey)) {
		t.Fatalf("the PUT response echoed the key: %s", body)
	}

	status, body, _ = owner.Raw(t, pivottest.Call{Method: http.MethodGet, Path: "/api/v1/orgs/" + org + "/credentials"})
	if status != http.StatusOK {
		t.Fatalf("GET: %d %s", status, body)
	}
	if bytes.Contains(body, []byte(openRouterKey)) {
		t.Fatalf("the GET response echoed the key: %s", body)
	}

	// The worker's read paths are the only ones that ever produce a plaintext,
	// and OpenPreferred's result never travels back through JSON.
	provider, model, plain, e := h.Secrets.OpenPreferred(context.Background(), org)
	if e != nil {
		t.Fatal(e)
	}
	if provider != secrets.ProviderOpenRouter || model != "openrouter/auto" || plain != openRouterKey {
		t.Fatalf("OpenPreferred = (%q,%q,%q)", provider, model, plain)
	}
}

// An organisation with no credential at all is the one case OpenPreferred and
// the existing missing-credential error must agree on.
func TestOpenPreferredWithNoCredentialAtAll(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	if _, _, _, e := h.Secrets.OpenPreferred(context.Background(), org); !errors.Is(e, secrets.ErrNoCredential) {
		t.Fatalf("OpenPreferred on an organisation with no credential returned %v, want ErrNoCredential", e)
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
