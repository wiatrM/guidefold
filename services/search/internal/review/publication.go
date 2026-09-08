package review

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// publishRequest is the body of POST {repo_base}/publish.
type publishRequest struct {
	IdempotencyKey string `json:"idempotency_key"`
	ImportID       string `json:"import_id"`
}

// handlePublish queues a build of one import.
//
// It queues; it does not publish. The head only moves inside the worker, after
// the graph and the package resources have been validated, so a request that
// returns 200 here has bought a *build*, not a live snapshot (U5).
func (s *Service) handlePublish(c *mgmt.Context) error {
	rc, e := s.authorize(c, mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req publishRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	if !parseUUID(req.ImportID) {
		return notFound("import_not_found", "No such import in this repository.")
	}
	var state, digestOf string
	var commit *string
	err := s.pool.QueryRow(c.Ctx(), `SELECT state,manifest_digest,commit FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2 AND import_id=$3::uuid`,
		rc.Org.ID, rc.RepoID, req.ImportID).Scan(&state, &digestOf, &commit)
	if isNoRows(err) {
		return notFound("import_not_found", "No such import in this repository.")
	}
	if err != nil {
		return mgmt.Internal(err)
	}
	// The state was read and then ignored, so a request could buy a build of an
	// import that can never produce one. `queued` and `parsing` are in flight
	// and the job's retry is the right answer for them; `created`, `uploading`,
	// `failed` and `cancelled` never become publishable, and enqueueing anyway
	// answers 200 with a job_id that then burns max_attempts with exponential
	// backoff before failing where nobody is looking (API-CONTRACT §6).
	switch state {
	case importer.StateReady, importer.StatePartial, importer.StateQueued, importer.StateParsing:
	default:
		return mgmt.Conflict("import_not_ready",
			"This import is "+state+"; only a parsed import can be published.")
	}
	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	payload, _ := json.Marshal(map[string]any{
		"schema_version": PublishPayloadVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"import_id": req.ImportID, "manifest_digest": digestOf, "commit": str(commit)})
	// The same idempotency key `finalize` used, so asking to publish an import
	// that already has a queued build joins that build instead of racing it.
	job, e2 := s.queue.Enqueue(c.Ctx(), tx, jobs.Job{OrgID: rc.Org.ID, RepoID: rc.RepoID,
		ImportID: req.ImportID, Kind: KindPublish, Payload: payload, InputDigest: digestOf,
		IdempotencyKey: KindPublish + ":" + req.ImportID})
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "publication.request", "import:"+req.ImportID,
		digestOf); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"job_id": job.JobID, "import_id": req.ImportID, "state": job.State})
}

// snapshotRow is one row of the snapshot list.
type snapshotRow struct {
	PublicationID string          `json:"publication_id"`
	SnapshotID    *string         `json:"snapshot_id"`
	State         string          `json:"state"`
	Active        bool            `json:"active"`
	ImportID      *string         `json:"import_id"`
	JobID         *string         `json:"job_id"`
	Commit        *string         `json:"commit"`
	NSkills       int             `json:"n_skills"`
	BuilderSHA256 *string         `json:"builder_sha256"`
	Validation    json.RawMessage `json:"validation"`
	Error         *string         `json:"error"`
	ActivatedAt   *time.Time      `json:"activated_at"`
	CreatedAt     time.Time       `json:"created_at"`
}

// handleListSnapshots lists this repository's publications, newest first, and
// says which one is actually serving. `state` is the engine's own vocabulary;
// `active` is the one fact a rollback needs (API-CONTRACT §5.4).
func (s *Service) handleListSnapshots(c *mgmt.Context) error {
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
	items, next, err := s.snapshots(c, rc, after, before, limit)
	if err != nil {
		return err
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"items": items, "next_cursor": nullable(next)})
}

func (s *Service) snapshots(c *mgmt.Context, rc *repoContext, after time.Time, before string,
	limit int) ([]snapshotRow, string, error) {
	rows, e := s.pool.Query(c.Ctx(), `SELECT p.publication_id::text,p.snapshot_id,p.state,
 p.import_id::text,p.job_id::text,p.commit,p.n_skills,p.builder_sha256,p.validation::text,p.error,
 p.activated_at,p.created_at,
 -- A publication that never produced a snapshot is not the active one; without
 -- COALESCE the comparison is NULL, which is neither true nor false.
 COALESCE(p.snapshot_id IS NOT NULL AND h.snapshot_id=p.snapshot_id, false) AS active
 FROM gfm.publications p
 LEFT JOIN gf.heads h ON h.tenant=p.org_id::text AND h.repo=p.repo_id
 WHERE p.org_id=$1::uuid AND p.repo_id=$2
   AND ($3::timestamptz IS NULL OR (p.created_at,p.publication_id::text) < ($3::timestamptz,$4))
 ORDER BY p.created_at DESC,p.publication_id DESC LIMIT $5`,
		rc.Org.ID, rc.RepoID, nullableTime(after), before, limit+1)
	if e != nil {
		return nil, "", mgmt.Internal(e)
	}
	defer rows.Close()
	items := []snapshotRow{}
	for rows.Next() {
		var r snapshotRow
		var validation *string
		if e = rows.Scan(&r.PublicationID, &r.SnapshotID, &r.State, &r.ImportID, &r.JobID,
			&r.Commit, &r.NSkills, &r.BuilderSHA256, &validation, &r.Error, &r.ActivatedAt,
			&r.CreatedAt, &r.Active); e != nil {
			return nil, "", mgmt.Internal(e)
		}
		if validation != nil {
			r.Validation = json.RawMessage(*validation)
		}
		items = append(items, r)
	}
	if e = rows.Err(); e != nil {
		return nil, "", mgmt.Internal(e)
	}
	next := ""
	if len(items) > limit {
		items = items[:limit]
		last := items[len(items)-1]
		next = mgmt.EncodeCursor(last.CreatedAt.UTC().Format(time.RFC3339Nano), last.PublicationID)
	}
	return items, next, nil
}

// activateRequest is the body of POST …/snapshots/{id}/activate. `reason` is
// required: a rollback is an owner decision with a stated reason like every
// other decision in this module (tech-lead decision 13).
type activateRequest struct {
	IdempotencyKey string `json:"idempotency_key"`
	Reason         string `json:"reason"`
}

// handleActivate rolls the serving head forward or back.
//
// The graph is re-validated before the head moves, even for a snapshot that was
// valid when it was built: the rule is "validation runs before a head change",
// including reactivation (ADR-0028).
func (s *Service) handleActivate(c *mgmt.Context) error {
	rc, e := s.authorize(c, mgmt.RoleOwner)
	if e != nil {
		return e
	}
	snapshotID := c.Param("snapshot_id")
	var req activateRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	if e := reasonRequired(req.Reason); e != nil {
		return e
	}
	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	var publicationID, state string
	err := tx.QueryRow(c.Ctx(), `SELECT publication_id::text,state FROM gfm.publications
 WHERE org_id=$1::uuid AND repo_id=$2 AND snapshot_id=$3 FOR UPDATE`,
		rc.Org.ID, rc.RepoID, snapshotID).Scan(&publicationID, &state)
	if isNoRows(err) {
		return notFound("not_found", "No such snapshot in this repository.")
	}
	if err != nil {
		return mgmt.Internal(err)
	}
	if state == PublicationFailed || state == PublicationBuilding {
		return mgmt.Conflict("proposal_state_invalid",
			"A snapshot that did not finish validation cannot be activated.")
	}
	nodes, known, e2 := snapshotNodes(c.Ctx(), tx, rc.Org.ID, rc.RepoID, snapshotID)
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	owners, e2 := s.scopeOwners(c.Ctx(), rc)
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	if e := ValidateGraph(nodes, known, owners).Err(); e != nil {
		return e
	}
	if _, e := tx.Exec(c.Ctx(), `INSERT INTO gf.heads(tenant,repo,snapshot_id)
 VALUES($1,$2,$3) ON CONFLICT(tenant,repo) DO UPDATE SET snapshot_id=excluded.snapshot_id`,
		rc.Org.ID, rc.RepoID, snapshotID); e != nil {
		return mgmt.Internal(e)
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.publications SET state='superseded',updated_at=now()
 WHERE org_id=$1::uuid AND repo_id=$2 AND state='active' AND publication_id<>$3::uuid`,
		rc.Org.ID, rc.RepoID, publicationID); e != nil {
		return mgmt.Internal(e)
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.publications
 SET state='active',activated_at=now(),updated_at=now()
 WHERE org_id=$1::uuid AND publication_id=$2::uuid`, rc.Org.ID, publicationID); e != nil {
		return mgmt.Internal(e)
	}
	// The reason is the audit row: without it a rollback is an unexplained
	// change of what every agent in the organisation reads.
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "snapshot.activate: "+req.Reason,
		"snapshot:"+snapshotID, snapshotID); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	items, _, err2 := s.snapshots(c, rc, time.Time{}, "", 100)
	if err2 != nil {
		return err2
	}
	for _, item := range items {
		if item.SnapshotID != nil && *item.SnapshotID == snapshotID {
			return c.JSON(http.StatusOK, map[string]any{
				"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
				"snapshot": item})
		}
	}
	// Unreachable: the row was just written inside the transaction that
	// committed. Saying so is better than a 200 with no body.
	return mgmt.Internal(errors.New("the activated snapshot disappeared between write and read"))
}

// handlePublicationJob answers the job and the publication it produced, which
// is what a progress view polls (API-CONTRACT §4.4).
func (s *Service) handlePublicationJob(c *mgmt.Context) error {
	rc, e := s.authorize(c, mgmt.RoleAny)
	if e != nil {
		return e
	}
	jobID := c.Param("job_id")
	if !parseUUID(jobID) {
		return notFound("not_found", "No such publication job in this repository.")
	}
	job, err := s.queue.Get(c.Ctx(), rc.Org.ID, jobID)
	if err != nil {
		return notFound("not_found", "No such publication job in this repository.")
	}
	if job.RepoID != rc.RepoID || job.Kind != KindPublish {
		return notFound("not_found", "No such publication job in this repository.")
	}
	var publication any
	var row snapshotRow
	var validation *string
	e2 := s.pool.QueryRow(c.Ctx(), `SELECT publication_id::text,snapshot_id,state,import_id::text,
 job_id::text,commit,n_skills,builder_sha256,validation::text,error,activated_at,created_at
 FROM gfm.publications WHERE org_id=$1::uuid AND job_id=$2::uuid`, rc.Org.ID, jobID).
		Scan(&row.PublicationID, &row.SnapshotID, &row.State, &row.ImportID, &row.JobID,
			&row.Commit, &row.NSkills, &row.BuilderSHA256, &validation, &row.Error,
			&row.ActivatedAt, &row.CreatedAt)
	if e2 == nil {
		if validation != nil {
			row.Validation = json.RawMessage(*validation)
		}
		publication = row
	} else if !isNoRows(e2) {
		return mgmt.Internal(e2)
	}
	var cost any
	if len(job.Cost) > 0 {
		_ = json.Unmarshal(job.Cost, &cost)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"job": map[string]any{"job_id": job.JobID, "kind": job.Kind, "state": job.State,
			"attempts": job.Attempts, "generation": job.Generation,
			"error": optional(job.Error), "cost": cost,
			"started_at": job.StartedAt, "finished_at": job.FinishedAt},
		"publication": publication})
}

// handleProposalPublication answers where one proposal stands on the road from
// approval to serving. `awaiting_git` is a real state and not a spinner: the
// change exists as a patch and nothing has published it yet.
func (s *Service) handleProposalPublication(c *mgmt.Context) error {
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
	state := StateAwaitingGit
	switch p.State {
	case StatePublished:
		state = StatePublished
	case StateSuperseded:
		state = StateSuperseded
	}
	var publishedRevision, snapshotID *string
	if p.TargetSkillID != "" {
		if e := s.pool.QueryRow(c.Ctx(), `SELECT published_revision_id,published_snapshot_id
 FROM gfm.skills WHERE org_id=$1::uuid AND repo_id=$2 AND skill_id=$3`,
			rc.Org.ID, rc.RepoID, p.TargetSkillID).Scan(&publishedRevision, &snapshotID); e != nil &&
			!isNoRows(e) {
			return mgmt.Internal(e)
		}
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"proposal_id": id, "state": state, "published_revision_id": publishedRevision,
		"import_id": nullable(p.ImportID), "snapshot_id": snapshotID})
}
