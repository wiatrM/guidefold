package importer

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
)

// Builder is the outbound port that turns a materialised tree into a serving
// snapshot and a per-skill inventory.
//
// There is exactly one implementation and it is deliberately not Go: the
// snapshot, the scope map and the frontmatter rules already exist in the CLI,
// and a second implementation in another language is the fastest way to publish
// a snapshot the ranker disagrees with. The worker image carries the pinned
// Python builder; the API image carries no Python at all (PIVOT-ARCHITECTURE,
// "Co wdrażamy").
type Builder interface {
	Build(ctx context.Context, tree, repoID, commit, outDir string) (*domain.Snapshot, *domain.Inventory, error)
}

// BuildTimeout bounds one builder run. A tree that cannot be built in this time
// is a failed import, not a worker that never comes back.
const BuildTimeout = 10 * time.Minute

// PythonBuilder runs tools/worker/build_tree.py. It executes the repository's
// own trusted script and never anything from the imported tree: the tree is
// data, and the worker does not run a customer's code (U3, security baseline).
type PythonBuilder struct {
	// Python is the interpreter, from GUIDEFOLD_PYTHON (default python3).
	Python string
	// Script is the builder, from GUIDEFOLD_BUILD_TREE, resolved against Root
	// when relative (default tools/worker/build_tree.py).
	Script string
	// Root is the checkout the builder runs in, from GUIDEFOLD_REPO_ROOT.
	Root string
}

// NewPythonBuilder reads the worker's builder configuration from the
// environment. Nothing here is caller-supplied: a path from an HTTP request
// must never reach an exec argument.
func NewPythonBuilder() *PythonBuilder {
	root := os.Getenv("GUIDEFOLD_REPO_ROOT")
	if root == "" {
		root, _ = os.Getwd()
	}
	script := os.Getenv("GUIDEFOLD_BUILD_TREE")
	if script == "" {
		script = "tools/worker/build_tree.py"
	}
	if !filepath.IsAbs(script) {
		script = filepath.Join(root, script)
	}
	python := os.Getenv("GUIDEFOLD_PYTHON")
	if python == "" {
		python = "python3"
	}
	return &PythonBuilder{Python: python, Script: script, Root: root}
}

// BuildError is a builder run that failed. It carries the interpreter's own
// last line, which is what tells an owner that a tree has no guidefold.yaml.
type BuildError struct {
	Reason string
	Output string
}

func (e *BuildError) Error() string {
	if e.Output == "" {
		return e.Reason
	}
	return e.Reason + ": " + e.Output
}

// Build runs the builder over one materialised tree and reads back both files
// it writes.
func (b *PythonBuilder) Build(ctx context.Context, tree, repoID, commit, outDir string) (*domain.Snapshot, *domain.Inventory, error) {
	if e := os.MkdirAll(outDir, 0o700); e != nil {
		return nil, nil, fmt.Errorf("create builder output directory: %w", e)
	}
	snapshotPath := filepath.Join(outDir, "snapshot.json")
	inventoryPath := filepath.Join(outDir, "inventory.json")
	run, cancel := context.WithTimeout(ctx, BuildTimeout)
	defer cancel()
	cmd := exec.CommandContext(run, b.Python, b.Script,
		"--tree", tree, "--repo-id", repoID, "--commit", commit,
		"--output", snapshotPath, "--inventory", inventoryPath)
	cmd.Dir = b.Root
	// The builder imports the repository's own modules; it needs no environment
	// from the request and gets none.
	cmd.Env = append(os.Environ(), "PYTHONDONTWRITEBYTECODE=1")
	var stderr bytes.Buffer
	cmd.Stdout = &bytes.Buffer{}
	cmd.Stderr = &stderr
	if e := cmd.Run(); e != nil {
		return nil, nil, &BuildError{Reason: "build_tree_failed", Output: lastLine(stderr.String())}
	}
	snapshot := &domain.Snapshot{}
	if e := readJSON(snapshotPath, snapshot); e != nil {
		return nil, nil, &BuildError{Reason: "snapshot_unreadable", Output: e.Error()}
	}
	inventory := &domain.Inventory{}
	if e := readJSON(inventoryPath, inventory); e != nil {
		return nil, nil, &BuildError{Reason: "inventory_unreadable", Output: e.Error()}
	}
	if inventory.Format != domain.InventoryFormat {
		return nil, nil, &BuildError{Reason: "unsupported_inventory_format", Output: inventory.Format}
	}
	return snapshot, inventory, nil
}

func readJSON(path string, into any) error {
	raw, e := os.ReadFile(path)
	if e != nil {
		return e
	}
	return json.Unmarshal(raw, into)
}

// lastLine keeps the interpreter's final message and drops the traceback, so
// the import's error field names the cause without pasting a stack into an API
// response. It is also capped: an error message is not a log sink.
func lastLine(s string) string {
	lines := strings.Split(strings.TrimRight(s, "\n"), "\n")
	out := strings.TrimSpace(lines[len(lines)-1])
	if len(out) > 300 {
		out = out[:300]
	}
	return out
}

var _ Builder = (*PythonBuilder)(nil)
