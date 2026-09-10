// Package domain turns decoded telemetry events into the usage report. It has
// no I/O: no database, no HTTP, no clock of its own. Everything it needs — the
// events, the catalog metadata of the skills they name, the window and the
// filters — arrives as arguments, so the definitions below can be read, tested
// and compared against tools/telemetry/report.py without a server.
//
// Four rules run through all of it, and each one is a way the numbers would
// otherwise lie.
//
// A server response is never evidence. Nothing here reads an HTTP status: an
// exposure exists because an adapter said it emitted a card, a load exists
// because an adapter said it completed one. `/v1/use` answering 200 moves no
// counter (PRODUCT-PIVOT §9 AC2).
//
// Unknown is not zero. A skill nobody judged has `feedback: null`, not five
// zeros; a ratio with no denominator is `null`, not 0 %; an adapter that cannot
// confirm that a card reached the model's context counts as `context_unknown`,
// not as a failure to load.
//
// Transport repetition is not use. Exposures dedupe on `exposure_id`, verified
// loads on `load_id`, and applied episodes on `(task, skill, revision)`, so a
// retried batch, a duplicated event or a client that re-sends its spool changes
// nothing (SEARCH-USE-TELEMETRY §4).
//
// A judgment is one vote. A correction names the judgment it replaces and takes
// its place; it does not add a second opinion for the same episode.
package domain

import (
	"encoding/json"
	"sort"
	"strings"
	"time"
)

// Event is one decoded row of the ledger.
type Event struct {
	Type       string
	OccurredAt time.Time
	EventID    string
	Payload    map[string]any
}

// Str reads a string field of the payload, or "" when it is absent or of
// another type. A field of the wrong type is missing data, not a crash.
func (e Event) Str(key string) string {
	s, _ := e.Payload[key].(string)
	return s
}

// Int reads a numeric field. The second result separates "absent" from "zero",
// which is the whole point of the coverage numbers. json.Number is one of the
// accepted shapes because the delivery endpoint decodes request bodies that way.
func (e Event) Int(key string) (int, bool) {
	switch v := e.Payload[key].(type) {
	case json.Number:
		parsed, err := v.Int64()
		if err != nil {
			return 0, false
		}
		return int(parsed), true
	case float64:
		return int(v), true
	case int:
		return v, true
	case int64:
		return int(v), true
	}
	return 0, false
}

// SkillMeta is what the catalog knows about one skill. The usage module reads
// it; it never writes any of it (module-boundaries-go: telemetry does not
// modify skills or membership).
type SkillMeta struct {
	RepoID            string
	Scope             string
	Owner             string
	Revision          string // gfm.skills.current_revision_id
	PublishedRevision string // gfm.skills.published_revision_id
	Published         bool
	PublishedAt       time.Time
}

// Filter narrows the view. Every field is optional; an empty field filters
// nothing. `Repo` is not user input — it is the repository the request proved,
// so it is never echoed.
//
// The tags are the query parameter names on purpose: `/usage` echoes this
// struct back as `filters`, and a reader comparing what they asked for with
// what was applied has to see the same words (API-CONTRACT §5.5). `omitempty`
// keeps "not asked for" and "asked for and empty" distinguishable.
type Filter struct {
	Repo     string `json:"-"`
	Scope    string `json:"scope,omitempty"`
	SkillID  string `json:"skill_id,omitempty"`
	Revision string `json:"revision,omitempty"`
	Harness  string `json:"harness,omitempty"`
	// Window is the applied window spec, including the default: unlike the
	// others it always has a value, because a report always covers a period.
	Window string `json:"window,omitempty"`
}

// Revisions resolves the identifiers one revision answers to.
//
// A revision has three names: the catalog `revision_id`, the `card_revision`
// the publication minted for it, and its `content_sha256`. The delivery path
// hands a harness the card revision and adapter telemetry echoes it; a judgment
// recorded in the UI names the catalog revision. Counting those as two rows
// would report one skill twice, so every identifier is resolved to the catalog
// revision before anything is counted (API-CONTRACT §5.5).
//
// The catalog revision is the canonical one rather than the card revision
// because it is the key the reference implementation (tools/telemetry/report.py)
// can also compute: it has the ledger and no catalog, and §5.5 requires the two
// to agree for the same event set.
type Revisions struct {
	// Canonical maps any of the three identifiers to the catalog revision.
	Canonical map[string]string
	// Card and Content are keyed by the catalog revision.
	Card    map[string]string
	Content map[string]string
}

// canonical resolves one identifier. An identifier the catalog does not know is
// returned unchanged: the ledger saw it, so it is still counted, under the only
// name anybody has for it.
func (r Revisions) canonical(revision string) string {
	if revision == "" {
		return ""
	}
	if known, ok := r.Canonical[revision]; ok {
		return known
	}
	return revision
}

// Window is the reporting period. `Watermark` is the newest `received_at` in
// the ledger, so the window does not move while a reader is looking at it and
// two readers at different clocks see the same numbers.
type Window struct {
	From      time.Time `json:"from"`
	To        time.Time `json:"to"`
	Watermark time.Time `json:"watermark"`
}

// Windows are the three the contract exposes.
var windowDays = map[string]int{"7d": 7, "30d": 30, "90d": 90}

// DefaultWindow is used when the caller names none.
const DefaultWindow = "30d"

// WindowFor builds the window for a spec. An unknown spec is refused rather
// than silently widened: a reader who asked for a week must not be shown a
// quarter.
func WindowFor(spec string, watermark time.Time) (Window, bool) {
	if spec == "" {
		spec = DefaultWindow
	}
	days, ok := windowDays[spec]
	if !ok {
		return Window{}, false
	}
	return Window{From: watermark.AddDate(0, 0, -days).UTC(), To: watermark.UTC(),
		Watermark: watermark.UTC()}, true
}

// Feedback counts one bucket's verdicts. `N` is the number of judgments behind
// them, after corrections replaced what they corrected.
type Feedback struct {
	Helped        int `json:"helped"`
	Hindered      int `json:"hindered"`
	Mixed         int `json:"mixed"`
	NotApplicable int `json:"not_applicable"`
	Unknown       int `json:"unknown"`
	N             int `json:"n"`
}

// Ratio is a proportion that always shows its own arithmetic. There is no
// percentage field: below the floor the reader gets counts, and a reader who
// only ever sees a percentage cannot tell 1/1 from 200/200.
type Ratio struct {
	Numerator   int  `json:"numerator"`
	Denominator int  `json:"denominator"`
	SmallSample bool `json:"small_sample"`
}

// SmallSampleFloor is the eligibility floor from PRODUCT-PIVOT §9 AC3. Twenty
// judgments is not statistical proof; it is the point below which a percentage
// is misleading enough to withhold.
const SmallSampleFloor = 20

// HelpedRatio is helped / (helped + hindered), or nil when nothing was judged
// either way. Zero judgments is not 0 % usability.
func HelpedRatio(f Feedback) *Ratio {
	denominator := f.Helped + f.Hindered
	if denominator == 0 {
		return nil
	}
	return &Ratio{Numerator: f.Helped, Denominator: denominator,
		SmallSample: denominator < SmallSampleFloor}
}

// Totals is the sum over the rows the filter selected.
type Totals struct {
	Exposures      int `json:"exposures"`
	LoadsVerified  int `json:"loads_verified"`
	ContextLoaded  int `json:"context_loaded"`
	ContextUnknown int `json:"context_unknown"`
	UseReported    int `json:"use_reported"`
	UseObserved    int `json:"use_observed"`
	UseEpisodes    int `json:"use_episodes"`
	// ExposuresExpanded and LoadsUnlinked (contract 1.1.4) say whether the
	// card was enough. See Skill for the definitions.
	ExposuresExpanded int              `json:"exposures_expanded"`
	LoadsUnlinked     int              `json:"loads_unlinked"`
	Feedback          *Feedback        `json:"feedback"`
	Metrics           ExecutionMetrics `json:"metrics"`
}

// ExecutionMetrics powers the organisation scorecards. These are task and
// harness observations, separate from per-skill delivery counts.
type ExecutionMetrics struct {
	TasksStarted   int  `json:"tasks_started"`
	TasksFinished  int  `json:"tasks_finished"`
	TasksSucceeded int  `json:"tasks_succeeded"`
	TasksFailed    int  `json:"tasks_failed"`
	TasksUnknown   int  `json:"tasks_unknown"`
	HarnessErrors  int  `json:"harness_errors"`
	SearchRequests int  `json:"search_requests"`
	SearchResults  int  `json:"search_results"`
	SearchErrors   int  `json:"search_errors"`
	UseRequests    int  `json:"use_requests"`
	AskCount       int  `json:"ask_count"`
	InputTokens    int  `json:"input_tokens"`
	OutputTokens   int  `json:"output_tokens"`
	ToolCalls      int  `json:"tool_calls"`
	LatencyMs      int  `json:"latency_ms"`
	LatencySamples int  `json:"latency_samples"`
	TasksObserved  bool `json:"tasks_observed"`
	CostObserved   bool `json:"cost_observed"`
}

// Skill is one `(skill_id, revision)` row of the report.
type Skill struct {
	SkillID  string  `json:"skill_id"`
	Revision *string `json:"revision"`
	// CardRevision and ContentSHA256 are the same revision's other two names,
	// or nil when the catalog does not know this revision at all.
	CardRevision   *string `json:"card_revision"`
	ContentSHA256  *string `json:"content_sha256"`
	Scope          *string `json:"scope"`
	Owner          *string `json:"owner"`
	Harness        *string `json:"harness"`
	Exposures      int     `json:"exposures"`
	LoadsVerified  int     `json:"loads_verified"`
	ContextLoaded  int     `json:"context_loaded"`
	ContextUnknown int     `json:"context_unknown"`
	UseReported    int     `json:"use_reported"`
	UseObserved    int     `json:"use_observed"`
	UseEpisodes    int     `json:"use_episodes"`
	// ExposuresExpanded counts exposures whose search_id also appears on a
	// verified load of the same skill in the window: the card was followed by
	// the body. Linked by skill_id and search_id, not by revision, because the
	// card and the body of one skill may carry different revision names and
	// the question is "was the body fetched after this card", not "which one".
	ExposuresExpanded int `json:"exposures_expanded"`
	// LoadsUnlinked counts verified loads that carried no search_id. That is
	// unknown provenance, never "loaded without a card": while it is non-zero,
	// Exposures − ExposuresExpanded is an upper bound on cards that sufficed.
	LoadsUnlinked int       `json:"loads_unlinked"`
	Feedback      *Feedback `json:"feedback"`
	HelpedRatio   *Ratio    `json:"helped_ratio"`
	ZeroLoads     bool      `json:"zero_loads"`
}

// Coverage says how much of what happened this report can see. It is reported
// beside every number rather than folded into one, because an absent event and
// an event that says "nothing happened" are different facts.
type Coverage struct {
	EventsReceived  int  `json:"events_received"`
	DroppedReported int  `json:"dropped_reported"`
	OldestLagS      *int `json:"oldest_lag_s"`
	TaskIDsPresent  bool `json:"task_ids_present"`
}

// Computed is a queue item this report derived rather than read from
// gfm.owner_queue. It is an observation asking for a decision, never a decision.
type Computed struct {
	Reason   string
	SkillID  string
	Revision string
	Since    time.Time
	Evidence map[string]any
}

// Report is everything Aggregate produces.
type Report struct {
	Window   Window
	Coverage Coverage
	Totals   Totals
	Skills   []Skill
	Computed []Computed
}

// Input is what Aggregate needs.
type Input struct {
	// Events are the ledger rows of the six measured types plus
	// telemetry_health, for one organisation. Aggregate applies the window
	// itself, so a caller that over-fetches is correct and merely slower.
	Events []Event
	// EventsReceived counts every row of every type the ledger received inside
	// the window. It comes from the ledger, not from Events, because the
	// measured types are a subset and coverage has to describe the whole flow.
	EventsReceived int
	// OldestLagS is the worst ingest lag the projection observed, or nil when
	// no adapter has reported: unknown lag is not zero lag.
	OldestLagS *int
	// Meta is the catalog view of the skills, keyed by skill_id, for the whole
	// organisation. A skill_id absent from it is still counted — the ledger saw
	// it — but it carries no scope or owner.
	Meta   map[string]SkillMeta
	Window Window
	Filter Filter
	// Revisions resolves the two revision namespaces into one before counting.
	// An empty index is the identity: every revision stands for itself.
	Revisions Revisions
	// Now anchors the "published for at least a week" half of the zero-loads
	// rule. It is an argument so the rule is testable without waiting a week.
	Now time.Time
}

// ZeroLoadDays is the second half of the zero-loads rule: a skill that has been
// published for a week has had an opportunity to be loaded, whether or not a
// card was ever put in front of an agent.
const ZeroLoadDays = 7

// verifiedLoadStatus is the closed set of `skill_load_completed.status` values
// that mean the client actually got the revision. A denied, errored or
// truncated load is not a load (SEARCH-USE-TELEMETRY §6).
var verifiedLoadStatus = map[string]bool{"ok": true, "verified": true}

// contextConfirmed is the adapter's own confirmation that the loaded bytes
// reached the model's context. Everything else — `download_verified`,
// `unsupported`, a missing field — is context_unknown. An adapter that cannot
// observe context must not be read as one that observed failure.
const contextConfirmed = "context_loaded"

type bucket struct {
	skillID   string
	revision  string
	exposures map[string]bool
	// exposureSearch remembers the search_id of each exposure so that a later
	// verified load carrying the same search_id can be linked back to it.
	exposureSearch map[string]string
	loads          map[string]bool
	// loadSearch is the search_id of each verified load, "" when the adapter
	// did not know which exposure it followed.
	loadSearch map[string]string
	context    map[string]bool
	reported   map[string]bool
	observed   map[string]bool
	episodes   map[string]bool
	producers  map[string]bool
	feedback   Feedback
}

func newBucket(skillID, revision string) *bucket {
	return &bucket{skillID: skillID, revision: revision,
		exposures: map[string]bool{}, exposureSearch: map[string]string{},
		loads: map[string]bool{}, loadSearch: map[string]string{}, context: map[string]bool{},
		reported: map[string]bool{}, observed: map[string]bool{}, episodes: map[string]bool{},
		producers: map[string]bool{}}
}

// judgment is one resolved opinion about one episode.
type judgment struct {
	verdict  string
	skillID  string
	revision string
	producer string
}

// Aggregate computes the report. It is deterministic: the same events in any
// order produce the same numbers.
func Aggregate(in Input) Report {
	// `in` is a copy, so resolving the filter here cannot change what the
	// caller echoes back: `filters.revision` must repeat what was asked for,
	// whichever of the three identifiers that was.
	in.Filter.Revision = in.Revisions.canonical(in.Filter.Revision)
	report := Report{Window: in.Window}
	report.Coverage.EventsReceived = in.EventsReceived
	report.Coverage.OldestLagS = in.OldestLagS

	windowed := make([]Event, 0, len(in.Events))
	for _, e := range in.Events {
		// The window's upper bound is the watermark, which is the newest thing
		// the ledger received. An event whose own clock ran past it was still
		// received, so it stays in the newest window rather than vanishing.
		if e.OccurredAt.Before(in.Window.From) {
			continue
		}
		if e.Type == "telemetry_health" {
			if dropped, ok := e.Int("dropped"); ok && dropped > 0 {
				report.Coverage.DroppedReported += dropped
			}
			continue
		}
		if e.Str("task_id") != "" {
			report.Coverage.TaskIDsPresent = true
		}
		windowed = append(windowed, e)
	}

	verdicts := resolveFeedback(windowed)

	buckets := map[string]*bucket{}
	get := func(skillID, revision string) *bucket {
		key := skillID + "\x00" + revision
		b := buckets[key]
		if b == nil {
			b = newBucket(skillID, revision)
			buckets[key] = b
		}
		return b
	}
	keep := func(skillID, revision, producer string) bool {
		return in.Filter.matches(skillID, revision, producer, in.Meta)
	}

	for _, e := range windowed {
		updateMetrics(&report.Totals.Metrics, e)
		skillID, producer := e.Str("skill_id"), e.Str("producer")
		revision := in.Revisions.canonical(e.Str("revision"))
		if skillID == "" {
			// An unresolved selector cannot be attributed to a revision-level
			// outcome (SEARCH-USE-TELEMETRY §4).
			continue
		}
		if !keep(skillID, revision, producer) {
			continue
		}
		b := get(skillID, revision)
		if producer != "" {
			b.producers[producer] = true
		}
		switch e.Type {
		case "card_injected":
			id := fallbackID(e.Str("exposure_id"), e.EventID)
			b.exposures[id] = true
			if s := e.Str("search_id"); s != "" {
				b.exposureSearch[id] = s
			}
		case "skill_load_completed":
			if !verifiedLoadStatus[e.Str("status")] {
				continue
			}
			id := fallbackID(e.Str("load_id"), e.EventID)
			b.loads[id] = true
			// search_id on a completed load is optional and additive
			// (contract 1.1.4); a replayed duplicate must not turn a linked
			// load into an unlinked one, so a known search_id wins.
			if s := e.Str("search_id"); s != "" || b.loadSearch[id] == "" {
				b.loadSearch[id] = s
			}
			if e.Str("context_confirmation") == contextConfirmed {
				b.context[id] = true
			}
		case "skill_use_reported":
			b.reported[fallbackID(e.Str("use_id"), e.EventID)] = true
			addEpisode(b, e, skillID, revision)
		case "skill_use_observed":
			b.observed[fallbackID(e.Str("use_id"), e.EventID)] = true
			addEpisode(b, e, skillID, revision)
		}
	}

	for _, j := range verdicts {
		// A judgment recorded in the UI names the catalog revision and one from
		// an adapter names the card revision. Both are opinions about the same
		// revision and belong in the same row.
		revision := in.Revisions.canonical(j.revision)
		if !keep(j.skillID, revision, j.producer) {
			continue
		}
		b := get(j.skillID, revision)
		if j.producer != "" {
			b.producers[j.producer] = true
		}
		switch j.verdict {
		case "helped":
			b.feedback.Helped++
		case "hindered":
			b.feedback.Hindered++
		case "mixed":
			b.feedback.Mixed++
		case "not_applicable":
			b.feedback.NotApplicable++
		default:
			b.feedback.Unknown++
		}
		b.feedback.N++
	}

	// A load is linked to the exposure it followed by skill_id and search_id
	// across every revision row of that skill (contract 1.1.4): the card and
	// the body of one skill may carry different revision names.
	linkedSearches := map[string]map[string]bool{}
	for _, b := range buckets {
		for _, s := range b.loadSearch {
			if s == "" {
				continue
			}
			if linkedSearches[b.skillID] == nil {
				linkedSearches[b.skillID] = map[string]bool{}
			}
			linkedSearches[b.skillID][s] = true
		}
	}

	rows := make([]*bucket, 0, len(buckets))
	for _, b := range buckets {
		rows = append(rows, b)
	}
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].skillID != rows[j].skillID {
			return rows[i].skillID < rows[j].skillID
		}
		return rows[i].revision < rows[j].revision
	})

	totalFeedback := Feedback{}
	judged := false
	for _, b := range rows {
		meta := in.Meta[b.skillID]
		row := Skill{
			SkillID:        b.skillID,
			Revision:       optional(b.revision),
			CardRevision:   optional(in.Revisions.Card[b.revision]),
			ContentSHA256:  optional(in.Revisions.Content[b.revision]),
			Scope:          optional(meta.Scope),
			Owner:          optional(meta.Owner),
			Harness:        soleProducer(b.producers),
			Exposures:      len(b.exposures),
			LoadsVerified:  len(b.loads),
			ContextLoaded:  len(b.context),
			ContextUnknown: len(b.loads) - len(b.context),
			UseReported:    len(b.reported),
			UseObserved:    len(b.observed),
			UseEpisodes:    len(b.episodes),
			ZeroLoads:      len(b.loads) == 0,
		}
		for _, s := range b.exposureSearch {
			if linkedSearches[b.skillID][s] {
				row.ExposuresExpanded++
			}
		}
		for id := range b.loads {
			if b.loadSearch[id] == "" {
				row.LoadsUnlinked++
			}
		}
		if b.feedback.N > 0 {
			f := b.feedback
			row.Feedback = &f
			row.HelpedRatio = HelpedRatio(f)
			judged = true
			totalFeedback.Helped += f.Helped
			totalFeedback.Hindered += f.Hindered
			totalFeedback.Mixed += f.Mixed
			totalFeedback.NotApplicable += f.NotApplicable
			totalFeedback.Unknown += f.Unknown
			totalFeedback.N += f.N
		}
		report.Totals.Exposures += row.Exposures
		report.Totals.LoadsVerified += row.LoadsVerified
		report.Totals.ContextLoaded += row.ContextLoaded
		report.Totals.ContextUnknown += row.ContextUnknown
		report.Totals.UseReported += row.UseReported
		report.Totals.UseObserved += row.UseObserved
		report.Totals.ExposuresExpanded += row.ExposuresExpanded
		report.Totals.LoadsUnlinked += row.LoadsUnlinked
		report.Skills = append(report.Skills, row)
	}
	if judged {
		f := totalFeedback
		report.Totals.Feedback = &f
	}
	report.Totals.UseEpisodes = countEpisodes(rows)
	if report.Skills == nil {
		report.Skills = []Skill{}
	}
	report.Computed = computeQueue(report.Skills, in)
	return report
}

// updateMetrics reads explicit task, routing and harness counters. Missing
// optional values stay unknown; the observed flags prevent the UI from
// presenting an absent measurement as a zero.
func updateMetrics(m *ExecutionMetrics, e Event) {
	switch e.Type {
	case "task_started":
		m.TasksStarted++
		m.TasksObserved = true
	case "task_finished":
		m.TasksFinished++
		m.TasksObserved = true
		switch strings.ToLower(e.Str("outcome")) {
		case "success", "succeeded", "pass", "passed":
			m.TasksSucceeded++
		case "failure", "failed", "fail":
			m.TasksFailed++
		default:
			m.TasksUnknown++
		}
		status := strings.ToLower(e.Str("terminal_status"))
		if strings.Contains(status, "harness") || strings.Contains(status, "error") {
			m.HarnessErrors++
		}
		addMetricInt(e, "input_tokens", &m.InputTokens, &m.CostObserved)
		addMetricInt(e, "output_tokens", &m.OutputTokens, &m.CostObserved)
		addMetricInt(e, "tool_calls", &m.ToolCalls, &m.CostObserved)
		if value, ok := e.Int("duration_ms"); ok {
			m.LatencyMs += value
			m.LatencySamples++
		}
	case "search_requested":
		m.SearchRequests++
	case "search_results":
		m.SearchResults++
		status := strings.ToLower(e.Str("status"))
		if status != "" && status != "ok" && status != "abstained" {
			m.SearchErrors++
		}
		if timings, ok := e.Payload["timings"].(map[string]any); ok {
			if value, ok := numberFromAny(timings["total_ms"]); ok {
				m.LatencyMs += value
				m.LatencySamples++
			}
		}
	case "skill_load_requested":
		m.UseRequests++
	case "skill_load_completed":
		if strings.EqualFold(e.Str("status"), "denied") || strings.EqualFold(e.Str("status"), "ask") {
			m.AskCount++
		}
	}
}

func addMetricInt(e Event, key string, dst *int, observed *bool) {
	if value, ok := e.Int(key); ok {
		*dst += value
		*observed = true
	}
}

func numberFromAny(value any) (int, bool) {
	switch v := value.(type) {
	case json.Number:
		n, err := v.Int64()
		return int(n), err == nil
	case float64:
		return int(v), true
	case int:
		return v, true
	case int64:
		return int(v), true
	default:
		return 0, false
	}
}

// addEpisode records one applied episode. An event with no task_id has no
// episode identity: it is counted as an application and left out of the episode
// count rather than invented as its own task.
func addEpisode(b *bucket, e Event, skillID, revision string) {
	task := e.Str("task_id")
	if task == "" {
		return
	}
	b.episodes[task+"\x00"+skillID+"\x00"+revision] = true
}

// countEpisodes counts distinct (task, skill, revision) triples across every
// row, so a reported and an observed application of the same skill in the same
// task is one episode, not two (SEARCH-USE-TELEMETRY §3: "deduplicating their
// linked episode when showing a combined count. Never add them blindly").
func countEpisodes(rows []*bucket) int {
	seen := map[string]bool{}
	for _, b := range rows {
		for key := range b.episodes {
			seen[key] = true
		}
	}
	return len(seen)
}

// resolveFeedback turns feedback events into one opinion per episode.
//
// A judgment is keyed by the judgment it is about: an event that names
// `corrects_judgment_id` is filed under that identifier and replaces what was
// there, and a second event re-using a judgment_id replaces it too. Ordering is
// by occurred_at then event_id, so a correction that arrives late still wins
// and the outcome does not depend on ingest order.
func resolveFeedback(events []Event) []judgment {
	feedback := make([]Event, 0)
	for _, e := range events {
		if e.Type == "skill_feedback" {
			feedback = append(feedback, e)
		}
	}
	sort.SliceStable(feedback, func(i, j int) bool {
		if !feedback[i].OccurredAt.Equal(feedback[j].OccurredAt) {
			return feedback[i].OccurredAt.Before(feedback[j].OccurredAt)
		}
		return feedback[i].EventID < feedback[j].EventID
	})
	resolved := map[string]judgment{}
	order := []string{}
	for _, e := range feedback {
		key := e.Str("corrects_judgment_id")
		if key == "" {
			key = e.Str("judgment_id")
		}
		if key == "" {
			key = e.EventID
		}
		if _, seen := resolved[key]; !seen {
			order = append(order, key)
		}
		resolved[key] = judgment{verdict: e.Str("verdict"), skillID: e.Str("skill_id"),
			revision: e.Str("revision"), producer: e.Str("producer")}
	}
	out := make([]judgment, 0, len(order))
	for _, key := range order {
		j := resolved[key]
		if j.skillID == "" {
			continue
		}
		out = append(out, j)
	}
	return out
}

// computeQueue derives the two review reasons that come from telemetry rather
// than from a source change. Both are observations: "this revision was called
// harmful at least once" and "nobody loaded this published skill". Neither says
// the skill is wrong, and neither changes it.
func computeQueue(rows []Skill, in Input) []Computed {
	items := []Computed{}
	loaded := map[string]bool{}
	exposed := map[string]bool{}
	for _, row := range rows {
		revision := ""
		if row.Revision != nil {
			revision = *row.Revision
		}
		meta := in.Meta[row.SkillID]
		if row.LoadsVerified > 0 {
			loaded[row.SkillID] = true
		}
		if row.Exposures > 0 {
			exposed[row.SkillID] = true
		}
		if row.Feedback != nil && row.Feedback.Hindered > 0 && revision != "" &&
			(revision == meta.Revision || revision == meta.PublishedRevision) {
			items = append(items, Computed{Reason: "negative_feedback", SkillID: row.SkillID,
				Revision: revision, Since: in.Window.To,
				Evidence: map[string]any{"hindered": row.Feedback.Hindered,
					"judgments": row.Feedback.N, "window_from": in.Window.From.Format(time.RFC3339)}})
		}
	}
	skills := make([]string, 0, len(in.Meta))
	for id := range in.Meta {
		skills = append(skills, id)
	}
	sort.Strings(skills)
	for _, id := range skills {
		meta := in.Meta[id]
		if !meta.Published || loaded[id] {
			continue
		}
		if in.Filter.Repo != "" && meta.RepoID != in.Filter.Repo {
			continue
		}
		// The harness filter narrows observed traffic; it cannot narrow the
		// absence of traffic, so it is not applied to a zero-loads candidate.
		scoped := in.Filter
		scoped.Harness = ""
		if !scoped.matches(id, meta.PublishedRevision, "", in.Meta) {
			continue
		}
		days := 0
		if !meta.PublishedAt.IsZero() {
			days = int(in.Now.Sub(meta.PublishedAt).Hours() / 24)
		}
		if !exposed[id] && days < ZeroLoadDays {
			// Too new and never shown: silence here is absence of opportunity,
			// not absence of value.
			continue
		}
		items = append(items, Computed{Reason: "zero_loads", SkillID: id,
			Revision: meta.PublishedRevision, Since: in.Window.To,
			Evidence: map[string]any{"exposures_in_window": exposureCount(rows, id),
				"days_published": days, "window_from": in.Window.From.Format(time.RFC3339)}})
	}
	sort.SliceStable(items, func(i, j int) bool {
		if items[i].SkillID != items[j].SkillID {
			return items[i].SkillID < items[j].SkillID
		}
		return items[i].Reason < items[j].Reason
	})
	return items
}

func exposureCount(rows []Skill, skillID string) int {
	n := 0
	for _, row := range rows {
		if row.SkillID == skillID {
			n += row.Exposures
		}
	}
	return n
}

// matches applies the four query filters. Scope comes from the catalog, so a
// skill the catalog does not know cannot satisfy a scope filter — it is not
// silently included under "no scope".
func (f Filter) matches(skillID, revision, producer string, meta map[string]SkillMeta) bool {
	known, isKnown := meta[skillID]
	if f.Repo != "" && isKnown && known.RepoID != f.Repo {
		return false
	}
	if f.SkillID != "" && skillID != f.SkillID {
		return false
	}
	if f.Revision != "" && revision != f.Revision {
		return false
	}
	if f.Scope != "" && (!isKnown || known.Scope != f.Scope) {
		return false
	}
	if f.Harness != "" && producer != f.Harness {
		return false
	}
	return true
}

// soleProducer names the adapter behind a row when exactly one produced it.
// Two adapters give nil: "which harness" then has no single answer, and picking
// one would attribute a number to a client that did not report it.
func soleProducer(producers map[string]bool) *string {
	if len(producers) != 1 {
		return nil
	}
	for name := range producers {
		v := name
		return &v
	}
	return nil
}

func optional(s string) *string {
	if s == "" {
		return nil
	}
	v := s
	return &v
}

// fallbackID keeps an event countable when the adapter omitted the identifier
// that would have deduplicated it. The event_id is unique per tenant, so the
// event counts once and repetition of the same event still counts once.
func fallbackID(id, eventID string) string {
	if strings.TrimSpace(id) != "" {
		return id
	}
	return "event:" + eventID
}
