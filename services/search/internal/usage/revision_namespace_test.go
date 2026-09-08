package usage_test

import (
	"context"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

// U6-3 / ACT-01 — one revision, one row.
//
// A revision answers to two names. The delivery path hands a harness the card
// revision (`gf.skills.skill_revision`) and adapter telemetry echoes it; a
// judgment recorded in the UI names the catalog revision. The acceptance run
// found the consequence: a skill judged in the UI and delivered to a harness
// occupied two rows of the same report, so neither row was the truth about it.

// published writes one skill whose revision has both names, the way an import
// followed by a publication leaves it.
func (f *fixture) publishedWithCard(t *testing.T, skillID, revision, card string) {
	t.Helper()
	f.skill(t, f.org, f.repo, skillID, "atlas", "identity-team", revision, "published",
		f.clock.Add(-30*24*time.Hour))
	f.exec(t, `UPDATE gfm.skill_revisions SET card_revision=$3
 WHERE org_id=$1::uuid AND revision_id=$2`, f.org, revision, card)
}

func (f *fixture) usageRows(t *testing.T, query string) []map[string]any {
	t.Helper()
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/usage" + query})
	if status != http.StatusOK {
		t.Fatalf("usage%s: %d %v", query, status, body)
	}
	raw, _ := body["skills"].([]any)
	out := make([]map[string]any, 0, len(raw))
	for _, item := range raw {
		if row, ok := item.(map[string]any); ok {
			out = append(out, row)
		}
	}
	return out
}

// A judgment from the UI and one from an adapter are the same observation about
// the same revision, so they land in one row — under the catalog revision, with
// the card revision and the content digest beside it.
func TestAUIJudgmentAndAnAdapterJudgmentShareOneUsageRow(t *testing.T) {
	f := newFixture(t)
	const skillID = "urn:skill:meridian:atlas:postgres-auth"
	const revision = "revision-of-the-catalog"
	const card = "revision-of-the-card"
	f.publishedWithCard(t, skillID, revision, card)

	// The adapter names the revision the delivery path gave it.
	f.emit(t, f.org, map[string]any{"event_type": "card_injected", "skill_id": skillID,
		"revision": card, "exposure_id": "x-1", "position": 1, "surface": "hook",
		"delivery_evidence": "client_confirmed"})
	f.emit(t, f.org, map[string]any{"event_type": "skill_feedback", "skill_id": skillID,
		"revision": card, "judgment_id": "j-adapter", "verdict": "helped",
		"reason_category": "the runbook matched"})
	// The UI names the revision the catalog gave it.
	f.emit(t, f.org, map[string]any{"event_type": "skill_feedback", "skill_id": skillID,
		"revision": revision, "judgment_id": "j-ui", "verdict": "hindered",
		"reason_category": "the example was stale", "producer": "guidefold-management-api",
		"source": "ui", "content_sha256": revision})

	rows := f.usageRows(t, "?window=30d")
	if len(rows) != 1 {
		t.Fatalf("one skill judged twice produced %d rows: %v", len(rows), rows)
	}
	row := rows[0]
	if row["revision"] != revision {
		t.Fatalf("the row is keyed by %v, want the catalog revision %q", row["revision"], revision)
	}
	if row["card_revision"] != card {
		t.Fatalf("the row does not name the card revision: %v", row["card_revision"])
	}
	if row["content_sha256"] == nil {
		t.Fatalf("the row does not name the content digest: %v", row)
	}
	feedback, _ := row["feedback"].(map[string]any)
	if feedback == nil {
		t.Fatalf("two judgments produced no feedback totals: %v", row)
	}
	if feedback["helped"] != float64(1) || feedback["hindered"] != float64(1) ||
		feedback["n"] != float64(2) {
		t.Fatalf("the two judgments were not counted once each: %v", feedback)
	}
	if row["exposures"] != float64(1) {
		t.Fatalf("the adapter's exposure did not join the row: %v", row["exposures"])
	}
	// Two adapters contributed, so no single harness owns the row.
	if row["harness"] != nil {
		t.Fatalf("a row two producers built named one of them: %v", row["harness"])
	}
}

// The filter accepts whichever of the three names the reader has, and echoes
// back exactly what they typed rather than the identifier it resolved to.
func TestTheRevisionFilterAcceptsEitherNameAndEchoesTheOneAsked(t *testing.T) {
	f := newFixture(t)
	const skillID = "urn:skill:meridian:atlas:postgres-auth"
	const revision = "revision-of-the-catalog"
	const card = "revision-of-the-card"
	f.publishedWithCard(t, skillID, revision, card)
	f.emit(t, f.org, map[string]any{"event_type": "card_injected", "skill_id": skillID,
		"revision": card, "exposure_id": "x-1", "position": 1, "surface": "hook",
		"delivery_evidence": "client_confirmed"})

	for _, asked := range []string{revision, card} {
		status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
			Path: f.base + "/usage?revision=" + asked})
		if status != http.StatusOK {
			t.Fatalf("usage?revision=%s: %d %v", asked, status, body)
		}
		rows, _ := body["skills"].([]any)
		if len(rows) != 1 {
			t.Fatalf("revision=%s matched %d rows", asked, len(rows))
		}
		filters, _ := body["filters"].(map[string]any)
		if filters["revision"] != asked {
			t.Fatalf("the echo says %v, the reader asked for %q", filters["revision"], asked)
		}
		// §5.5: the echo is keyed exactly as the query parameters are, and the
		// window that was applied is named even when it was not asked for.
		if filters["window"] != "30d" {
			t.Fatalf("the echo does not name the applied window: %v", filters)
		}
		if _, present := filters["scope"]; present {
			t.Fatalf("a filter nobody asked for appeared in the echo: %v", filters)
		}
	}
}

// U9 / ACT-01 — the owner's decision, not the next publication, answers the
// question drift asked. Deciding a `source_changed` item returns the skill to
// `published`; deciding a `source_removed` item leaves it archived, because the
// file is still gone.
func TestDecidingADriftItemSettlesTheSkillStatus(t *testing.T) {
	f := newFixture(t)
	changed := "urn:skill:meridian:atlas:changed"
	removed := "urn:skill:meridian:atlas:removed"
	f.skill(t, f.org, f.repo, changed, "atlas", "identity-team", "rev-changed", "needs_review",
		f.clock)
	f.skill(t, f.org, f.repo, removed, "atlas", "identity-team", "rev-removed", "archived",
		f.clock)
	changedItem := f.queueRow(t, changed, "source_changed", "rev-changed")
	removedItem := f.queueRow(t, removed, "source_removed", "rev-removed")

	for _, item := range []struct{ id, want string }{
		{changedItem, "published"}, {removedItem, "archived"},
	} {
		status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
			Path: f.base + "/usage/queue/" + item.id + "/decision",
			Body: map[string]any{"idempotency_key": "decide-" + item.id, "action": "reviewed",
				"reason": "read the diff and the change is fine"},
			Key: "decide-" + item.id})
		if status != http.StatusOK {
			t.Fatalf("decision on %s: %d %v", item.id, status, body)
		}
	}
	if got := f.status(t, changed); got != "published" {
		t.Fatalf("a decided source_changed item left the skill %q, want published", got)
	}
	if got := f.status(t, removed); got != "archived" {
		t.Fatalf("a decision on a removed source moved the skill to %q; the file is still gone", got)
	}
}

// A decision on an item that says nothing about the source never touches the
// publication status: usage is an observation, not a publication decision.
func TestDecidingAUsageItemLeavesThePublicationStatusAlone(t *testing.T) {
	f := newFixture(t)
	skillID := "urn:skill:meridian:atlas:quiet"
	f.skill(t, f.org, f.repo, skillID, "atlas", "identity-team", "rev-quiet", "needs_review",
		f.clock)
	item := f.queueRow(t, skillID, "negative_feedback", "rev-quiet")
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/usage/queue/" + item + "/decision",
		Body: map[string]any{"idempotency_key": "decide-quiet", "action": "no_change",
			"reason": "one complaint is not a defect"},
		Key: "decide-quiet"})
	if status != http.StatusOK {
		t.Fatalf("decision: %d %v", status, body)
	}
	if got := f.status(t, skillID); got != "needs_review" {
		t.Fatalf("a usage decision changed the publication status to %q", got)
	}
}

// queueRow writes one open owner-queue item the way the import worker would and
// returns its id.
func (f *fixture) queueRow(t *testing.T, skillID, reason, revision string) string {
	t.Helper()
	var id string
	if e := f.h.Pool.QueryRow(context.Background(), `INSERT INTO gfm.owner_queue
 (org_id,item_id,repo_id,skill_id,revision_id,reason,evidence)
 VALUES($1::uuid,gen_random_uuid(),$2,$3,$4,$5,'{}'::jsonb) RETURNING item_id::text`,
		f.org, f.repo, skillID, revision, reason).Scan(&id); e != nil {
		t.Fatal(e)
	}
	return id
}

func (f *fixture) status(t *testing.T, skillID string) string {
	t.Helper()
	var status string
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT publication_status FROM gfm.skills WHERE org_id=$1::uuid AND skill_id=$2`,
		f.org, skillID).Scan(&status); e != nil {
		t.Fatal(e)
	}
	return strings.TrimSpace(status)
}
