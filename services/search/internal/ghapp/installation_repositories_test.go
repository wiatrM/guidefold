package ghapp_test

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"testing"
)

// TestListInstallationRepositoriesFollowsPagination covers the completeness
// gap a webhook payload alone cannot fill for a large "All repositories"
// installation: two pages, both returned in full.
func TestListInstallationRepositoriesFollowsPagination(t *testing.T) {
	var seenPages []int
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/installation/repositories", func(w http.ResponseWriter, r *http.Request) {
			page := r.URL.Query().Get("page")
			if page == "" {
				page = "1"
			}
			n, _ := strconv.Atoi(page)
			seenPages = append(seenPages, n)
			if n == 1 {
				w.Header().Set("Link", `<http://`+r.Host+r.URL.Path+`?per_page=100&page=2>; rel="next"`)
				_ = json.NewEncoder(w).Encode(map[string]any{
					"total_count":  3,
					"repositories": []map[string]any{{"full_name": "acme/one"}, {"full_name": "acme/two"}},
				})
				return
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"total_count":  3,
				"repositories": []map[string]any{{"full_name": "acme/three"}},
			})
		})
	})
	client := newTestClient(t, server.URL)
	names, err := client.ListInstallationRepositories(context.Background(), 1)
	if err != nil {
		t.Fatalf("ListInstallationRepositories: %v", err)
	}
	if len(names) != 3 || names[0] != "acme/one" || names[1] != "acme/two" || names[2] != "acme/three" {
		t.Fatalf("names = %v, want all three pages", names)
	}
	if len(seenPages) != 2 {
		t.Fatalf("expected two page requests, got %v", seenPages)
	}
}

func TestListInstallationRepositoriesRejectsIncompleteResultsAtPageLimit(t *testing.T) {
	requests := 0
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/installation/repositories", func(w http.ResponseWriter, r *http.Request) {
			page, _ := strconv.Atoi(r.URL.Query().Get("page"))
			if page == 0 {
				page = 1
			}
			requests++
			w.Header().Set("Link", "<http://"+r.Host+r.URL.Path+"?page="+strconv.Itoa(page+1)+">; rel=\"next\"")
			_ = json.NewEncoder(w).Encode(map[string]any{"repositories": []any{}})
		})
	})
	client := newTestClient(t, server.URL)

	_, err := client.ListInstallationRepositories(context.Background(), 1)
	if err == nil || !strings.Contains(err.Error(), "pagination") {
		t.Fatalf("ListInstallationRepositories error = %v, want a pagination limit error", err)
	}
	if requests != 50 {
		t.Fatalf("page requests = %d, want the 50-page safety limit", requests)
	}
}
