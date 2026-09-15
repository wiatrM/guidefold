package importer_test

import (
	"os"
	"path/filepath"
	"testing"
)

const brokenCardPath = ".agents/skills/broken-card/SKILL.md"

// writeBrokenCard puts a SKILL.md the builder cannot parse into the tree. The
// frontmatter opens a flow sequence and never closes it, which is what the ten
// real cards of this repository did to the rehearsal import (D1): valid enough
// for a lenient harness loader, not valid YAML.
func writeBrokenCard(t *testing.T, tree string) {
	t.Helper()
	full := filepath.Join(tree, filepath.FromSlash(brokenCardPath))
	if e := os.MkdirAll(filepath.Dir(full), 0o755); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(full, []byte("---\nname: [unclosed\n---\n\n# broken\n"), 0o644); e != nil {
		t.Fatal(e)
	}
}

// Contract 1.16.0 / U9: a file the builder could not parse becomes one item in
// the owner's queue, with the builder's own reason on it.
//
// This is the half of U2.1 that publication no longer enforces. A partial
// import now publishes (API-CONTRACT §4.4), so the unparsable file has to be
// reported somewhere a person looks; otherwise "one broken file fails alone"
// would mean "one broken file disappears".
func TestAnUnparsableFileRaisesOneOwnerQueueItem(t *testing.T) {
	d := newDrifting(t)
	writeBrokenCard(t, d.tree)
	d.push(t, "with-a-broken-card", true)

	var found map[string]any
	for _, item := range d.queue(t) {
		if item["reason"] == "import_file_failed" {
			if found != nil {
				t.Fatalf("two import_file_failed items for one broken file: %v and %v", found, item)
			}
			found = item
		}
	}
	if found == nil {
		t.Fatalf("no import_file_failed item after an unparsable card: %v", d.queue(t))
	}
	// The item is about a file, not a skill: nothing in the catalog carries
	// this identity, so it cannot be a URN.
	if found["skill_id"] != "file:"+brokenCardPath {
		t.Fatalf("item skill_id = %v, want file:%s", found["skill_id"], brokenCardPath)
	}
	if found["state"] != "open" {
		t.Fatalf("the item is %v, want open", found["state"])
	}
	evidence, _ := found["evidence"].(map[string]any)
	if evidence["path"] != brokenCardPath {
		t.Fatalf("evidence.path = %v, want %s", evidence["path"], brokenCardPath)
	}
	if text, _ := evidence["error"].(string); text == "" {
		t.Fatalf("the item does not say why the file failed: %v", evidence)
	}
	if id, _ := evidence["import_id"].(string); id == "" {
		t.Fatalf("the item does not name the import it came from: %v", evidence)
	}
}

// A second import that still cannot parse the file does not ask the owner a
// second time. The partial unique index on open items is what enforces it —
// the same rule that keeps a repeated `source_changed` to one row (U9).
func TestASecondImportDoesNotDuplicateTheFailedFileItem(t *testing.T) {
	d := newDrifting(t)
	writeBrokenCard(t, d.tree)
	d.push(t, "with-a-broken-card", true)
	// Change an unrelated file so the manifest digest differs and the second
	// push is a real second import rather than a reuse of the first.
	d.editSkill(t, adrPath, "## An added section")
	d.push(t, "and-again", true)

	open := 0
	for _, item := range d.queue(t) {
		if item["reason"] == "import_file_failed" && item["state"] == "open" {
			open++
		}
	}
	if open != 1 {
		t.Fatalf("%d open import_file_failed items after two failing imports, want 1", open)
	}
}
