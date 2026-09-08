package knowledge_test

import (
	"context"
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

// U6-3 — one revision, two names.
//
// The delivery path hands a harness the card revision and adapter telemetry
// echoes it; a judgment recorded in the UI names the catalog revision. These
// tests pin down that the catalog says so out loud and that a reader is shown
// both halves of their own organisation's judgments rather than one.

// withCardRevision stamps the card identifier a publication would have written.
func (c *catalog) withCardRevision(t *testing.T, revisionID, card string) {
	t.Helper()
	if _, e := c.h.Pool.Exec(context.Background(), `UPDATE gfm.skill_revisions
 SET card_revision=$3 WHERE org_id=$1::uuid AND revision_id=$2`, c.org, revisionID, card); e != nil {
		t.Fatal(e)
	}
}

// An unpublished revision has no card revision, and says so with null rather
// than repeating the catalog revision under a second name.
func TestCardRevisionIsNullUntilTheRevisionIsPublished(t *testing.T) {
	c := newCatalog(t)
	summary, _ := c.firstSkill(t)
	skillID := summary["skill_id"].(string)
	if value, present := summary["card_revision"]; !present || value != nil {
		t.Fatalf("an unpublished summary carries card_revision %v", value)
	}
	detail := c.mustGet(t, c.skillPath(skillID))
	refs := detail["revisions"].([]any)
	if len(refs) == 0 {
		t.Fatal("the skill has no revisions")
	}
	if value := refs[0].(map[string]any)["card_revision"]; value != nil {
		t.Fatalf("an unpublished revision ref carries card_revision %v", value)
	}
}

// Once the revision is published, all three views name the card revision.
func TestTheCatalogNamesTheCardRevisionOfAPublishedRevision(t *testing.T) {
	c := newCatalog(t)
	summary, _ := c.firstSkill(t)
	skillID, revisionID := summary["skill_id"].(string), summary["revision_id"].(string)
	const card = "the-card-revision"
	c.withCardRevision(t, revisionID, card)

	detail := c.mustGet(t, c.skillPath(skillID))
	if detail["card_revision"] != card {
		t.Fatalf("the summary names %v, want %q", detail["card_revision"], card)
	}
	ref := detail["revisions"].([]any)[0].(map[string]any)
	if ref["card_revision"] != card {
		t.Fatalf("the revision ref names %v, want %q", ref["card_revision"], card)
	}
	revision := c.mustGet(t, c.skillPath(skillID)+"/revisions/"+revisionID)
	if revision["card_revision"] != card {
		t.Fatalf("the revision names %v, want %q", revision["card_revision"], card)
	}
}

// A judgment recorded in the UI carries the content digest and, once the
// revision is published, the card revision beside the catalog one — so the
// usage report can resolve them to a single row without guessing.
func TestAUIJudgmentNamesEveryIdentifierOfItsRevision(t *testing.T) {
	c := newCatalog(t)
	summary, _ := c.firstSkill(t)
	skillID, revisionID := summary["skill_id"].(string), summary["revision_id"].(string)
	const card = "the-card-revision"
	c.withCardRevision(t, revisionID, card)

	status, body, _ := c.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: c.base + c.skillPath(skillID) + "/revisions/" + revisionID + "/feedback",
		Body: map[string]any{"idempotency_key": "j-card", "verdict": "helped",
			"reason": "the runbook matched"}, Key: "j-card"})
	if status != http.StatusOK {
		t.Fatalf("feedback: %d %v", status, body)
	}
	if len(c.h.Events.Events) != 1 {
		t.Fatalf("the ledger received %d events", len(c.h.Events.Events))
	}
	event := c.h.Events.Events[0]
	// `revision` stays the catalog revision: it is the key the reference report
	// can compute without a catalog (API-CONTRACT §5.5).
	if event["revision"] != revisionID {
		t.Fatalf("the event names revision %v, want the catalog revision", event["revision"])
	}
	if event["card_revision"] != card {
		t.Fatalf("the event does not carry the card revision: %v", event["card_revision"])
	}
	if event["content_sha256"] == nil || event["content_sha256"] == "" {
		t.Fatalf("the event does not carry the content digest: %v", event)
	}
}

// A judgment an adapter filed under the card revision is about this revision,
// so the revision shows it. Matching only the catalog revision would show a
// reader an empty list while their own organisation's judgments sat in the
// ledger.
func TestARevisionShowsJudgmentsFiledUnderEitherName(t *testing.T) {
	c := newCatalog(t)
	summary, _ := c.firstSkill(t)
	skillID, revisionID := summary["skill_id"].(string), summary["revision_id"].(string)
	const card = "the-card-revision"
	c.withCardRevision(t, revisionID, card)

	event := map[string]any{"schema_version": "1.0", "event_id": "adapter-judgment",
		"event_type": "skill_feedback", "sequence": 1, "producer": "claude-code",
		"adapter_version": "1.2.0", "environment": "pilot",
		"occurred_at": time.Now().UTC().Format(time.RFC3339),
		"judgment_id": "j-adapter", "skill_id": skillID, "revision": card,
		"verdict": "hindered", "reason_category": "the example was stale"}
	payload, e := json.Marshal(event)
	if e != nil {
		t.Fatal(e)
	}
	if _, e := c.h.Pool.Exec(context.Background(), `INSERT INTO gf.events
 (tenant_id,event_id,event_type,schema_version,occurred_at,received_at,payload)
 VALUES($1,$2,'skill_feedback','1.0',$3,$3,$4)`,
		c.org, []byte("adapter-judgment"), event["occurred_at"], payload); e != nil {
		t.Fatal(e)
	}

	revision := c.mustGet(t, c.skillPath(skillID)+"/revisions/"+revisionID)
	entries := revision["feedback"].([]any)
	if len(entries) != 1 {
		t.Fatalf("the revision shows %d judgments, want the adapter's one: %v", len(entries), entries)
	}
	if entries[0].(map[string]any)["judgment_id"] != "j-adapter" {
		t.Fatalf("feedback entry %v", entries[0])
	}
}
