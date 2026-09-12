package ghapp_test

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync/atomic"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
)

// testPR is shared by the write-operation tests that all address the same
// pull request.
const testPR = 42

// The marker is absent: UpsertStickyComment lists (finding nothing) and
// POSTs a new comment. It never reaches a PATCH endpoint, because none is
// registered on this test server — a PATCH attempt would surface as the
// generic "GitHub answered 404" this test's error check would catch.
func TestUpsertStickyCommentPostsWhenMarkerAbsent(t *testing.T) {
	var listCalls, postCalls int32
	var postedBody string
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc(fmt.Sprintf("/repos/acme/widgets/issues/%d/comments", testPR),
			func(w http.ResponseWriter, r *http.Request) {
				switch r.Method {
				case http.MethodGet:
					atomic.AddInt32(&listCalls, 1)
					_ = json.NewEncoder(w).Encode([]any{
						map[string]any{"id": 1, "body": "unrelated human comment"},
					})
				case http.MethodPost:
					atomic.AddInt32(&postCalls, 1)
					var body struct {
						Body string `json:"body"`
					}
					_ = json.NewDecoder(r.Body).Decode(&body)
					postedBody = body.Body
					w.WriteHeader(http.StatusCreated)
					_ = json.NewEncoder(w).Encode(map[string]any{"id": 2})
				default:
					t.Fatalf("unexpected method %s", r.Method)
				}
			})
	})
	client := newTestClient(t, server.URL)
	if err := client.UpsertStickyComment(context.Background(), 1, "acme/widgets", testPR, "the report"); err != nil {
		t.Fatalf("UpsertStickyComment: %v", err)
	}
	if atomic.LoadInt32(&listCalls) == 0 {
		t.Fatal("the comment list was never read")
	}
	if got := atomic.LoadInt32(&postCalls); got != 1 {
		t.Fatalf("POST called %d times, want 1", got)
	}
	if !strings.HasPrefix(postedBody, ghapp.StickyCommentMarker) {
		t.Fatalf("posted body = %q, want it to start with the marker", postedBody)
	}
}

// The marker is present, but only on the second page of comments:
// UpsertStickyComment must follow the Link: rel="next" header before
// concluding the marker is absent, then PATCH the comment it found instead
// of posting a new one.
func TestUpsertStickyCommentPatchesWhenMarkerPresentAcrossPages(t *testing.T) {
	var patchCalls, postCalls int32
	var patchedBody string
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc(fmt.Sprintf("/repos/acme/widgets/issues/%d/comments", testPR),
			func(w http.ResponseWriter, r *http.Request) {
				switch r.Method {
				case http.MethodGet:
					page := r.URL.Query().Get("page")
					if page == "" || page == "1" {
						w.Header().Set("Link",
							fmt.Sprintf(`<http://%s/repos/acme/widgets/issues/%d/comments?page=2>; rel="next"`,
								r.Host, testPR))
						_ = json.NewEncoder(w).Encode([]any{
							map[string]any{"id": 1, "body": "an unrelated human comment"},
						})
						return
					}
					_ = json.NewEncoder(w).Encode([]any{
						map[string]any{"id": 7, "body": ghapp.StickyCommentMarker + "\nold report"},
					})
				case http.MethodPost:
					atomic.AddInt32(&postCalls, 1)
					w.WriteHeader(http.StatusCreated)
					_ = json.NewEncoder(w).Encode(map[string]any{"id": 99})
				default:
					t.Fatalf("unexpected method %s", r.Method)
				}
			})
		mux.HandleFunc("/repos/acme/widgets/issues/comments/7", func(w http.ResponseWriter, r *http.Request) {
			if r.Method != http.MethodPatch {
				t.Fatalf("expected PATCH, got %s", r.Method)
			}
			atomic.AddInt32(&patchCalls, 1)
			var body struct {
				Body string `json:"body"`
			}
			_ = json.NewDecoder(r.Body).Decode(&body)
			patchedBody = body.Body
			_ = json.NewEncoder(w).Encode(map[string]any{"id": 7})
		})
	})
	client := newTestClient(t, server.URL)
	if err := client.UpsertStickyComment(context.Background(), 1, "acme/widgets", testPR, "new report"); err != nil {
		t.Fatalf("UpsertStickyComment: %v", err)
	}
	if got := atomic.LoadInt32(&patchCalls); got != 1 {
		t.Fatalf("PATCH called %d times, want 1", got)
	}
	if got := atomic.LoadInt32(&postCalls); got != 0 {
		t.Fatalf("POST called %d times, want 0 (the marker was found on page 2)", got)
	}
	if !strings.Contains(patchedBody, "new report") {
		t.Fatalf("patched body = %q, want the new report text", patchedBody)
	}
}
