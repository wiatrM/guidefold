package ghapp_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
)

func TestExchangeUserCodeReturnsTheAccessToken(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/login/oauth/access_token" {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		if err := r.ParseForm(); err != nil {
			t.Fatal(err)
		}
		if r.Form.Get("client_id") != "app-id" || r.Form.Get("client_secret") != "app-secret" ||
			r.Form.Get("code") != "the-code" {
			t.Fatalf("unexpected form: %v", r.Form)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"access_token": "user-token", "token_type": "bearer"})
	}))
	t.Cleanup(server.Close)
	cfg := ghapp.UserOAuthConfig{ClientID: "app-id", ClientSecret: "app-secret", AuthBaseURL: server.URL}
	token, err := ghapp.ExchangeUserCode(context.Background(), cfg, "the-code")
	if err != nil {
		t.Fatalf("ExchangeUserCode: %v", err)
	}
	if token != "user-token" {
		t.Fatalf("token = %q", token)
	}
}

func TestExchangeUserCodeRefusesAGitHubError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "bad_verification_code"})
	}))
	t.Cleanup(server.Close)
	cfg := ghapp.UserOAuthConfig{ClientID: "app-id", ClientSecret: "app-secret", AuthBaseURL: server.URL}
	if _, err := ghapp.ExchangeUserCode(context.Background(), cfg, "stale-code"); err == nil {
		t.Fatal("expected an error for a refused code")
	}
}

func TestListUserInstallationsFollowsPagination(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/user/installations", func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer user-token" {
			t.Fatalf("missing bearer token: %q", r.Header.Get("Authorization"))
		}
		if r.URL.Query().Get("page") == "" {
			w.Header().Set("Link", `<http://`+r.Host+r.URL.Path+`?per_page=100&page=2>; rel="next"`)
			_ = json.NewEncoder(w).Encode(map[string]any{"installations": []map[string]any{
				{"id": 111, "account": map[string]any{"login": "acme"}}}})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"installations": []map[string]any{
			{"id": 222, "account": map[string]any{"login": "other"}}}})
	})
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	cfg := ghapp.UserOAuthConfig{APIBaseURL: server.URL}
	ids, err := ghapp.ListUserInstallations(context.Background(), cfg, "user-token")
	if err != nil {
		t.Fatalf("ListUserInstallations: %v", err)
	}
	if len(ids) != 2 || ids[0].ID != 111 || ids[0].AccountLogin != "acme" || ids[1].ID != 222 || ids[1].AccountLogin != "other" {
		t.Fatalf("ids = %v", ids)
	}
}
