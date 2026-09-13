package ghapp_test

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
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
