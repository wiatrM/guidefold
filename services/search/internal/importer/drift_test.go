package importer_test

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

// U9 / P13 — what a second import means for a skill that is already published.
//
// The rule the tests below pin down is that drift is an observation, not a
// decision: a changed source asks for a review, a removed source archives an
// identity, and neither ever deletes a revision or edits a skill's body.

const adrPath = ".agents/skills/adr-process/SKILL.md"

type drifting struct {
	*fixture
	scratch string
}

func newDrifting(t *testing.T) *drifting {
	t.Helper()
	f := newFixture(t)
	d := &drifting{fixture: f, scratch: pivottest.Scratch(t, "drift")}
	d.push(t, "first", true)
	return d
}

// push runs one whole import of the current tree and parses it.
func (d *drifting) push(t *testing.T, key string, complete bool) string {
	t.Helper()
	id := pivottest.Push(t, d.owner, d.org, d.repo, d.tree, d.manifest(t, complete), key)
	d.h.RunParse(t, d.scratch)
	return id
}

// publish marks a skill published, which is the state the review module would
// leave behind. Only a published skill can drift into needs_review.
func (d *drifting) publish(t *testing.T, path string) string {
	t.Helper()
	var skillID, revisionID string
	if e := d.h.Pool.QueryRow(context.Background(), `UPDATE gfm.skills
 SET publication_status='published',published_revision_id=current_revision_id
 WHERE org_id=$1::uuid AND path=$2 RETURNING skill_id,current_revision_id`,
		d.org, path).Scan(&skillID, &revisionID); e != nil {
		t.Fatalf("no skill at %s: %v", path, e)
	}
	return skillID
}

func (d *drifting) skill(t *testing.T, skillID string) (publication, source string) {
	t.Helper()
	if e := d.h.Pool.QueryRow(context.Background(),
		`SELECT publication_status,source_status FROM gfm.skills
 WHERE org_id=$1::uuid AND skill_id=$2`, d.org, skillID).Scan(&publication, &source); e != nil {
		t.Fatal(e)
	}
	return publication, source
}

func (d *drifting) queue(t *testing.T) []map[string]any {
	t.Helper()
	rows, e := d.h.Pool.Query(context.Background(),
		`SELECT skill_id,reason,COALESCE(revision_id,''),evidence::text,state FROM gfm.owner_queue
 WHERE org_id=$1::uuid ORDER BY skill_id,reason`, d.org)
	if e != nil {
		t.Fatal(e)
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var skillID, reason, revision, evidence, state string
		if e := rows.Scan(&skillID, &reason, &revision, &evidence, &state); e != nil {
			t.Fatal(e)
		}
		var decoded map[string]any
		_ = json.Unmarshal([]byte(evidence), &decoded)
		out = append(out, map[string]any{"skill_id": skillID, "reason": reason,
			"revision_id": revision, "evidence": decoded, "state": state})
	}
	return out
}

func (d *drifting) editSkill(t *testing.T, path, marker string) {
	t.Helper()
	full := filepath.Join(d.tree, filepath.FromSlash(path))
	raw, e := os.ReadFile(full)
	if e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(full, append(raw, []byte("\n"+marker+"\n")...), 0o644); e != nil {
		t.Fatal(e)
	}
}

// A changed source under a published skill asks for a review and keeps the old
// revision. The previous snapshot goes on serving; nothing is deleted.
func TestAChangedSourceMarksAPublishedSkillNeedsReview(t *testing.T) {
	d := newDrifting(t)
	skillID := d.publish(t, adrPath)
	d.editSkill(t, adrPath, "## An added section")
	importID := d.push(t, "second", true)

	publication, source := d.skill(t, skillID)
	if publication != "needs_review" || source != "active" {
		t.Fatalf("publication %q source %q", publication, source)
	}
	items := d.queue(t)
	if len(items) != 1 {
		t.Fatalf("owner queue holds %d items: %v", len(items), items)
	}
	item := items[0]
	if item["reason"] != "source_changed" || item["skill_id"] != skillID {
		t.Fatalf("queue item %v", item)
	}
	evidence := item["evidence"].(map[string]any)
	if evidence["import_id"] != importID {
		t.Fatalf("the queue item does not name the import that caused it: %v", evidence)
	}
	// Both revisions survive; the change never overwrote the published bytes.
	var revisions int
	if e := d.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skill_revisions WHERE org_id=$1::uuid AND skill_id=$2`,
		d.org, skillID).Scan(&revisions); e != nil {
		t.Fatal(e)
	}
	if revisions != 2 {
		t.Fatalf("the skill holds %d revisions after one edit", revisions)
	}
}

// A skill that is only a draft changes quietly: there is nothing published to
// review, so the owner is not asked a question they did not need.
func TestAChangedDraftRaisesNoQueueItem(t *testing.T) {
	d := newDrifting(t)
	d.editSkill(t, adrPath, "## An added section")
	d.push(t, "second", true)
	if items := d.queue(t); len(items) != 0 {
		t.Fatalf("a draft change raised %d queue items: %v", len(items), items)
	}
}

// A file that is gone from a *complete* scan archives its skill and keeps every
// revision. The decision to delete belongs to the owner, not to the import.
func TestARemovedSourceArchivesTheSkillOnACompleteScan(t *testing.T) {
	d := newDrifting(t)
	skillID := d.publish(t, adrPath)
	if e := os.Remove(filepath.Join(d.tree, filepath.FromSlash(adrPath))); e != nil {
		t.Fatal(e)
	}
	d.push(t, "second", true)

	publication, source := d.skill(t, skillID)
	if publication != "archived" || source != "removed" {
		t.Fatalf("publication %q source %q", publication, source)
	}
	items := d.queue(t)
	if len(items) != 1 || items[0]["reason"] != "source_removed" {
		t.Fatalf("owner queue %v", items)
	}
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

// A partial scan proves nothing about absence, so it removes nothing.
func TestAPartialScanNeverRemovesAnything(t *testing.T) {
	d := newDrifting(t)
	skillID := d.publish(t, adrPath)
	if e := os.Remove(filepath.Join(d.tree, filepath.FromSlash(adrPath))); e != nil {
		t.Fatal(e)
	}
	d.push(t, "second", false)

	publication, source := d.skill(t, skillID)
	if publication != "published" || source != "active" {
		t.Fatalf("a partial scan changed the skill: publication %q source %q", publication, source)
	}
	if items := d.queue(t); len(items) != 0 {
		t.Fatalf("a partial scan raised %d queue items: %v", len(items), items)
	}
}

// Re-running the same manifest is a no-op: no new revisions and, above all, no
// second queue item for a question the owner has already been asked.
func TestRerunningTheSameManifestAddsNoQueueItems(t *testing.T) {
	d := newDrifting(t)
	d.publish(t, adrPath)
	d.editSkill(t, adrPath, "## An added section")
	d.push(t, "second", true)
	first := d.queue(t)
	if len(first) != 1 {
		t.Fatalf("expected one item after the change, got %v", first)
	}

	// The same tree again: same digest, same import, and the parse job is
	// re-run from scratch.
	importID := pivottest.Push(t, d.owner, d.org, d.repo, d.tree, d.manifest(t, true), "third")
	d.h.Requeue(t, importID)
	if _, e := d.h.Pool.Exec(context.Background(),
		`UPDATE gfm.imports SET state='queued' WHERE import_id=$1::uuid`, importID); e != nil {
		t.Fatal(e)
	}
	d.h.RunParse(t, d.scratch)

	second := d.queue(t)
	if len(second) != len(first) {
		t.Fatalf("a repeated import grew the owner queue from %d to %d items", len(first), len(second))
	}
}

// U1.5 — an alias keeps a moved skill's identity: no new skill, no removal.
func TestAnAliasKeepsTheIdentityOfARenamedSkill(t *testing.T) {
	d := newDrifting(t)
	skillID := d.publish(t, adrPath)
	moved := ".agents/skills/adr-conventions/SKILL.md"
	if e := os.Rename(filepath.Join(d.tree, ".agents/skills/adr-process"),
		filepath.Join(d.tree, ".agents/skills/adr-conventions")); e != nil {
		t.Fatal(e)
	}
	manifest := d.manifest(t, true)
	manifest["aliases"] = []any{map[string]any{"from": adrPath, "to": moved}}
	importID := pivottest.Push(t, d.owner, d.org, d.repo, d.tree, manifest, "renamed")
	d.h.RunParse(t, d.scratch)
	_ = importID

	var path, publication string
	if e := d.h.Pool.QueryRow(context.Background(),
		`SELECT path,publication_status FROM gfm.skills WHERE org_id=$1::uuid AND skill_id=$2`,
		d.org, skillID).Scan(&path, &publication); e != nil {
		t.Fatalf("the aliased skill lost its identity: %v", e)
	}
	if path != moved {
		t.Fatalf("the skill still points at %s", path)
	}
	for _, item := range d.queue(t) {
		if item["reason"] == "source_removed" {
			t.Fatalf("an aliased rename looked like a deletion: %v", item)
		}
	}
	var skills int
	if e := d.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid`, d.org).Scan(&skills); e != nil {
		t.Fatal(e)
	}
	if skills != fixtureSkills {
		t.Fatalf("the rename produced %d skills, want the original %d", skills, fixtureSkills)
	}
}

// Without an alias the same rename is a new skill plus a removal, and the owner
// is told so instead of the old identity disappearing silently.
func TestARenameWithoutAnAliasRemovesTheOldIdentity(t *testing.T) {
	d := newDrifting(t)
	skillID := d.publish(t, adrPath)
	if e := os.Rename(filepath.Join(d.tree, ".agents/skills/adr-process"),
		filepath.Join(d.tree, ".agents/skills/adr-conventions")); e != nil {
		t.Fatal(e)
	}
	d.push(t, "renamed", true)

	publication, source := d.skill(t, skillID)
	if publication != "archived" || source != "removed" {
		t.Fatalf("the old identity is %q/%q", publication, source)
	}
	found := false
	for _, item := range d.queue(t) {
		if item["reason"] == "source_removed" && item["skill_id"] == skillID {
			found = true
		}
	}
	if !found {
		t.Fatalf("the owner was not told about the removal: %v", d.queue(t))
	}
	var skills int
	if e := d.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid`, d.org).Scan(&skills); e != nil {
		t.Fatal(e)
	}
	if skills != fixtureSkills+1 {
		t.Fatalf("an unaliased rename left %d skills, want %d (%d plus the new identity)",
			skills, fixtureSkills+1, fixtureSkills)
	}
}
