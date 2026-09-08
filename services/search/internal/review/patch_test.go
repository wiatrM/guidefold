package review_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/review"
)

// An export is only useful if git accepts it. These tests hand the patch to
// `git apply --check` in a real repository, because "it looks like a diff" and
// "it applies" are different claims.

func gitRepo(t *testing.T, files map[string]string) string {
	t.Helper()
	if _, e := exec.LookPath("git"); e != nil {
		t.Skip("git is not installed; the patch cannot be verified here")
	}
	dir := t.TempDir()
	run := func(args ...string) {
		cmd := exec.Command("git", args...)
		cmd.Dir = dir
		cmd.Env = append(os.Environ(), "GIT_CONFIG_GLOBAL=/dev/null", "GIT_CONFIG_SYSTEM=/dev/null")
		if out, e := cmd.CombinedOutput(); e != nil {
			t.Fatalf("git %s: %v\n%s", strings.Join(args, " "), e, out)
		}
	}
	run("init", "-q")
	for path, body := range files {
		full := filepath.Join(dir, filepath.FromSlash(path))
		if e := os.MkdirAll(filepath.Dir(full), 0o755); e != nil {
			t.Fatal(e)
		}
		if e := os.WriteFile(full, []byte(body), 0o644); e != nil {
			t.Fatal(e)
		}
	}
	return dir
}

func applies(t *testing.T, dir, patch string) error {
	t.Helper()
	cmd := exec.Command("git", "apply", "--check", "-")
	cmd.Dir = dir
	cmd.Stdin = strings.NewReader(patch)
	cmd.Env = append(os.Environ(), "GIT_CONFIG_GLOBAL=/dev/null", "GIT_CONFIG_SYSTEM=/dev/null")
	if out, e := cmd.CombinedOutput(); e != nil {
		return &applyError{msg: strings.TrimSpace(string(out))}
	}
	return nil
}

type applyError struct{ msg string }

func (e *applyError) Error() string { return e.msg }

func TestNewFilePatchApplies(t *testing.T) {
	const body = "---\nname: rotate\n---\n\n# Rotate\n\n1. Pause.\n2. Rotate.\n"
	dir := gitRepo(t, map[string]string{".gitkeep": ""})
	patch := review.UnifiedPatch(".agents/skills/rotate/SKILL.md", "", body)
	if e := applies(t, dir, patch); e != nil {
		t.Fatalf("git apply --check refused the new-file patch: %v\n%s", e, patch)
	}
	// And it really writes the bytes the export promised.
	cmd := exec.Command("git", "apply", "-")
	cmd.Dir = dir
	cmd.Stdin = strings.NewReader(patch)
	if out, e := cmd.CombinedOutput(); e != nil {
		t.Fatalf("git apply: %v\n%s", e, out)
	}
	got, e := os.ReadFile(filepath.Join(dir, ".agents/skills/rotate/SKILL.md"))
	if e != nil {
		t.Fatal(e)
	}
	if string(got) != body {
		t.Fatalf("the applied file differs from the export:\n%q\n%q", string(got), body)
	}
}

func TestModificationPatchAppliesToTheSourceRevision(t *testing.T) {
	const before = "---\nname: rotate\n---\n\n# Rotate\n\n1. Pause.\n"
	const after = "---\nname: rotate\n---\n\n# Rotate\n\n1. Pause.\n2. Rotate.\n"
	path := "libs/auth-sdk/.agents/skills/rotate/SKILL.md"
	dir := gitRepo(t, map[string]string{path: before})
	patch := review.UnifiedPatch(path, before, after)
	if e := applies(t, dir, patch); e != nil {
		t.Fatalf("git apply --check refused the modification: %v\n%s", e, patch)
	}
	cmd := exec.Command("git", "apply", "-")
	cmd.Dir = dir
	cmd.Stdin = strings.NewReader(patch)
	if out, e := cmd.CombinedOutput(); e != nil {
		t.Fatalf("git apply: %v\n%s", e, out)
	}
	got, _ := os.ReadFile(filepath.Join(dir, filepath.FromSlash(path)))
	if string(got) != after {
		t.Fatalf("the applied file differs from the export:\n%q", string(got))
	}
}

// The patch is a whole-file hunk on purpose: it must refuse to apply to a file
// that has moved on since the proposal was approved, rather than merging into
// text nobody reviewed.
func TestModificationPatchRefusesAChangedFile(t *testing.T) {
	const before = "---\nname: rotate\n---\n\n# Rotate\n\n1. Pause.\n"
	const after = "---\nname: rotate\n---\n\n# Rotate\n\n1. Pause.\n2. Rotate.\n"
	path := "libs/auth-sdk/.agents/skills/rotate/SKILL.md"
	dir := gitRepo(t, map[string]string{path: before + "\nSomebody else edited this.\n"})
	if e := applies(t, dir, review.UnifiedPatch(path, before, after)); e == nil {
		t.Fatal("a patch against a stale revision must not apply")
	}
}

// A file with no trailing newline round-trips: silently adding one would make
// the patch describe a file that does not exist.
func TestPatchPreservesAMissingTrailingNewline(t *testing.T) {
	before := "one\ntwo"
	after := "one\ntwo\nthree"
	path := "notes.md"
	dir := gitRepo(t, map[string]string{path: before})
	patch := review.UnifiedPatch(path, before, after)
	if !strings.Contains(patch, "\\ No newline at end of file") {
		t.Fatalf("the patch hides the missing newline:\n%s", patch)
	}
	if e := applies(t, dir, patch); e != nil {
		t.Fatalf("git apply --check: %v\n%s", e, patch)
	}
	cmd := exec.Command("git", "apply", "-")
	cmd.Dir = dir
	cmd.Stdin = strings.NewReader(patch)
	if out, e := cmd.CombinedOutput(); e != nil {
		t.Fatalf("git apply: %v\n%s", e, out)
	}
	got, _ := os.ReadFile(filepath.Join(dir, path))
	if string(got) != after {
		t.Fatalf("round trip lost bytes: %q", string(got))
	}
}
