package domain_test

import (
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/usage/domain"
)

// The measure definitions, exercised without a database. Each case is one way
// the numbers would otherwise lie.

var base = time.Date(2026, 9, 1, 12, 0, 0, 0, time.UTC)

func event(kind string, offset time.Duration, id string, fields map[string]any) domain.Event {
	payload := map[string]any{"producer": "claude-code"}
	for k, v := range fields {
		payload[k] = v
	}
	payload["event_id"] = id
	return domain.Event{Type: kind, EventID: id, OccurredAt: base.Add(offset),
		Payload: payload}
}

func aggregate(t *testing.T, events []domain.Event, meta map[string]domain.SkillMeta,
	filter domain.Filter) domain.Report {
	t.Helper()
	window, ok := domain.WindowFor("30d", base.Add(time.Hour))
	if !ok {
		t.Fatal("30d is not a window")
	}
	return domain.Aggregate(domain.Input{Events: events, EventsReceived: len(events),
		Meta: meta, Window: window, Filter: filter, Now: base.Add(time.Hour)})
}

func onlyRow(t *testing.T, report domain.Report) domain.Skill {
	t.Helper()
	if len(report.Skills) != 1 {
		t.Fatalf("want one row, got %d: %v", len(report.Skills), report.Skills)
	}
	return report.Skills[0]
}

func TestWindowRejectsAnythingItDoesNotKnowInsteadOfWidening(t *testing.T) {
	if _, ok := domain.WindowFor("1y", base); ok {
		t.Fatal("an unknown window was accepted")
	}
	w, ok := domain.WindowFor("", base)
	if !ok || w.To != base || w.From != base.AddDate(0, 0, -30) {
		t.Fatalf("the default window is not 30 days ending at the watermark: %v", w)
	}
	seven, _ := domain.WindowFor("7d", base)
	if seven.From != base.AddDate(0, 0, -7) {
		t.Fatalf("7d: %v", seven)
	}
}

func TestExecutionMetricsKeepUnknownOutcomesAndCountRoutingSignals(t *testing.T) {
	report := aggregate(t, []domain.Event{
		event("task_started", 0, "t-start", map[string]any{"task_id": "task-1"}),
		event("task_finished", time.Minute, "t-ok", map[string]any{"task_id": "task-1", "outcome": "success", "input_tokens": 100, "output_tokens": 25, "tool_calls": 2, "duration_ms": 400}),
		event("task_finished", 2*time.Minute, "t-unknown", map[string]any{"task_id": "task-2", "outcome": "partial", "terminal_status": "harness_error", "duration_ms": 200}),
		event("search_requested", 3*time.Minute, "s-request", nil),
		event("search_results", 4*time.Minute, "s-results", map[string]any{"status": "error", "timings": map[string]any{"total_ms": 80}}),
		event("skill_load_requested", 5*time.Minute, "use-request", nil),
		event("skill_load_completed", 6*time.Minute, "ask", map[string]any{"status": "denied"}),
	}, nil, domain.Filter{})
	m := report.Totals.Metrics
	if m.TasksStarted != 1 || m.TasksFinished != 2 || m.TasksSucceeded != 1 || m.TasksFailed != 0 || m.TasksUnknown != 1 {
		t.Fatalf("task scorecard metrics: %+v", m)
	}
	if m.HarnessErrors != 1 || m.SearchRequests != 1 || m.SearchResults != 1 || m.SearchErrors != 1 || m.UseRequests != 1 || m.AskCount != 1 {
		t.Fatalf("routing scorecard metrics: %+v", m)
	}
	if m.InputTokens != 100 || m.OutputTokens != 25 || m.ToolCalls != 2 || m.LatencyMs != 680 || m.LatencySamples != 3 || !m.CostObserved || !m.TasksObserved {
		t.Fatalf("cost and time scorecard metrics: %+v", m)
	}
}

func TestExecutionMetricsTreatTimeoutAsHarnessError(t *testing.T) {
	report := aggregate(t, []domain.Event{
		event("task_finished", time.Minute, "t-timeout", map[string]any{
			"task_id": "task-timeout", "outcome": "unknown", "terminal_status": "timeout",
		}),
	}, nil, domain.Filter{})
	metrics := report.Totals.Metrics
	if metrics.TasksUnknown != 1 || metrics.HarnessErrors != 1 {
		t.Fatalf("timeout must remain unknown while counting as harness error: %+v", metrics)
	}
}

func TestHelpedRatioIsAbsentRatherThanZeroWhenNothingWasJudgedEitherWay(t *testing.T) {
	if r := domain.HelpedRatio(domain.Feedback{Mixed: 4, Unknown: 9, N: 13}); r != nil {
		t.Fatalf("mixed and unknown are not a denominator: %v", r)
	}
	r := domain.HelpedRatio(domain.Feedback{Helped: 19, Hindered: 0, N: 19})
	if r.Numerator != 19 || r.Denominator != 19 || !r.SmallSample {
		t.Fatalf("nineteen judgments must still be flagged: %v", r)
	}
	r = domain.HelpedRatio(domain.Feedback{Helped: 19, Hindered: 1, N: 20})
	if r.Denominator != 20 || r.SmallSample {
		t.Fatalf("twenty judgments clear the floor: %v", r)
	}
}

func TestRepeatedTransportIsNotRepeatedUse(t *testing.T) {
	skill, revision := "urn:skill:acme:a:b", "rev-1"
	fields := map[string]any{"skill_id": skill, "revision": revision}
	with := func(extra map[string]any) map[string]any {
		out := map[string]any{}
		for k, v := range fields {
			out[k] = v
		}
		for k, v := range extra {
			out[k] = v
		}
		return out
	}
	events := []domain.Event{
		// The same exposure, reported twice by a client that replayed its spool.
		event("card_injected", 0, "e1", with(map[string]any{"exposure_id": "x1"})),
		event("card_injected", time.Minute, "e2", with(map[string]any{"exposure_id": "x1"})),
		event("card_injected", 2*time.Minute, "e3", with(map[string]any{"exposure_id": "x2"})),
		// The same load, completed once and reported twice.
		event("skill_load_completed", 3*time.Minute, "e4",
			with(map[string]any{"load_id": "l1", "status": "ok"})),
		event("skill_load_completed", 4*time.Minute, "e5",
			with(map[string]any{"load_id": "l1", "status": "ok"})),
		// A denied load is not a load.
		event("skill_load_completed", 5*time.Minute, "e6",
			with(map[string]any{"load_id": "l2", "status": "denied"})),
		// One episode, reported and observed.
		event("skill_use_reported", 6*time.Minute, "e7",
			with(map[string]any{"use_id": "u1", "task_id": "t1"})),
		event("skill_use_observed", 7*time.Minute, "e8",
			with(map[string]any{"use_id": "u2", "task_id": "t1"})),
	}
	row := onlyRow(t, aggregate(t, events, nil, domain.Filter{}))
	if row.Exposures != 2 {
		t.Fatalf("exposures dedupe on exposure_id: %d", row.Exposures)
	}
	if row.LoadsVerified != 1 || row.ContextUnknown != 1 || row.ContextLoaded != 0 {
		t.Fatalf("loads: %+v", row)
	}
	if row.UseReported != 1 || row.UseObserved != 1 {
		t.Fatalf("reported and observed are separate: %+v", row)
	}
	if row.UseEpisodes != 1 {
		t.Fatalf("one task, one skill, one revision is one episode: %d", row.UseEpisodes)
	}
	if row.Feedback != nil || row.HelpedRatio != nil {
		t.Fatalf("no judgment is null, not zeros: %+v", row)
	}
}

func TestACorrectionReplacesTheJudgmentItNamesEvenWhenItArrivesLate(t *testing.T) {
	skill, revision := "urn:skill:acme:a:b", "rev-1"
	judgment := func(offset time.Duration, id, jid, verdict, corrects string) domain.Event {
		fields := map[string]any{"skill_id": skill, "revision": revision,
			"judgment_id": jid, "verdict": verdict}
		if corrects != "" {
			fields["corrects_judgment_id"] = corrects
		}
		return event("skill_feedback", offset, id, fields)
	}
	// Ingested out of order: the correction is written to the ledger first.
	events := []domain.Event{
		judgment(2*time.Hour, "e2", "j2", "helped", "j1"),
		judgment(time.Hour, "e1", "j1", "hindered", ""),
		judgment(time.Hour, "e3", "j3", "hindered", ""),
	}
	row := onlyRow(t, aggregate(t, events, nil, domain.Filter{}))
	if row.Feedback.N != 2 {
		t.Fatalf("three events, two episodes: %+v", row.Feedback)
	}
	if row.Feedback.Helped != 1 || row.Feedback.Hindered != 1 {
		t.Fatalf("the correction did not replace j1: %+v", row.Feedback)
	}
	if row.HelpedRatio.Numerator != 1 || row.HelpedRatio.Denominator != 2 {
		t.Fatalf("ratio: %+v", row.HelpedRatio)
	}
}

func TestARowNamesItsHarnessOnlyWhenOneAdapterProducedIt(t *testing.T) {
	skill, revision := "urn:skill:acme:a:b", "rev-1"
	card := func(id, exposure, producer string) domain.Event {
		return event("card_injected", 0, id, map[string]any{"skill_id": skill,
			"revision": revision, "exposure_id": exposure, "producer": producer})
	}
	one := onlyRow(t, aggregate(t, []domain.Event{card("e1", "x1", "claude-code")}, nil,
		domain.Filter{}))
	if one.Harness == nil || *one.Harness != "claude-code" {
		t.Fatalf("one adapter: %v", one.Harness)
	}
	two := onlyRow(t, aggregate(t, []domain.Event{card("e1", "x1", "claude-code"),
		card("e2", "x2", "copilot-cli")}, nil, domain.Filter{}))
	if two.Harness != nil {
		t.Fatalf("two adapters have no single answer: %v", *two.Harness)
	}
}

func TestEventsOlderThanTheWindowAreNotCounted(t *testing.T) {
	skill := "urn:skill:acme:a:b"
	old := event("card_injected", -60*24*time.Hour, "e-old",
		map[string]any{"skill_id": skill, "revision": "r", "exposure_id": "x-old"})
	fresh := event("card_injected", 0, "e-new",
		map[string]any{"skill_id": skill, "revision": "r", "exposure_id": "x-new"})
	row := onlyRow(t, aggregate(t, []domain.Event{old, fresh}, nil, domain.Filter{}))
	if row.Exposures != 1 {
		t.Fatalf("a two-month-old event landed in a 30-day window: %d", row.Exposures)
	}
}

func TestAScopeFilterCannotMatchASkillTheCatalogDoesNotKnow(t *testing.T) {
	known, unknown := "urn:skill:acme:a:known", "urn:skill:acme:a:unknown"
	meta := map[string]domain.SkillMeta{
		known: {RepoID: "meridian", Scope: "atlas", Owner: "platform", Revision: "r"}}
	events := []domain.Event{
		event("card_injected", 0, "e1", map[string]any{"skill_id": known,
			"revision": "r", "exposure_id": "x1"}),
		event("card_injected", 0, "e2", map[string]any{"skill_id": unknown,
			"revision": "r", "exposure_id": "x2"}),
	}
	// No filter: both rows, the unknown one without a scope or an owner.
	all := aggregate(t, events, meta, domain.Filter{Repo: "meridian"})
	if len(all.Skills) != 2 {
		t.Fatalf("an unattributed skill must still be counted: %v", all.Skills)
	}
	for _, row := range all.Skills {
		if row.SkillID == unknown && (row.Scope != nil || row.Owner != nil) {
			t.Fatalf("an unknown skill was given a scope: %+v", row)
		}
	}
	// With a scope filter: only the one the catalog places in that scope.
	filtered := aggregate(t, events, meta, domain.Filter{Repo: "meridian", Scope: "atlas"})
	if len(filtered.Skills) != 1 || filtered.Skills[0].SkillID != known {
		t.Fatalf("scope filter: %v", filtered.Skills)
	}
	// A row whose skill belongs to another repository is not this repository's.
	other := aggregate(t, events, meta, domain.Filter{Repo: "other"})
	for _, row := range other.Skills {
		if row.SkillID == known {
			t.Fatalf("a skill of another repository appeared: %+v", row)
		}
	}
}

func TestZeroLoadsNeedsAnOpportunityBeforeItAsksForAReview(t *testing.T) {
	fresh, stale := "urn:skill:acme:a:fresh", "urn:skill:acme:a:stale"
	now := base.Add(time.Hour)
	meta := map[string]domain.SkillMeta{
		fresh: {RepoID: "meridian", Scope: "atlas", Revision: "r1",
			PublishedRevision: "r1", Published: true, PublishedAt: now.Add(-time.Hour)},
		stale: {RepoID: "meridian", Scope: "atlas", Revision: "r2",
			PublishedRevision: "r2", Published: true, PublishedAt: now.AddDate(0, 0, -20)},
	}
	report := aggregate(t, nil, meta, domain.Filter{Repo: "meridian"})
	reasons := map[string]string{}
	for _, item := range report.Computed {
		reasons[item.SkillID] = item.Reason
	}
	if reasons[stale] != "zero_loads" {
		t.Fatalf("a skill published three weeks ago with no loads: %v", report.Computed)
	}
	if _, raised := reasons[fresh]; raised {
		t.Fatalf("a skill published an hour ago and never shown is not evidence: %v",
			report.Computed)
	}
}

func TestAnExposureIsExpandedOnlyWhenItsOwnSearchLedToAVerifiedLoadOfTheSameSkill(t *testing.T) {
	// Contract 1.1.4. Two skills share one search; only one of them was then
	// loaded. The load names the search it followed; a second load of the
	// same skill does not, and a load of the other skill under a different
	// revision name still links, because the link is by skill_id and
	// search_id, not by revision.
	a, b := "urn:skill:acme:a:one", "urn:skill:acme:a:two"
	events := []domain.Event{
		event("card_injected", 0, "e1", map[string]any{"skill_id": a, "revision": "card-1",
			"exposure_id": "x1", "search_id": "s1"}),
		event("card_injected", 0, "e2", map[string]any{"skill_id": b, "revision": "card-1",
			"exposure_id": "x2", "search_id": "s1"}),
		// A second exposure of `a` from another search, never followed by a load.
		event("card_injected", time.Minute, "e3", map[string]any{"skill_id": a, "revision": "card-1",
			"exposure_id": "x3", "search_id": "s2"}),
		// The body of `a` fetched after search s1, under the catalog revision name.
		event("skill_load_completed", 2*time.Minute, "e4", map[string]any{"skill_id": a,
			"revision": "catalog-1", "load_id": "l1", "status": "ok", "search_id": "s1"}),
		// The same load replayed without the field must not unlink it.
		event("skill_load_completed", 3*time.Minute, "e5", map[string]any{"skill_id": a,
			"revision": "catalog-1", "load_id": "l1", "status": "ok"}),
		// A load of `a` by an adapter that does not know which exposure it followed.
		event("skill_load_completed", 4*time.Minute, "e6", map[string]any{"skill_id": a,
			"revision": "catalog-1", "load_id": "l2", "status": "ok"}),
		// A denied load carrying a search_id is not a load and links nothing.
		event("skill_load_completed", 5*time.Minute, "e7", map[string]any{"skill_id": b,
			"revision": "card-1", "load_id": "l3", "status": "denied", "search_id": "s1"}),
	}
	report := aggregate(t, events, nil, domain.Filter{})
	rows := map[string]domain.Skill{}
	for _, r := range report.Skills {
		rows[r.SkillID+"@"+*r.Revision] = r
	}
	if len(rows) != 3 {
		t.Fatalf("want a@card-1, a@catalog-1 and b@card-1, got %v", report.Skills)
	}
	aCard := rows[a+"@card-1"]
	if aCard.Exposures != 2 || aCard.ExposuresExpanded != 1 {
		t.Fatalf("one of a's two exposures was followed by its body: %+v", aCard)
	}
	aCatalog := rows[a+"@catalog-1"]
	if aCatalog.LoadsVerified != 2 || aCatalog.LoadsUnlinked != 1 {
		t.Fatalf("two loads of a, one without a search_id: %+v", aCatalog)
	}
	bCard := rows[b+"@card-1"]
	if bCard.Exposures != 1 || bCard.ExposuresExpanded != 0 || bCard.LoadsVerified != 0 {
		t.Fatalf("b was shown in the same search but never loaded: %+v", bCard)
	}
	if report.Totals.ExposuresExpanded != 1 || report.Totals.LoadsUnlinked != 1 {
		t.Fatalf("totals: %+v", report.Totals)
	}
}

func TestAnAdapterThatNeverSendsSearchIDLeavesEveryLoadUnlinkedRatherThanCountingCardsAsSufficient(t *testing.T) {
	skill := "urn:skill:acme:a:b"
	events := []domain.Event{
		event("card_injected", 0, "e1", map[string]any{"skill_id": skill, "revision": "r",
			"exposure_id": "x1", "search_id": "s1"}),
		event("skill_load_completed", time.Minute, "e2", map[string]any{"skill_id": skill,
			"revision": "r", "load_id": "l1", "status": "ok"}),
	}
	row := onlyRow(t, aggregate(t, events, nil, domain.Filter{}))
	if row.ExposuresExpanded != 0 || row.LoadsUnlinked != 1 || row.LoadsVerified != 1 {
		t.Fatalf("an unlinked load is unknown provenance, not a sufficient card: %+v", row)
	}
}
