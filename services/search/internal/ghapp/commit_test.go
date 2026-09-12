package ghapp_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
)

// A file path outside AGENTS.md and .agents/skills is refused before any
// request is made: the client points at an address nothing listens on, so
// any request that did leave this package would surface as a connection
// error rather than the named error this asserts on.
func TestCreateBranchCommitRefusesDisallowedPathBeforeAnyRequest(t *testing.T) {
	_, key := testAppKey(t)
	client, err := ghapp.New(ghapp.Config{AppID: "12345", PrivateKey: key, BaseURL: "http://127.0.0.1:1"})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	_, err = client.CreateBranchCommit(context.Background(), 1, "acme/widgets", "main", "guidefold/report",
		"add a proposal", map[string][]byte{"src/main.go": []byte("package main")})
	if !errors.Is(err, ghapp.ErrPathNotAllowed) {
		t.Fatalf("CreateBranchCommit on a disallowed path = %v, want ErrPathNotAllowed", err)
	}
}

// The commit is built with base_tree set to the base commit's own tree, so a
// file this call did not touch survives; the blob, tree, commit and ref
// creation calls all happen in the git-data-API order this operation
// promises, with no clone and no git binary involved.
func TestCreateBranchCommitUsesBaseTreeAndCreatesTheRef(t *testing.T) {
	var gotBaseTree string
	var gotEntries []map[string]any
	var gotParents []string
	var refCreated bool

	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/commits/main", func(w http.ResponseWriter, r *http.Request) {
			_ = json.NewEncoder(w).Encode(map[string]any{
				"sha": "base-commit-sha",
				"commit": map[string]any{
					"tree": map[string]any{"sha": "base-tree-sha"},
				},
			})
		})
		mux.HandleFunc("/repos/acme/widgets/git/blobs", func(w http.ResponseWriter, r *http.Request) {
			var body struct{ Content, Encoding string }
			_ = json.NewDecoder(r.Body).Decode(&body)
			if body.Encoding != "base64" {
				t.Errorf("blob encoding = %q, want base64", body.Encoding)
			}
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"sha": "blob-sha-" + body.Content[:4]})
		})
		mux.HandleFunc("/repos/acme/widgets/git/trees", func(w http.ResponseWriter, r *http.Request) {
			var body struct {
				BaseTree string           `json:"base_tree"`
				Tree     []map[string]any `json:"tree"`
			}
			_ = json.NewDecoder(r.Body).Decode(&body)
			gotBaseTree = body.BaseTree
			gotEntries = body.Tree
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"sha": "new-tree-sha"})
		})
		mux.HandleFunc("/repos/acme/widgets/git/commits", func(w http.ResponseWriter, r *http.Request) {
			var body struct {
				Tree    string   `json:"tree"`
				Parents []string `json:"parents"`
			}
			_ = json.NewDecoder(r.Body).Decode(&body)
			if body.Tree != "new-tree-sha" {
				t.Errorf("commit tree = %q, want new-tree-sha", body.Tree)
			}
			gotParents = body.Parents
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"sha": "new-commit-sha"})
		})
		mux.HandleFunc("/repos/acme/widgets/git/refs", func(w http.ResponseWriter, r *http.Request) {
			refCreated = true
			var body struct{ Ref, SHA string }
			_ = json.NewDecoder(r.Body).Decode(&body)
			if body.Ref != "refs/heads/guidefold/report" {
				t.Errorf("ref = %q, want refs/heads/guidefold/report", body.Ref)
			}
			if body.SHA != "new-commit-sha" {
				t.Errorf("ref sha = %q, want new-commit-sha", body.SHA)
			}
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"ref": body.Ref})
		})
	})

	client := newTestClient(t, server.URL)
	sha, err := client.CreateBranchCommit(context.Background(), 1, "acme/widgets", "main", "guidefold/report",
		"propose a rule", map[string][]byte{
			".agents/skills/rotate/SKILL.md": []byte("---\nname: rotate\n---\n"),
			"AGENTS.md":                      []byte("# Agents\n"),
		})
	if err != nil {
		t.Fatalf("CreateBranchCommit: %v", err)
	}
	if sha != "new-commit-sha" {
		t.Fatalf("CreateBranchCommit sha = %q, want new-commit-sha", sha)
	}
	if gotBaseTree != "base-tree-sha" {
		t.Fatalf("tree base_tree = %q, want base-tree-sha", gotBaseTree)
	}
	if len(gotEntries) != 2 {
		t.Fatalf("tree entries = %d, want 2", len(gotEntries))
	}
	if len(gotParents) != 1 || gotParents[0] != "base-commit-sha" {
		t.Fatalf("commit parents = %v, want [base-commit-sha]", gotParents)
	}
	if !refCreated {
		t.Fatal("the branch ref was never created")
	}
}

// A branch that already exists is fast-forwarded (PATCH), not treated as a
// failure: GitHub's "Reference already exists" 422 on ref creation is the
// expected shape on every push after the branch's first commit.
func TestCreateBranchCommitFastForwardsAnExistingBranch(t *testing.T) {
	var patched bool
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/commits/main", func(w http.ResponseWriter, r *http.Request) {
			_ = json.NewEncoder(w).Encode(map[string]any{
				"sha":    "base-sha",
				"commit": map[string]any{"tree": map[string]any{"sha": "base-tree"}},
			})
		})
		mux.HandleFunc("/repos/acme/widgets/git/blobs", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"sha": "blob-sha"})
		})
		mux.HandleFunc("/repos/acme/widgets/git/trees", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"sha": "tree-sha"})
		})
		mux.HandleFunc("/repos/acme/widgets/git/commits", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusCreated)
			_ = json.NewEncoder(w).Encode(map[string]any{"sha": "commit-sha-2"})
		})
		mux.HandleFunc("/repos/acme/widgets/git/refs", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusUnprocessableEntity)
			_ = json.NewEncoder(w).Encode(map[string]any{"message": "Reference already exists"})
		})
		mux.HandleFunc("/repos/acme/widgets/git/refs/heads/guidefold/report", func(w http.ResponseWriter, r *http.Request) {
			if r.Method != http.MethodPatch {
				t.Fatalf("expected PATCH to fast-forward, got %s", r.Method)
			}
			patched = true
			var body struct {
				SHA   string `json:"sha"`
				Force bool   `json:"force"`
			}
			_ = json.NewDecoder(r.Body).Decode(&body)
			if body.Force {
				t.Error("fast-forward set force:true, want false")
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"ref": "refs/heads/guidefold/report", "object": map[string]any{"sha": body.SHA},
			})
		})
	})
	client := newTestClient(t, server.URL)
	_, err := client.CreateBranchCommit(context.Background(), 1, "acme/widgets", "main", "guidefold/report",
		"propose a rule", map[string][]byte{"AGENTS.md": []byte("# Agents\n")})
	if err != nil {
		t.Fatalf("CreateBranchCommit: %v", err)
	}
	if !patched {
		t.Fatal("the existing branch was never fast-forwarded")
	}
}
