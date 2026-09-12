package knowledge

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// skillReference is the `SkillReference` DTO: one file of the skill package.
type skillReference struct {
	Path      string `json:"path"`
	SHA256    string `json:"sha256"`
	Size      int64  `json:"size"`
	Type      string `json:"type"`
	Required  bool   `json:"required"`
	Available bool   `json:"available"`
}

// relationEdge is the `RelationEdge` DTO.
type relationEdge struct {
	From       string `json:"from"`
	To         string `json:"to"`
	Type       string `json:"type"`
	Provenance string `json:"provenance"`
	Revision   string `json:"revision"`
}

// feedbackEntry is the `FeedbackEntry` DTO, read back out of the ledger.
type feedbackEntry struct {
	JudgmentID string  `json:"judgment_id"`
	Verdict    string  `json:"verdict"`
	Reason     *string `json:"reason"`
	Source     *string `json:"source"`
	TaskID     *string `json:"task_id"`
	OccurredAt *string `json:"occurred_at"`
	Actor      *string `json:"actor"`
}

// handleRevision answers one immutable revision in full: the exact body, the
// parsed frontmatter, where it came from, its package files, its declared
// relations and the judgments people recorded against it.
func (s *Service) handleRevision(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	skillID, revisionID := c.Param("skill_id"), c.Param("revision_id")
	rev, err := s.loadRevision(c.Ctx(), org.ID, repo.ID, skillID, revisionID)
	if err != nil {
		return err
	}
	// A revision whose raw upload has expired keeps its metadata: the hashes
	// and the provenance are still true. The body is then null — a named
	// absence — rather than an empty document or another revision's text.
	var body *string
	if s.blobs != nil {
		if raw, e := s.blobs.Get(c.Ctx(), org.ID, rev.BlobSHA256); e == nil {
			text := string(raw)
			body = &text
		}
	}
	references, err2 := s.references(c.Ctx(), org.ID, revisionID)
	if err2 != nil {
		return mgmt.Internal(err2)
	}
	edges, err2 := s.relations(c.Ctx(), org.ID, skillID, revisionID, "", 0)
	if err2 != nil {
		return mgmt.Internal(err2)
	}
	requires, refines := []string{}, []string{}
	for _, edge := range edges {
		if edge.From != skillID || edge.Revision != revisionID {
			continue
		}
		switch edge.Type {
		case "requires":
			requires = append(requires, edge.To)
		case "refines":
			refines = append(refines, edge.To)
		}
	}
	feedback, err2 := s.feedback(c.Ctx(), org.ID, skillID, revisionID, rev.CardRevision)
	if err2 != nil {
		return mgmt.Internal(err2)
	}
	var frontmatter any
	if rev.Frontmatter != "" {
		_ = json.Unmarshal([]byte(rev.Frontmatter), &frontmatter)
	}
	source := map[string]any{"path": rev.SourcePath, "commit": nullable(rev.Commit),
		"url": nullable(repo.SourceURL(rev.Commit, rev.SourcePath))}
	provenance := map[string]any{"origin": rev.Origin,
		"import_id": nullable(rev.ImportID), "proposal_id": nullable(rev.ProposalID)}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": org.ID, "repo_id": repo.ID,
		"skill_id": rev.SkillID, "revision_id": rev.RevisionID,
		"content_sha256": rev.ContentSHA256, "card_revision": nullable(rev.CardRevision),
		"body": body, "frontmatter": frontmatter,
		"source": source, "references": references, "requires": requires, "refines": refines,
		"relations": edges, "feedback": feedback, "provenance": provenance,
		"publication_status": rev.Publication, "created_at": rev.CreatedAt})
}

// handleRaw answers the exact bytes that were imported, with their digest in a
// header so a caller can verify them without trusting the transport.
func (s *Service) handleRaw(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	rev, err := s.loadRevision(c.Ctx(), org.ID, repo.ID, c.Param("skill_id"), c.Param("revision_id"))
	if err != nil {
		return err
	}
	if s.blobs == nil {
		return mgmt.Conflict("revision_unavailable", "The bytes of this revision are no longer stored.")
	}
	raw, e2 := s.blobs.Get(c.Ctx(), org.ID, rev.BlobSHA256)
	if e2 != nil {
		return mgmt.Conflict("revision_unavailable", "The bytes of this revision are no longer stored.")
	}
	// application/octet-stream, not text/markdown: these are the bytes as
	// imported, including any that are not valid UTF-8, and nothing downstream
	// may re-encode them.
	c.W.Header().Set("Content-Type", "application/octet-stream")
	c.W.Header().Set("X-Content-SHA256", rev.ContentSHA256)
	c.W.WriteHeader(http.StatusOK)
	_, _ = c.W.Write(raw)
	return nil
}

func (s *Service) references(ctx context.Context, orgID, revisionID string) ([]skillReference, error) {
	rows, e := s.pool.Query(ctx, `SELECT path,sha256,size_bytes,type,required,available
 FROM gfm.skill_resources WHERE org_id=$1::uuid AND revision_id=$2 ORDER BY path`, orgID, revisionID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []skillReference{}
	for rows.Next() {
		var v skillReference
		if e = rows.Scan(&v.Path, &v.SHA256, &v.Size, &v.Type, &v.Required, &v.Available); e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

// relations reads the neighbourhood of one skill in both directions. A limit of
// zero means "everything this revision declares".
func (s *Service) relations(ctx context.Context, orgID, skillID, revisionID, kind string, limit int) ([]relationEdge, error) {
	if limit <= 0 {
		limit = 500
	}
	rows, e := s.pool.Query(ctx, `SELECT from_skill_id,to_skill_id,type,provenance,COALESCE(revision_id,'')
 FROM gfm.relations
 WHERE org_id=$1::uuid AND (from_skill_id=$2 OR to_skill_id=$2)
   AND ($3='' OR revision_id=$3 OR to_skill_id=$2)
   AND ($4='' OR type=$4)
 ORDER BY from_skill_id,type,to_skill_id LIMIT $5`,
		orgID, skillID, revisionID, kind, limit)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []relationEdge{}
	for rows.Next() {
		var v relationEdge
		if e = rows.Scan(&v.From, &v.To, &v.Type, &v.Provenance, &v.Revision); e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

// maxFeedbackScan bounds how far back the ledger is read for one revision's
// judgments. The ledger has no per-skill index; the substring pre-filter keeps
// the scan small and the exact match happens on the decoded event.
const maxFeedbackScan = 500

// feedback reads a revision's judgments out of the event ledger. There is no
// feedback table on purpose: a rating from the UI and a rating from an adapter
// have to be the same observation, counted once (API-CONTRACT §7).
//
// One revision answers to two identifiers: the UI names the catalog revision and
// the delivery path names the card revision. Matching only one of them would
// show a reader an empty list while the other half of their own organisation's
// judgments sat in the ledger, so both are accepted (API-CONTRACT §5.3).
func (s *Service) feedback(ctx context.Context, orgID, skillID, revisionID, cardRevision string) ([]feedbackEntry, error) {
	rows, e := s.pool.Query(ctx, `SELECT convert_from(payload,'UTF8'),occurred_at FROM gf.events
 WHERE tenant_id=$1 AND event_type='skill_feedback'
   AND position($2 in convert_from(payload,'UTF8'))>0
 ORDER BY occurred_at DESC LIMIT $3`, orgID, skillID, maxFeedbackScan)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []feedbackEntry{}
	for rows.Next() {
		var payload, occurred string
		if e = rows.Scan(&payload, &occurred); e != nil {
			return nil, e
		}
		var event struct {
			JudgmentID     string `json:"judgment_id"`
			SkillID        string `json:"skill_id"`
			Revision       string `json:"revision"`
			Verdict        string `json:"verdict"`
			ReasonCategory string `json:"reason_category"`
			Source         string `json:"source"`
			TaskID         string `json:"task_id"`
			Actor          string `json:"actor"`
		}
		if json.Unmarshal([]byte(payload), &event) != nil {
			continue
		}
		if event.SkillID != skillID {
			continue
		}
		if event.Revision != revisionID && (cardRevision == "" || event.Revision != cardRevision) {
			continue
		}
		at := occurred
		out = append(out, feedbackEntry{JudgmentID: event.JudgmentID, Verdict: event.Verdict,
			Reason: optional(event.ReasonCategory), Source: optional(event.Source),
			TaskID: optional(event.TaskID), OccurredAt: optional(at), Actor: optional(event.Actor)})
	}
	return out, rows.Err()
}

func optional(s string) *string {
	if s == "" {
		return nil
	}
	v := s
	return &v
}

type feedbackRequest struct {
	IdempotencyKey string `json:"idempotency_key"`
	Verdict        string `json:"verdict"`
	Reason         string `json:"reason"`
	TaskID         string `json:"task_id"`
}

// verdicts is the closed domain the telemetry schema already defines. "unknown"
// is one of them: a person who has no opinion is not a neutral rating, and it
// is not zero.
var verdicts = map[string]bool{"helped": true, "hindered": true, "mixed": true,
	"not_applicable": true, "unknown": true}

// handleFeedback records one judgment against one revision.
//
// It writes an event, not a row in a feedback table: the same definition then
// serves the UI and the harness adapters, so a rating is counted once whichever
// surface produced it. The event goes through the ledger's own validator, so a
// verdict this deployment does not know is refused here rather than becoming an
// uncountable row.
func (s *Service) handleFeedback(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	var req feedbackRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	if !verdicts[req.Verdict] {
		return mgmt.Invalid("invalid_request",
			"verdict must be one of helped, hindered, mixed, not_applicable, unknown.")
	}
	if len(req.Reason) > 500 || len(req.TaskID) > 200 {
		return mgmt.Invalid("invalid_request", "reason and task_id are too long.")
	}
	skillID, revisionID := c.Param("skill_id"), c.Param("revision_id")
	rev, err := s.loadRevision(c.Ctx(), org.ID, repo.ID, skillID, revisionID)
	if err != nil {
		return err
	}
	if s.events == nil {
		return mgmt.Fail(http.StatusServiceUnavailable, "backend_unavailable",
			"The telemetry ledger is not configured on this deployment.")
	}
	judgmentID := newID()
	reason := strings.TrimSpace(req.Reason)
	if reason == "" {
		reason = "unspecified"
	}
	event := map[string]any{
		"schema_version":  "1.0",
		"event_id":        newID(),
		"event_type":      "skill_feedback",
		"occurred_at":     time.Now().UTC().Format(time.RFC3339),
		"sequence":        1,
		"producer":        "guidefold-management-api",
		"adapter_version": mgmt.SchemaVersion,
		"environment":     s.environment,
		"judgment_id":     judgmentID,
		"skill_id":        skillID,
		"revision":        rev.RevisionID,
		"content_sha256":  rev.ContentSHA256,
		"verdict":         req.Verdict,
		"reason_category": reason,
		"source":          "ui",
		"actor":           c.Principal.ID(),
	}
	// The delivery path names this revision by its card identifier, so the event
	// carries both. `revision` stays the catalog revision the caller addressed:
	// it is the key the reference report (tools/telemetry/report.py) can compute
	// without a catalog, and the usage aggregate resolves the pair itself
	// (API-CONTRACT §5.5).
	if rev.CardRevision != "" {
		event["card_revision"] = rev.CardRevision
	}
	if req.TaskID != "" {
		event["task_id"] = req.TaskID
	}
	result, e2 := s.events(c.Ctx(), org.ID, []any{event})
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	if rejected, ok := result["rejected"].([]any); ok && len(rejected) > 0 {
		return mgmt.Invalid("invalid_request", "The ledger refused this judgment.")
	}
	// The judgment is an observation, not a decision: nothing about the skill
	// changes here. The owner queue reacts to feedback in its own module.
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "judgment_id": judgmentID})
}

func newID() string { return mgmt.NewID() }
