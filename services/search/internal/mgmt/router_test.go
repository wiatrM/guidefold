package mgmt_test

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/testdb"
)

func TestMain(m *testing.M) { testdb.Main(m) }

const testUser = "77777777-7777-4777-8777-777777777777"

func router(t *testing.T, principal *mgmt.Principal) *mgmt.Router {
	t.Helper()
	_, pool := testdb.Start(t)
	return mgmt.New(mgmt.Options{Pool: pool, Resolve: func(context.Context, *http.Request) (*mgmt.Principal, error) {
		return principal, nil
	}})
}

func session() *mgmt.Principal {
	return &mgmt.Principal{UserID: testUser, Source: mgmt.SourceSession, CSRF: "csrf-value"}
}

func do(t *testing.T, rt *mgmt.Router, req *http.Request) (*http.Response, map[string]any) {
	t.Helper()
	w := httptest.NewRecorder()
	rt.ServeHTTP(w, req)
	resp := w.Result()
	raw, _ := io.ReadAll(resp.Body)
	out := map[string]any{}
	if len(raw) > 0 && raw[0] == '{' {
		if e := json.Unmarshal(raw, &out); e != nil {
			t.Fatalf("%s: %v", raw, e)
		}
	}
	return resp, out
}

func TestUnknownPathUnderApiStillGetsTheEnvelope(t *testing.T) {
	rt := router(t, nil)
	resp, body := do(t, rt, httptest.NewRequest(http.MethodGet, "/api/v1/no-such-thing", nil))
	if resp.StatusCode != 404 || body["error"] != "not_found" {
		t.Fatalf("%d %v", resp.StatusCode, body)
	}
	if body["request_id"] != resp.Header.Get("X-Request-Id") || body["request_id"] == "" {
		t.Fatalf("request id %v", body)
	}
	if resp.Header.Get("Cache-Control") != "no-store" {
		t.Fatalf("Cache-Control %q", resp.Header.Get("Cache-Control"))
	}
	if body["message"] == "" {
		t.Fatal("no message")
	}
}

func TestRequestIdIsEchoedOnlyWhenItIsSafe(t *testing.T) {
	rt := router(t, nil)
	rt.Handle(http.MethodGet, "/api/v1/ping", func(c *mgmt.Context) error {
		return c.JSON(200, map[string]any{"ok": true})
	}, mgmt.Public())

	req := httptest.NewRequest(http.MethodGet, "/api/v1/ping", nil)
	req.Header.Set("X-Request-Id", "trace-abc-123")
	resp, _ := do(t, rt, req)
	if resp.Header.Get("X-Request-Id") != "trace-abc-123" {
		t.Fatalf("a safe identifier was not echoed: %q", resp.Header.Get("X-Request-Id"))
	}
	for _, bad := range []string{"short", "with space", "line\nbreak", strings.Repeat("x", 65),
		`<script>alert(1)</script>`} {
		req = httptest.NewRequest(http.MethodGet, "/api/v1/ping", nil)
		req.Header.Set("X-Request-Id", bad)
		resp, _ = do(t, rt, req)
		got := resp.Header.Get("X-Request-Id")
		if got == bad || got == "" {
			t.Fatalf("unsafe identifier %q was echoed as %q", bad, got)
		}
	}
}

func TestBodyLimit(t *testing.T) {
	rt := router(t, session())
	seen := atomic.Bool{}
	rt.Handle(http.MethodPost, "/api/v1/echo", func(c *mgmt.Context) error {
		seen.Store(true)
		return c.JSON(200, map[string]any{"bytes": len(c.Body)})
	}, mgmt.NoCSRF())
	req := httptest.NewRequest(http.MethodPost, "/api/v1/echo",
		strings.NewReader(strings.Repeat("x", mgmt.DefaultBodyLimit+1)))
	resp, body := do(t, rt, req)
	if resp.StatusCode != 413 || body["error"] != "body_too_large" {
		t.Fatalf("%d %v", resp.StatusCode, body)
	}
	if seen.Load() {
		t.Fatal("the handler ran on an over-sized body")
	}
	req = httptest.NewRequest(http.MethodPost, "/api/v1/echo", strings.NewReader(`{"a":1}`))
	if resp, body = do(t, rt, req); resp.StatusCode != 200 || body["bytes"].(float64) != 7 {
		t.Fatalf("%d %v", resp.StatusCode, body)
	}
}

func TestUnauthenticatedRequestsAreRejectedBeforeTheHandler(t *testing.T) {
	rt := router(t, nil)
	rt.Handle(http.MethodGet, "/api/v1/private", func(c *mgmt.Context) error {
		t.Error("the handler ran without a principal")
		return nil
	})
	resp, body := do(t, rt, httptest.NewRequest(http.MethodGet, "/api/v1/private", nil))
	if resp.StatusCode != 401 || body["error"] != "unauthenticated" {
		t.Fatalf("%d %v", resp.StatusCode, body)
	}
}

func TestDecodeRejectsUnknownFields(t *testing.T) {
	rt := router(t, session())
	rt.Handle(http.MethodPost, "/api/v1/typed", func(c *mgmt.Context) error {
		var in struct {
			Name string `json:"name"`
		}
		if e := c.Decode(&in); e != nil {
			return e
		}
		return c.JSON(200, map[string]any{"name": in.Name})
	}, mgmt.NoCSRF())
	req := httptest.NewRequest(http.MethodPost, "/api/v1/typed", strings.NewReader(`{"nmae":"typo"}`))
	resp, body := do(t, rt, req)
	if resp.StatusCode != 400 || body["error"] != "invalid_json" {
		t.Fatalf("a misspelled field was accepted: %d %v", resp.StatusCode, body)
	}
}

// Two concurrent requests with the same key must not both do the work.
func TestConcurrentIdempotentRequestsRunOnce(t *testing.T) {
	rt := router(t, session())
	var runs atomic.Int32
	release := make(chan struct{})
	rt.Handle(http.MethodPost, "/api/v1/slow", func(c *mgmt.Context) error {
		runs.Add(1)
		<-release
		return c.JSON(201, map[string]any{"created": true})
	}, mgmt.NoCSRF(), mgmt.Idempotent())

	results := make([]int, 2)
	var wg sync.WaitGroup
	for i := range results {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			req := httptest.NewRequest(http.MethodPost, "/api/v1/slow", strings.NewReader(`{"a":1}`))
			req.Header.Set("Idempotency-Key", "one-key")
			resp, _ := do(t, rt, req)
			results[i] = resp.StatusCode
		}(i)
		if i == 0 {
			// Give the first request time to claim the key.
			time.Sleep(150 * time.Millisecond)
		}
	}
	close(release)
	wg.Wait()
	if runs.Load() != 1 {
		t.Fatalf("the handler ran %d times", runs.Load())
	}
	sorted := results[0] + results[1]
	if sorted != 201+409 && sorted != 201+201 {
		t.Fatalf("statuses %v", results)
	}
}

func TestIdempotencyKeyMayComeFromTheBody(t *testing.T) {
	rt := router(t, session())
	rt.Handle(http.MethodPost, "/api/v1/keyed", func(c *mgmt.Context) error {
		return c.JSON(201, map[string]any{"id": "fixed"})
	}, mgmt.NoCSRF(), mgmt.Idempotent())
	body := `{"idempotency_key":"from-body","name":"x"}`
	for i := 0; i < 2; i++ {
		resp, out := do(t, rt, httptest.NewRequest(http.MethodPost, "/api/v1/keyed", strings.NewReader(body)))
		if resp.StatusCode != 201 || out["id"] != "fixed" {
			t.Fatalf("attempt %d: %d %v", i, resp.StatusCode, out)
		}
	}
}

func TestBearerPrincipalsSkipTheCSRFCheck(t *testing.T) {
	rt := router(t, &mgmt.Principal{UserID: testUser, Source: mgmt.SourcePersonal, TokenID: "t"})
	rt.Handle(http.MethodPost, "/api/v1/act", func(c *mgmt.Context) error {
		return c.JSON(200, map[string]any{"ok": true})
	})
	resp, body := do(t, rt, httptest.NewRequest(http.MethodPost, "/api/v1/act", nil))
	if resp.StatusCode != 200 {
		t.Fatalf("%d %v", resp.StatusCode, body)
	}
}

func TestRelativeRejectsOffSiteRedirects(t *testing.T) {
	for _, path := range []string{"/", "/organization?tab=x"} {
		if !mgmt.Relative(path) {
			t.Errorf("%q should be relative", path)
		}
	}
	for _, path := range []string{"", "https://evil.example/", "//evil.example/",
		"\\\\evil.example", "/ok\nSet-Cookie: a=b"} {
		if mgmt.Relative(path) {
			t.Errorf("%q should not be relative", path)
		}
	}
}

func TestPrincipalScopes(t *testing.T) {
	installation := &mgmt.Principal{Source: mgmt.SourceInstallation, Scopes: []string{"search"}}
	if !installation.HasScope("search") || installation.HasScope("use") {
		t.Fatal("installation scopes are not enforced literally")
	}
	if installation.IsUser() {
		t.Fatal("an installation token counts as a person")
	}
	personal := &mgmt.Principal{Source: mgmt.SourcePersonal, UserID: testUser, Scopes: []string{"user"}}
	for _, scope := range []string{"search", "use", "events"} {
		if !personal.HasScope(scope) {
			t.Fatalf("a personal token lacks %s", scope)
		}
	}
	if personal.HasScope("validate") {
		t.Fatal("a personal token acquired the CI scope")
	}
	if !personal.IsUser() {
		t.Fatal("a personal token is not a person")
	}
	ci := &mgmt.Principal{Source: mgmt.SourceCI, Scopes: []string{"validate"}}
	if ci.HasScope("search") || !ci.HasScope("validate") {
		t.Fatal("CI scopes are wrong")
	}
	if (*mgmt.Principal)(nil).ID() != "anonymous" {
		t.Fatal("a nil principal is not anonymous")
	}
	if (*mgmt.Principal)(nil).HasScope("search") || (*mgmt.Principal)(nil).IsUser() {
		t.Fatal("a nil principal carries authority")
	}
	if installation.ID() != "token:" && (&mgmt.Principal{TokenID: "t7",
		Source: mgmt.SourceInstallation}).ID() != "token:t7" {
		t.Fatal("token principals are not identified by their token")
	}
	if personal.ID() != "user:"+testUser {
		t.Fatalf("personal principal id %q", personal.ID())
	}
}
