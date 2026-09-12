package ghapp_test

import (
	"context"
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
)

// parseAndVerifyJWT decodes a compact JWT and checks its RS256 signature
// against pub. It returns the decoded claims so a test can assert on them.
// This is deliberately hand-rolled, not a library call: it exercises the
// same four stdlib primitives ghapp.appJWT uses, from the other side.
func parseAndVerifyJWT(t *testing.T, token string, pub *rsa.PublicKey) map[string]any {
	t.Helper()
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		t.Fatalf("JWT has %d parts, want 3: %q", len(parts), token)
	}
	header, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		t.Fatalf("JWT header is not base64url: %v", err)
	}
	var headerFields map[string]string
	if err := json.Unmarshal(header, &headerFields); err != nil {
		t.Fatalf("JWT header is not JSON: %v", err)
	}
	if headerFields["alg"] != "RS256" {
		t.Fatalf("JWT alg = %q, want RS256", headerFields["alg"])
	}
	claimsRaw, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		t.Fatalf("JWT claims are not base64url: %v", err)
	}
	sig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		t.Fatalf("JWT signature is not base64url: %v", err)
	}
	hashed := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	if err := rsa.VerifyPKCS1v15(pub, crypto.SHA256, hashed[:], sig); err != nil {
		t.Fatalf("JWT signature does not verify against the App's own key: %v", err)
	}
	var claims map[string]any
	if err := json.Unmarshal(claimsRaw, &claims); err != nil {
		t.Fatalf("JWT claims are not JSON: %v", err)
	}
	return claims
}

func writeTokenResponse(w http.ResponseWriter, token string, expires time.Time) {
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"token": token, "expires_at": expires.Format(time.RFC3339),
	})
}

// The JWT this package builds is sent as the bearer on the token exchange,
// signed with the App's configured key, naming the configured App id, and
// bounded per ADR-0036: iat ~60s in the past, exp ~10 minutes out.
func TestAppJWTSentAsBearerOnTokenExchange(t *testing.T) {
	_, key := testAppKey(t)
	var gotAuth string
	var calls int32

	mux := http.NewServeMux()
	mux.HandleFunc("/app/installations/999/access_tokens", func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&calls, 1)
		gotAuth = r.Header.Get("Authorization")
		writeTokenResponse(w, "installation-token", time.Now().Add(time.Hour))
	})
	mux.HandleFunc("/repos/acme/widgets/git/trees/main", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"tree": []any{}, "truncated": false})
	})
	server := httptest.NewServer(mux)
	defer server.Close()

	client := newTestClient(t, server.URL)
	before := time.Now()
	if _, err := client.ListSkillFiles(context.Background(), 999, "acme/widgets", "main"); err != nil {
		t.Fatalf("ListSkillFiles: %v", err)
	}
	after := time.Now()

	if got := atomic.LoadInt32(&calls); got != 1 {
		t.Fatalf("token exchange called %d times, want 1", got)
	}
	if !strings.HasPrefix(gotAuth, "Bearer ") {
		t.Fatalf("token exchange Authorization = %q, want a Bearer JWT", gotAuth)
	}
	jwt := strings.TrimPrefix(gotAuth, "Bearer ")
	claims := parseAndVerifyJWT(t, jwt, &key.PublicKey)

	if claims["iss"] != "12345" {
		t.Fatalf("JWT iss = %v, want the configured App id", claims["iss"])
	}
	iat := int64(claims["iat"].(float64))
	exp := int64(claims["exp"].(float64))
	// iat is backdated 60s and exp is 10 minutes (600s) after the real signing
	// time, so exp-iat is their sum, 660s, not the 600s lifetime alone.
	if got, want := exp-iat, int64(660); got != want {
		t.Fatalf("JWT exp-iat = %ds, want %ds", got, want)
	}
	// iat is backdated ~60s from signing time; allow the test's own execution window.
	if lo, hi := before.Add(-65*time.Second).Unix(), after.Add(-55*time.Second).Unix(); iat < lo || iat > hi {
		t.Fatalf("JWT iat = %d, not ~60s before signing time (%d..%d)", iat, before.Unix(), after.Unix())
	}
}

// The cache must not re-request within the token's window, and must
// re-request once the clock crosses the refresh margin before expiry.
func TestInstallationTokenCachedThenRefreshedAfterExpiry(t *testing.T) {
	clk := newClock(time.Date(2026, 9, 12, 12, 0, 0, 0, time.UTC))
	var tokenCalls, contentCalls, seq int32

	mux := http.NewServeMux()
	mux.HandleFunc("/app/installations/1/access_tokens", func(w http.ResponseWriter, r *http.Request) {
		n := atomic.AddInt32(&tokenCalls, 1)
		atomic.StoreInt32(&seq, n)
		writeTokenResponse(w, fmt.Sprintf("token-%d", n), clk.Now().Add(time.Hour))
	})
	mux.HandleFunc("/repos/acme/widgets/contents/AGENTS.md", func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&contentCalls, 1)
		wantAuth := fmt.Sprintf("Bearer token-%d", atomic.LoadInt32(&seq))
		if got := r.Header.Get("Authorization"); got != wantAuth {
			t.Errorf("content call Authorization = %q, want %q", got, wantAuth)
		}
		body := base64.StdEncoding.EncodeToString([]byte("# Agents\n"))
		_ = json.NewEncoder(w).Encode(map[string]any{
			"content": body, "encoding": "base64", "size": 9, "type": "file",
		})
	})
	server := httptest.NewServer(mux)
	defer server.Close()

	client := newTestClient(t, server.URL)
	client.SetClock(clk.Now)

	if _, err := client.ReadFile(context.Background(), 1, "acme/widgets", "main", "AGENTS.md"); err != nil {
		t.Fatalf("first ReadFile: %v", err)
	}
	if _, err := client.ReadFile(context.Background(), 1, "acme/widgets", "main", "AGENTS.md"); err != nil {
		t.Fatalf("second ReadFile: %v", err)
	}
	if got := atomic.LoadInt32(&tokenCalls); got != 1 {
		t.Fatalf("token exchange called %d times within the window, want 1 (cache not used)", got)
	}

	// Still short of the 5-minute refresh margin before the 1h expiry: no refresh yet.
	clk.Advance(50 * time.Minute)
	if _, err := client.ReadFile(context.Background(), 1, "acme/widgets", "main", "AGENTS.md"); err != nil {
		t.Fatalf("third ReadFile: %v", err)
	}
	if got := atomic.LoadInt32(&tokenCalls); got != 1 {
		t.Fatalf("token exchange called %d times before the refresh margin, want 1", got)
	}

	// Now inside the 5-minute refresh margin: the cache must refresh.
	clk.Advance(6 * time.Minute)
	if _, err := client.ReadFile(context.Background(), 1, "acme/widgets", "main", "AGENTS.md"); err != nil {
		t.Fatalf("fourth ReadFile: %v", err)
	}
	if got := atomic.LoadInt32(&tokenCalls); got != 2 {
		t.Fatalf("token exchange called %d times after crossing the refresh margin, want 2", got)
	}
	if got := atomic.LoadInt32(&contentCalls); got != 4 {
		t.Fatalf("content endpoint called %d times, want 4", got)
	}
}

// The installation token is sent as the Authorization header on content
// calls, and never appears in a returned error even when the content call
// itself fails.
func TestInstallationTokenNeverAppearsInAnErrorString(t *testing.T) {
	const canary = "ghs_CANARY_INSTALLATION_TOKEN_VALUE"
	var gotAuth string
	mux := http.NewServeMux()
	mux.HandleFunc("/app/installations/1/access_tokens", func(w http.ResponseWriter, r *http.Request) {
		writeTokenResponse(w, canary, time.Now().Add(time.Hour))
	})
	mux.HandleFunc("/repos/acme/widgets/contents/AGENTS.md", func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		// The provider's own error body could echo request state back; either
		// way the client must not fold it, or the token, into its own error.
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"message":"internal error, saw ` + canary + `"}`))
	})
	server := httptest.NewServer(mux)
	defer server.Close()

	client := newTestClient(t, server.URL)
	_, err := client.ReadFile(context.Background(), 1, "acme/widgets", "main", "AGENTS.md")
	if err == nil {
		t.Fatal("a 500 from the content endpoint is not a success")
	}
	if gotAuth != "Bearer "+canary {
		t.Fatalf("content call Authorization = %q, want the installation token as a bearer", gotAuth)
	}
	if strings.Contains(err.Error(), canary) {
		t.Fatalf("the installation token leaked into the error: %v", err)
	}
}

func TestInstallationNotFoundIsANamedError(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/app/installations/404/access_tokens", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		_ = json.NewEncoder(w).Encode(map[string]any{"message": "Not Found"})
	})
	server := httptest.NewServer(mux)
	defer server.Close()

	client := newTestClient(t, server.URL)
	_, err := client.ReadFile(context.Background(), 404, "acme/widgets", "main", "AGENTS.md")
	if !errors.Is(err, ghapp.ErrInstallationNotFound) {
		t.Fatalf("ReadFile against a deleted installation = %v, want ErrInstallationNotFound", err)
	}
}
