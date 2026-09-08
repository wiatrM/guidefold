package importer_test

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

// U9 / ACT-01 — the order the acceptance run walks: a partial scan first, then
// a complete one over the same tree.
//
// A partial scan proves nothing about absence, so it removes nothing. The
// complete scan that follows it is the first evidence of the deletion, and it
// has to act on that evidence even though a *later* import (the partial one)
// already saw the file gone. The two live in the same catalog, so a bug in
// which drift compares against "the last import" rather than "what the catalog
// holds" would show up here and nowhere else.

// TestACompleteScanAfterAPartialOneStillArchivesTheRemovedSkill pins the
// sequence the acceptance run executes.
func TestACompleteScanAfterAPartialOneStillArchivesTheRemovedSkill(t *testing.T) {
	d := newDrifting(t)
	skillID := d.publish(t, adrPath)
	if e := os.Remove(filepath.Join(d.tree, filepath.FromSlash(adrPath))); e != nil {
		t.Fatal(e)
	}

	// A partial scan is not evidence of a deletion.
	d.push(t, "partial", false)
	publication, source := d.skill(t, skillID)
	if publication != "published" || source != "active" {
		t.Fatalf("a partial scan changed the skill: publication %q source %q", publication, source)
	}
	if items := d.queue(t); len(items) != 0 {
		t.Fatalf("a partial scan raised %d queue items: %v", len(items), items)
	}

	// The complete scan that follows it is.
	d.push(t, "complete", true)
	publication, source = d.skill(t, skillID)
	if publication != "archived" || source != "removed" {
		t.Fatalf("after the complete scan the skill is %q/%q, want archived/removed",
			publication, source)
	}
	found := false
	for _, item := range d.queue(t) {
		if item["reason"] == "source_removed" && item["skill_id"] == skillID {
			found = true
		}
	}
	if !found {
		t.Fatalf("no source_removed item after the complete scan: %v", d.queue(t))
	}
	// Archiving keeps the record: the revisions are still there to read.
	var revisions int
	if e := d.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skill_revisions WHERE org_id=$1::uuid AND skill_id=$2`,
		d.org, skillID).Scan(&revisions); e != nil {
		t.Fatal(e)
	}
	if revisions != 1 {
		t.Fatalf("archiving cost the skill its revisions (%d left)", revisions)
	}
}

// A skill the builder never puts in the catalog — a committed *generated* card,
// which `Index.build` excludes because it has no snapshot card — cannot drift.
// Deleting it is not a `source_removed`: there was no catalog identity to
// archive. This is the shape the acceptance run tripped over, so it is written
// down rather than left as folklore.
func TestRemovingAGeneratedCardRaisesNoQueueItem(t *testing.T) {
	d := newDrifting(t)
	const generated = ".agents/skills/hierarchy-index/SKILL.md"
	if _, e := os.Stat(filepath.Join(d.tree, filepath.FromSlash(generated))); e != nil {
		t.Skipf("the fixture no longer carries a generated card: %v", e)
	}
	var rows int
	if e := d.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid AND path=$2`,
		d.org, generated).Scan(&rows); e != nil {
		t.Fatal(e)
	}
	if rows != 0 {
		t.Fatalf("the generated card holds %d catalog rows; it should hold none", rows)
	}
	if e := os.RemoveAll(filepath.Join(d.tree, ".agents/skills/hierarchy-index")); e != nil {
		t.Fatal(e)
	}
	d.push(t, "without-the-generated-card", true)
	for _, item := range d.queue(t) {
		if item["reason"] == "source_removed" {
			t.Fatalf("removing a generated card looked like a deletion: %v", item)
		}
	}
}
