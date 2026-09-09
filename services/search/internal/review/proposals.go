package review

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// handleListProposals answers one keyset page of proposals, newest first
// (API-CONTRACT §3, "importy, propozycje i audyt `created_at desc, id desc`").
// Members read; only owners decide.
func (s *Service) handleListProposals(c *mgmt.Context) error {
	rc, e := s.authorize(c, mgmt.RoleAny)
	if e != nil {
		return e
	}
	limit := 50
	if v := c.Query("limit"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n < 1 || n > 100 {
			return mgmt.Invalid("invalid_request", "limit must be between 1 and 100.")
		}
		limit = n
	}
	state, kind, scope := c.Query("state"), c.Query("kind"), c.Query("scope")
	if state != "" && !knownState(state) {
		return mgmt.Invalid("invalid_filter_value", "state names no proposal state.")
	}
	if kind != "" && !knownKind(kind) {
		return mgmt.Invalid("invalid_filter_value", "kind names no generation kind.")
	}
	after, before := time.Time{}, ""
	if v := c.Query("cursor"); v != "" {
		parts, err := mgmt.DecodeCursor(v, 2)
		if err != nil {
			return err
		}
		ts, perr := time.Parse(time.RFC3339Nano, parts[0])
		if perr != nil {
			return mgmt.Invalid("invalid_cursor", "cursor must be the next_cursor of a previous page.")
		}
		after, before = ts, parts[1]
	}
	rows, err := s.pool.Query(c.Ctx(), `SELECT proposal_id::text,kind,state,scope,owner,
 target_skill_id,candidate_path,created_at FROM gfm.proposals
 WHERE org_id=$1::uuid AND repo_id=$2
   AND ($3='' OR state=$3) AND ($4='' OR kind=$4) AND ($5='' OR scope=$5)
   AND ($6::timestamptz IS NULL OR (created_at,proposal_id::text) < ($6::timestamptz,$7))
 ORDER BY created_at DESC,proposal_id DESC LIMIT $8`,
		rc.Org.ID, rc.RepoID, state, kind, scope, nullableTime(after), before, limit+1)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []map[string]any{}
	for rows.Next() {
		var id, kind, state, path string
		var scope, owner, target *string
		var createdAt time.Time
		if err = rows.Scan(&id, &kind, &state, &scope, &owner, &target, &path, &createdAt); err != nil {
			return mgmt.Internal(err)
		}
		items = append(items, map[string]any{"proposal_id": id, "kind": kind, "state": state,
			"scope": scope, "owner": owner, "target_skill_id": target, "path": path,
			"created_at": createdAt})
	}
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	next := ""
	if len(items) > limit {
		items = items[:limit]
		last := items[len(items)-1]
		next = mgmt.EncodeCursor(last["created_at"].(time.Time).UTC().Format(time.RFC3339Nano),
			last["proposal_id"].(string))
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"items": items, "next_cursor": nullable(next)})
}

func nullableTime(t time.Time) any {
	if t.IsZero() {
		return nil
	}
	return t
}

func knownState(v string) bool {
	switch v {
	case StateDraft, StateApprovedForExport, StateAwaitingGit, StatePublished, StateRejected,
		StateSuperseded:
		return true
	}
	return false
}

func knownKind(v string) bool {
	switch v {
	case generator.KindExtraction, generator.KindEnrichment, generator.KindConsolidation:
		return true
	}
	return false
}

// handleProposal answers the whole ProposalDetail: the candidate's bytes, the
// body it would replace, where every field came from, and the revision the
// decision must still agree with.
//
// `source_body` is what makes a review possible at all — an owner comparing a
// candidate against nothing is approving prose, not a change.
func (s *Service) handleProposal(c *mgmt.Context) error {
	rc, e := s.authorize(c, mgmt.RoleAny)
	if e != nil {
		return e
	}
	id := c.Param("proposal_id")
	if !parseUUID(id) {
		return notFound("proposal_not_found", "No such proposal in this repository.")
	}
	p, err := s.loadProposal(c.Ctx(), rc.Org.ID, rc.RepoID, id)
	if isNoRows(err) {
		return notFound("proposal_not_found", "No such proposal in this repository.")
	}
	if err != nil {
		return mgmt.Internal(err)
	}
	candidate, err := s.blobs.Get(c.Ctx(), rc.Org.ID, p.CandidateBlobSHA256)
	var body *string
	if err == nil {
		text := string(candidate)
		body = &text
	}
	fields, err := s.proposalFields(c.Ctx(), rc.Org.ID, id)
	if err != nil {
		return mgmt.Internal(err)
	}
	relations, err := s.proposalRelations(c.Ctx(), rc.Org.ID, id)
	if err != nil {
		return mgmt.Internal(err)
	}
	decision, err := s.lastDecision(c.Ctx(), rc.Org.ID, id)
	if err != nil {
		return mgmt.Internal(err)
	}
	sourceBody, current, err := s.targetBody(c, rc, p)
	if err != nil {
		return mgmt.Internal(err)
	}
	provenance := make([]map[string]any, 0, len(fields))
	for _, f := range fields {
		provenance = append(provenance, map[string]any{"field": f.Field, "origin": f.Origin,
			"source_ref": f.sourceRef(), "needs_confirmation": f.NeedsConfirmation,
			"value_sha256": f.ValueSHA256})
	}
	var frontmatter any
	_ = json.Unmarshal(p.CandidateFrontmater, &frontmatter)
	var sources any
	_ = json.Unmarshal(p.Sources, &sources)
	if sources == nil {
		sources = []any{}
	}
	var cost any
	if len(p.Cost) > 0 {
		_ = json.Unmarshal(p.Cost, &cost)
	}
	// The expected revision is the current one, re-read now: a detail page that
	// echoed a stale value would invite a decision the server then rejects.
	expected := p.ExpectedRevision
	if current != "" {
		expected = current
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"proposal_id": p.ProposalID, "kind": p.Kind, "state": p.State,
		"scope": nullable(p.Scope), "owner": nullable(p.Owner),
		"target_skill_id": nullable(p.TargetSkillID), "path": p.CandidatePath,
		"target_revision_id": nullable(p.TargetRevisionID),
		"sources":            sources,
		"recipe": map[string]any{"version": p.RecipeVersion, "generator": p.Generator,
			"model": nullable(p.Model)},
		"candidate": map[string]any{"path": p.CandidatePath, "body": body,
			"sha256": p.CandidateSHA256, "frontmatter": frontmatter},
		"source_body": sourceBody, "provenance": provenance, "relations": relations,
		"decision": decision, "expected_revision": nullable(expected),
		"cost": cost, "created_at": p.CreatedAt, "updated_at": p.UpdatedAt})
}

// targetBody reads the bytes an enrichment or edit proposal would replace, and
// the revision id those bytes belong to.
func (s *Service) targetBody(c *mgmt.Context, rc *repoContext, p *proposal) (*string, string, error) {
	if p.TargetSkillID == "" {
		return nil, "", nil
	}
	var revisionID, blobSHA string
	e := s.pool.QueryRow(c.Ctx(), `SELECT COALESCE(s.current_revision_id,''),COALESCE(r.blob_sha256,'')
 FROM gfm.skills s LEFT JOIN gfm.skill_revisions r
   ON r.org_id=s.org_id AND r.revision_id=s.current_revision_id
 WHERE s.org_id=$1::uuid AND s.repo_id=$2 AND s.skill_id=$3`,
		rc.Org.ID, rc.RepoID, p.TargetSkillID).Scan(&revisionID, &blobSHA)
	if isNoRows(e) {
		return nil, "", nil
	}
	if e != nil {
		return nil, "", e
	}
	if blobSHA == "" {
		return nil, revisionID, nil
	}
	raw, e := s.blobs.Get(c.Ctx(), rc.Org.ID, blobSHA)
	if e != nil {
		// The raw upload expired. The revision id is still true; the body is a
		// named absence rather than an empty string.
		return nil, revisionID, nil
	}
	text := string(raw)
	return &text, revisionID, nil
}

// decisionRequest is the body of POST …/proposals/{id}/decision.
type decisionRequest struct {
	IdempotencyKey   string `json:"idempotency_key"`
	Decision         string `json:"decision"`
	Reason           string `json:"reason"`
	CandidateBody    string `json:"candidate_body"`
	ExpectedRevision string `json:"expected_revision"`
}

// handleDecision records an owner's approve, edit or reject.
//
// Four things happen in one transaction, or none of them do: the proposal
// moves, a decision row records who decided what and why, an approval writes a
// revision with `origin: human`, and the audit log gets its entry. A decision
// that half-applied would leave a revision nobody chose.
func (s *Service) handleDecision(c *mgmt.Context) error {
	rc, e := s.authorizeReviewer(c)
	if e != nil {
		return e
	}
	id := c.Param("proposal_id")
	if !parseUUID(id) {
		return notFound("proposal_not_found", "No such proposal in this repository.")
	}
	var req decisionRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	switch req.Decision {
	case "approve", "edit", "reject":
	default:
		return mgmt.Invalid("invalid_request", "decision must be approve, edit or reject.")
	}
	if e := reasonRequired(req.Reason); e != nil {
		return e
	}
	if req.Decision == "edit" && strings.TrimSpace(req.CandidateBody) == "" {
		return mgmt.Invalid("invalid_request", "edit requires candidate_body.")
	}
	if req.Decision != "edit" && req.CandidateBody != "" {
		return mgmt.Invalid("invalid_request", "candidate_body is only accepted with decision: edit.")
	}

	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	p, err := lockProposal(c.Ctx(), tx, rc.Org.ID, rc.RepoID, id)
	if isNoRows(err) {
		return notFound("proposal_not_found", "No such proposal in this repository.")
	}
	if err != nil {
		return mgmt.Internal(err)
	}
	if p.State != StateDraft {
		return mgmt.Conflict("proposal_state_invalid",
			"Only a draft proposal can be decided; this one is "+p.State+".")
	}

	// The revision check comes before any work: a candidate built against a
	// revision that has since moved is a review of text that no longer exists,
	// and hydrating it anyway is exactly the failure the contract names.
	current, err := currentRevision(c.Ctx(), tx, rc.Org.ID, rc.RepoID, p.TargetSkillID)
	if err != nil {
		return mgmt.Internal(err)
	}
	if current != "" && req.ExpectedRevision != current {
		return mgmt.Conflict("stale_revision",
			"The skill moved since this proposal was generated; re-read it before deciding.").
			WithDetails(map[string]any{"current_revision": current})
	}

	body := ""
	if req.Decision != "reject" {
		raw, e := s.blobs.Get(c.Ctx(), rc.Org.ID, p.CandidateBlobSHA256)
		if e != nil {
			return mgmt.Conflict("proposal_state_invalid",
				"The candidate's bytes are no longer stored; regenerate the proposal.")
		}
		body = string(raw)
	}
	if req.Decision == "edit" {
		// An edit may change prose. It may not change identity: frontmatter,
		// scope, owner and relations are what the graph and the scope policy are
		// validated against, and changing them here would bypass both.
		if e := sameIdentity(body, req.CandidateBody); e != nil {
			return e
		}
		body = req.CandidateBody
	}

	if req.Decision == "reject" {
		if e := s.recordDecision(c, tx, rc, p, req, ""); e != nil {
			return e
		}
		if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.proposals SET state='rejected',updated_at=now()
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid`, rc.Org.ID, id); e != nil {
			return mgmt.Internal(e)
		}
		if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "proposal.reject", "proposal:"+id, p.CacheKey); e != nil {
			return mgmt.Internal(e)
		}
		if e := tx.Commit(c.Ctx()); e != nil {
			return mgmt.Internal(e)
		}
		return c.JSON(http.StatusOK, map[string]any{
			"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
			"proposal_id": id, "state": StateRejected, "revision_id": nil,
			"expected_revision": nullable(current)})
	}

	// Approval is the point at which a candidate becomes part of the graph, so
	// the graph rules are checked here rather than only at publication: an owner
	// finds out that a candidate closes a cycle now, not two steps later.
	skillID, e2 := s.resolveSkillID(c, tx, rc, p)
	if e2 != nil {
		return e2
	}
	if e := s.validateApproval(c.Ctx(), tx, rc, p, skillID); e != nil {
		return e
	}

	revisionID, e2 := s.writeHumanRevision(c, tx, rc, p, skillID, body)
	if e2 != nil {
		return e2
	}
	if e := s.recordDecision(c, tx, rc, p, req, revisionID); e != nil {
		return e
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.proposals SET state='approved_for_export',
 target_skill_id=$3,target_revision_id=$4,candidate_sha256=$5,candidate_blob_sha256=$6,
 expected_revision=$7,updated_at=now()
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid`,
		rc.Org.ID, id, skillID, revisionID, digest(body), digest(body),
		nullable(current)); e != nil {
		return mgmt.Internal(e)
	}
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "proposal."+req.Decision, "proposal:"+id,
		revisionID); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"proposal_id": id, "state": StateApprovedForExport, "revision_id": revisionID,
		"expected_revision": revisionID})
}

func (s *Service) recordDecision(c *mgmt.Context, tx pgxTx, rc *repoContext, p *proposal,
	req decisionRequest, revisionID string) error {
	_, e := tx.Exec(c.Ctx(), `INSERT INTO gfm.decisions
 (org_id,decision_id,proposal_id,decision,reason,actor_user_id,expected_revision,
  result_revision_id,request_id)
 VALUES($1::uuid,$2::uuid,$3::uuid,$4,$5,$6::uuid,$7,$8,$9)`,
		rc.Org.ID, newID(), p.ProposalID, req.Decision, strings.TrimSpace(req.Reason),
		c.Principal.UserID, nullable(req.ExpectedRevision), nullable(revisionID), c.RequestID)
	if e != nil {
		return mgmt.Internal(e)
	}
	return nil
}
