package ghapp_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
)

func TestOpenPullRequestReturnsTheHTMLURL(t *testing.T) {
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/pulls", func(w http.ResponseWriter, r *http.Request) {
			if r.Method != http.MethodPost {
				t.Fatalf("expected POST, got %s", r.Method)
			}
			var body struct{ Title, Head, Base, Body string }
			_ = json.NewDecoder(r.Body).Decode(&body)
			if body.Head != "guidefold/report" || body.Base != "main" {
				t.Errorf("head/base = %q/%q, want guidefold/report/main", body.Head, body.Base)
			}
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"html_url": "https://github.com/acme/widgets/pull/9",
			})
		})
	})
	client := newTestClient(t, server.URL)
	url, err := client.OpenPullRequest(context.Background(), 1, "acme/widgets", "guidefold/report", "main",
		"Guidefold proposals", "body")
	if err != nil {
		t.Fatalf("OpenPullRequest: %v", err)
	}
	if url != "https://github.com/acme/widgets/pull/9" {
		t.Fatalf("OpenPullRequest url = %q, want the created PR's html_url", url)
	}
}

// A retried job must not open a second pull request for a head branch that
// already has one open: GitHub's 422 "already exists" is turned into a
// lookup of the existing PR, and its URL is returned rather than an error.
func TestOpenPullRequestReturnsExistingURLInsteadOfFailing(t *testing.T) {
	var lookupCalled bool
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/pulls", func(w http.ResponseWriter, r *http.Request) {
			switch r.Method {
			case http.MethodPost:
				w.WriteHeader(http.StatusUnprocessableEntity)
				_ = json.NewEncoder(w).Encode(map[string]any{
					"message": "Validation Failed",
					"errors":  []any{map[string]any{"message": "A pull request already exists for acme:guidefold/report."}},
				})
			case http.MethodGet:
				lookupCalled = true
				if got := r.URL.Query().Get("head"); got != "acme:guidefold/report" {
					t.Errorf("lookup head query = %q, want acme:guidefold/report", got)
				}
				_ = json.NewEncoder(w).Encode([]any{
					map[string]any{"html_url": "https://github.com/acme/widgets/pull/5"},
				})
			default:
				t.Fatalf("unexpected method %s", r.Method)
			}
		})
	})
	client := newTestClient(t, server.URL)
	url, err := client.OpenPullRequest(context.Background(), 1, "acme/widgets", "guidefold/report", "main",
		"Guidefold proposals", "body")
	if err != nil {
		t.Fatalf("OpenPullRequest: %v", err)
	}
	if url != "https://github.com/acme/widgets/pull/5" {
		t.Fatalf("OpenPullRequest url = %q, want the existing PR's html_url", url)
	}
	if !lookupCalled {
		t.Fatal("the existing pull request was never looked up")
	}
}

// A 403 (missing permission) is distinguishable from a plain failure, and
// carries no token in its text even though the token it sent was real.
func TestOpenPullRequestOn403IsErrPermissionRefused(t *testing.T) {
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/pulls", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusForbidden)
			_ = json.NewEncoder(w).Encode(map[string]any{
				"message": "Resource not accessible by integration",
			})
		})
	})
	client := newTestClient(t, server.URL)
	_, err := client.OpenPullRequest(context.Background(), 1, "acme/widgets", "guidefold/report", "main", "t", "b")
	if !errors.Is(err, ghapp.ErrPermissionRefused) {
		t.Fatalf("OpenPullRequest on a 403 = %v, want ErrPermissionRefused", err)
	}
	// serverWithToken always answers the token exchange with this literal;
	// it must never appear in the returned error, even one about a refusal.
	if strings.Contains(err.Error(), "installation-token") {
		t.Fatalf("token leaked into the error: %v", err)
	}
}

func TestListPullRequestFilesFollowsSameOriginPagination(t *testing.T) {
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/pulls/7/files", func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Query().Get("page") == "2" {
				_ = json.NewEncoder(w).Encode([]map[string]string{{"filename": "second.go", "patch": "+second"}})
				return
			}
			w.Header().Set("Link", "<http://"+r.Host+r.URL.Path+"?page=2>; rel=\"next\"")
			_ = json.NewEncoder(w).Encode([]map[string]string{{"filename": "first.go", "patch": "+first"}})
		})
	})
	client := newTestClient(t, server.URL)

	files, err := client.ListPullRequestFiles(context.Background(), 1, "acme/widgets", 7)
	if err != nil {
		t.Fatalf("ListPullRequestFiles: %v", err)
	}
	if len(files) != 2 || files[0].Path != "first.go" || files[1].Path != "second.go" {
		t.Fatalf("ListPullRequestFiles = %#v, want both pages in order", files)
	}
}

func TestListPullRequestFilesRejectsCrossOriginPagination(t *testing.T) {
	var receivedAuthorization string
	attacker := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedAuthorization = r.Header.Get("Authorization")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`[]`))
	}))
	defer attacker.Close()

	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/pulls/7/files", func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Link", "<"+attacker.URL+"/steal?page=2>; rel=\"next\"")
			_ = json.NewEncoder(w).Encode([]map[string]string{{"filename": "first.go", "patch": "+first"}})
		})
	})
	client := newTestClient(t, server.URL)

	_, err := client.ListPullRequestFiles(context.Background(), 1, "acme/widgets", 7)
	if err == nil || !strings.Contains(err.Error(), "origin") {
		t.Fatalf("ListPullRequestFiles error = %v, want a cross-origin pagination error", err)
	}
	if receivedAuthorization != "" {
		t.Fatalf("cross-origin server received Authorization header %q", receivedAuthorization)
	}
	if strings.Contains(err.Error(), "installation-token") {
		t.Fatalf("installation token leaked into error: %v", err)
	}
}

func TestListPullRequestFilesRejectsIncompleteResultsAtPageLimit(t *testing.T) {
	requests := 0
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/pulls/7/files", func(w http.ResponseWriter, r *http.Request) {
			page, _ := strconv.Atoi(r.URL.Query().Get("page"))
			if page == 0 {
				page = 1
			}
			requests++
			w.Header().Set("Link", "<http://"+r.Host+r.URL.Path+"?page="+strconv.Itoa(page+1)+">; rel=\"next\"")
			_ = json.NewEncoder(w).Encode([]any{})
		})
	})
	client := newTestClient(t, server.URL)

	_, err := client.ListPullRequestFiles(context.Background(), 1, "acme/widgets", 7)
	if err == nil || !strings.Contains(err.Error(), "pagination") {
		t.Fatalf("ListPullRequestFiles error = %v, want a pagination limit error", err)
	}
	if requests != 50 {
		t.Fatalf("page requests = %d, want the 50-page safety limit", requests)
	}
}
