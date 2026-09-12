// Package usage is the reporting side of the ledger: what an organisation's
// adapters actually did with the skills it publishes, the owner's review queue,
// and the health of the adapters that reported it.
//
// It only reads. Nothing here changes a skill, a revision, a publication or a
// membership — the one row it writes is an owner's decision about a queue item,
// which records that a person looked, not that anything about the skill was
// altered (module-boundaries-go). The aggregation itself lives in domain/ and
// touches no database, so the definitions can be read and compared with
// tools/telemetry/report.py without a server.
//
// The ledger is organisation-scoped (`gf.events.tenant_id = org_id`) while
// these endpoints are repository-scoped. A row is therefore attributed to this
// repository when the catalog says its skill belongs here, and a skill the
// catalog has never seen is still counted — the ledger observed it — with no
// scope and no owner rather than being silently dropped.
package usage

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/usage/domain"
)

// Service holds the usage endpoints.
type Service struct {
	pool *pgxpool.Pool
}

// New builds the service.
func New(pool *pgxpool.Pool) *Service { return &Service{pool: pool} }

// Register mounts the usage surface (API-CONTRACT §4.6). Reading is a member
// action; deciding a queue item is an owner action and, being a mutation, an
// idempotent one.
func (s *Service) Register(r *mgmt.Router) {
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/usage", s.handleUsage)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/repos/{repo}/usage/export", s.handleExport)
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/repos/{repo}/usage/queue/{item_id}/decision",
		s.handleDecision, mgmt.Idempotent())
}

// measuredTypes are the ledger rows the report reads. `search_requested`,
// `search_results` and `skill_load_requested` are deliberately absent: an
// intention to load is not a load, and a served result is not an exposure.
var measuredTypes = []string{"card_injected", "skill_load_completed", "skill_use_reported",
	"skill_use_observed", "skill_feedback", "task_started", "task_finished", "telemetry_health"}

// unattributedTypes carry no skill_id, so a per-skill filter must not remove
// them: they answer "how much did we lose" and "are task identifiers present",
// which are properties of the window and not of one skill.
const unattributedTypes = "('telemetry_health','task_started','task_finished')"

// receivedLayout is the format ingestEvents writes into gf.events.received_at.
// It is server-generated and therefore the one timestamp column that can be
// compared as text.
const receivedLayout = "2006-01-02T15:04:05Z"

// occurredLayouts are the forms an adapter may send. The column stores the
// client's exact string, so the comparison happens here rather than in SQL.
var occurredLayouts = []string{time.RFC3339Nano,
	"2006-01-02 15:04:05.999999999Z07:00",
	"2006-01-02T15:04:05.999999999Z0700",
	"20060102T150405.999999999Z07:00"}

func parseEventTime(value string) (time.Time, bool) {
	for _, layout := range occurredLayouts {
		if t, e := time.Parse(layout, value); e == nil {
			return t.UTC(), true
		}
	}
	return time.Time{}, false
}

// view is one assembled answer: the aggregate, the queue and the adapters.
type view struct {
	report     domain.Report
	previous   domain.Totals
	prevWindow domain.Window
	queue      []queueItem
	health     []adapterHealth
	filters    domain.Filter
}

// build reads everything one usage answer needs.
func (s *Service) build(ctx context.Context, c *mgmt.Context, orgID, repoID string) (*view, error) {
	filter := domain.Filter{Repo: repoID,
		Scope:    strings.TrimSpace(c.Query("scope")),
		SkillID:  strings.TrimSpace(c.Query("skill_id")),
		Revision: strings.TrimSpace(c.Query("revision")),
		Harness:  strings.TrimSpace(c.Query("harness"))}
	for _, v := range []string{filter.Scope, filter.SkillID, filter.Revision, filter.Harness} {
		if len(v) > 300 {
			return nil, mgmt.Invalid("invalid_request", "A filter value is too long.")
		}
	}
	watermark, e := s.watermark(ctx, orgID, c.Now())
	if e != nil {
		return nil, e
	}
	spec := strings.TrimSpace(c.Query("window"))
	window, ok := domain.WindowFor(spec, watermark)
	if !ok {
		return nil, mgmt.Invalid("invalid_request", "window must be one of 7d, 30d, 90d.")
	}
	// The echo names the window that was applied, the default included: a report
	// always covers a period, and a reader must not have to guess which.
	if spec == "" {
		spec = domain.DefaultWindow
	}
	filter.Window = spec
	received, e := s.receivedCount(ctx, orgID, window.From)
	if e != nil {
		return nil, e
	}
	meta, e := s.skillMeta(ctx, orgID)
	if e != nil {
		return nil, e
	}
	events, e := s.events(ctx, orgID, filter.SkillID)
	if e != nil {
		return nil, e
	}
	revisions, e := s.revisions(ctx, orgID)
	if e != nil {
		return nil, e
	}
	health, lag, e := s.adapters(ctx, orgID)
	if e != nil {
		return nil, e
	}
	report := domain.Aggregate(domain.Input{Events: events, EventsReceived: received,
		OldestLagS: lag, Meta: meta, Window: window, Filter: filter, Revisions: revisions,
		Now: c.Now().UTC()})
	queue, e := s.queue(ctx, orgID, repoID, report, meta)
	if e != nil {
		return nil, e
	}
	prevWindow, prevTotals := previousTotals(events, meta, revisions, filter, window, c.Now().UTC())
	return &view{report: report, previous: prevTotals, prevWindow: prevWindow,
		queue: queue, health: health, filters: filter}, nil
}

// previousTotals answers contract 1.3.0's `previous`: the window of the same
// length that ends where the requested window begins, counted the same way
// and under the same filters (API-CONTRACT §5.5).
//
// domain.Aggregate only enforces the window's lower bound — it trusts that
// `Window.To` is the watermark, so nothing in `Events` can be newer than
// "now". That trust does not hold for a window anchored in the past, so this
// function enforces the upper bound itself before handing the events to
// Aggregate; otherwise a "previous" window would silently absorb every event
// between its end and the watermark, double-counting the current window.
func previousTotals(events []domain.Event, meta map[string]domain.SkillMeta,
	revisions domain.Revisions, filter domain.Filter, window domain.Window,
	now time.Time) (domain.Window, domain.Totals) {
	prevWindow := domain.Window{From: window.From.Add(-window.To.Sub(window.From)),
		To: window.From, Watermark: window.From}
	prevEvents := make([]domain.Event, 0, len(events))
	for _, e := range events {
		if e.OccurredAt.Before(prevWindow.To) {
			prevEvents = append(prevEvents, e)
		}
	}
	prevReport := domain.Aggregate(domain.Input{Events: prevEvents, Meta: meta,
		Window: prevWindow, Filter: filter, Revisions: revisions, Now: now})
	return prevWindow, prevReport.Totals
}

// watermark is the newest received_at in the ledger. With no events at all the
// window is anchored on the server clock, so an empty report still says which
// period it describes instead of claiming the epoch.
func (s *Service) watermark(ctx context.Context, orgID string, now time.Time) (time.Time, error) {
	var newest *string
	if e := s.pool.QueryRow(ctx,
		`SELECT max(received_at) FROM gf.events WHERE tenant_id=$1`, orgID).Scan(&newest); e != nil {
		return time.Time{}, mgmt.Internal(e)
	}
	if newest == nil {
		return now.UTC(), nil
	}
	if t, ok := parseEventTime(*newest); ok {
		return t, nil
	}
	return now.UTC(), nil
}

func (s *Service) receivedCount(ctx context.Context, orgID string, from time.Time) (int, error) {
	var n int
	if e := s.pool.QueryRow(ctx, `SELECT count(*) FROM gf.events
 WHERE tenant_id=$1 AND received_at >= $2`, orgID, from.UTC().Format(receivedLayout)).Scan(&n); e != nil {
		return 0, mgmt.Internal(e)
	}
	return n, nil
}

// events reads the measured rows. The skill filter is pushed into SQL through
// the gf.event_field expression index; the rows that carry no skill are kept
// whatever the filter says, because coverage is not a per-skill number.
func (s *Service) events(ctx context.Context, orgID, skillID string) ([]domain.Event, error) {
	rows, e := s.pool.Query(ctx, `SELECT event_type,occurred_at,received_at,event_id,payload
 FROM gf.events
 WHERE tenant_id=$1 AND event_type = ANY($2)
   AND ($3='' OR gf.event_field(payload,'skill_id')=$3 OR event_type IN `+unattributedTypes+`)`,
		orgID, measuredTypes, skillID)
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	defer rows.Close()
	out := []domain.Event{}
	for rows.Next() {
		var kind, occurred, received string
		var id, payload []byte
		if e := rows.Scan(&kind, &occurred, &received, &id, &payload); e != nil {
			return nil, mgmt.Internal(e)
		}
		event := domain.Event{Type: kind, EventID: string(id)}
		if t, ok := parseEventTime(occurred); ok {
			event.OccurredAt = t
		} else {
			// A timestamp the validator accepted but this reader cannot parse
			// must not silently land in every window. Fall back to when the
			// server received it, which is a fact the server owns.
			if t, ok := parseEventTime(received); ok {
				event.OccurredAt = t
			}
		}
		if e := json.Unmarshal(payload, &event.Payload); e != nil || event.Payload == nil {
			continue
		}
		out = append(out, event)
	}
	if e := rows.Err(); e != nil {
		return nil, mgmt.Internal(e)
	}
	return out, nil
}

// skillMeta is the catalog's view of every skill of the organisation: which
// repository it belongs to, its scope and owner, and when its published
// revision came into being. The usage module reads this and writes none of it.
func (s *Service) skillMeta(ctx context.Context, orgID string) (map[string]domain.SkillMeta, error) {
	rows, e := s.pool.Query(ctx, `SELECT s.skill_id,s.repo_id,s.scope,s.owner,
 s.current_revision_id,s.published_revision_id,s.publication_status,r.created_at
 FROM gfm.skills s
 LEFT JOIN gfm.skill_revisions r
   ON r.org_id=s.org_id AND r.revision_id=s.published_revision_id
 WHERE s.org_id=$1::uuid`, orgID)
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	defer rows.Close()
	meta := map[string]domain.SkillMeta{}
	for rows.Next() {
		var id, repo, scope, status string
		var owner, current, published *string
		var publishedAt *time.Time
		if e := rows.Scan(&id, &repo, &scope, &owner, &current, &published, &status,
			&publishedAt); e != nil {
			return nil, mgmt.Internal(e)
		}
		m := domain.SkillMeta{RepoID: repo, Scope: scope, Owner: text(owner),
			Revision: text(current), PublishedRevision: text(published),
			Published: status == "published"}
		if publishedAt != nil {
			m.PublishedAt = publishedAt.UTC()
		}
		meta[id] = m
	}
	if e := rows.Err(); e != nil {
		return nil, mgmt.Internal(e)
	}
	return meta, nil
}

// revisions reads the three names every revision of the organisation answers
// to, so the aggregate can resolve a card revision and a catalog revision to
// one row. It reads gfm.skill_revisions and writes none of it: the usage module
// never modifies the catalog (module-boundaries-go).
func (s *Service) revisions(ctx context.Context, orgID string) (domain.Revisions, error) {
	index := domain.Revisions{Canonical: map[string]string{}, Card: map[string]string{},
		Content: map[string]string{}}
	rows, e := s.pool.Query(ctx, `SELECT revision_id,content_sha256,COALESCE(card_revision,'')
 FROM gfm.skill_revisions WHERE org_id=$1::uuid`, orgID)
	if e != nil {
		return index, mgmt.Internal(e)
	}
	defer rows.Close()
	for rows.Next() {
		var revision, content, card string
		if e := rows.Scan(&revision, &content, &card); e != nil {
			return index, mgmt.Internal(e)
		}
		index.Canonical[revision] = revision
		index.Content[revision] = content
		// The content digest is reported beside the row but is deliberately not
		// an alias: two skills whose SKILL.md is byte-identical share it, so it
		// names no single revision. Only the two identifiers the ledger actually
		// carries resolve.
		if card != "" {
			index.Canonical[card] = revision
			index.Card[revision] = card
		}
	}
	if e := rows.Err(); e != nil {
		return index, mgmt.Internal(e)
	}
	return index, nil
}

// usageResponse is the `Usage` DTO (API-CONTRACT §5.5).
type usageResponse struct {
	SchemaVersion string           `json:"schema_version"`
	Window        windowDTO        `json:"window"`
	Coverage      *domain.Coverage `json:"coverage"`
	Totals        domain.Totals    `json:"totals"`
	Skills        []domain.Skill   `json:"skills"`
	Queue         []queueItem      `json:"queue"`
	Health        *healthDTO       `json:"health"`
	Filters       domain.Filter    `json:"filters"`
	Previous      *previousDTO     `json:"previous"`
}

type windowDTO struct {
	From      string `json:"from"`
	To        string `json:"to"`
	Watermark string `json:"watermark"`
}

// previousDTO is the `previous` object contract 1.3.0 adds to `Usage`
// (API-CONTRACT §5.5): the window of the same length ending where the
// requested window begins, and the totals counted over it, same filters. It
// is nil only when the report carries no totals at all.
type previousDTO struct {
	Window struct {
		From string `json:"from"`
		To   string `json:"to"`
	} `json:"window"`
	Totals domain.Totals `json:"totals"`
}

func previousOf(w domain.Window, totals domain.Totals) *previousDTO {
	p := &previousDTO{Totals: totals}
	p.Window.From = w.From.Format(time.RFC3339)
	p.Window.To = w.To.Format(time.RFC3339)
	return p
}

type healthDTO struct {
	Adapters []adapterHealth `json:"adapters"`
}

func windowOf(w domain.Window) windowDTO {
	return windowDTO{From: w.From.Format(time.RFC3339), To: w.To.Format(time.RFC3339),
		Watermark: w.Watermark.Format(time.RFC3339)}
}

// handleUsage answers the owner's dashboard in one request: the window, what
// the window can and cannot see, the aggregate, the per-skill rows, the review
// queue and the adapters behind it all.
func (s *Service) handleUsage(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	v, e := s.build(c.Ctx(), c, org.ID, repo.ID)
	if e != nil {
		return e
	}
	coverage := v.report.Coverage
	return c.JSON(http.StatusOK, usageResponse{
		SchemaVersion: mgmt.SchemaVersion,
		Window:        windowOf(v.report.Window),
		Coverage:      &coverage,
		Totals:        v.report.Totals,
		Skills:        v.report.Skills,
		Queue:         v.queue,
		Health:        &healthDTO{Adapters: v.health},
		Filters:       v.filters,
		Previous:      previousOf(v.prevWindow, v.previous),
	})
}

// adapterHealth is the `AdapterHealth` DTO. Every field but the harness is
// nullable: an adapter that has never reported its capabilities is unknown, not
// incapable.
type adapterHealth struct {
	Harness        string   `json:"harness"`
	AdapterVersion *string  `json:"adapter_version"`
	Capabilities   []string `json:"capabilities"`
	LastSeenAt     *string  `json:"last_seen_at"`
	LagS           *int     `json:"lag_s"`
	Dropped        *int     `json:"dropped"`
}

// adapters reads the ingest-time projection. The second result is the worst lag
// any adapter of this organisation showed, which is the coverage number: a
// report cannot say how stale it is from rows it never received.
func (s *Service) adapters(ctx context.Context, orgID string) ([]adapterHealth, *int, error) {
	rows, e := s.pool.Query(ctx, `SELECT harness,adapter_version,capabilities,
 last_seen_at,oldest_lag_s,dropped FROM gfm.adapter_health
 WHERE org_id=$1::uuid ORDER BY harness`, orgID)
	if e != nil {
		return nil, nil, mgmt.Internal(e)
	}
	defer rows.Close()
	out := []adapterHealth{}
	var worst *int
	for rows.Next() {
		var h adapterHealth
		var capabilities []byte
		var seen *time.Time
		var dropped int64
		if e := rows.Scan(&h.Harness, &h.AdapterVersion, &capabilities, &seen, &h.LagS,
			&dropped); e != nil {
			return nil, nil, mgmt.Internal(e)
		}
		if seen != nil {
			v := seen.UTC().Format(time.RFC3339)
			h.LastSeenAt = &v
		}
		n := int(dropped)
		h.Dropped = &n
		h.Capabilities = decodeCapabilities(capabilities)
		if h.LagS != nil && (worst == nil || *h.LagS > *worst) {
			v := *h.LagS
			worst = &v
		}
		out = append(out, h)
	}
	if e := rows.Err(); e != nil {
		return nil, nil, mgmt.Internal(e)
	}
	return out, worst, nil
}

// decodeCapabilities accepts both shapes an adapter sends: a list of flag names
// and a map of flag to boolean. An unreadable value is nil — unknown — rather
// than an empty list, which would read as "this adapter can do nothing".
func decodeCapabilities(raw []byte) []string {
	if len(raw) == 0 {
		return nil
	}
	var list []string
	if json.Unmarshal(raw, &list) == nil {
		return list
	}
	var flags map[string]any
	if json.Unmarshal(raw, &flags) != nil {
		return nil
	}
	out := []string{}
	for name, value := range flags {
		if on, ok := value.(bool); ok && !on {
			continue
		}
		out = append(out, name)
	}
	sort.Strings(out)
	return out
}

func text(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}

var errNoRows = pgx.ErrNoRows

func isNoRows(e error) bool { return errors.Is(e, errNoRows) }
