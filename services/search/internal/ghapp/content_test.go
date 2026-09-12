package ghapp_test

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
)

// serverWithToken wires a valid installation-token endpoint plus whatever
// extra routes a test registers on the mux, so content tests do not each
// repeat the token-exchange boilerplate.
func serverWithToken(t *testing.T, register func(mux *http.ServeMux)) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/app/installations/1/access_tokens", func(w http.ResponseWriter, r *http.Request) {
		writeTokenResponse(w, "installation-token", time.Now().Add(time.Hour))
	})
	register(mux)
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return server
}

// A truncated tree is a named error, not a short list that looks complete.
func TestTruncatedTreeIsAnError(t *testing.T) {
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/git/trees/main", func(w http.ResponseWriter, r *http.Request) {
			_ = json.NewEncoder(w).Encode(map[string]any{
				"tree": []any{map[string]any{
					"path": ".agents/skills/foo/SKILL.md", "type": "blob",
				}},
				"truncated": true,
			})
		})
	})
	client := newTestClient(t, server.URL)
	_, err := client.ListSkillFiles(context.Background(), 1, "acme/widgets", "main")
	if !errors.Is(err, ghapp.ErrTreeTruncated) {
		t.Fatalf("ListSkillFiles on a truncated tree = %v, want ErrTreeTruncated", err)
	}
}

// The tree filter keeps AGENTS.md only at the root and SKILL.md only when it
// sits one or more directories below .agents/skills/, wherever in the
// repository that pair of directories occurs; it drops everything else,
// including a non-blob (directory) entry that happens to match the name.
func TestListSkillFilesMatchesOnlyAgentsAndSkillFiles(t *testing.T) {
	tree := []map[string]any{
		{"path": "AGENTS.md", "type": "blob"},
		{"path": "docs/AGENTS.md", "type": "blob"},                           // not the root
		{"path": ".agents/skills/foo/SKILL.md", "type": "blob"},              // root-level skill
		{"path": "services/api/.agents/skills/bar/SKILL.md", "type": "blob"}, // nested skill
		{"path": ".agents/skills/foo/bar/SKILL.md", "type": "blob"},          // nested under the skill dir
		{"path": ".agents/skills/SKILL.md", "type": "blob"},                  // no skill directory
		{"path": ".agents/skills/foo/SKILL.md", "type": "tree"},              // a directory, not a file
		{"path": "README.md", "type": "blob"},
		{"path": ".agents/skills/foo/SKILL.md.bak", "type": "blob"},
	}
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/git/trees/main", func(w http.ResponseWriter, r *http.Request) {
			_ = json.NewEncoder(w).Encode(map[string]any{"tree": tree, "truncated": false})
		})
	})
	client := newTestClient(t, server.URL)
	got, err := client.ListSkillFiles(context.Background(), 1, "acme/widgets", "main")
	if err != nil {
		t.Fatalf("ListSkillFiles: %v", err)
	}
	want := []string{
		".agents/skills/foo/SKILL.md",
		".agents/skills/foo/bar/SKILL.md",
		"AGENTS.md",
		"services/api/.agents/skills/bar/SKILL.md",
	}
	if !equalSets(got, want) {
		t.Fatalf("ListSkillFiles = %v, want %v", got, want)
	}
}

// A file over the ceiling is a named error, never a silently truncated read.
func TestOversizeFileIsAnError(t *testing.T) {
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/contents/big.md", func(w http.ResponseWriter, r *http.Request) {
			_ = json.NewEncoder(w).Encode(map[string]any{
				"content": "", "encoding": "base64", "size": ghapp.MaxFileBytes + 1, "type": "file",
			})
		})
	})
	client := newTestClient(t, server.URL)
	_, err := client.ReadFile(context.Background(), 1, "acme/widgets", "main", "big.md")
	if !errors.Is(err, ghapp.ErrFileTooLarge) {
		t.Fatalf("ReadFile on an oversize file = %v, want ErrFileTooLarge", err)
	}
}

// A file at or under the ceiling reads back exactly the bytes GitHub sent,
// base64 decoded.
func TestReadFileDecodesContent(t *testing.T) {
	want := []byte("---\nname: rotate\n---\n\n## Steps\n")
	server := serverWithToken(t, func(mux *http.ServeMux) {
		mux.HandleFunc("/repos/acme/widgets/contents/.agents/skills/rotate/SKILL.md",
			func(w http.ResponseWriter, r *http.Request) {
				if got := r.URL.Query().Get("ref"); got != "deadbeef" {
					t.Errorf("ref query = %q, want deadbeef", got)
				}
				_ = json.NewEncoder(w).Encode(map[string]any{
					"content":  base64.StdEncoding.EncodeToString(want),
					"encoding": "base64", "size": len(want), "type": "file",
				})
			})
	})
	client := newTestClient(t, server.URL)
	got, err := client.ReadFile(context.Background(), 1, "acme/widgets", "deadbeef", ".agents/skills/rotate/SKILL.md")
	if err != nil {
		t.Fatalf("ReadFile: %v", err)
	}
	if string(got) != string(want) {
		t.Fatalf("ReadFile = %q, want %q", got, want)
	}
}

func equalSets(got, want []string) bool {
	if len(got) != len(want) {
		return false
	}
	seen := map[string]bool{}
	for _, g := range got {
		seen[g] = true
	}
	for _, w := range want {
		if !seen[w] {
			return false
		}
	}
	return true
}
