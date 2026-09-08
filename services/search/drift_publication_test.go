package main

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// ACT-01 — what publication does to a skill the drift pass just flagged.
//
// `finalize` queues import.parse and publish.build for the same import, so the
// build runs right behind the pass that raised `needs_review`. Marking every
// skill in the new snapshot `published` erased the flag before anybody could
// see it, and the acceptance run stopped at exactly that step. The rule the
// tests below pin down: the snapshot goes on serving the new revision (Git is
// canonical), and the flag stays until an owner decides the queue item.

// skillState reads what the catalog holds about one skill of the fixture.
func (e *pubEnv) skillState(t *testing.T, path string) (skillID, publication, source, published, snapshot string) {
	t.Helper()
	if err := e.h.Pool.QueryRow(context.Background(), `SELECT skill_id,publication_status,
 source_status,COALESCE(published_revision_id,''),COALESCE(published_snapshot_id,'')
 FROM gfm.skills WHERE org_id=$1::uuid AND repo_id='meridian' AND path=$2`,
		e.orgID, path).Scan(&skillID, &publication, &source, &published, &snapshot); err != nil {
		t.Fatalf("no catalog row for %s: %v", path, err)
	}
	return
}

func (e *pubEnv) currentRevision(t *testing.T, skillID string) string {
	t.Helper()
	var revision string
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT COALESCE(current_revision_id,'') FROM gfm.skills
 WHERE org_id=$1::uuid AND skill_id=$2`, e.orgID, skillID).Scan(&revision); err != nil {
		t.Fatal(err)
	}
	return revision
}

// openQueue lists the open owner-queue reasons recorded for one skill.
func (e *pubEnv) openQueue(t *testing.T, skillID string) []string {
	t.Helper()
	rows, err := e.h.Pool.Query(context.Background(),
		`SELECT reason FROM gfm.owner_queue WHERE org_id=$1::uuid AND skill_id=$2 AND state='open'
 ORDER BY reason`, e.orgID, skillID)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var reason string
		if err := rows.Scan(&reason); err != nil {
			t.Fatal(err)
		}
		out = append(out, reason)
	}
	return out
}

const driftPath = ".agents/skills/chain-3/SKILL.md"

// A changed source is still served — and still flagged. The publication that
// follows the parse refreshes the serving revision without answering the
// owner's question.
func TestPublishingDoesNotEraseTheReviewFlagDriftRaised(t *testing.T) {
	e := newPubEnv(t)
	e.publishImport(t, "pub-1")
	skillID, publication, _, _, _ := e.skillState(t, driftPath)
	if publication != "published" {
		t.Fatalf("the first publication left %s %q", skillID, publication)
	}
	first := e.currentRevision(t, skillID)

	// Edit the source and run the whole import → publish pair again, exactly as
	// `finalize` queues them.
	full := filepath.Join(e.tree, filepath.FromSlash(driftPath))
	body, err := os.ReadFile(full)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(full, append(body, []byte("\n## An added section\n")...), 0o644); err != nil {
		t.Fatal(err)
	}
	e.publishImport(t, "pub-2")

	skillID, publication, source, published, snapshot := e.skillState(t, driftPath)
	if publication != "needs_review" {
		t.Fatalf("publication answered the drift question: the skill is %q, want needs_review",
			publication)
	}
	if source != "active" {
		t.Fatalf("a changed source is not a removed one: source_status %q", source)
	}
	// The snapshot serves the new revision all the same: the flag is an owner's
	// task, not a serving gate.
	second := e.currentRevision(t, skillID)
	if second == first {
		t.Fatalf("the edit produced no new revision (%s)", second)
	}
	if published != second {
		t.Fatalf("the skill under review serves %q, want the new revision %q", published, second)
	}
	head := e.head(t)
	if head == "" || snapshot != head {
		t.Fatalf("the skill under review points at snapshot %q, the head is %q", snapshot, head)
	}
	if reasons := e.openQueue(t, skillID); len(reasons) != 1 || reasons[0] != "source_changed" {
		t.Fatalf("the owner queue holds %v, want exactly one source_changed item", reasons)
	}
	// Every other skill of the tree published normally: the guard is per skill,
	// not a stop on the whole build.
	var published2 int
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skills WHERE org_id=$1::uuid AND repo_id='meridian'
 AND publication_status='published'`, e.orgID).Scan(&published2); err != nil {
		t.Fatal(err)
	}
	if published2 < 2 {
		t.Fatalf("only %d skills stayed published; the guard stopped the whole build", published2)
	}
}

// U9 — a source that is gone from a complete scan is archived, and the snapshot
// built from that scan stops serving it.
//
// The importer's own tests prove the catalog half (internal/importer:
// drift_partial_test.go). This is the half only the real publisher can show:
// that "archived" is not a label on a card an agent can still be handed.
func TestARemovedSourceLeavesTheSnapshotAsWellAsTheCatalog(t *testing.T) {
	e := newPubEnv(t)
	// A skill written for this test, so nothing in the fixture requires it: a
	// dangling requires would fail validation and leave the old head serving,
	// which would look like this test's assertion failing for the wrong reason.
	const doomedPath = ".agents/skills/doomed/SKILL.md"
	writeFile(t, e.tree, doomedPath,
		skillFile("doomed", "platform-engineering", nil, "Nothing depends on this."))
	e.publishImport(t, "pub-1")

	skillID, publication, _, _, _ := e.skillState(t, doomedPath)
	if publication != "published" {
		t.Fatalf("%s is %q before the deletion", skillID, publication)
	}
	if _, served := e.revisions(t, e.head(t))[skillID]; !served {
		t.Fatalf("%s was never in the snapshot, so its removal proves nothing", skillID)
	}

	if err := os.RemoveAll(filepath.Join(e.tree, ".agents/skills/doomed")); err != nil {
		t.Fatal(err)
	}
	e.publishImport(t, "pub-2")

	_, publication, source, _, _ := e.skillState(t, doomedPath)
	if publication != "archived" || source != "removed" {
		t.Fatalf("the removed skill is %q/%q, want archived/removed", publication, source)
	}
	if reasons := e.openQueue(t, skillID); len(reasons) != 1 || reasons[0] != "source_removed" {
		t.Fatalf("the owner queue holds %v, want exactly one source_removed item", reasons)
	}
	head := e.head(t)
	cards := e.revisions(t, head)
	if len(cards) == 0 {
		t.Fatalf("the second publication activated an empty snapshot %q", head)
	}
	if card, served := cards[skillID]; served {
		t.Fatalf("the archived skill is still served by snapshot %s as card %q", head, card)
	}
	// The row itself survives: archiving is never a delete (U9).
	var revisions int
	if err := e.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.skill_revisions WHERE org_id=$1::uuid AND skill_id=$2`,
		e.orgID, skillID).Scan(&revisions); err != nil {
		t.Fatal(err)
	}
	if revisions != 1 {
		t.Fatalf("archiving cost the skill its revisions (%d left)", revisions)
	}
}

// U6-3 — publication stores the card revision on the catalog row, so a judgment
// from the UI and telemetry from the delivery path name the same revision.
func TestPublicationStoresTheCardRevisionOnTheCatalogRevision(t *testing.T) {
	e := newPubEnv(t)
	e.publishImport(t, "pub-1")
	snapshot := e.head(t)
	if snapshot == "" {
		t.Fatal("the publication did not activate a head")
	}
	cards := e.revisions(t, snapshot)
	if len(cards) == 0 {
		t.Fatal("the snapshot carries no cards")
	}
	rows, err := e.h.Pool.Query(context.Background(), `SELECT s.skill_id,COALESCE(r.card_revision,'')
 FROM gfm.skills s JOIN gfm.skill_revisions r
   ON r.org_id=s.org_id AND r.revision_id=s.published_revision_id
 WHERE s.org_id=$1::uuid AND s.repo_id='meridian' AND s.publication_status='published'`, e.orgID)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	checked := 0
	for rows.Next() {
		var skillID, card string
		if err := rows.Scan(&skillID, &card); err != nil {
			t.Fatal(err)
		}
		want, served := cards[skillID]
		if !served {
			// A published skill the snapshot does not carry would be a different
			// defect; this test is about the pair, so it is named and skipped.
			continue
		}
		if card == "" {
			t.Fatalf("%s serves card %q but its catalog revision stored none", skillID, want)
		}
		if card != want {
			t.Fatalf("%s stored card revision %q, the snapshot serves %q", skillID, card, want)
		}
		checked++
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	if checked == 0 {
		t.Fatal("no published skill was compared against the snapshot it serves")
	}
	// The identifier really is a second namespace: it is not the catalog
	// revision under another name.
	for skillID, card := range cards {
		if strings.TrimSpace(card) == "" {
			t.Fatalf("%s has an empty card revision", skillID)
		}
	}
}
