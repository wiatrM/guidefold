package importer

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// mapBlobs is the smallest blob store that answers Get: these tests are about
// what the worker does with the bytes, not about where they came from.
type mapBlobs map[string][]byte

func (m mapBlobs) Put(context.Context, string, string, []byte) (bool, error) { return false, nil }
func (m mapBlobs) Get(_ context.Context, _, sha string) ([]byte, error) {
	b, ok := m[sha]
	if !ok {
		return nil, ErrBlobNotFound
	}
	return b, nil
}
func (m mapBlobs) Exists(context.Context, string, []string) (map[string]bool, error) {
	return map[string]bool{}, nil
}

func digestOf(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

// W4 — safeJoin is the only thing between a client-supplied manifest and the
// worker's filesystem, and until now nothing tested it.
func TestSafeJoinRefusesEveryPathThatLeavesTheTree(t *testing.T) {
	root := t.TempDir()
	for _, rel := range []string{
		"", ".", "..", "../", "../escape", "a/../../b", "a/./b", "/etc/passwd",
		"a//b", `a\b`, "a/\x00b", "./a", "a/..",
	} {
		if got, e := safeJoin(root, rel); e == nil {
			t.Fatalf("safeJoin accepted %q and would have written %q", rel, got)
		}
	}
	for _, rel := range []string{"a", "a/b", "a/b/SKILL.md", "..a", "a..b"} {
		got, e := safeJoin(root, rel)
		if e != nil {
			t.Fatalf("safeJoin refused the legitimate path %q: %v", rel, e)
		}
		if !strings.HasPrefix(got, root+string(filepath.Separator)) {
			t.Fatalf("safeJoin(%q) escaped the tree: %q", rel, got)
		}
	}
}

// W4 — the job carries its own organisation claim, and it has to agree with the
// row the queue handed out before a single byte is read for that tenant. The
// check runs before any database access, so this needs no cluster.
func TestParseRefusesAJobWhosePayloadNamesAnotherOrganisation(t *testing.T) {
	w := &ParseWorker{blobs: mapBlobs{}, scratch: t.TempDir()}
	payload, _ := json.Marshal(parsePayload{SchemaVersion: PayloadVersion,
		OrgID: "00000000-0000-0000-0000-0000000000bb", RepoID: "repo",
		ImportID: "00000000-0000-0000-0000-0000000000cc"})
	task := &worker.Task{Job: &jobs.Job{
		OrgID:    "00000000-0000-0000-0000-0000000000aa",
		RepoID:   "repo",
		ImportID: "00000000-0000-0000-0000-0000000000cc",
		Payload:  payload,
	}}
	e := w.Run(context.Background(), task)
	if e == nil || !strings.Contains(e.Error(), "does not match its job row") {
		t.Fatalf("a cross-organisation payload was accepted: %v", e)
	}
}

// W1 — Manifest.Validate bounds the sizes the client *declared*. materialise
// writes the bytes that actually arrive, so it re-checks both: each blob
// against its declared size, and the running total against the same ceiling.
func TestMaterialiseRefusesABlobThatIsNotItsDeclaredSize(t *testing.T) {
	body := []byte("eight bytes and then some more")
	sha := digestOf(body)
	w := &ParseWorker{blobs: mapBlobs{sha: body}, scratch: t.TempDir()}
	tree := filepath.Join(t.TempDir(), "tree")
	manifest := &domain.Manifest{Files: []domain.File{
		{Path: "a/SKILL.md", SHA256: sha, Size: 1, Mode: "100644"},
	}}
	e := w.materialise(context.Background(), "org", tree, manifest)
	if e == nil || !strings.Contains(e.Error(), "declares 1 bytes") {
		t.Fatalf("a manifest that under-declares a blob was materialised: %v", e)
	}
	if _, statErr := os.Stat(filepath.Join(tree, "a", "SKILL.md")); statErr == nil {
		t.Fatal("the misdeclared file was written anyway")
	}
	// The same bytes, declared honestly, are written.
	manifest.Files[0].Size = int64(len(body))
	if e := w.materialise(context.Background(), "org", tree, manifest); e != nil {
		t.Fatalf("an honest manifest was refused: %v", e)
	}
	if b, readErr := os.ReadFile(filepath.Join(tree, "a", "SKILL.md")); readErr != nil ||
		string(b) != string(body) {
		t.Fatalf("materialised %q (%v)", b, readErr)
	}
}

// G8 — the manifest's mode is not the filesystem's. Nothing in the worker executes a
// materialised file, and the chart's emptyDir cannot be mounted noexec the way Compose
// mounts /work, so an executable bit from client input buys nothing and costs that.
func TestMaterialiseNeverWritesAnExecutableFile(t *testing.T) {
	body := []byte("#!/bin/sh\necho pwned\n")
	sha := digestOf(body)
	w := &ParseWorker{blobs: mapBlobs{sha: body}, scratch: t.TempDir()}
	tree := filepath.Join(t.TempDir(), "tree")
	manifest := &domain.Manifest{Files: []domain.File{
		{Path: "tools/run.sh", SHA256: sha, Size: int64(len(body)), Mode: "100755"},
	}}
	if e := w.materialise(context.Background(), "org", tree, manifest); e != nil {
		t.Fatal(e)
	}
	info, e := os.Stat(filepath.Join(tree, "tools", "run.sh"))
	if e != nil {
		t.Fatal(e)
	}
	if info.Mode().Perm()&0o111 != 0 {
		t.Fatalf("a manifest mode of 100755 produced %v on disk", info.Mode().Perm())
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("materialised mode %v, want 0600", info.Mode().Perm())
	}
}

func TestMaterialiseStopsAtTheTotalByteCeiling(t *testing.T) {
	// Two files whose honest sizes sum past MaxTotalBytes. Validate would have
	// caught this manifest; materialise must catch it too, because the tree is
	// what actually lands on the volume.
	half := make([]byte, 3<<20)
	sha := digestOf(half)
	w := &ParseWorker{blobs: mapBlobs{sha: half}, scratch: t.TempDir()}
	tree := filepath.Join(t.TempDir(), "tree")
	var files []domain.File
	for i := 0; i < (domain.MaxTotalBytes/len(half))+2; i++ {
		files = append(files, domain.File{
			Path:   filepath.Join("d", string(rune('a'+i%26)), "f"+string(rune('a'+i/26))+".md"),
			SHA256: sha, Size: int64(len(half)), Mode: "100644"})
	}
	e := w.materialise(context.Background(), "org", tree, &domain.Manifest{Files: files})
	if e == nil || !strings.Contains(e.Error(), "more than") {
		t.Fatalf("the worker wrote past the ceiling: %v", e)
	}
}
