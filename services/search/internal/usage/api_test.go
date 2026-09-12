package usage_test

import (
	"context"
	"encoding/csv"
	"encoding/json"
	"net/http"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/identity"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

func TestMain(m *testing.M) { pivottest.Main(m) }

// pinnedCSVColumns is the order API-CONTRACT §5.5 fixes. It is written out here
// rather than derived from the code, so a reordering in the implementation
// fails this test instead of silently redefining the contract.
var pinnedCSVColumns = []string{"skill_id", "revision", "scope", "owner", "harness",
	"window_from", "window_to", "exposures", "loads_verified", "context_loaded",
	"context_unknown", "use_reported", "use_observed", "helped", "hindered", "mixed",
	"not_applicable", "unknown", "feedback_n", "helped_numerator", "helped_denominator",
	"small_sample", "zero_loads",
	// Appended in contract 1.1.1. Everything above them keeps its position: a
	// column may be added at the end, never inserted (API-CONTRACT §5.5).
	"card_revision", "content_sha256",
	// Appended in contract 1.1.4, same rule.
	"exposures_expanded", "loads_unlinked"}

// fixture is one organisation with one repository and a signed-in owner.
type fixture struct {
	h      *pivottest.Harness
	owner  *pivottest.Client
	org    string
	repo   string
	base   string
	clock  time.Time
	serial int
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	h := pivottest.New(t)
	owner := h.SignIn(t, "usage-owner", "owner@example.test")
	org := owner.CreateOrg(t, "usage-org")
	owner.CreateRepo(t, org, "meridian", "")
	return &fixture{h: h, owner: owner, org: org, repo: "meridian",
		base:  pivottest.RepoBase(org, "meridian"),
		clock: time.Now().UTC().Add(-2 * time.Hour).Truncate(time.Second)}
}

// member signs a second person in and gives them the member role.
func (f *fixture) member(t *testing.T) *pivottest.Client {
	t.Helper()
	c := f.h.SignIn(t, "usage-member", "member@example.test")
	var userID string
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT user_id::text FROM gfm.identities WHERE provider='google' AND subject='usage-member'`).
		Scan(&userID); e != nil {
		t.Fatal(e)
	}
	f.exec(t, `INSERT INTO gfm.memberships(org_id,user_id,role) VALUES($1::uuid,$2::uuid,'member')`,
		f.org, userID)
	return c
}

func (f *fixture) exec(t *testing.T, sql string, args ...any) {
	t.Helper()
	if _, e := f.h.Pool.Exec(context.Background(), sql, args...); e != nil {
		t.Fatalf("%s: %v", sql, e)
	}
}

// skill writes one catalog row the way an import would, so the usage module can
// resolve a scope and an owner without running the whole import pipeline.
func (f *fixture) skill(t *testing.T, org, repo, skillID, scope, owner, revision, status string,
	publishedAt time.Time) {
	t.Helper()
	blob := strings.Repeat("a", 64)
	f.exec(t, `INSERT INTO gfm.blobs(org_id,sha256,size_bytes,content)
 VALUES($1::uuid,$2,1,'\x00') ON CONFLICT DO NOTHING`, org, blob)
	published := any(nil)
	if status == "published" {
		published = revision
	}
	f.exec(t, `INSERT INTO gfm.skills
 (org_id,skill_id,repo_id,name,scope,owner,path,publication_status,
  current_revision_id,published_revision_id)
 VALUES($1::uuid,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
		org, skillID, repo, skillID, scope, nilable(owner),
		"/.agents/skills/"+skillID+"/SKILL.md", status, revision, published)
	f.exec(t, `INSERT INTO gfm.skill_revisions
 (org_id,revision_id,skill_id,content_sha256,blob_sha256,frontmatter,source_path,created_at)
 VALUES($1::uuid,$2,$3,$4,$5,'{}'::jsonb,$6,$7)`,
		org, revision, skillID, revision, blob, "SKILL.md", publishedAt)
}

func nilable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// emit appends one event to the ledger exactly as ingestEvents does: the whole
// event as the payload, a server-generated received_at, and the verified
// organisation as the tenant.
func (f *fixture) emit(t *testing.T, tenant string, event map[string]any) {
	t.Helper()
	f.serial++
	if event["event_id"] == nil {
		event["event_id"] = "e-" + time.Now().Format("150405.000000000") + "-" +
			identity.NewID()
	}
	if event["occurred_at"] == nil {
		event["occurred_at"] = f.clock.Format(time.RFC3339)
	}
	if event["producer"] == nil {
		event["producer"] = "claude-code"
	}
	base := map[string]any{"schema_version": "1.0", "sequence": f.serial,
		"adapter_version": "1.2.0", "environment": "pilot"}
	for k, v := range base {
		if _, ok := event[k]; !ok {
			event[k] = v
		}
	}
	payload, e := json.Marshal(event)
	if e != nil {
		t.Fatal(e)
	}
	received := f.clock.Add(time.Minute).UTC().Format("2006-01-02T15:04:05Z")
	f.exec(t, `INSERT INTO gf.events
 (tenant_id,event_id,event_type,schema_version,occurred_at,received_at,payload)
 VALUES($1,$2,$3,'1.0',$4,$5,$6) ON CONFLICT DO NOTHING`,
		tenant, []byte(event["event_id"].(string)), event["event_type"],
		event["occurred_at"], received, payload)
}

func (f *fixture) get(t *testing.T, path string) map[string]any {
	t.Helper()
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: f.base + path})
	if status != http.StatusOK {
		t.Fatalf("GET %s: %d %v", path, status, body)
	}
	return body
}

func totals(t *testing.T, body map[string]any) map[string]any {
	t.Helper()
	out, ok := body["totals"].(map[string]any)
	if !ok {
		t.Fatalf("no totals in %v", body)
	}
	return out
}

func number(t *testing.T, m map[string]any, key string) int {
	t.Helper()
	v, ok := m[key].(float64)
	if !ok {
		t.Fatalf("%s is %v, not a number", key, m[key])
	}
	return int(v)
}

func skillRow(t *testing.T, body map[string]any, skillID string) map[string]any {
	t.Helper()
	for _, raw := range body["skills"].([]any) {
		row := raw.(map[string]any)
		if row["skill_id"] == skillID {
			return row
		}
	}
	t.Fatalf("no row for %s in %v", skillID, body["skills"])
	return nil
}

// ---------------------------------------------------------------------------
// U6.3 — a proportion is never shown without the counts behind it.
// ---------------------------------------------------------------------------

func TestUsageRatiosCarryNumeratorDenominatorAndTheSmallSampleFlag(t *testing.T) {
	f := newFixture(t)
	rev := strings.Repeat("1", 64)
	f.skill(t, f.org, f.repo, "urn:skill:acme:atlas:retry", "atlas", "platform", rev,
		"published", f.clock.Add(-24*time.Hour))
	for i := 0; i < 3; i++ {
		f.feedback(t, "urn:skill:acme:atlas:retry", rev, "helped")
	}
	f.feedback(t, "urn:skill:acme:atlas:retry", rev, "hindered")
	f.feedback(t, "urn:skill:acme:atlas:retry", rev, "mixed")
	f.feedback(t, "urn:skill:acme:atlas:retry", rev, "unknown")

	row := skillRow(t, f.get(t, "/usage"), "urn:skill:acme:atlas:retry")
	ratio, ok := row["helped_ratio"].(map[string]any)
	if !ok {
		t.Fatalf("helped_ratio missing: %v", row)
	}
	if number(t, ratio, "numerator") != 3 || number(t, ratio, "denominator") != 4 {
		t.Fatalf("ratio is %v, want 3/4 (mixed and unknown are not in the denominator)", ratio)
	}
	if ratio["small_sample"] != true {
		t.Fatalf("four judgments must be flagged as a small sample: %v", ratio)
	}
	feedback := row["feedback"].(map[string]any)
	for key, want := range map[string]int{"helped": 3, "hindered": 1, "mixed": 1,
		"not_applicable": 0, "unknown": 1, "n": 6} {
		if got := number(t, feedback, key); got != want {
			t.Fatalf("feedback %s = %d, want %d", key, got, want)
		}
	}

	// Twenty judgments clear the floor. The flag is about display, not proof.
	for i := 0; i < 16; i++ {
		f.feedback(t, "urn:skill:acme:atlas:retry", rev, "helped")
	}
	row = skillRow(t, f.get(t, "/usage"), "urn:skill:acme:atlas:retry")
	ratio = row["helped_ratio"].(map[string]any)
	if number(t, ratio, "denominator") != 20 || ratio["small_sample"] != false {
		t.Fatalf("twenty judgments still flagged small: %v", ratio)
	}
}

// feedback writes one judgment event.
func (f *fixture) feedback(t *testing.T, skillID, revision, verdict string) string {
	t.Helper()
	judgment := identity.NewID()
	f.emit(t, f.org, map[string]any{"event_type": "skill_feedback",
		"judgment_id": judgment, "skill_id": skillID, "revision": revision,
		"verdict": verdict, "reason_category": "unspecified", "source": "ui",
		"task_id": "task-" + judgment[:8]})
	return judgment
}

// ---------------------------------------------------------------------------
// U6.2 — nothing on the server side is evidence of use.
// ---------------------------------------------------------------------------

func TestUsageShowsNoRatioAndNoZeroPercentWithoutJudgments(t *testing.T) {
	f := newFixture(t)
	rev := strings.Repeat("2", 64)
	skill := "urn:skill:acme:atlas:deploy"
	f.skill(t, f.org, f.repo, skill, "atlas", "platform", rev, "published",
		f.clock.Add(-24*time.Hour))
	// Traffic without any judgment: exposures, loads and reported use.
	f.emit(t, f.org, map[string]any{"event_type": "card_injected", "exposure_id": "x-1",
		"skill_id": skill, "revision": rev, "position": 1, "surface": "hook",
		"delivery_evidence": "emitted"})
	f.emit(t, f.org, map[string]any{"event_type": "skill_load_completed", "load_id": "l-1",
		"skill_id": skill, "revision": rev, "status": "ok", "cache_source": "cold",
		"bytes": 100, "duration_ms": 4, "closure_status": "complete"})
	f.emit(t, f.org, map[string]any{"event_type": "skill_use_reported", "use_id": "u-1",
		"skill_id": skill, "revision": rev, "source": "agent", "report_category": "applied",
		"task_id": "task-a"})

	body := f.get(t, "/usage")
	row := skillRow(t, body, skill)
	if row["helped_ratio"] != nil {
		t.Fatalf("a ratio appeared with no judgments: %v", row["helped_ratio"])
	}
	if row["feedback"] != nil {
		t.Fatalf("unjudged is not zeros: %v", row["feedback"])
	}
	if totals(t, body)["feedback"] != nil {
		t.Fatalf("totals invented a feedback object: %v", totals(t, body))
	}
	if number(t, row, "use_reported") != 1 || number(t, row, "use_observed") != 0 {
		t.Fatalf("reported and observed must be counted apart: %v", row)
	}
	if number(t, row, "use_episodes") != 1 {
		t.Fatalf("one task, one skill, one revision is one episode: %v", row)
	}
	// The adapter could not confirm the card reached the context: unknown, not
	// a failed load.
	if number(t, row, "loads_verified") != 1 || number(t, row, "context_loaded") != 0 ||
		number(t, row, "context_unknown") != 1 {
		t.Fatalf("context confirmation must default to unknown: %v", row)
	}
}

func TestUsageCountsContextConfirmationSeparatelyFromTheLoad(t *testing.T) {
	f := newFixture(t)
	rev := strings.Repeat("3", 64)
	skill := "urn:skill:acme:atlas:migrate"
	f.skill(t, f.org, f.repo, skill, "atlas", "platform", rev, "published", f.clock)
	for id, confirmation := range map[string]string{
		"l-confirmed": "context_loaded", "l-downloaded": "download_verified",
		"l-unsupported": "unsupported"} {
		f.emit(t, f.org, map[string]any{"event_type": "skill_load_completed", "load_id": id,
			"skill_id": skill, "revision": rev, "status": "ok", "cache_source": "warm",
			"bytes": 10, "duration_ms": 1, "closure_status": "complete",
			"context_confirmation": confirmation})
	}
	// A denied load is not a load at all.
	f.emit(t, f.org, map[string]any{"event_type": "skill_load_completed", "load_id": "l-denied",
		"skill_id": skill, "revision": rev, "status": "denied", "cache_source": "none",
		"bytes": 0, "duration_ms": 1, "closure_status": "unresolved"})

	row := skillRow(t, f.get(t, "/usage"), skill)
	if number(t, row, "loads_verified") != 3 {
		t.Fatalf("denied load counted: %v", row)
	}
	if number(t, row, "context_loaded") != 1 || number(t, row, "context_unknown") != 2 {
		t.Fatalf("context split wrong: %v", row)
	}
}

// ---------------------------------------------------------------------------
// U6.4 — filters and export.
// ---------------------------------------------------------------------------

func TestUsageFiltersNarrowTheViewAndTheExportReproducesIt(t *testing.T) {
	f := newFixture(t)
	revA, revB := strings.Repeat("a", 64), strings.Repeat("b", 64)
	atlas := "urn:skill:acme:atlas:index"
	orion := "urn:skill:acme:orion:index"
	f.skill(t, f.org, f.repo, atlas, "atlas", "platform", revA, "published", f.clock)
	f.skill(t, f.org, f.repo, orion, "orion", "search", revB, "published", f.clock)
	f.expose(t, atlas, revA, "claude-code", 2)
	f.expose(t, orion, revB, "copilot-cli", 3)

	all := f.get(t, "/usage")
	if number(t, totals(t, all), "exposures") != 5 {
		t.Fatalf("unfiltered totals: %v", totals(t, all))
	}
	for query, want := range map[string]int{
		"?scope=atlas":                        2,
		"?scope=orion":                        3,
		"?skill_id=" + url.QueryEscape(atlas): 2,
		"?revision=" + revB:                   3,
		"?harness=claude-code":                2,
		"?harness=copilot-cli":                3,
		"?scope=atlas&harness=copilot-cli":    0,
	} {
		body := f.get(t, "/usage"+query)
		if got := number(t, totals(t, body), "exposures"); got != want {
			t.Fatalf("filter %s: exposures %d, want %d", query, got, want)
		}
		// Coverage describes the window, not the filter.
		coverage := body["coverage"].(map[string]any)
		if number(t, coverage, "events_received") != 5 {
			t.Fatalf("filter %s narrowed coverage: %v", query, coverage)
		}
	}

	// CSV: the pinned header, byte for byte, and no field that carries content.
	status, raw, header := f.owner.Raw(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/usage/export?format=csv"})
	if status != http.StatusOK {
		t.Fatalf("csv export: %d %s", status, raw)
	}
	if ct := header.Get("Content-Type"); !strings.HasPrefix(ct, "text/csv") {
		t.Fatalf("csv content type is %q", ct)
	}
	records, e := csv.NewReader(strings.NewReader(string(raw))).ReadAll()
	if e != nil {
		t.Fatalf("export is not valid CSV: %v", e)
	}
	if len(records) != 3 {
		t.Fatalf("want a header and two rows, got %d", len(records))
	}
	if strings.Join(records[0], ",") != strings.Join(pinnedCSVColumns, ",") {
		t.Fatalf("CSV header drifted:\n got %v\nwant %v", records[0], pinnedCSVColumns)
	}
	for _, forbidden := range []string{"path", "prompt", "query", "body", "content", "email"} {
		for _, column := range records[0] {
			if column == forbidden {
				t.Fatalf("the export carries a %q column", forbidden)
			}
		}
	}
	// An unjudged row leaves the feedback cells empty rather than writing zeros.
	for _, row := range records[1:] {
		for i, column := range records[0] {
			if column == "feedback_n" && row[i] != "" {
				t.Fatalf("unjudged row wrote %q into feedback_n", row[i])
			}
		}
	}

	// JSON: the pinned document shape, with the same rows as objects.
	document := f.get(t, "/usage/export?format=json")
	if document["schema_version"] != "mgmt-1" {
		t.Fatalf("export schema_version: %v", document["schema_version"])
	}
	for _, key := range []string{"window", "coverage", "rows"} {
		if _, ok := document[key]; !ok {
			t.Fatalf("export JSON is missing %s: %v", key, document)
		}
	}
	rows := document["rows"].([]any)
	if len(rows) != 2 {
		t.Fatalf("export rows: %d", len(rows))
	}
	first := rows[0].(map[string]any)
	for _, column := range pinnedCSVColumns {
		if _, ok := first[column]; !ok {
			t.Fatalf("export row is missing the pinned field %s: %v", column, first)
		}
	}
	if first["feedback_n"] != nil {
		t.Fatalf("unjudged row is null, not zero: %v", first["feedback_n"])
	}

	if status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/usage/export?format=xml"}); status != http.StatusBadRequest ||
		body["error"] != "invalid_request" {
		t.Fatalf("unknown format: %d %v", status, body)
	}
	if status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/usage?window=1y"}); status != http.StatusBadRequest {
		t.Fatalf("unknown window silently widened: %d %v", status, body)
	}
}

// expose emits n exposures of one revision from one adapter.
func (f *fixture) expose(t *testing.T, skillID, revision, producer string, n int) {
	t.Helper()
	for i := 0; i < n; i++ {
		f.emit(t, f.org, map[string]any{"event_type": "card_injected",
			"exposure_id": producer + "-" + skillID + "-" + string(rune('a'+i)),
			"skill_id":    skillID, "revision": revision, "position": i + 1,
			"surface": "hook", "delivery_evidence": "emitted", "producer": producer})
	}
}

// exposeAt emits one exposure of one revision at a specific occurred_at, so a
// test can place an event in a window other than the one around f.clock.
func (f *fixture) exposeAt(t *testing.T, skillID, revision string, at time.Time) {
	t.Helper()
	f.emit(t, f.org, map[string]any{"event_type": "card_injected",
		"exposure_id": "prev-" + skillID + "-" + at.Format(time.RFC3339Nano),
		"skill_id":    skillID, "revision": revision, "position": 1,
		"surface": "hook", "delivery_evidence": "emitted",
		"occurred_at": at.UTC().Format(time.RFC3339)})
}

// ---------------------------------------------------------------------------
// Contract 1.3.0 — the window before the requested one, and who decided a
// queue item.
// ---------------------------------------------------------------------------

func TestUsagePreviousWindowCoversTheWindowBeforeTheCurrentOne(t *testing.T) {
	f := newFixture(t)
	rev := strings.Repeat("p", 64)
	skill := "urn:skill:acme:atlas:previous"
	f.skill(t, f.org, f.repo, skill, "atlas", "platform", rev, "published",
		f.clock.Add(-90*24*time.Hour))
	// Two exposures land in the 30 days before the requested window, one
	// lands inside it.
	f.exposeAt(t, skill, rev, f.clock.Add(-40*24*time.Hour))
	f.exposeAt(t, skill, rev, f.clock.Add(-35*24*time.Hour))
	f.exposeAt(t, skill, rev, f.clock.Add(-5*24*time.Hour))

	body := f.get(t, "/usage?window=30d")
	if got := number(t, totals(t, body), "exposures"); got != 1 {
		t.Fatalf("current window exposures = %d, want 1 (only the 5-day-old one): %v",
			got, totals(t, body))
	}
	window := body["window"].(map[string]any)
	previous, ok := body["previous"].(map[string]any)
	if !ok {
		t.Fatalf("no previous object: %v", body)
	}
	prevWindow, ok := previous["window"].(map[string]any)
	if !ok {
		t.Fatalf("previous.window missing: %v", previous)
	}
	// The previous window ends exactly where the requested one begins.
	if prevWindow["to"] != window["from"] {
		t.Fatalf("previous.window.to = %v, want the current window's from %v",
			prevWindow["to"], window["from"])
	}
	from, e1 := time.Parse(time.RFC3339, prevWindow["from"].(string))
	to, e2 := time.Parse(time.RFC3339, prevWindow["to"].(string))
	if e1 != nil || e2 != nil {
		t.Fatalf("previous.window timestamps do not parse: %v / %v", e1, e2)
	}
	if got := to.Sub(from); got != 30*24*time.Hour {
		t.Fatalf("previous window is %s long, want 30d", got)
	}
	prevTotals, ok := previous["totals"].(map[string]any)
	if !ok {
		t.Fatalf("previous.totals missing: %v", previous)
	}
	if got := number(t, prevTotals, "exposures"); got != 2 {
		t.Fatalf("previous.totals.exposures = %d, want 2 (the 40- and 35-day-old ones): %v",
			got, prevTotals)
	}
}

func TestUsageQueueDecisionActorRoundTripsThroughDecidedByAndNullStaysNull(t *testing.T) {
	f := newFixture(t)
	rev := strings.Repeat("q", 64)
	skill := "urn:skill:acme:atlas:actor"
	f.skill(t, f.org, f.repo, skill, "atlas", "platform", rev, "published", f.clock)
	f.feedback(t, skill, rev, "hindered")
	ownerID, _ := f.owner.User["id"].(string)
	if ownerID == "" {
		t.Fatalf("fixture owner has no id: %v", f.owner.User)
	}

	// A computed item, decided by the signed-in owner: the decision response
	// names who decided it (decideComputed's own Actor: optional(actor)).
	itemID := "negative_feedback:" + skill + ":" + rev
	decided := f.decide(t, itemID, "reviewed", "Looked at the feedback.")
	decision := decided["item"].(map[string]any)["decision"].(map[string]any)
	if decision["actor"] != ownerID {
		t.Fatalf("decision.actor = %v, want the deciding owner %s", decision["actor"], ownerID)
	}

	// A worker-raised (source_changed) item, still undecided: it carries no
	// decision object at all yet.
	driftID := identity.NewID()
	f.exec(t, `INSERT INTO gfm.owner_queue
 (org_id,item_id,repo_id,skill_id,revision_id,reason,evidence)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,'source_changed','{"sha256":"deadbeef"}'::jsonb)`,
		f.org, driftID, f.repo, skill, rev)
	if open := queueOf(t, f.get(t, "/usage"))[driftID]; open["decision"] != nil {
		t.Fatalf("an undecided worker item must carry no decision: %v", open)
	}
	// Deciding it through the API is decidePersisted's path: the actor in the
	// response must be read back from the decided_by column the UPDATE wrote,
	// not merely echo the request.
	drift := f.decide(t, driftID, "fixed_in_git", "Rewrote the step.")
	driftDecision := drift["item"].(map[string]any)["decision"].(map[string]any)
	if driftDecision["actor"] != ownerID {
		t.Fatalf("persisted decision.actor = %v, want the deciding owner %s",
			driftDecision["actor"], ownerID)
	}

	// A row that already carries a decision but whose decided_by is NULL — the
	// shape a decision written outside the owner API would have (nothing in
	// this codebase currently writes one, but the column is nullable and the
	// SELECT in queue() must not invent an actor for it). Left `open` so it is
	// listed rather than filtered out as resolved.
	nullActorItem := identity.NewID()
	f.exec(t, `INSERT INTO gfm.owner_queue
 (org_id,item_id,repo_id,skill_id,revision_id,reason,evidence,state,
  decision,decision_reason,decided_at)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,'source_changed','{}'::jsonb,'open',
  'fixed_in_git','Reconciled during import.',now())`,
		f.org, nullActorItem, f.repo, skill, rev)

	queue := queueOf(t, f.get(t, "/usage"))
	row, ok := queue[nullActorItem]
	if !ok {
		t.Fatalf("the null-actor item is missing from the queue: %v", queue)
	}
	rowDecision, ok := row["decision"].(map[string]any)
	if !ok {
		t.Fatalf("the row carries no decision: %v", row)
	}
	if rowDecision["actor"] != nil {
		t.Fatalf("a NULL decided_by must not surface as an invented actor: %v", rowDecision)
	}
}

// ---------------------------------------------------------------------------
// The queue: what a worker raised, what telemetry computed, and the decision.
// ---------------------------------------------------------------------------

func TestUsageQueueMergesDriftItemsWithComputedOnesAndCloses(t *testing.T) {
	f := newFixture(t)
	rev := strings.Repeat("c", 64)
	skill := "urn:skill:acme:atlas:runbook"
	f.skill(t, f.org, f.repo, skill, "atlas", "platform", rev, "published",
		f.clock.Add(-30*24*time.Hour))
	// What the import worker writes when a source file changed under a
	// published skill (importer.applyDrift).
	driftID := identity.NewID()
	f.exec(t, `INSERT INTO gfm.owner_queue
 (org_id,item_id,repo_id,skill_id,revision_id,reason,evidence)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,'source_changed','{"sha256":"deadbeef"}'::jsonb)`,
		f.org, driftID, f.repo, skill, rev)
	// One verified load, so the zero-loads reason stays quiet and this test is
	// only about the drift item and the negative-feedback one.
	f.emit(t, f.org, map[string]any{"event_type": "skill_load_completed", "load_id": "l-run",
		"skill_id": skill, "revision": rev, "status": "ok", "cache_source": "warm",
		"bytes": 12, "duration_ms": 2, "closure_status": "complete"})
	// What telemetry computes: one person called this revision harmful.
	f.feedback(t, skill, rev, "hindered")

	body := f.get(t, "/usage")
	items := queueOf(t, body)
	if len(items) != 2 {
		t.Fatalf("want the drift item and the computed one, got %v", items)
	}
	computedID := "negative_feedback:" + skill + ":" + rev
	if _, ok := items[driftID]; !ok {
		t.Fatalf("the importer's drift item is missing: %v", items)
	}
	computed, ok := items[computedID]
	if !ok {
		t.Fatalf("no computed negative_feedback item: %v", items)
	}
	if computed["reason"] != "negative_feedback" || computed["source"] != "computed" {
		t.Fatalf("computed item is wrong: %v", computed)
	}
	if computed["evidence"].(map[string]any)["hindered"].(float64) != 1 {
		t.Fatalf("evidence must carry the count: %v", computed["evidence"])
	}

	// Re-reading changes nothing, and neither does the same events arriving
	// twice: the ledger dedupes and the computed identifier is stable.
	f.emit(t, f.org, map[string]any{"event_type": "card_injected", "exposure_id": "x",
		"skill_id": skill, "revision": rev, "position": 1, "surface": "hook",
		"delivery_evidence": "emitted", "event_id": "dup-1"})
	f.emit(t, f.org, map[string]any{"event_type": "card_injected", "exposure_id": "x",
		"skill_id": skill, "revision": rev, "position": 1, "surface": "hook",
		"delivery_evidence": "emitted", "event_id": "dup-1"})
	again := f.get(t, "/usage")
	if len(queueOf(t, again)) != 2 {
		t.Fatalf("a replay duplicated queue items: %v", queueOf(t, again))
	}
	if got := number(t, skillRow(t, again, skill), "exposures"); got != 1 {
		t.Fatalf("a duplicated event counted twice: %d", got)
	}

	// Deciding the computed item closes it and is audited.
	f.decide(t, computedID, "no_change", "The warning is about the caller, not the runbook.")
	afterComputed := f.get(t, "/usage")
	if _, still := queueOf(t, afterComputed)[computedID]; still {
		t.Fatalf("a decided item stayed open: %v", queueOf(t, afterComputed))
	}
	// Deciding the worker's item closes that one too.
	f.decide(t, driftID, "fixed_in_git", "Rewrote the runbook step.")
	if len(queueOf(t, f.get(t, "/usage"))) != 0 {
		t.Fatalf("queue not empty: %v", queueOf(t, f.get(t, "/usage")))
	}

	var audits int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.audit WHERE org_id=$1::uuid AND action LIKE 'usage.queue.%'`,
		f.org).Scan(&audits); e != nil {
		t.Fatal(e)
	}
	if audits != 2 {
		t.Fatalf("want one audit row per decision, got %d", audits)
	}
	// Deciding the same item again is not a second close.
	status, body2, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/usage/queue/" + url.PathEscape(driftID) + "/decision",
		Body: map[string]any{"action": "reviewed", "reason": "Looked again."},
		Key:  "second-" + driftID})
	if status != http.StatusNotFound {
		t.Fatalf("re-deciding a closed item: %d %v", status, body2)
	}
}

func (f *fixture) decide(t *testing.T, itemID, action, reason string) map[string]any {
	t.Helper()
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/usage/queue/" + url.PathEscape(itemID) + "/decision",
		Body: map[string]any{"idempotency_key": "d-" + itemID + action,
			"action": action, "reason": reason},
		Key: "d-" + itemID + action})
	if status != http.StatusOK {
		t.Fatalf("decide %s: %d %v", itemID, status, body)
	}
	return body
}

func queueOf(t *testing.T, body map[string]any) map[string]map[string]any {
	t.Helper()
	out := map[string]map[string]any{}
	for _, raw := range body["queue"].([]any) {
		item := raw.(map[string]any)
		out[item["item_id"].(string)] = item
	}
	return out
}

func TestUsageRaisesZeroLoadsOnlyWhenThereWasAnOpportunity(t *testing.T) {
	f := newFixture(t)
	old, fresh := strings.Repeat("d", 64), strings.Repeat("e", 64)
	stale := "urn:skill:acme:atlas:stale"
	brandNew := "urn:skill:acme:atlas:new"
	f.skill(t, f.org, f.repo, stale, "atlas", "platform", old, "published",
		f.clock.Add(-30*24*time.Hour))
	f.skill(t, f.org, f.repo, brandNew, "atlas", "platform", fresh, "published", f.clock)

	items := queueOf(t, f.get(t, "/usage"))
	if _, ok := items["zero_loads:"+stale+":"+old]; !ok {
		t.Fatalf("a month-old published skill with no loads must be raised: %v", items)
	}
	if _, ok := items["zero_loads:"+brandNew+":"+fresh]; ok {
		t.Fatalf("a skill published today and never shown is not evidence: %v", items)
	}
	// One exposure is an opportunity, whatever the age.
	f.expose(t, brandNew, fresh, "claude-code", 1)
	items = queueOf(t, f.get(t, "/usage"))
	if _, ok := items["zero_loads:"+brandNew+":"+fresh]; !ok {
		t.Fatalf("an exposed but never loaded skill must be raised: %v", items)
	}
	// A load closes it.
	f.emit(t, f.org, map[string]any{"event_type": "skill_load_completed", "load_id": "l-new",
		"skill_id": brandNew, "revision": fresh, "status": "ok", "cache_source": "cold",
		"bytes": 1, "duration_ms": 1, "closure_status": "complete"})
	items = queueOf(t, f.get(t, "/usage"))
	if _, ok := items["zero_loads:"+brandNew+":"+fresh]; ok {
		t.Fatalf("a loaded skill is still queued: %v", items)
	}
}

// ---------------------------------------------------------------------------
// U3.3 — one organisation never sees another's numbers.
// ---------------------------------------------------------------------------

func TestUsageNeverCrossesOrganisations(t *testing.T) {
	f := newFixture(t)
	other := f.h.SignIn(t, "usage-other", "other@example.test")
	orgB := other.CreateOrg(t, "usage-org-b")
	other.CreateRepo(t, orgB, "meridian", "")

	rev := strings.Repeat("f", 64)
	skill := "urn:skill:acme:atlas:shared"
	// The same skill_id and the same repo_id exist in both organisations.
	f.skill(t, f.org, f.repo, skill, "atlas", "platform", rev, "published", f.clock)
	f.skill(t, orgB, "meridian", skill, "atlas", "platform", rev, "published", f.clock)
	f.expose(t, skill, rev, "claude-code", 4)
	f.feedback(t, skill, rev, "hindered")
	f.exec(t, `INSERT INTO gfm.adapter_health(org_id,harness,adapter_version,dropped,oldest_lag_s)
 VALUES($1::uuid,'claude-code','1.2.0',7,42)`, f.org)

	mine := f.get(t, "/usage")
	if number(t, totals(t, mine), "exposures") != 4 {
		t.Fatalf("own organisation: %v", totals(t, mine))
	}

	status, theirs, _ := other.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: pivottest.RepoBase(orgB, "meridian") + "/usage"})
	if status != http.StatusOK {
		t.Fatalf("organisation B: %d %v", status, theirs)
	}
	if number(t, totals(t, theirs), "exposures") != 0 {
		t.Fatalf("organisation B saw A's exposures: %v", totals(t, theirs))
	}
	if len(theirs["skills"].([]any)) != 0 || len(theirs["queue"].([]any)) != 0 {
		t.Fatalf("organisation B saw A's rows or queue: %v", theirs)
	}
	if adapters := theirs["health"].(map[string]any)["adapters"].([]any); len(adapters) != 0 {
		t.Fatalf("organisation B saw A's adapters: %v", adapters)
	}
	coverage := theirs["coverage"].(map[string]any)
	if number(t, coverage, "events_received") != 0 || coverage["oldest_lag_s"] != nil {
		t.Fatalf("organisation B saw A's coverage: %v", coverage)
	}

	// And the other direction is a 403, not a 404: membership is the only thing
	// the API confirms.
	status, body, _ := other.Call(t, pivottest.Call{Method: http.MethodGet, Path: f.base + "/usage"})
	if status != http.StatusForbidden || body["error"] != "forbidden" {
		t.Fatalf("cross-organisation read: %d %v", status, body)
	}
}

// ---------------------------------------------------------------------------
// Roles: reading is a member action, deciding is not.
// ---------------------------------------------------------------------------

func TestUsageMemberReadsButOnlyAnOwnerDecides(t *testing.T) {
	f := newFixture(t)
	rev := strings.Repeat("9", 64)
	skill := "urn:skill:acme:atlas:policy"
	f.skill(t, f.org, f.repo, skill, "atlas", "platform", rev, "published", f.clock)
	f.feedback(t, skill, rev, "hindered")
	member := f.member(t)

	status, body, _ := member.Call(t, pivottest.Call{Method: http.MethodGet, Path: f.base + "/usage"})
	if status != http.StatusOK {
		t.Fatalf("a member cannot read usage: %d %v", status, body)
	}
	if status, body, _ = member.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/usage/export?format=json"}); status != http.StatusOK {
		t.Fatalf("a member cannot export: %d %v", status, body)
	}
	itemID := "negative_feedback:" + skill + ":" + rev
	status, body, _ = member.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/usage/queue/" + url.PathEscape(itemID) + "/decision",
		Body: map[string]any{"action": "reviewed", "reason": "Looks fine to me."},
		Key:  "member-decision"})
	if status != http.StatusForbidden {
		t.Fatalf("a member decided a review item: %d %v", status, body)
	}
	// Still open for the owner.
	if _, ok := queueOf(t, f.get(t, "/usage"))[itemID]; !ok {
		t.Fatalf("the refused decision closed the item anyway")
	}
}

// ---------------------------------------------------------------------------
// The document and the server describe the same surface.
// ---------------------------------------------------------------------------

func TestUsageResponsesMatchTheOpenAPIComponents(t *testing.T) {
	spec := pivottest.LoadContract(t)
	f := newFixture(t)
	rev := strings.Repeat("7", 64)
	skill := "urn:skill:acme:atlas:spec"
	f.skill(t, f.org, f.repo, skill, "atlas", "platform", rev, "published",
		f.clock.Add(-30*24*time.Hour))
	f.expose(t, skill, rev, "claude-code", 1)
	f.feedback(t, skill, rev, "hindered")
	f.exec(t, `INSERT INTO gfm.adapter_health(org_id,harness,adapter_version,capabilities,
 last_seen_at,dropped,oldest_lag_s)
 VALUES($1::uuid,'claude-code','1.2.0','["context_confirmation"]'::jsonb,now(),3,11)`, f.org)

	body := f.get(t, "/usage")
	spec.Check(t, "Usage", body)
	spec.Check(t, "UsageTotals", totals(t, body))
	spec.Check(t, "UsageWindow", body["window"].(map[string]any))
	spec.Check(t, "UsageCoverage", body["coverage"].(map[string]any))
	for _, raw := range body["skills"].([]any) {
		spec.Check(t, "UsageSkill", raw.(map[string]any))
	}
	items := body["queue"].([]any)
	if len(items) == 0 {
		t.Fatal("the fixture must produce at least one queue item")
	}
	for _, raw := range items {
		spec.Check(t, "QueueItem", raw.(map[string]any))
	}
	for _, raw := range body["health"].(map[string]any)["adapters"].([]any) {
		spec.Check(t, "AdapterHealth", raw.(map[string]any))
	}
	export := f.get(t, "/usage/export?format=json")
	spec.Check(t, "UsageExport", export)
	for _, raw := range export["rows"].([]any) {
		spec.Check(t, "UsageExportRow", raw.(map[string]any))
	}
	decision := f.decide(t, "negative_feedback:"+skill+":"+rev, "reviewed", "Read the report.")
	spec.Check(t, "QueueDecisionResult", decision)
	spec.Check(t, "QueueItem", decision["item"].(map[string]any))

	status, envelope, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/usage?window=nonsense"})
	if status != http.StatusBadRequest {
		t.Fatalf("window validation: %d %v", status, envelope)
	}
	spec.Check(t, "Error", envelope)

	// The document and the router describe the same three routes.
	document := spec.Document["paths"].(map[string]any)
	for _, route := range []string{
		"/api/v1/orgs/{org}/repos/{repo}/usage",
		"/api/v1/orgs/{org}/repos/{repo}/usage/export",
		"/api/v1/orgs/{org}/repos/{repo}/usage/queue/{item_id}/decision"} {
		if _, ok := document[route]; !ok {
			t.Fatalf("the OpenAPI document does not describe %s", route)
		}
	}
}
