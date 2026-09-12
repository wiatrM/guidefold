package pivottest

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"io/fs"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// Monorepo copies the Meridian fixture into a private working directory, so a
// test can edit, rename and delete files without touching the repository.
func Monorepo(t *testing.T) string {
	t.Helper()
	dst := filepath.Join(Scratch(t, "tree"), "meridian")
	src := filepath.Join(Root(t), "examples", "monorepo")
	if e := copyTree(src, dst); e != nil {
		t.Fatal(e)
	}
	// The fixture ships a .guidefold cache; the scan ignores it and so do we.
	_ = os.RemoveAll(filepath.Join(dst, ".guidefold"))
	return dst
}

func copyTree(src, dst string) error {
	return filepath.WalkDir(src, func(path string, d fs.DirEntry, e error) error {
		if e != nil {
			return e
		}
		rel, e := filepath.Rel(src, path)
		if e != nil {
			return e
		}
		target := filepath.Join(dst, rel)
		if d.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		if !d.Type().IsRegular() {
			return nil
		}
		data, e := os.ReadFile(path)
		if e != nil {
			return e
		}
		if e := os.MkdirAll(filepath.Dir(target), 0o755); e != nil {
			return e
		}
		return os.WriteFile(target, data, 0o644)
	})
}

// ScanFiles reads a tree and classifies its files the way `guidefold scan`
// does: guidefold.yaml is the config, `.agents/skills/*/SKILL.md` are skills,
// the well-known root documents are documents, and anything else inside a skill
// package directory is a resource. Everything else is not imported.
func ScanFiles(t *testing.T, tree string) []map[string]any {
	t.Helper()
	skillDirs := map[string]bool{}
	var paths []string
	e := filepath.WalkDir(tree, func(path string, d fs.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() {
			if d.Name() == ".git" || d.Name() == ".guidefold" {
				return filepath.SkipDir
			}
			return nil
		}
		if !d.Type().IsRegular() {
			return nil
		}
		rel, e := filepath.Rel(tree, path)
		if e != nil {
			return e
		}
		rel = filepath.ToSlash(rel)
		paths = append(paths, rel)
		if strings.HasSuffix(rel, "/SKILL.md") && strings.Contains(rel, ".agents/skills/") {
			skillDirs[strings.TrimSuffix(rel, "/SKILL.md")] = true
		}
		return nil
	})
	if e != nil {
		t.Fatal(e)
	}
	sort.Strings(paths)
	files := []map[string]any{}
	for _, rel := range paths {
		kind := classify(rel, skillDirs)
		if kind == "" {
			continue
		}
		data, e := os.ReadFile(filepath.Join(tree, filepath.FromSlash(rel)))
		if e != nil {
			t.Fatal(e)
		}
		sum := sha256.Sum256(data)
		files = append(files, map[string]any{"path": rel, "sha256": hex.EncodeToString(sum[:]),
			"size": len(data), "kind": kind, "mode": "100644"})
	}
	return files
}

func classify(rel string, skillDirs map[string]bool) string {
	if rel == "guidefold.yaml" {
		return "config"
	}
	if strings.HasSuffix(rel, "/SKILL.md") && strings.Contains(rel, ".agents/skills/") {
		return "skill"
	}
	switch filepath.Base(rel) {
	case "AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md":
		return "document"
	}
	for dir := range skillDirs {
		if strings.HasPrefix(rel, dir+"/") {
			return "resource"
		}
	}
	return ""
}

// Manifest builds a `guidefold-import-manifest-v1` document over a tree.
func Manifest(t *testing.T, tree, org, repo string, complete bool) map[string]any {
	t.Helper()
	return map[string]any{
		"format": "guidefold-import-manifest-v1", "org": org, "repo": repo,
		"commit": "0123456789abcdef0123456789abcdef01234567", "complete": complete,
		"dirty": false, "cli_version": "test", "scan_profile": "default", "root": ".",
		"files": ScanFiles(t, tree), "excluded": []any{}, "aliases": []any{},
		"suggestions": []any{},
		"limits":      map[string]any{"max_files": 10000, "max_bytes": 104857600},
	}
}

// Push runs the whole client side of an import: create, upload every missing
// blob, finalize. It returns the import id.
func Push(t *testing.T, c *Client, org, repo, tree string, manifest map[string]any, key string) string {
	t.Helper()
	base := RepoBase(org, repo)
	status, created, _ := c.Call(t, Call{Method: http.MethodPost, Path: base + "/imports",
		Body: map[string]any{"idempotency_key": key, "manifest": manifest}, Key: key})
	if status != http.StatusCreated {
		t.Fatalf("create import: %d %v", status, created)
	}
	importID := created["import_id"].(string)
	byDigest := map[string]string{}
	for _, raw := range manifest["files"].([]map[string]any) {
		byDigest[raw["sha256"].(string)] = raw["path"].(string)
	}
	for _, sha := range created["missing_blobs"].([]any) {
		digest := sha.(string)
		path, ok := byDigest[digest]
		if !ok {
			t.Fatalf("the server asked for %s, which is not in the manifest", digest)
		}
		data, e := os.ReadFile(filepath.Join(tree, filepath.FromSlash(path)))
		if e != nil {
			t.Fatal(e)
		}
		status, body, _ := c.Call(t, Call{Method: http.MethodPut,
			Path: base + "/imports/" + importID + "/blobs/" + digest,
			Raw:  data, ContentType: "application/octet-stream"})
		if status != http.StatusCreated && status != http.StatusOK {
			t.Fatalf("upload %s: %d %v", path, status, body)
		}
	}
	status, finalized, _ := c.Call(t, Call{Method: http.MethodPost,
		Path: base + "/imports/" + importID + "/finalize",
		Body: map[string]any{"idempotency_key": key + ":finalize"}, Key: key + ":finalize"})
	if status != http.StatusOK {
		t.Fatalf("finalize: %d %v", status, finalized)
	}
	return importID
}

// Builder is the real Python builder, configured against this repository.
func Builder(t *testing.T) importer.Builder {
	t.Helper()
	root := Root(t)
	return &importer.PythonBuilder{Python: python(), Root: root,
		Script: filepath.Join(root, "tools", "worker", "build_tree.py")}
}

func python() string {
	if v := os.Getenv("GUIDEFOLD_PYTHON"); v != "" {
		return v
	}
	return "python3"
}

// RunParse leases and runs every queued import.parse job once, with the real
// builder over a real materialised tree. It returns how many it ran.
func (h *Harness) RunParse(t *testing.T, scratch string) int {
	t.Helper()
	parser := importer.NewParseWorker(h.Pool, h.Blobs, Builder(t), scratch)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	ran := 0
	for i := 0; i < 20; i++ {
		before := h.queued(t, importer.KindParse)
		if before == 0 {
			break
		}
		if e := worker.Run(ctx, h.Pool, "test-worker", parser.Handlers(),
			worker.Options{Once: true, Lease: 60 * time.Second}); e != nil {
			t.Fatal(e)
		}
		ran++
	}
	return ran
}

// RunParseOnce leases at most one import.parse job and reports whether it ran
// one. A test that needs a worker running *while* something else talks to the
// API calls it in a loop.
func (h *Harness) RunParseOnce(ctx context.Context, t *testing.T, scratch string) bool {
	t.Helper()
	if h.queued(t, importer.KindParse) == 0 {
		return false
	}
	parser := importer.NewParseWorker(h.Pool, h.Blobs, Builder(t), scratch)
	if e := worker.Run(ctx, h.Pool, "test-worker", parser.Handlers(),
		worker.Options{Once: true, Lease: 60 * time.Second}); e != nil && ctx.Err() == nil {
		t.Error(e)
	}
	return true
}

func (h *Harness) queued(t *testing.T, kind string) int {
	t.Helper()
	var n int
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.jobs WHERE kind=$1 AND state='queued'`, kind).Scan(&n); e != nil {
		t.Fatal(e)
	}
	return n
}

// Requeue puts a finished job back in the queue with its checkpoint intact,
// which is what a worker that died after a checkpoint leaves behind.
func (h *Harness) Requeue(t *testing.T, importID string) {
	t.Helper()
	if _, e := h.Pool.Exec(context.Background(), `UPDATE gfm.jobs
 SET state='queued',worker_id=NULL,lease_until=NULL,finished_at=NULL,result=NULL
 WHERE import_id=$1::uuid AND kind=$2`, importID, importer.KindParse); e != nil {
		t.Fatal(e)
	}
}

// JobOf reads one job of an import.
func (h *Harness) JobOf(t *testing.T, importID, kind string) *jobs.Job {
	t.Helper()
	var orgID string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT org_id::text FROM gfm.jobs WHERE import_id=$1::uuid AND kind=$2`,
		importID, kind).Scan(&orgID); e != nil {
		t.Fatalf("no %s job for import %s: %v", kind, importID, e)
	}
	list, e := jobs.New(h.Pool).List(context.Background(), orgID, importID, 10)
	if e != nil {
		t.Fatal(e)
	}
	for i := range list {
		if list[i].Kind == kind {
			return &list[i]
		}
	}
	t.Fatalf("no %s job for import %s", kind, importID)
	return nil
}

// RunGenerate leases and runs every queued proposal.generate job once, with the
// generator the caller supplies. Passing nil uses the environment's own choice,
// which is how the "no generator configured" path is exercised.
func (h *Harness) RunGenerate(t *testing.T, engine generator.Generator, recipe generator.Recipe) int {
	t.Helper()
	w, e := review.NewGenerateWorker(h.Pool, h.Blobs, h.Keyring)
	if e != nil {
		t.Fatal(e)
	}
	if engine != nil {
		w = w.WithGenerator(engine, recipe)
	}
	return h.drain(t, review.KindGenerate, w.Handlers())
}

// RunPublish leases and runs every queued publish.build job once, with the real
// Python builder and the supplied snapshot publisher.
func (h *Harness) RunPublish(t *testing.T, publisher review.Publisher, scratch string) int {
	t.Helper()
	w := review.NewPublishWorker(h.Pool, h.Blobs, Builder(t), publisher, scratch)
	return h.drain(t, review.KindPublish, w.Handlers())
}

// drain runs one kind until its queue is empty, at most twenty times so a
// handler that keeps requeueing fails the test rather than hanging it.
func (h *Harness) drain(t *testing.T, kind string, handlers map[string]worker.Handler) int {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	ran := 0
	for i := 0; i < 20; i++ {
		if h.queued(t, kind) == 0 {
			break
		}
		if e := worker.Run(ctx, h.Pool, "test-worker", handlers,
			worker.Options{Once: true, Lease: 60 * time.Second}); e != nil {
			t.Fatal(e)
		}
		ran++
	}
	return ran
}

// Jobs lists an organisation's jobs of one kind.
func (h *Harness) Jobs(t *testing.T, kind string) []jobs.Job {
	t.Helper()
	rows, e := h.Pool.Query(context.Background(),
		`SELECT org_id::text,job_id::text FROM gfm.jobs WHERE kind=$1 ORDER BY created_at`, kind)
	if e != nil {
		t.Fatal(e)
	}
	type ref struct{ org, job string }
	refs := []ref{}
	for rows.Next() {
		var r ref
		if e := rows.Scan(&r.org, &r.job); e != nil {
			rows.Close()
			t.Fatal(e)
		}
		refs = append(refs, r)
	}
	rows.Close()
	queue := jobs.New(h.Pool)
	out := []jobs.Job{}
	for _, r := range refs {
		j, e := queue.Get(context.Background(), r.org, r.job)
		if e != nil {
			t.Fatal(e)
		}
		out = append(out, *j)
	}
	return out
}
