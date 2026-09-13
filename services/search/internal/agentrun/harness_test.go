package agentrun_test

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/json"
	"encoding/pem"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
)

func TestMain(m *testing.M) { pivottest.Main(m) }

// --- a fake GitHub App, standing in for api.github.com -------------------
//
// Duplicated from internal/ghapp's own test helpers rather than imported:
// they are unexported ghapp_test internals, and this package's own
// prFilesClient (pr_files.go) needs the identical token-exchange endpoint
// ghapp.Client itself uses, so one fake mux serves both.

var (
	testKeyOnce sync.Once
	testKeyPEM  []byte
	testRSAKey  *rsa.PrivateKey
)

func testAppKeyFile(t *testing.T) string {
	t.Helper()
	testKeyOnce.Do(func() {
		key, e := rsa.GenerateKey(rand.Reader, 2048)
		if e != nil {
			t.Fatal(e)
		}
		testRSAKey = key
		testKeyPEM = pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)})
	})
	dir := t.TempDir()
	path := filepath.Join(dir, "app.pem")
	if e := os.WriteFile(path, testKeyPEM, 0o600); e != nil {
		t.Fatal(e)
	}
	return path
}

// ghEnv builds the env func both ghapp.NewFromEnv and ghapp.ConfigFromEnv
// read, pointed at an httptest server standing in for api.github.com.
func ghEnv(t *testing.T, baseURL string) func(string) string {
	t.Helper()
	keyPath := testAppKeyFile(t)
	values := map[string]string{
		"GITHUB_APP_ID":               "12345",
		"GITHUB_APP_PRIVATE_KEY_FILE": keyPath,
		"GITHUB_API_BASE_URL":         baseURL,
	}
	return func(name string) string { return values[name] }
}

func newGHClient(t *testing.T, baseURL string) (*ghapp.Client, ghapp.Config) {
	t.Helper()
	env := ghEnv(t, baseURL)
	cfg, e := ghapp.ConfigFromEnv(env)
	if e != nil {
		t.Fatal(e)
	}
	client, e := ghapp.New(cfg)
	if e != nil {
		t.Fatal(e)
	}
	return client, cfg
}

// tokenHandler answers the installation-token exchange every test's fake
// GitHub server needs, regardless of which read or write operation the test
// itself is exercising.
func tokenHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"token": "test-installation-token", "expires_at": time.Now().Add(time.Hour),
	})
}

// --- database fixtures ----------------------------------------------------

// registerInstallation writes one gfm.github_installations row plus its
// gfm.github_installation_links row directly — there is no endpoint for the
// mirror yet (ADR-0036's own "thin github module" is not part of this
// task), the same shortcut internal/live's own api_test.go takes for a
// membership row an accepted invitation would otherwise leave. The link
// itself mirrors what internal/identity's linking callback would have
// written after a proven GitHub OAuth round trip (ADR-0034); these tests
// exercise the worker side of that link, not the callback.
func registerInstallation(t *testing.T, h *pivottest.Harness, orgID string, installationID int64, fullNames ...string) {
	t.Helper()
	repos, e := json.Marshal(fullNames)
	if e != nil {
		t.Fatal(e)
	}
	ctx := context.Background()
	if _, e := h.Pool.Exec(ctx, `INSERT INTO gfm.github_installations
 (installation_id,account,repositories) VALUES($1,'acme',$2::jsonb)
 ON CONFLICT (installation_id) DO UPDATE SET account=excluded.account,repositories=excluded.repositories`,
		installationID, string(repos)); e != nil {
		t.Fatal(e)
	}
	if _, e := h.Pool.Exec(ctx, `INSERT INTO gfm.github_installation_links(installation_id,org_id)
 VALUES($1,$2::uuid) ON CONFLICT (installation_id) DO UPDATE SET org_id=excluded.org_id`,
		installationID, orgID); e != nil {
		t.Fatal(e)
	}
}

func setCredential(t *testing.T, owner *pivottest.Client, org, apiKey string) {
	t.Helper()
	path := "/api/v1/orgs/" + org + "/credentials/" + secrets.ProviderOpenRouter
	status, body, _ := owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: path,
		Body: map[string]any{"api_key": apiKey}})
	if status != http.StatusOK {
		t.Fatalf("PUT credential: %d %v", status, body)
	}
}

// publishRule writes one minimal published skill directly into the catalog
// tables (gfm.scopes, gfm.skills, gfm.skill_revisions, gfm.blobs) rather than
// through the import pipeline — these tests exercise pr.report's own read of
// "the published catalog", not import.parse.
func publishRule(t *testing.T, h *pivottest.Harness, orgID, repoID, scope, scopePath, skillID, name, body string) {
	t.Helper()
	ctx := context.Background()
	if _, e := h.Pool.Exec(ctx, `INSERT INTO gfm.scopes(org_id,repo_id,scope,paths)
 VALUES($1::uuid,$2,$3,$4)`, orgID, repoID, scope, []string{scopePath}); e != nil {
		t.Fatal(e)
	}
	sha := skillID + "-sha"
	if _, e := h.Pool.Exec(ctx, `INSERT INTO gfm.blobs(org_id,sha256,size_bytes,content)
 VALUES($1::uuid,$2,$3,$4)`, orgID, sha, len(body), []byte(body)); e != nil {
		t.Fatal(e)
	}
	skillPath := scopePath + "/.agents/skills/" + skillID + "/SKILL.md"
	// skill_revisions has a foreign key to skills(org_id,skill_id), and
	// skills.current_revision_id points the other way — the row without a
	// revision comes first, exactly as review/approve.go's own two-step
	// write does for a real approval.
	if _, e := h.Pool.Exec(ctx, `INSERT INTO gfm.skills
 (org_id,skill_id,repo_id,name,description,scope,path,publication_status)
 VALUES($1::uuid,$2,$3,$4,$5,$6,$7,'published')`,
		orgID, skillID, repoID, name, "["+scope+"] "+name, scope, skillPath); e != nil {
		t.Fatal(e)
	}
	revisionID := skillID + "-rev1"
	if _, e := h.Pool.Exec(ctx, `INSERT INTO gfm.skill_revisions
 (org_id,revision_id,skill_id,content_sha256,blob_sha256,frontmatter,source_path)
 VALUES($1::uuid,$2,$3,$4,$4,'{}'::jsonb,$5)`,
		orgID, revisionID, skillID, sha, skillPath); e != nil {
		t.Fatal(e)
	}
	if _, e := h.Pool.Exec(ctx, `UPDATE gfm.skills SET current_revision_id=$3
 WHERE org_id=$1::uuid AND skill_id=$2`, orgID, skillID, revisionID); e != nil {
		t.Fatal(e)
	}
}

// --- a fake model provider -------------------------------------------------

// modelEnv points every provider's base-URL override at one fake server, so
// a test needs only one httptest.Server regardless of which provider name
// the run under test uses.
func modelEnv(baseURL string) func(string) string {
	values := map[string]string{
		"OPENROUTER_BASE_URL": baseURL,
		"OPENAI_BASE_URL":     baseURL,
		"ANTHROPIC_BASE_URL":  baseURL,
	}
	return func(name string) string { return values[name] }
}

// sseChatResponse writes one OpenAI/OpenRouter-shaped streamed answer
// carrying usage, the shape internal/model's chatcompletions.go decodes.
func sseChatResponse(w http.ResponseWriter, text string, tokensIn, tokensOut int) {
	w.Header().Set("Content-Type", "text/event-stream")
	_, _ = w.Write([]byte("data: " + mustJSON(map[string]any{
		"choices": []any{map[string]any{"delta": map[string]any{"content": text}}},
	}) + "\n\n"))
	_, _ = w.Write([]byte("data: " + mustJSON(map[string]any{
		"choices": []any{},
		"usage":   map[string]any{"prompt_tokens": tokensIn, "completion_tokens": tokensOut},
	}) + "\n\n"))
	_, _ = w.Write([]byte("data: [DONE]\n\n"))
}

func mustJSON(v any) string {
	b, e := json.Marshal(v)
	if e != nil {
		panic(e)
	}
	return string(b)
}

func newHarness(t *testing.T) (*pivottest.Harness, *pivottest.Client, string) {
	t.Helper()
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	return h, owner, org
}
