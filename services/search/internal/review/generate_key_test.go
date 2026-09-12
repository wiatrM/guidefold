package review_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// ADR-0045: proposal.generate must run on the organisation's own key when it
// has one, on the deployment's key file when it does not, and on neither
// silently. These three tests drive the real openai generator against a fake
// provider and read back which key the provider actually saw, rather than
// asserting on GenerateWorker's internals.

func writeKeyFile(t *testing.T, key string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "key")
	if e := os.WriteFile(path, []byte(key), 0o600); e != nil {
		t.Fatal(e)
	}
	return path
}

// fakeProviderRecordingAuth answers every call with an empty candidate list
// (valid against the output schema) and records the Authorization header the
// request carried, which is where the resolved key actually surfaces on the
// wire.
func fakeProviderRecordingAuth(t *testing.T, sawAuth *string) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		*sawAuth = r.Header.Get("Authorization")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"choices": []any{map[string]any{"message": map[string]any{
				"content": `{"candidates":[]}`}}}})
	}))
	t.Cleanup(server.Close)
	return server
}

// enqueueGenerate runs the same route generate(t, e) uses, without also
// draining the queue with the deterministic engine these key tests must not
// use.
func enqueueGenerate(t *testing.T, e *env, key string) {
	t.Helper()
	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: e.base + "/imports/" + e.importID + "/proposals:generate",
		Body: map[string]any{"idempotency_key": key}, Key: key})
	if status != http.StatusOK {
		t.Fatalf("generate: %d %v", status, body)
	}
	ids, _ := body["job_ids"].([]any)
	if len(ids) == 0 {
		t.Fatal("generate enqueued nothing")
	}
}

func assertNoJobSkippedOrFailed(t *testing.T, e *env) {
	t.Helper()
	for _, j := range e.h.Jobs(t, review.KindGenerate) {
		if j.State == "skipped" || j.State == "failed" {
			t.Fatalf("job %s ended %s: %s", j.JobID, j.State, j.Error)
		}
	}
}

// A job for an organisation with a stored key uses that key, even though a
// deployment file is also configured -- the organisation's own key wins
// (ADR-0045: charging the deployment for a customer's generation is exactly
// what BYOK exists to prevent).
func TestGenerateWorkerUsesTheOrganisationsStoredKeyOverTheDeploymentFile(t *testing.T) {
	e := setup(t)
	var sawAuth string
	server := fakeProviderRecordingAuth(t, &sawAuth)
	t.Setenv("GUIDEFOLD_GENERATOR", generator.NameOpenAI)
	t.Setenv("OPENAI_BASE_URL", server.URL)
	t.Setenv("OPENAI_API_KEY_FILE", writeKeyFile(t, "sk-deployment-key"))

	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + e.orgID + "/credentials/openai",
		Body: map[string]any{"api_key": "sk-organisation-own-key", "name": "acme's own key"}})
	if status != http.StatusOK {
		t.Fatalf("store credential: %d %v", status, body)
	}

	enqueueGenerate(t, e, "gen-org-key")
	e.h.RunGenerate(t, nil, generator.Recipe{})

	if sawAuth != "Bearer sk-organisation-own-key" {
		t.Fatalf("the provider saw authorization %q, want the organisation's own key", sawAuth)
	}
	assertNoJobSkippedOrFailed(t, e)
}

// A job for an organisation with no stored key falls back to the deployment's
// own key file -- nothing that worked before ADR-0045 stops working.
func TestGenerateWorkerFallsBackToTheDeploymentFileWithNoStoredKey(t *testing.T) {
	e := setup(t)
	var sawAuth string
	server := fakeProviderRecordingAuth(t, &sawAuth)
	t.Setenv("GUIDEFOLD_GENERATOR", generator.NameOpenAI)
	t.Setenv("OPENAI_BASE_URL", server.URL)
	t.Setenv("OPENAI_API_KEY_FILE", writeKeyFile(t, "sk-deployment-key"))

	enqueueGenerate(t, e, "gen-fallback")
	e.h.RunGenerate(t, nil, generator.Recipe{})

	if sawAuth != "Bearer sk-deployment-key" {
		t.Fatalf("the provider saw authorization %q, want the deployment's key file", sawAuth)
	}
	assertNoJobSkippedOrFailed(t, e)
}

// A job for an organisation with neither a stored key nor a deployment file
// ends skipped with the named reason -- never on a key belonging to somebody
// else, because there is no other key to fall back to (ADR-0045).
func TestGenerateWorkerSkipsWithNoKeyAnywhere(t *testing.T) {
	e := setup(t)
	t.Setenv("GUIDEFOLD_GENERATOR", generator.NameOpenAI)
	t.Setenv("OPENAI_API_KEY_FILE", "")

	enqueueGenerate(t, e, "gen-no-key")
	e.h.RunGenerate(t, nil, generator.Recipe{})

	jobs := e.h.Jobs(t, review.KindGenerate)
	if len(jobs) == 0 {
		t.Fatal("no proposal.generate jobs ran")
	}
	for _, j := range jobs {
		if j.State != "skipped" {
			t.Errorf("job %s is %s, expected skipped", j.JobID, j.State)
		}
		if j.Error != "model_credential_missing" {
			t.Errorf("job %s says %q, expected model_credential_missing", j.JobID, j.Error)
		}
	}
	status, importStatus, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: e.base + "/imports/" + e.importID})
	if status != http.StatusOK {
		t.Fatal(importStatus)
	}
	if importStatus["state"] != "ready" {
		t.Fatalf("import is %v, a missing credential must not change it", importStatus["state"])
	}
}

// fakeCandidateJSON is one minimal candidate valid against generator's output
// schema (a name, a purpose, one step that opts out of a source_ref), used
// wherever a test needs the fake provider to actually produce a proposal
// rather than an empty list.
const fakeCandidateJSON = `{"candidates":[{"name":"Rotate a key","purpose":"test purpose",
 "steps":[{"text":"do the thing","needs_confirmation":true}]}]}`

func fakeOpenAIServer(t *testing.T) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"choices": []any{map[string]any{"message": map[string]any{
				"content": fakeCandidateJSON}}}})
	}))
	t.Cleanup(server.Close)
	return server
}

func fakeAnthropicServer(t *testing.T, sawXAPIKey *string) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if sawXAPIKey != nil {
			*sawXAPIKey = r.Header.Get("x-api-key")
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"content": []any{map[string]any{"type": "text", "text": fakeCandidateJSON}}})
	}))
	t.Cleanup(server.Close)
	return server
}

// firstProposal reads back one proposal's cache key and recorded provider so
// a test can check what actually ran a job, not just that it succeeded.
func firstProposal(t *testing.T, e *env) (cacheKey, gen, model string) {
	t.Helper()
	row := e.h.Pool.QueryRow(context.Background(), `SELECT cache_key,generator,COALESCE(model,'')
 FROM gfm.proposals WHERE org_id=$1::uuid ORDER BY created_at LIMIT 1`, e.orgID)
	if err := row.Scan(&cacheKey, &gen, &model); err != nil {
		t.Fatalf("no proposal was stored for this organisation: %v", err)
	}
	return cacheKey, gen, model
}

// The deployment is configured for openai; the organisation's own preferred
// credential is anthropic. The organisation's own choice wins over the
// deployment's (API-CONTRACT §8): the job must reach the organisation's
// provider with the organisation's key, and never touch the deployment's
// openai endpoint or key file at all.
func TestGenerateWorkerUsesTheOrganisationsPreferredProviderOverADifferentDeployment(t *testing.T) {
	e := setup(t)
	var sawOpenAIAuth, sawAnthropicKey string
	openaiServer := fakeProviderRecordingAuth(t, &sawOpenAIAuth)
	anthropicServer := fakeAnthropicServer(t, &sawAnthropicKey)
	t.Setenv("GUIDEFOLD_GENERATOR", generator.NameOpenAI)
	t.Setenv("OPENAI_BASE_URL", openaiServer.URL)
	t.Setenv("OPENAI_API_KEY_FILE", writeKeyFile(t, "sk-deployment-key"))
	t.Setenv("ANTHROPIC_BASE_URL", anthropicServer.URL)

	status, body, _ := e.owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + e.orgID + "/credentials/anthropic",
		Body: map[string]any{"api_key": "sk-org-prefers-anthropic", "name": "acme's anthropic key"}})
	if status != http.StatusOK {
		t.Fatalf("store credential: %d %v", status, body)
	}

	enqueueGenerate(t, e, "gen-anthropic-preferred")
	e.h.RunGenerate(t, nil, generator.Recipe{})

	if sawAnthropicKey != "sk-org-prefers-anthropic" {
		t.Fatalf("anthropic saw x-api-key %q, want the organisation's own key", sawAnthropicKey)
	}
	if sawOpenAIAuth != "" {
		t.Fatalf("the deployment's openai endpoint was called even though the organisation prefers anthropic (auth: %q)",
			sawOpenAIAuth)
	}
	assertNoJobSkippedOrFailed(t, e)
	_, gen, _ := firstProposal(t, e)
	if gen != generator.NameAnthropic {
		t.Fatalf("the stored proposal names generator %q, want %q", gen, generator.NameAnthropic)
	}
}

// Two organisations on the same deployment, one left on the deployment's
// default (openai) and one preferring anthropic, generating from the same
// fixture: their proposals must carry different recipes and therefore
// different cache keys, never reused across a provider boundary
// (API-CONTRACT §8; Recipe.Generator and Recipe.Model are both part of
// CacheKey's input, so this also holds for two organisations that happened
// to prefer the same provider under two different models).
func TestTwoOrganisationsOnDifferentProvidersGetDifferentCacheKeys(t *testing.T) {
	openaiServer := fakeOpenAIServer(t)
	anthropicServer := fakeAnthropicServer(t, nil)
	t.Setenv("GUIDEFOLD_GENERATOR", generator.NameOpenAI)
	t.Setenv("OPENAI_BASE_URL", openaiServer.URL)
	t.Setenv("OPENAI_API_KEY_FILE", writeKeyFile(t, "sk-deployment-key"))
	t.Setenv("ANTHROPIC_BASE_URL", anthropicServer.URL)

	// setup(t) builds the identical Meridian tree, runbook and shared-procedure
	// skills for every caller, so both organisations' groups carry identical
	// input digests -- only the provider each one actually ran under can make
	// their cache keys differ.
	a := setup(t)
	enqueueGenerate(t, a, "gen-a")
	a.h.RunGenerate(t, nil, generator.Recipe{})

	b := setup(t)
	status, body, _ := b.owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: "/api/v1/orgs/" + b.orgID + "/credentials/anthropic",
		Body: map[string]any{"api_key": "sk-org-b-anthropic", "name": "b's anthropic key"}})
	if status != http.StatusOK {
		t.Fatalf("store credential: %d %v", status, body)
	}
	enqueueGenerate(t, b, "gen-b")
	b.h.RunGenerate(t, nil, generator.Recipe{})

	assertNoJobSkippedOrFailed(t, a)
	assertNoJobSkippedOrFailed(t, b)
	keyA, genA, modelA := firstProposal(t, a)
	keyB, genB, modelB := firstProposal(t, b)
	if genA != generator.NameOpenAI {
		t.Fatalf("organisation A's proposal names generator %q, want %q", genA, generator.NameOpenAI)
	}
	if genB != generator.NameAnthropic {
		t.Fatalf("organisation B's proposal names generator %q, want %q", genB, generator.NameAnthropic)
	}
	if modelA == "" || modelB == "" || modelA == modelB {
		t.Fatalf("recorded models are %q and %q, want two distinct provider defaults", modelA, modelB)
	}
	if keyA == keyB {
		t.Fatalf("two organisations on different providers share cache key %s", keyA)
	}
}
