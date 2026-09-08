package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	osexec "os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// The control ledger (U6.1). These tests drive the real delivery endpoint —
// `/v1/events:batch`, its validator and `ingestEvents` — and then read the
// management endpoint that reports on it, so the numbers come from the same
// path a harness adapter would take.
//
// The reference implementation, tools/telemetry/report.py over
// tools/telemetry/ledger.py, is run as a subprocess on the same events, and its
// numbers are compared with the ones the service produces. Where the reference
// does not define a measure (context confirmation, applied episodes, feedback
// corrections) the expected value is computed by hand in the test and the
// difference is stated, rather than being quietly skipped.

// referenceDriver replays batches through the reference ledger and prints the
// reference report as JSON.
const referenceDriver = `import json, sys
sys.path.insert(0, sys.argv[1])
from tools.telemetry import ledger, report
batches = json.load(open(sys.argv[2]))
conn = ledger.connect(sys.argv[3])
acks = [ledger.ingest(conn, sys.argv[4], batch) for batch in batches]
print(json.dumps({"report": report.compute_report(conn, sys.argv[4]), "acks": acks}))
`

// scratchDir is a private working directory under the user's Guidefold cache.
// Tests never write to /tmp.
func scratchDir(t *testing.T, name string) string {
	t.Helper()
	home, e := os.UserHomeDir()
	if e != nil {
		t.Fatal(e)
	}
	base := filepath.Join(home, ".cache", "guidefold", "worker")
	if e := os.MkdirAll(base, 0o700); e != nil {
		t.Fatal(e)
	}
	dir, e := os.MkdirTemp(base, "test-"+name+"-")
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = os.RemoveAll(dir) })
	return dir
}

// ledgerFixture is the control set of batches, written once and replayed
// against both implementations.
type ledgerFixture struct {
	batches [][]M
	skillA  string
	skillB  string
	revA    string
	revB    string
}

func newLedgerFixture() *ledgerFixture {
	f := &ledgerFixture{
		skillA: "urn:skill:acme:atlas:alpha", skillB: "urn:skill:acme:atlas:beta",
		revA: strings.Repeat("a", 64), revB: strings.Repeat("b", 64)}
	now := time.Now().UTC().Add(-time.Hour).Truncate(time.Second)
	at := func(d time.Duration) string { return now.Add(d).Format(time.RFC3339) }
	envelope := func(id, kind, occurred string, extra M) M {
		event := M{"schema_version": "1.0", "event_id": id, "event_type": kind,
			"occurred_at": occurred, "sequence": 1, "producer": "claude-code",
			"adapter_version": "1.4.0", "environment": "pilot"}
		for k, v := range extra {
			event[k] = v
		}
		return event
	}
	card := func(id, exposure, skill, revision, occurred string) M {
		return envelope(id, "card_injected", occurred, M{"exposure_id": exposure,
			"skill_id": skill, "revision": revision, "position": 1, "surface": "hook",
			"delivery_evidence": "emitted", "search_id": nil})
	}
	load := func(id, loadID, skill, revision, status, occurred string) M {
		return envelope(id, "skill_load_completed", occurred, M{"load_id": loadID,
			"skill_id": skill, "revision": revision, "status": status,
			"cache_source": "cold", "bytes": 2048, "duration_ms": 7,
			"closure_status": "complete"})
	}
	judge := func(id, judgment, skill, revision, verdict, occurred string, corrects any) M {
		extra := M{"judgment_id": judgment, "skill_id": skill, "revision": revision,
			"verdict": verdict, "reason_category": "accuracy", "source": "human"}
		if corrects != nil {
			extra["corrects_judgment_id"] = corrects
		}
		return envelope(id, "skill_feedback", occurred, extra)
	}

	first := []M{
		card("e1", "x1", f.skillA, f.revA, at(0)),
		card("e2", "x2", f.skillA, f.revA, at(time.Minute)),
		load("e3", "l1", f.skillA, f.revA, "ok", at(2*time.Minute)),
		judge("e4", "j1", f.skillA, f.revA, "helped", at(3*time.Minute), nil),
		envelope("e5", "telemetry_health", at(4*time.Minute), M{"produced": 5,
			"acknowledged": 5, "dropped": 2, "oldest_queued_age_s": 11,
			"capability_flags": []any{"context_confirmation"}, "window": "5m"}),
	}
	f.batches = [][]M{
		first,
		// A retry of the same batch: the transport repeated, the work did not.
		first,
		{
			card("e6", "x3", f.skillB, f.revB, at(5*time.Minute)),
			// Denied: never a load, however completed the event is.
			load("e7", "l2", f.skillB, f.revB, "denied", at(6*time.Minute)),
			load("e8", "l3", f.skillB, f.revB, "ok", at(7*time.Minute)),
			judge("e9", "j2", f.skillB, f.revB, "hindered", at(8*time.Minute), nil),
			envelope("e10", "skill_use_reported", at(9*time.Minute), M{"skill_id": f.skillA,
				"revision": f.revA, "source": "agent", "report_category": "applied",
				"use_id": "u1", "load_id": "l1", "task_id": "t1"}),
			// The same episode, observed rather than reported. Never two.
			envelope("e11", "skill_use_observed", at(10*time.Minute), M{"skill_id": f.skillA,
				"revision": f.revA, "adapter_evidence_type": "native_skill_invocation",
				"evidence_ref": "opaque-1", "use_id": "u2", "load_id": "l1",
				"task_id": "t1"}),
		},
		{
			// A late event: it happened three days ago and arrives now.
			card("e12", "x4", f.skillA, f.revA, at(-72*time.Hour)),
			// A correction: it replaces j2 rather than adding a second vote.
			judge("e13", "j3", f.skillB, f.revB, "helped", at(11*time.Minute), "j2"),
			// A duplicate inside one batch: first wins, second acknowledges.
			card("e12", "x4", f.skillA, f.revA, at(-72*time.Hour)),
		},
	}
	return f
}

// sessionClient is one signed-in person's browser against the delivery server.
type sessionClient struct {
	h    *deliveryHarness
	http *http.Client
	csrf string
}

func (h *deliveryHarness) signIn(t *testing.T, subject, email string) *sessionClient {
	t.Helper()
	jar := newJar(t)
	c := &sessionClient{h: h, http: &http.Client{Jar: jar,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}
	form := strings.NewReader("provider=google&subject=" + subject + "&email=" + email + "&name=" + subject)
	req, e := http.NewRequest(http.MethodPost, h.server.URL+"/api/v1/auth/dev", form)
	if e != nil {
		t.Fatal(e)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, e := c.http.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusFound {
		t.Fatalf("dev sign-in: %d", resp.StatusCode)
	}
	me := c.get(t, "/api/v1/me")
	c.csrf = str(me["csrf_token"])
	return c
}

func (c *sessionClient) get(t *testing.T, path string) M {
	t.Helper()
	req, e := http.NewRequest(http.MethodGet, c.h.server.URL+path, nil)
	if e != nil {
		t.Fatal(e)
	}
	resp, e := c.http.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("GET %s: %d %s", path, resp.StatusCode, raw)
	}
	var out M
	if e := json.Unmarshal(raw, &out); e != nil {
		t.Fatalf("GET %s: %v: %s", path, e, raw)
	}
	return out
}

// userIDOf reads the user the development provider created.
func userIDOf(t *testing.T, h *deliveryHarness, subject string) string {
	t.Helper()
	var id string
	if e := h.pool.QueryRow(context.Background(),
		`SELECT user_id::text FROM gfm.identities WHERE provider='google' AND subject=$1`,
		subject).Scan(&id); e != nil {
		t.Fatal(e)
	}
	return id
}

// TestUsageControlLedgerMatchesTheReferenceReport is U6.1: after retries,
// duplicates, a late event and a correction, the service reports what the
// reference ledger reports.
func TestUsageControlLedgerMatchesTheReferenceReport(t *testing.T) {
	h := newDeliveryHarness(t)
	f := newLedgerFixture()
	org := makeOrg(t, h.pool, "ledger-org")
	exec(t, h.pool, `INSERT INTO gfm.repos(org_id,repo_id) VALUES($1::uuid,'meridian')`, org)
	token := makeToken(t, h.pool, mgmt.SourceInstallation, org, "meridian", "",
		[]string{"search", "use", "events"})
	seedCatalogSkill(t, h, org, "meridian", f.skillA, "atlas", "platform", f.revA)
	seedCatalogSkill(t, h, org, "meridian", f.skillB, "orion", "search", f.revB)

	acks := make([]M, 0, len(f.batches))
	for i, batch := range f.batches {
		body, e := json.Marshal(M{"events": batch})
		if e != nil {
			t.Fatal(e)
		}
		status, out := h.post(t, "/v1/events:batch", token, string(body), nil)
		if status != http.StatusOK {
			t.Fatalf("batch %d: %d %v", i, status, out)
		}
		if rejected := arr(out["rejected"]); len(rejected) != 0 {
			t.Fatalf("batch %d rejected events: %v", i, rejected)
		}
		acks = append(acks, out)
	}
	// The retry is acknowledged, and nothing new is stored.
	if len(arr(acks[1]["accepted"])) != 0 || len(arr(acks[1]["duplicate"])) != len(f.batches[1]) {
		t.Fatalf("a retried batch was not fully deduplicated: %v", acks[1])
	}
	// The duplicate inside batch four is acknowledged the same way.
	if len(arr(acks[3]["duplicate"])) != 1 {
		t.Fatalf("the in-batch duplicate: %v", acks[3])
	}

	person := h.signIn(t, "ledger-owner", "owner@example.test")
	exec(t, h.pool, `INSERT INTO gfm.memberships(org_id,user_id,role) VALUES($1::uuid,$2::uuid,'owner')`,
		org, userIDOf(t, h, "ledger-owner"))
	usage := person.get(t, "/api/v1/orgs/"+org+"/repos/meridian/usage?window=90d")

	reference := runReference(t, f, "ledger-tenant")
	compareWithReference(t, usage, reference)

	// Measures the reference does not define, computed by hand from the fixture.
	rows := usageRows(t, usage)
	a, b := rows[f.skillA], rows[f.skillB]
	// One task, one skill, one revision: reported and observed are one episode.
	if intOf(t, a, "use_reported") != 1 || intOf(t, a, "use_observed") != 1 ||
		intOf(t, a, "use_episodes") != 1 {
		t.Fatalf("reported and observed must be separate and their episode one: %v", a)
	}
	// No adapter confirmed the context, so every verified load is unknown.
	if intOf(t, a, "context_loaded") != 0 || intOf(t, a, "context_unknown") != 1 {
		t.Fatalf("context confirmation defaults to unknown: %v", a)
	}
	// The correction replaced j2 instead of adding a vote. The reference report
	// has no notion of a correction and counts both, so this number is asserted
	// against the fixture, not against report.py.
	feedbackB := obj(b["feedback"])
	if intOf(t, feedbackB, "n") != 1 || intOf(t, feedbackB, "hindered") != 0 ||
		intOf(t, feedbackB, "helped") != 1 {
		t.Fatalf("the correction did not replace the judgment it corrects: %v", feedbackB)
	}
	referenceB := referenceRow(t, reference, f.skillB, f.revB)
	referenceFeedback := obj(referenceB["feedback"])
	if intOf(t, referenceFeedback, "hindered") != 1 || intOf(t, referenceFeedback, "helped") != 1 {
		t.Fatalf("the reference is expected to count both votes: %v", referenceFeedback)
	}

	coverage := obj(usage["coverage"])
	// The retried telemetry_health event is one observation, not two.
	if intOf(t, coverage, "dropped_reported") != 2 {
		t.Fatalf("dropped counted twice across a retry: %v", coverage)
	}
	if coverage["task_ids_present"] != true {
		t.Fatalf("the fixture carries task identifiers: %v", coverage)
	}
	if coverage["oldest_lag_s"] == nil {
		t.Fatalf("the ingest projection must give coverage a lag: %v", coverage)
	}

	// The projection the ingest wrote, from accepted events only.
	var dropped, produced int64
	var version string
	var installation *string
	var capabilities []byte
	var lag *int
	if e := h.pool.QueryRow(context.Background(),
		`SELECT dropped,produced,adapter_version,installation_id::text,capabilities,oldest_lag_s
 FROM gfm.adapter_health WHERE org_id=$1::uuid AND harness='claude-code'`, org).
		Scan(&dropped, &produced, &version, &installation, &capabilities, &lag); e != nil {
		t.Fatalf("adapter_health: %v", e)
	}
	if dropped != 2 || produced != 5 {
		t.Fatalf("the retried batch inflated the health counters: dropped=%d produced=%d",
			dropped, produced)
	}
	if version != "1.4.0" {
		t.Fatalf("adapter version: %q", version)
	}
	if installation == nil {
		t.Fatal("the installation token behind the batch was not recorded")
	}
	if string(capabilities) != `["context_confirmation"]` {
		t.Fatalf("capability flags: %s", capabilities)
	}
	if lag == nil || *lag < 0 {
		t.Fatalf("lag: %v", lag)
	}

	// A second organisation flushing a spool with the very same event_ids gets
	// its own ledger rows and its own health row. Nothing is relabelled: the
	// tenant is the organisation the caller proved, never one the events claim.
	otherOrg := makeOrg(t, h.pool, "ledger-org-b")
	exec(t, h.pool, `INSERT INTO gfm.repos(org_id,repo_id) VALUES($1::uuid,'meridian')`, otherOrg)
	otherToken := makeToken(t, h.pool, mgmt.SourceInstallation, otherOrg, "meridian", "",
		[]string{"search", "use", "events"})
	replay, _ := json.Marshal(M{"events": f.batches[0]})
	status, out := h.post(t, "/v1/events:batch", otherToken, string(replay), nil)
	if status != http.StatusOK || len(arr(out["accepted"])) != len(f.batches[0]) {
		t.Fatalf("organisation B's flush: %d %v", status, out)
	}
	var mine, theirs int64
	if e := h.pool.QueryRow(context.Background(),
		`SELECT (SELECT dropped FROM gfm.adapter_health WHERE org_id=$1::uuid AND harness='claude-code'),
  (SELECT dropped FROM gfm.adapter_health WHERE org_id=$2::uuid AND harness='claude-code')`,
		org, otherOrg).Scan(&mine, &theirs); e != nil {
		t.Fatal(e)
	}
	if mine != 2 || theirs != 2 {
		t.Fatalf("one organisation's flush changed another's health: %d and %d", mine, theirs)
	}

	// Replaying every batch once more changes nothing at all.
	before, _ := json.Marshal(usage["totals"])
	for _, batch := range f.batches {
		body, _ := json.Marshal(M{"events": batch})
		if status, out := h.post(t, "/v1/events:batch", token, string(body), nil); status != 200 {
			t.Fatalf("replay: %d %v", status, out)
		}
	}
	after, _ := json.Marshal(person.get(t,
		"/api/v1/orgs/"+org+"/repos/meridian/usage?window=90d")["totals"])
	if !bytes.Equal(before, after) {
		t.Fatalf("a full replay changed the totals:\nbefore %s\nafter  %s", before, after)
	}
}

// seedCatalogSkill writes the catalog row the usage module reads for scope and
// owner. The import pipeline is covered by its own tests.
func seedCatalogSkill(t *testing.T, h *deliveryHarness, org, repo, skillID, scope, owner, revision string) {
	t.Helper()
	blob := strings.Repeat("c", 64)
	exec(t, h.pool, `INSERT INTO gfm.blobs(org_id,sha256,size_bytes,content)
 VALUES($1::uuid,$2,1,'\x00') ON CONFLICT DO NOTHING`, org, blob)
	exec(t, h.pool, `INSERT INTO gfm.skills
 (org_id,skill_id,repo_id,name,scope,owner,path,publication_status,
  current_revision_id,published_revision_id)
 VALUES($1::uuid,$2,$3,$2,$4,$5,$6,'published',$7,$7)`,
		org, skillID, repo, scope, owner, "/.agents/skills/"+scope+"/SKILL.md", revision)
	exec(t, h.pool, `INSERT INTO gfm.skill_revisions
 (org_id,revision_id,skill_id,content_sha256,blob_sha256,frontmatter,source_path)
 VALUES($1::uuid,$2,$3,$2,$4,'{}'::jsonb,'SKILL.md')`, org, revision, skillID, blob)
}

// runReference replays the same batches through tools/telemetry and returns its
// report.
func runReference(t *testing.T, f *ledgerFixture, tenant string) M {
	t.Helper()
	dir := scratchDir(t, "reference-ledger")
	script := filepath.Join(dir, "driver.py")
	if e := os.WriteFile(script, []byte(referenceDriver), 0o600); e != nil {
		t.Fatal(e)
	}
	events := filepath.Join(dir, "batches.json")
	encoded, e := json.Marshal(f.batches)
	if e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(events, encoded, 0o600); e != nil {
		t.Fatal(e)
	}
	root, e := filepath.Abs("../..")
	if e != nil {
		t.Fatal(e)
	}
	cmd := osexec.Command("python3", script, root, events, filepath.Join(dir, "ledger.db"), tenant)
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	if e := cmd.Run(); e != nil {
		t.Skipf("the reference ledger could not be run (%v): %s", e, stderr.String())
	}
	var out M
	if e := json.Unmarshal(stdout.Bytes(), &out); e != nil {
		t.Fatalf("reference output: %v: %s", e, stdout.String())
	}
	return obj(out["report"])
}

func usageRows(t *testing.T, usage M) map[string]M {
	t.Helper()
	out := map[string]M{}
	for _, raw := range arr(usage["skills"]) {
		row := obj(raw)
		out[str(row["skill_id"])] = row
	}
	return out
}

func referenceRow(t *testing.T, reference M, skillID, revision string) M {
	t.Helper()
	for _, raw := range arr(reference["skills"]) {
		row := obj(raw)
		if str(row["skill_id"]) == skillID && str(row["revision"]) == revision {
			return row
		}
	}
	t.Fatalf("the reference has no row for %s@%s: %v", skillID, revision, reference["skills"])
	return nil
}

// compareWithReference asserts the measures both implementations define.
func compareWithReference(t *testing.T, usage, reference M) {
	t.Helper()
	rows := map[string]M{}
	for _, raw := range arr(usage["skills"]) {
		row := obj(raw)
		rows[str(row["skill_id"])+"@"+str(row["revision"])] = row
	}
	exposures, loads, expanded, unlinked := 0, 0, 0, 0
	for _, raw := range arr(reference["skills"]) {
		want := obj(raw)
		key := str(want["skill_id"]) + "@" + str(want["revision"])
		got, ok := rows[key]
		if !ok {
			t.Fatalf("the service has no row for %s; it has %v", key, keysOf(rows))
		}
		if intOf(t, got, "exposures") != intOf(t, want, "exposures") {
			t.Fatalf("%s exposures: service %v, reference %v", key, got["exposures"],
				want["exposures"])
		}
		if intOf(t, got, "loads_verified") != intOf(t, want, "loads") {
			t.Fatalf("%s loads: service %v, reference %v", key, got["loads_verified"],
				want["loads"])
		}
		// Contract 1.1.4: both implementations link a load to the exposure it
		// followed by skill_id and search_id; they must agree on the result.
		if intOf(t, got, "exposures_expanded") != intOf(t, want, "exposures_expanded") {
			t.Fatalf("%s exposures_expanded: service %v, reference %v", key,
				got["exposures_expanded"], want["exposures_expanded"])
		}
		if intOf(t, got, "loads_unlinked") != intOf(t, want, "loads_unlinked") {
			t.Fatalf("%s loads_unlinked: service %v, reference %v", key,
				got["loads_unlinked"], want["loads_unlinked"])
		}
		exposures += intOf(t, want, "exposures")
		loads += intOf(t, want, "loads")
		expanded += intOf(t, want, "exposures_expanded")
		unlinked += intOf(t, want, "loads_unlinked")
	}
	totals := obj(usage["totals"])
	if intOf(t, totals, "exposures") != exposures || intOf(t, totals, "loads_verified") != loads {
		t.Fatalf("totals disagree with the reference: service %v, reference %d/%d",
			totals, exposures, loads)
	}
	if intOf(t, totals, "exposures_expanded") != expanded || intOf(t, totals, "loads_unlinked") != unlinked {
		t.Fatalf("1.1.4 totals disagree with the reference: service %v, reference %d/%d",
			totals, expanded, unlinked)
	}
	if len(rows) != len(arr(reference["skills"])) {
		t.Fatalf("row counts differ: service %d, reference %d", len(rows),
			len(arr(reference["skills"])))
	}
}

func keysOf(m map[string]M) []string {
	out := []string{}
	for k := range m {
		out = append(out, k)
	}
	return out
}

func intOf(t *testing.T, m M, key string) int {
	t.Helper()
	switch v := m[key].(type) {
	case float64:
		return int(v)
	case int:
		return v
	}
	t.Fatalf("%s is %v (%T), not a number", key, m[key], m[key])
	return 0
}

// TestUseResponseNeverCountsAsUseOrHelped is U6.2: the delivery endpoints
// answering 200 is not evidence of anything.
func TestUseResponseNeverCountsAsUseOrHelped(t *testing.T) {
	h := newDeliveryHarness(t)
	a, _ := twoTenants(t, h)
	exec(t, h.pool, `INSERT INTO gfm.orgs(org_id,slug,name) VALUES($1::uuid,$2,$2)
 ON CONFLICT DO NOTHING`, a.OrgID, "org-a")
	person := h.signIn(t, "use-owner", "use@example.test")
	exec(t, h.pool, `INSERT INTO gfm.memberships(org_id,user_id,role) VALUES($1::uuid,$2::uuid,'owner')`,
		a.OrgID, userIDOf(t, h, "use-owner"))

	for i := 0; i < 5; i++ {
		status, body := h.post(t, "/v1/use", a.Token,
			fmt.Sprintf(`{"skill_id":"u:01","revision":%q}`, a.Revisions["u:01"]), nil)
		if status != http.StatusOK {
			t.Fatalf("use: %d %v", status, body)
		}
	}
	status, body := h.post(t, "/v1/search", a.Token,
		`{"schema_version":"1.1","query":"retry","workspace":{"repo_id":"meridian","cwd":"services/alpha"}}`, nil)
	if status != http.StatusOK {
		t.Fatalf("search: %d %v", status, body)
	}

	usage := person.get(t, "/api/v1/orgs/"+a.OrgID+"/repos/meridian/usage")
	totals := obj(usage["totals"])
	for _, key := range []string{"exposures", "loads_verified", "context_loaded",
		"use_reported", "use_observed", "use_episodes"} {
		if intOf(t, totals, key) != 0 {
			t.Fatalf("a server response moved %s: %v", key, totals)
		}
	}
	if totals["feedback"] != nil {
		t.Fatalf("a server response produced feedback: %v", totals["feedback"])
	}
	if len(arr(usage["skills"])) != 0 {
		t.Fatalf("a server response produced rows: %v", usage["skills"])
	}
	// No judgments and no observations: the ratio is absent, not zero per cent.
	export := person.get(t, "/api/v1/orgs/"+a.OrgID+"/repos/meridian/usage/export?format=json")
	if len(arr(export["rows"])) != 0 {
		t.Fatalf("export rows from server traffic: %v", export["rows"])
	}
	coverage := obj(usage["coverage"])
	if coverage["oldest_lag_s"] != nil {
		t.Fatalf("no adapter reported, so lag is unknown, not zero: %v", coverage)
	}
	if coverage["task_ids_present"] != false {
		t.Fatalf("no task identifiers exist: %v", coverage)
	}
}
