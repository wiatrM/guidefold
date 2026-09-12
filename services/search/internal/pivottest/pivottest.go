// Package pivottest is the shared harness for the API tests of the pivot
// modules: one embedded PostgreSQL, one mgmt router with identity, import and
// knowledge mounted, and one httptest server in front of them.
//
// It exists so the import tests and the knowledge tests exercise the same
// server the CLI talks to, rather than each package standing up its own
// approximation. Nothing here is used by the service binary: it is imported
// only from _test files.
package pivottest

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/identity"
	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/knowledge"
	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
	"github.com/wiatrM/guidefold/services/search/internal/testdb"
	"github.com/wiatrM/guidefold/services/search/internal/usage"
)

// Main runs one embedded PostgreSQL cluster for the whole test binary.
func Main(m *testing.M) { testdb.Main(m) }

// Harness is one server plus everything behind it.
type Harness struct {
	Pool     *pgxpool.Pool
	Router   *mgmt.Router
	Server   *httptest.Server
	Identity *identity.Service
	Importer *importer.Service
	Blobs    importer.BlobStore
	// Events collects the telemetry the knowledge module emits, so a test can
	// assert on a judgment without standing up the delivery service.
	Events *EventLog
	Review *review.Service
	// Secrets is mounted with a fixed in-memory keyring and a verifier that
	// accepts every key but one, so the credential routes can be exercised
	// without a master key file and without reaching a provider.
	Secrets *secrets.Service
	Keyring *secrets.Keyring
	// Live is mounted over the same pool as everything else, so a test can
	// drive live.Append directly to exercise the worker's own path without
	// standing up a worker.
	Live *live.Service
}

// TestVerifier rejects any key containing "-bad" and accepts everything else,
// so a test can drive both answers without a network.
type TestVerifier struct{}

// Verify implements secrets.Verifier.
func (TestVerifier) Verify(_ context.Context, _, apiKey string) error {
	if strings.Contains(apiKey, "-bad") {
		return secrets.ErrRejected
	}
	return nil
}

// EventLog is a test double for the ledger port that also writes through to
// gf.events, so the read path sees exactly what the write path recorded.
type EventLog struct {
	Pool   *pgxpool.Pool
	Events []map[string]any
	// Reject makes the sink refuse the batch, for the "the ledger refused it"
	// path.
	Reject bool
}

// Ingest implements knowledge.EventSink.
func (l *EventLog) Ingest(ctx context.Context, tenantID string, events []any) (map[string]any, error) {
	if l.Reject {
		return map[string]any{"rejected": []any{map[string]any{"reason": "test_rejected"}}}, nil
	}
	accepted := []any{}
	for _, e := range events {
		event, _ := e.(map[string]any)
		if event == nil {
			continue
		}
		l.Events = append(l.Events, event)
		payload, _ := json.Marshal(event)
		if _, err := l.Pool.Exec(ctx, `INSERT INTO gf.events
 (tenant_id,event_id,event_type,schema_version,occurred_at,received_at,payload)
 VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING`,
			tenantID, []byte(str(event["event_id"])), str(event["event_type"]),
			str(event["schema_version"]), str(event["occurred_at"]),
			str(event["occurred_at"]), payload); err != nil {
			return nil, err
		}
		accepted = append(accepted, event["event_id"])
	}
	return map[string]any{"accepted": accepted, "rejected": []any{}}, nil
}

func str(v any) string {
	s, _ := v.(string)
	return s
}

// New starts a migrated database and a server with every pivot module mounted.
func New(t *testing.T) *Harness {
	t.Helper()
	_, pool := testdb.Start(t)
	svc, e := identity.New(pool, identity.Config{Mode: identity.ModeDev,
		PublicURL: "http://127.0.0.1", InsecureCookies: true})
	if e != nil {
		t.Fatal(e)
	}
	spec, e := os.ReadFile(filepath.Join(Root(t), "services/search/openapi/management-v1.yaml"))
	if e != nil {
		t.Fatal(e)
	}
	router := mgmt.New(mgmt.Options{Pool: pool, Resolve: svc.Resolve, OpenAPI: spec})
	svc.Register(router)
	blobs := importer.NewBlobStore(pool)
	imports := importer.New(pool, blobs)
	imports.Register(router)
	log := &EventLog{Pool: pool}
	knowledge.New(pool, blobs, log.Ingest, "pilot").Register(router)
	usage.New(pool).Register(router)
	// The review module is mounted with the generator the environment names, so
	// a test that wants candidates sets GUIDEFOLD_GENERATOR=deterministic and a
	// test of the "no generator configured" path sets nothing.
	reviewer, e := review.New(pool, blobs)
	if e != nil {
		t.Fatal(e)
	}
	reviewer.Register(router)
	keyring, e := secrets.NewKeyring("test-1", map[string][]byte{"test-1": bytes.Repeat([]byte{7}, 32)})
	if e != nil {
		t.Fatal(e)
	}
	credentials := secrets.New(pool, keyring, TestVerifier{})
	credentials.Register(router)
	liveAgent := live.New(pool)
	liveAgent.Register(router)
	server := httptest.NewServer(router)
	t.Cleanup(server.Close)
	return &Harness{Pool: pool, Router: router, Server: server, Identity: svc,
		Importer: imports, Blobs: blobs, Events: log, Review: reviewer,
		Secrets: credentials, Keyring: keyring, Live: liveAgent}
}

// Root is the repository root, found by walking up to the directory that holds
// tools/worker/build_tree.py.
func Root(t *testing.T) string {
	t.Helper()
	dir, e := os.Getwd()
	if e != nil {
		t.Fatal(e)
	}
	for i := 0; i < 8; i++ {
		if _, e := os.Stat(filepath.Join(dir, "tools", "worker", "build_tree.py")); e == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	t.Fatal("repository root not found above the working directory")
	return ""
}

// Scratch is a private working directory under the user's Guidefold cache.
// Tests never write to /tmp: a worker tree can hold a whole monorepo, and the
// service's own rule is that scratch lives where the operator put it.
func Scratch(t *testing.T, name string) string {
	t.Helper()
	home, e := os.UserHomeDir()
	if e != nil {
		t.Fatal(e)
	}
	base := filepath.Join(home, ".cache", "guidefold", "worker")
	if e := os.MkdirAll(base, 0o700); e != nil {
		t.Fatal(e)
	}
	dir, e := os.MkdirTemp(base, "test-"+name+"-")
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = os.RemoveAll(dir) })
	return dir
}

// Client is one signed-in person's browser.
type Client struct {
	h     *Harness
	http  *http.Client
	CSRF  string
	Token string
	User  map[string]any
}

// SignIn drives the development provider exactly as a browser would.
func (h *Harness) SignIn(t *testing.T, subject, email string) *Client {
	t.Helper()
	jar, _ := cookiejar.New(nil)
	c := &Client{h: h, http: &http.Client{Jar: jar,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}
	form := url.Values{"provider": {"google"}, "subject": {subject}, "email": {email}, "name": {subject}}
	req, e := http.NewRequest(http.MethodPost, h.Server.URL+"/api/v1/auth/dev",
		strings.NewReader(form.Encode()))
	if e != nil {
		t.Fatal(e)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, e := c.http.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	_, _ = io.Copy(io.Discard, resp.Body)
	resp.Body.Close()
	if resp.StatusCode != http.StatusFound {
		t.Fatalf("dev sign-in: %d", resp.StatusCode)
	}
	status, body, _ := c.Call(t, Call{Method: http.MethodGet, Path: "/api/v1/me"})
	if status != 200 {
		t.Fatalf("/me: %d %v", status, body)
	}
	c.CSRF, _ = body["csrf_token"].(string)
	c.User, _ = body["user"].(map[string]any)
	return c
}

// Anonymous is a client with no credentials.
func (h *Harness) Anonymous() *Client {
	jar, _ := cookiejar.New(nil)
	return &Client{h: h, http: &http.Client{Jar: jar}}
}

// Call describes one request.
type Call struct {
	Method, Path string
	Body         any
	Raw          []byte
	ContentType  string
	Key          string // Idempotency-Key
	NoCSRF       bool
	Headers      map[string]string
}

// Call sends a request and decodes a JSON object response.
func (c *Client) Call(t *testing.T, x Call) (int, map[string]any, http.Header) {
	t.Helper()
	status, raw, header := c.Raw(t, x)
	out := map[string]any{}
	if len(raw) > 0 && raw[0] == '{' {
		if e := json.Unmarshal(raw, &out); e != nil {
			t.Fatalf("%s %s: %v: %s", x.Method, x.Path, e, raw)
		}
	}
	return status, out, header
}

// Raw sends a request and returns the response bytes untouched, which is what a
// test of exact bytes needs.
func (c *Client) Raw(t *testing.T, x Call) (int, []byte, http.Header) {
	t.Helper()
	var payload io.Reader
	switch {
	case x.Raw != nil:
		payload = bytes.NewReader(x.Raw)
	case x.Body != nil:
		encoded, e := json.Marshal(x.Body)
		if e != nil {
			t.Fatal(e)
		}
		payload = bytes.NewReader(encoded)
	}
	req, e := http.NewRequest(x.Method, c.h.Server.URL+x.Path, payload)
	if e != nil {
		t.Fatal(e)
	}
	switch {
	case x.ContentType != "":
		req.Header.Set("Content-Type", x.ContentType)
	case x.Body != nil:
		req.Header.Set("Content-Type", "application/json")
	}
	if !x.NoCSRF && c.CSRF != "" {
		req.Header.Set("X-CSRF-Token", c.CSRF)
	}
	if x.Key != "" {
		req.Header.Set("Idempotency-Key", x.Key)
	}
	if c.Token != "" {
		req.Header.Set("Authorization", "Bearer "+c.Token)
	}
	for k, v := range x.Headers {
		req.Header.Set(k, v)
	}
	resp, e := c.http.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, raw, resp.Header
}

// CreateOrg makes an organisation with the caller as its owner.
func (c *Client) CreateOrg(t *testing.T, slug string) string {
	t.Helper()
	status, body, _ := c.Call(t, Call{Method: http.MethodPost, Path: "/api/v1/orgs",
		Body: map[string]any{"name": slug, "slug": slug}, Key: "org-" + slug})
	if status != http.StatusCreated {
		t.Fatalf("create org: %d %v", status, body)
	}
	return body["org_id"].(string)
}

// CreateRepo registers a repository.
func (c *Client) CreateRepo(t *testing.T, org, repo, gitURL string) {
	t.Helper()
	status, body, _ := c.Call(t, Call{Method: http.MethodPost, Path: "/api/v1/orgs/" + org + "/repos",
		Body: map[string]any{"repo_id": repo, "name": repo, "git_host_url": gitURL},
		Key:  "repo-" + org + "-" + repo})
	if status != http.StatusCreated && status != http.StatusOK {
		t.Fatalf("create repo: %d %v", status, body)
	}
}

// RepoBase is the path prefix every repository-scoped endpoint shares.
func RepoBase(org, repo string) string {
	return "/api/v1/orgs/" + org + "/repos/" + repo
}
