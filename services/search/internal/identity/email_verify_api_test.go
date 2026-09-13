package identity_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/identity"
)

// emailVerificationProvider is a fake WorkOS: the authorization_code grant
// always answers email_verification_required, carrying pendingToken and
// email; the email-verification grant accepts exactly rightCode against
// pendingToken. It never itself limits attempts — that is the identity
// service's own job (EmailVerificationMaxAttempts), which these tests exist
// to check.
func emailVerificationProvider(t *testing.T, pendingToken, rightCode, email string) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]string
		_ = json.NewDecoder(r.Body).Decode(&body)
		switch body["grant_type"] {
		case "authorization_code":
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnprocessableEntity)
			out, _ := json.Marshal(map[string]string{
				"code": "email_verification_required", "message": "verify your email",
				"pending_authentication_token": pendingToken, "email": email,
				"email_verification_id": "email_verification_1",
			})
			_, _ = w.Write(out)
		case "urn:workos:oauth:grant-type:email-verification:code":
			if body["pending_authentication_token"] != pendingToken || body["code"] != rightCode {
				w.WriteHeader(http.StatusBadRequest)
				_, _ = w.Write([]byte(`{"code":"invalid_grant","message":"wrong code"}`))
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"user":{"id":"workos-verify-1","email":"` + email + `","first_name":"Vera","last_name":"Fy"}}`))
		default:
			w.WriteHeader(http.StatusBadRequest)
		}
	}))
	t.Cleanup(server.Close)
	return server
}

func workOSHarness(t *testing.T, base string) *harness {
	t.Helper()
	return newHarnessWith(t, identity.Config{Mode: identity.ModeWorkOS,
		PublicURL: "https://guidefold.example", InsecureCookies: true,
		WorkOSAPIKey: "sk_test_key", WorkOSClientID: "client_123", WorkOSBase: base})
}

// startLoginToEmailVerification drives a login through the point WorkOS
// answers email_verification_required, and returns the callback's redirect
// response so a test can inspect it before continuing to verify-email.
func startLoginToEmailVerification(t *testing.T, h *harness, c *client) *http.Response {
	t.Helper()
	login, e := c.http.Get(h.server.URL + "/api/v1/auth/login/github?return_to=/organization")
	if e != nil {
		t.Fatal(e)
	}
	login.Body.Close()
	state := mustURL(t, login.Header.Get("Location")).Query().Get("state")
	callback, e := c.http.Get(h.server.URL + "/api/v1/auth/callback?code=code-1&state=" + url.QueryEscape(state))
	if e != nil {
		t.Fatal(e)
	}
	callback.Body.Close()
	return callback
}

// Wrong code, then the correct code, succeeds — the case a destructive
// consumeAuthState/matchAuthStateCookie reuse would have broken (a wrong
// code would have invalidated the round trip instead of leaving it
// retryable).
func TestEmailVerificationRequiredFlow(t *testing.T) {
	provider := emailVerificationProvider(t, "ptok-1", "123456", "verify@example.test")
	h := workOSHarness(t, provider.URL)
	c := h.newClient()

	callback := startLoginToEmailVerification(t, h, c)
	loc := callback.Header.Get("Location")
	if callback.StatusCode != http.StatusFound || !strings.HasPrefix(loc, "/login/verify-email?email=") {
		t.Fatalf("callback did not redirect to the code screen: %d %q", callback.StatusCode, loc)
	}
	// Only a masked email travels in the URL — never the address WorkOS
	// returned, never the pending token, never the state secret.
	masked := mustURL(t, loc).Query().Get("email")
	if masked == "" || strings.Contains(loc, "verify@example.test") || strings.Contains(loc, "ptok-1") {
		t.Fatalf("the redirect leaked more than a masked email: %q (masked=%q)", loc, masked)
	}
	var sawStateCookie bool
	for _, ck := range callback.Cookies() {
		if ck.Name == identity.AuthStateCookie && ck.Value != "" {
			sawStateCookie = true
		}
		if ck.Name == identity.SessionCookie && ck.Value != "" {
			t.Fatal("a session was started before the code was verified")
		}
	}
	if !sawStateCookie {
		t.Fatal("no new auth-state cookie was set for the verification round trip")
	}

	// A wrong code is refused and the round trip remains usable.
	status, body, _ := c.call(t, call{method: http.MethodPost, path: "/api/v1/auth/verify-email",
		body: map[string]any{"code": "000000"}})
	if status != http.StatusBadRequest || body["error"] != "email_code_invalid" {
		t.Fatalf("wrong code: %d %v", status, body)
	}

	// The correct code finishes sign-in and honours the original return_to.
	status, body, _ = c.call(t, call{method: http.MethodPost, path: "/api/v1/auth/verify-email",
		body: map[string]any{"code": "123456"}})
	if status != http.StatusOK || body["return_to"] != "/organization" {
		t.Fatalf("correct code: %d %v", status, body)
	}
	me := c.refresh(t)
	if me["user"].(map[string]any)["email"] != "verify@example.test" {
		t.Fatalf("user after verification: %v", me["user"])
	}

	// Single-use: the state cannot be replayed even with the right code again.
	status, body, _ = c.call(t, call{method: http.MethodPost, path: "/api/v1/auth/verify-email",
		body: map[string]any{"code": "123456"}})
	if status != http.StatusBadRequest || body["error"] != "invalid_state" {
		t.Fatalf("replayed verification: %d %v", status, body)
	}
}

func TestEmailVerificationAttemptsExceeded(t *testing.T) {
	provider := emailVerificationProvider(t, "ptok-2", "999999", "limit@example.test")
	h := workOSHarness(t, provider.URL)
	c := h.newClient()
	startLoginToEmailVerification(t, h, c)

	for i := 0; i < identity.EmailVerificationMaxAttempts; i++ {
		status, body, _ := c.call(t, call{method: http.MethodPost, path: "/api/v1/auth/verify-email",
			body: map[string]any{"code": "wrong"}})
		if status != http.StatusBadRequest || body["error"] != "email_code_invalid" {
			t.Fatalf("attempt %d: %d %v", i, status, body)
		}
	}
	status, body, _ := c.call(t, call{method: http.MethodPost, path: "/api/v1/auth/verify-email",
		body: map[string]any{"code": "wrong"}})
	if status != http.StatusBadRequest || body["error"] != "email_code_attempts_exceeded" {
		t.Fatalf("attempts exceeded: %d %v", status, body)
	}
	// The row is gone: even the right code no longer works, and the caller
	// must sign in again from the start.
	status, body, _ = c.call(t, call{method: http.MethodPost, path: "/api/v1/auth/verify-email",
		body: map[string]any{"code": "999999"}})
	if status != http.StatusBadRequest || body["error"] != "invalid_state" {
		t.Fatalf("after exhaustion: %d %v", status, body)
	}
}

func TestEmailVerificationExpiredState(t *testing.T) {
	provider := emailVerificationProvider(t, "ptok-3", "111111", "expire@example.test")
	h := workOSHarness(t, provider.URL)
	c := h.newClient()
	startLoginToEmailVerification(t, h, c)

	h.svc.SetClock(func() time.Time { return time.Now().Add(identity.AuthStateTTL + time.Minute) })
	status, body, _ := c.call(t, call{method: http.MethodPost, path: "/api/v1/auth/verify-email",
		body: map[string]any{"code": "111111"}})
	if status != http.StatusBadRequest || body["error"] != "expired_state" {
		t.Fatalf("expired state: %d %v", status, body)
	}
}

func TestVerifyEmailCodeRequiresAState(t *testing.T) {
	provider := emailVerificationProvider(t, "ptok-4", "222222", "nostate@example.test")
	h := workOSHarness(t, provider.URL)
	c := h.newClient()
	status, body, _ := c.call(t, call{method: http.MethodPost, path: "/api/v1/auth/verify-email",
		body: map[string]any{"code": "222222"}})
	if status != http.StatusBadRequest || body["error"] != "invalid_state" {
		t.Fatalf("no round trip in progress: %d %v", status, body)
	}
}

// email_verification_required is the only pending outcome this service
// carries into a second step. The other three WorkOS may answer with
// (API-CONTRACT §2) are reported and not built: the browser lands back on
// the sign-in page with WorkOS's own outcome code, and no verification round
// trip is opened.
func TestOtherPendingAuthStatesReturnToLoginWithTheirOwnCode(t *testing.T) {
	for _, code := range []string{"organization_selection_required", "mfa_enrollment", "mfa_challenge"} {
		t.Run(code, func(t *testing.T) {
			provider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusBadRequest)
				out, _ := json.Marshal(map[string]string{"code": code, "message": "pending",
					"pending_authentication_token": "ptok-x"})
				_, _ = w.Write(out)
			}))
			defer provider.Close()
			h := workOSHarness(t, provider.URL)
			c := h.newClient()
			callback := startLoginToEmailVerification(t, h, c)
			want := "/login?auth=" + code
			if callback.StatusCode != http.StatusFound || callback.Header.Get("Location") != want {
				t.Fatalf("%s: %d %q, want %q", code, callback.StatusCode, callback.Header.Get("Location"), want)
			}
			for _, ck := range callback.Cookies() {
				if ck.Name == identity.AuthStateCookie && ck.Value != "" {
					t.Fatalf("%s must not open a verification round trip", code)
				}
			}
		})
	}
}

// A genuine provider failure — no recognised code at all — is unaffected by
// the pending-outcome dispatch added to handleCallback: it still ends in
// provider_unavailable, never a fabricated pending state.
func TestCallbackStillReportsProviderUnavailableOnGenuineFailure(t *testing.T) {
	provider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer provider.Close()
	h := workOSHarness(t, provider.URL)
	c := h.newClient()
	callback := startLoginToEmailVerification(t, h, c)
	if callback.StatusCode != http.StatusFound || callback.Header.Get("Location") != "/login?auth=provider_unavailable" {
		t.Fatalf("genuine failure: %d %q", callback.StatusCode, callback.Header.Get("Location"))
	}
}
