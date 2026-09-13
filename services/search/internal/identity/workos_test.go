package identity_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/identity"
)

func fakeWorkOS(t *testing.T, handler http.HandlerFunc) *identity.WorkOS {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)
	return &identity.WorkOS{APIKey: "sk_test", ClientID: "client_1", Base: server.URL}
}

// Each of the four pending outcomes WorkOS documents for
// POST /user_management/authenticate is recognised, whatever HTTP status it
// arrives with — WorkOS's own reference never names one, so Authenticate must
// not depend on it (identity/workos.go).
func TestWorkOSAuthenticateRecognisesEveryDocumentedPendingOutcome(t *testing.T) {
	cases := []struct {
		code   string
		status int
	}{
		{"email_verification_required", http.StatusUnprocessableEntity},
		{"organization_selection_required", http.StatusBadRequest},
		{"mfa_enrollment", http.StatusUnprocessableEntity},
		{"mfa_challenge", http.StatusBadRequest},
	}
	for _, tc := range cases {
		t.Run(tc.code, func(t *testing.T) {
			w := fakeWorkOS(t, func(rw http.ResponseWriter, r *http.Request) {
				rw.Header().Set("Content-Type", "application/json")
				rw.WriteHeader(tc.status)
				body, _ := json.Marshal(map[string]string{
					"code": tc.code, "message": "pending",
					"pending_authentication_token": "ptok-" + tc.code, "email": "kay@example.test",
				})
				_, _ = rw.Write(body)
			})
			_, err := w.Authenticate(context.Background(), "code-1")
			pending, ok := err.(*identity.PendingAuthError)
			if !ok {
				t.Fatalf("Authenticate did not report a PendingAuthError for %s: %v", tc.code, err)
			}
			if pending.Code != tc.code {
				t.Fatalf("Code = %q, want %q", pending.Code, tc.code)
			}
			if tc.code == "email_verification_required" {
				if pending.PendingAuthenticationToken != "ptok-"+tc.code || pending.Email != "kay@example.test" {
					t.Fatalf("pending fields not carried: %+v", pending)
				}
			}
		})
	}
}

// A genuine transport/provider failure — including a non-200 response that
// names no recognised code at all — must still surface as a plain error, the
// one auth.go maps to provider_unavailable. The typed dispatch added for the
// pending outcomes must never swallow this.
func TestWorkOSAuthenticateUnrecognisedFailureIsNotPending(t *testing.T) {
	w := fakeWorkOS(t, func(rw http.ResponseWriter, r *http.Request) {
		rw.WriteHeader(http.StatusInternalServerError)
		_, _ = rw.Write([]byte(`not json`))
	})
	_, err := w.Authenticate(context.Background(), "code-1")
	if err == nil {
		t.Fatal("an unrecognised failure was accepted")
	}
	if _, ok := err.(*identity.PendingAuthError); ok {
		t.Fatalf("an unrecognised failure was reported as pending: %v", err)
	}
}

func TestWorkOSAuthenticateParsesOAuthTokensWhenPresent(t *testing.T) {
	w := fakeWorkOS(t, func(rw http.ResponseWriter, r *http.Request) {
		rw.Header().Set("Content-Type", "application/json")
		_, _ = rw.Write([]byte(`{"user":{"id":"u1","email":"a@example.test","first_name":"A","last_name":"B"},
"oauth_tokens":{"provider":"GitHubOAuth","access_token":"gho_x","refresh_token":"ghr_y",
"expires_at":"2026-01-01T00:00:00Z","scopes":["repo","read:org"]}}`))
	})
	result, err := w.Authenticate(context.Background(), "code-1")
	if err != nil {
		t.Fatal(err)
	}
	if result.OAuthTokens == nil {
		t.Fatal("oauth_tokens present in the response but not parsed")
	}
	if result.OAuthTokens.Provider != "GitHubOAuth" || result.OAuthTokens.AccessToken != "gho_x" ||
		result.OAuthTokens.RefreshToken != "ghr_y" || len(result.OAuthTokens.Scopes) != 2 {
		t.Fatalf("oauth tokens parsed incorrectly: %+v", result.OAuthTokens)
	}
}

// WorkOS examples for this field disagree on shape (a unix timestamp number vs. an RFC3339
// string); ExpiresAt is typed as raw JSON precisely so either one decodes, instead of a wrong
// guess failing OAuthTokens's own decode and discarding the whole object.
func TestWorkOSAuthenticateParsesOAuthTokensWithNumericExpiresAt(t *testing.T) {
	w := fakeWorkOS(t, func(rw http.ResponseWriter, r *http.Request) {
		rw.Header().Set("Content-Type", "application/json")
		_, _ = rw.Write([]byte(`{"user":{"id":"u1","email":"a@example.test","first_name":"A","last_name":"B"},
"oauth_tokens":{"provider":"GitHubOAuth","access_token":"gho_x","refresh_token":"ghr_y",
"expires_at":1735141800,"scopes":["repo"]}}`))
	})
	result, err := w.Authenticate(context.Background(), "code-1")
	if err != nil {
		t.Fatal(err)
	}
	if result.OAuthTokens == nil || result.OAuthTokens.AccessToken != "gho_x" {
		t.Fatalf("a numeric expires_at discarded the whole oauth_tokens object: %+v", result.OAuthTokens)
	}
}

func TestWorkOSAuthenticateWithoutOAuthTokens(t *testing.T) {
	w := fakeWorkOS(t, func(rw http.ResponseWriter, r *http.Request) {
		rw.Header().Set("Content-Type", "application/json")
		_, _ = rw.Write([]byte(`{"user":{"id":"u1","email":"a@example.test","first_name":"A","last_name":"B"}}`))
	})
	result, err := w.Authenticate(context.Background(), "code-1")
	if err != nil {
		t.Fatal(err)
	}
	if result.OAuthTokens != nil {
		t.Fatalf("oauth_tokens absent from the response but parsed anyway: %+v", result.OAuthTokens)
	}
}

// A connection without "Return OAuth tokens" enabled, or a future shape this
// service did not anticipate, must never fail sign-in over that one field.
func TestWorkOSAuthenticateToleratesUnexpectedOAuthTokensShape(t *testing.T) {
	w := fakeWorkOS(t, func(rw http.ResponseWriter, r *http.Request) {
		rw.Header().Set("Content-Type", "application/json")
		_, _ = rw.Write([]byte(`{"user":{"id":"u1","email":"a@example.test","first_name":"A","last_name":"B"},
"oauth_tokens":"not-an-object"}`))
	})
	result, err := w.Authenticate(context.Background(), "code-1")
	if err != nil {
		t.Fatalf("an unexpected oauth_tokens shape failed sign-in: %v", err)
	}
	if result.OAuthTokens != nil {
		t.Fatalf("an unparseable oauth_tokens should not have produced a value: %+v", result.OAuthTokens)
	}
	if result.User.Email != "a@example.test" {
		t.Fatalf("the rest of the user was not decoded: %+v", result.User)
	}
}

func TestWorkOSAuthenticateEmailVerificationCode(t *testing.T) {
	var seen struct {
		Grant, PendingToken, Code string
	}
	w := fakeWorkOS(t, func(rw http.ResponseWriter, r *http.Request) {
		var body map[string]string
		_ = json.NewDecoder(r.Body).Decode(&body)
		seen.Grant, seen.PendingToken, seen.Code = body["grant_type"], body["pending_authentication_token"], body["code"]
		if body["code"] != "123456" {
			rw.WriteHeader(http.StatusBadRequest)
			_, _ = rw.Write([]byte(`{"code":"invalid_grant","message":"wrong code"}`))
			return
		}
		rw.Header().Set("Content-Type", "application/json")
		_, _ = rw.Write([]byte(`{"user":{"id":"u1","email":"kay@example.test","first_name":"Kay","last_name":"Ng"}}`))
	})
	if _, err := w.AuthenticateEmailVerificationCode(context.Background(), "ptok-1", "000000"); err == nil {
		t.Fatal("a wrong code was accepted")
	}
	if seen.Grant != "urn:workos:oauth:grant-type:email-verification:code" || seen.PendingToken != "ptok-1" {
		t.Fatalf("the grant call was not built correctly: %+v", seen)
	}
	result, err := w.AuthenticateEmailVerificationCode(context.Background(), "ptok-1", "123456")
	if err != nil {
		t.Fatal(err)
	}
	if result.User.Email != "kay@example.test" {
		t.Fatalf("user %+v", result.User)
	}
}
