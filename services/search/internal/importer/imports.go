package importer

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// Import states (API-CONTRACT §6).
const (
	StateCreated   = "created"
	StateUploading = "uploading"
	StateQueued    = "queued"
	StateParsing   = "parsing"
	StateReady     = "ready"
	StatePartial   = "partial"
	StateFailed    = "failed"
	StateCancelled = "cancelled"
)

// maxStatusFiles bounds the file list one status response carries. Beyond it
// the response says so in files_truncated rather than pretending the import
// held fewer files than it did.
const maxStatusFiles = 20000

type createImportRequest struct {
	IdempotencyKey string          `json:"idempotency_key"`
	Manifest       json.RawMessage `json:"manifest"`
}

// CreateImportOptions carries what only the caller can supply: the manifest's
// exact bytes (ManifestDigest and gfm.imports.manifest both need the bytes as
// sent, not a value re-marshalled from the parsed struct) and who to credit.
// Actor and RequestID feed the audit row exactly as mgmt.Context.Audit would;
// a caller with no HTTP request behind it — a worker — supplies its own job
// identity instead, the way internal/review/generate.go's worker-side writes
// already name "worker" as the actor and a job id as the request.
type CreateImportOptions struct {
	RawManifest []byte
	// CreatedBy is gfm.imports.created_by: empty when no human principal made
	// the request.
	CreatedBy string
	// Actor and RequestID are gfm.audit's actor and request_id for the
	// import.create entry this call writes.
	Actor     string
	RequestID string
}

// CreateImportResult is what a caller needs to act on a create, whether that
// caller is an HTTP response or a worker's next step: the id, whether the
// manifest's digest matched an import already recorded (U1.4), the row's
// state, and the blobs still missing before FinalizeImport will accept it.
type CreateImportResult struct {
	ImportID string
	State    string
	Reused   bool
	Missing  []string
}

// CreateImport records one scan, or reuses the import already recorded for the
// same manifest digest (U1.4), and reports the blobs it still needs. It never
// stores blob content itself: the manifest is the plan, PutBlob fills it, and
// only FinalizeImport turns the pair into queued work.
//
// This is the state machine's own entry point, not a thing layered on top of
// it: handleCreateImport is one caller, and a worker that already holds a
// manifest and its bytes in memory (the Live Agent's reason for existing —
// see internal/README.md) is another, without duplicating the reuse rule or
// the row shape. The caller owns tx and commits it; CreateImport leaves it in
// whatever state its own commit makes durable, exactly as it does inside
// handleCreateImport today.
func (s *Service) CreateImport(ctx context.Context, tx pgx.Tx, orgID, repoID string,
	manifest *domain.Manifest, opts CreateImportOptions) (CreateImportResult, error) {
	if err := manifest.Validate(repoID); err != nil {
		return CreateImportResult{}, err
	}
	digest, err := domain.ManifestDigest(opts.RawManifest)
	if err != nil {
		return CreateImportResult{}, err
	}

	// A manifest digest identifies a tree. Sending the same tree twice reuses
	// the import that already exists for it, so an interrupted sync resumes
	// instead of starting a second upload of the same bytes (U1.4).
	var importID, state string
	reused := false
	scan := tx.QueryRow(ctx, `SELECT import_id::text,state FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2 AND manifest_digest=$3 AND state<>'failed'`,
		orgID, repoID, digest)
	switch e := scan.Scan(&importID, &state); {
	case e == nil:
		reused = true
	case errors.Is(e, pgx.ErrNoRows):
		importID = jobs.NewID()
		state = StateCreated
		if err := s.insertImportRow(ctx, tx, orgID, repoID, importID, digest, manifest, opts); err != nil {
			return CreateImportResult{}, err
		}
	default:
		return CreateImportResult{}, e
	}

	missing, err := s.missingBlobs(ctx, orgID, manifest)
	if err != nil {
		return CreateImportResult{}, err
	}
	return CreateImportResult{ImportID: importID, State: state, Reused: reused, Missing: missing}, nil
}

// handleCreateImport is the HTTP route over CreateImport: authorisation,
// idempotency-key replay and response shaping are request concerns and stay
// here, while the reuse rule and the row writes live in the seam above.
func (s *Service) handleCreateImport(c *mgmt.Context) error {
	rc, e := s.authorizeRepo(c, mgmt.RoleOwner)
	if e != nil {
		return e
	}
	var req createImportRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	manifest, err := domain.ParseManifest(req.Manifest)
	if err != nil {
		return asAPIError(err)
	}

	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())

	result, err := s.CreateImport(c.Ctx(), tx, rc.Org.ID, rc.RepoID, manifest, CreateImportOptions{
		RawManifest: req.Manifest, CreatedBy: c.Principal.UserID,
		Actor: auditActor(c), RequestID: c.RequestID})
	if err != nil {
		return asAPIError(err)
	}
	if err := tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}

	body := map[string]any{
		"schema_version": mgmt.SchemaVersion,
		"import_id":      result.ImportID,
		"state":          result.State,
		"missing_blobs":  result.Missing,
		"limits": map[string]int64{
			"max_blob_bytes": domain.MaxBlobBytes, "max_total_bytes": domain.MaxTotalBytes,
			"max_files": domain.MaxFiles},
		"reused_import_id": nil,
	}
	if result.Reused {
		body["reused_import_id"] = result.ImportID
	}
	return c.JSON(http.StatusCreated, body)
}

// auditActor mirrors mgmt.Context.Audit's own rule, so a caller of the seam
// below that has no *mgmt.Context can supply the same actor string a request
// would have produced.
func auditActor(c *mgmt.Context) string {
	if c.Principal == nil {
		return "system"
	}
	return c.Principal.ID()
}

func (s *Service) insertImportRow(ctx context.Context, tx pgx.Tx, orgID, repoID, importID, digest string,
	manifest *domain.Manifest, opts CreateImportOptions) error {
	if _, e := tx.Exec(ctx, `INSERT INTO gfm.imports
 (org_id,import_id,repo_id,state,manifest_digest,commit,complete,dirty,cli_version,scan_profile,
  manifest,publish,created_by)
 VALUES($1::uuid,$2::uuid,$3,'created',$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12::uuid)`,
		orgID, importID, repoID, digest, nullable(manifest.CommitOrEmpty()),
		manifest.Complete, manifest.Dirty, manifest.CLIVersion, manifest.ScanProfile,
		string(opts.RawManifest), manifest.Publishes(), nullable(opts.CreatedBy)); e != nil {
		return e
	}
	// The file rows are the import's own record of what it promised to carry;
	// the worker later marks each accepted, omitted or failed.
	paths := make([]string, 0, len(manifest.Files))
	shas := make([]string, 0, len(manifest.Files))
	sizes := make([]int64, 0, len(manifest.Files))
	kinds := make([]string, 0, len(manifest.Files))
	modes := make([]string, 0, len(manifest.Files))
	for _, f := range manifest.Files {
		mode := f.Mode
		if mode == "" {
			mode = "100644"
		}
		paths = append(paths, f.Path)
		shas = append(shas, f.SHA256)
		sizes = append(sizes, f.Size)
		kinds = append(kinds, f.Kind)
		modes = append(modes, mode)
	}
	if len(paths) > 0 {
		if _, e := tx.Exec(ctx, `INSERT INTO gfm.import_files
 (org_id,import_id,path,sha256,size_bytes,kind,mode)
 SELECT $1::uuid,$2::uuid,p,s,z,k,m
 FROM unnest($3::text[],$4::text[],$5::bigint[],$6::text[],$7::text[]) AS t(p,s,z,k,m)`,
			orgID, importID, paths, shas, sizes, kinds, modes); e != nil {
			return e
		}
	}
	actor := opts.Actor
	if actor == "" {
		actor = "system"
	}
	return mgmt.Audit(ctx, tx, orgID, actor, "import.create", "import:"+importID, digest, opts.RequestID)
}

func (s *Service) missingBlobs(ctx context.Context, orgID string, manifest *domain.Manifest) ([]string, error) {
	wanted := manifest.Digests()
	held, e := s.blobs.Exists(ctx, orgID, wanted)
	if e != nil {
		return nil, e
	}
	missing := []string{}
	for _, sha := range wanted {
		if !held[sha] {
			missing = append(missing, sha)
		}
	}
	return missing, nil
}

// BlobsMissingError names the blobs FinalizeImport needs before it will queue
// work. It is a typed error rather than a bare string so a caller — HTTP or
// not — can read the list back with errors.As instead of parsing a message.
type BlobsMissingError struct{ Missing []string }

func (e *BlobsMissingError) Error() string {
	return "blobs missing before finalize"
}

// FinalizeResult is what a caller needs after a finalize attempt: the state
// the row ended in, and the ids of any job this call newly enqueued.
// Finalizing an import already past uploading is a no-op (U1.4): QueuedJobIDs
// is empty and State is whatever the row already held, exactly as a retried
// CLI run converges instead of queueing a second parse.
type FinalizeResult struct {
	State        string
	QueuedJobIDs []string
}

// FinalizeOptions carries the audit identity for the import.finalize entry
// this call writes, the same way CreateImportOptions does for import.create:
// an HTTP caller supplies the signed-in principal, a worker its own job
// identity, and the audit row is never left saying "system" for a request
// a person actually made.
type FinalizeOptions struct {
	Actor     string
	RequestID string
}

// FinalizeImport turns a complete upload into queued work, in the same
// transaction as the state change and both job rows, so a job never exists
// without the import that justifies it (API-CONTRACT §8). It is the other
// half of the seam CreateImport starts: a worker that filled an import's
// blobs itself calls this directly instead of going through the HTTP route
// to reach the same state machine.
func (s *Service) FinalizeImport(ctx context.Context, tx pgx.Tx, orgID, repoID, importID string,
	opts FinalizeOptions) (FinalizeResult, error) {
	rec, e := s.lockImport(ctx, tx, orgID, repoID, importID)
	if e != nil {
		return FinalizeResult{}, e
	}
	switch rec.State {
	case StateCancelled:
		return FinalizeResult{}, mgmt.Conflict("import_already_finalized", "This import was cancelled.")
	case StateQueued, StateParsing, StateReady, StatePartial, StateFailed:
		return FinalizeResult{State: rec.State}, nil
	}
	missing, err := s.missingBlobs(ctx, orgID, rec.Manifest)
	if err != nil {
		return FinalizeResult{}, err
	}
	if len(missing) > 0 {
		return FinalizeResult{}, &BlobsMissingError{Missing: missing}
	}
	if _, e := tx.Exec(ctx, `UPDATE gfm.imports SET state='queued',finalized_at=now(),updated_at=now()
 WHERE org_id=$1::uuid AND import_id=$2::uuid`, orgID, importID); e != nil {
		return FinalizeResult{}, e
	}
	payload, _ := json.Marshal(map[string]any{
		"schema_version": PayloadVersion, "org_id": orgID, "repo_id": repoID,
		"import_id": importID, "manifest_digest": rec.Digest,
		"commit": rec.Commit, "complete": rec.Complete})
	limits, _ := json.Marshal(map[string]int64{
		"max_files": domain.MaxFiles, "max_bytes": domain.MaxTotalBytes})
	parse := jobs.Job{OrgID: orgID, RepoID: repoID, ImportID: importID, Kind: KindParse,
		Payload: payload, InputDigest: rec.Digest, Limits: limits,
		IdempotencyKey: KindParse + ":" + importID}
	parseJob, e := s.queue.Enqueue(ctx, tx, parse)
	if e != nil {
		return FinalizeResult{}, e
	}
	jobIDs := []string{parseJob.JobID}
	if rec.Publish {
		// The publication module is not deployed yet. The job is still written
		// here, because the decision "this import should publish" belongs to
		// the manifest, not to whichever worker happens to be running; the
		// worker leases only the kinds it has handlers for, so this row waits
		// rather than failing.
		build, _ := json.Marshal(map[string]any{
			"schema_version": PayloadVersion, "org_id": orgID, "repo_id": repoID,
			"import_id": importID, "manifest_digest": rec.Digest, "commit": rec.Commit})
		publish := jobs.Job{OrgID: orgID, RepoID: repoID, ImportID: importID,
			Kind: KindPublish, Payload: build, InputDigest: rec.Digest,
			IdempotencyKey: KindPublish + ":" + importID}
		publishJob, e := s.queue.Enqueue(ctx, tx, publish)
		if e != nil {
			return FinalizeResult{}, e
		}
		jobIDs = append(jobIDs, publishJob.JobID)
	}
	actor := opts.Actor
	if actor == "" {
		actor = "system"
	}
	if e := mgmt.Audit(ctx, tx, orgID, actor, "import.finalize", "import:"+importID, rec.Digest,
		opts.RequestID); e != nil {
		return FinalizeResult{}, e
	}
	return FinalizeResult{State: StateQueued, QueuedJobIDs: jobIDs}, nil
}

// handleFinalize is the HTTP route over FinalizeImport: authorisation, the
// transaction boundary, the audit actor and response shaping stay here.
func (s *Service) handleFinalize(c *mgmt.Context) error {
	rc, e := s.authorizeRepo(c, mgmt.RoleOwner)
	if e != nil {
		return e
	}
	importID := c.Param("import_id")
	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	_, err := s.FinalizeImport(c.Ctx(), tx, rc.Org.ID, rc.RepoID, importID,
		FinalizeOptions{Actor: auditActor(c), RequestID: c.RequestID})
	if err != nil {
		var missing *BlobsMissingError
		switch {
		case errors.As(err, &missing):
			return mgmt.Conflict("blobs_missing",
				"Upload the listed blobs before finalizing this import.").
				WithDetails(map[string]any{"missing": missing.Missing})
		default:
			return err
		}
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return s.respondStatus(c, rc, importID)
}

// handleCancel stops an import. Queued jobs become cancelled and a leased job's
// generation moves, so a worker still holding the old lease is fenced at its
// next write instead of finishing into a cancelled import.
func (s *Service) handleCancel(c *mgmt.Context) error {
	rc, e := s.authorizeRepo(c, mgmt.RoleOwner)
	if e != nil {
		return e
	}
	importID := c.Param("import_id")
	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	rec, e := s.lockImport(c.Ctx(), tx, rc.Org.ID, rc.RepoID, importID)
	if e != nil {
		return e
	}
	if rec.State != StateCancelled {
		if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.imports SET state='cancelled',updated_at=now()
 WHERE org_id=$1::uuid AND import_id=$2::uuid`, rc.Org.ID, importID); e != nil {
			return mgmt.Internal(e)
		}
		if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.jobs
 SET state='cancelled',worker_id=NULL,lease_until=NULL,finished_at=now(),generation=generation+1
 WHERE org_id=$1::uuid AND import_id=$2::uuid AND state IN ('queued','leased')`,
			rc.Org.ID, importID); e != nil {
			return mgmt.Internal(e)
		}
		if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "import.cancel", "import:"+importID, ""); e != nil {
			return mgmt.Internal(e)
		}
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return s.respondStatus(c, rc, importID)
}

func (s *Service) handleGetImport(c *mgmt.Context) error {
	rc, e := s.authorizeRepo(c, mgmt.RoleAny)
	if e != nil {
		return e
	}
	return s.respondStatus(c, rc, c.Param("import_id"))
}

func (s *Service) handleListImports(c *mgmt.Context) error {
	rc, e := s.authorizeRepo(c, mgmt.RoleAny)
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
	rows, err := s.pool.Query(c.Ctx(), `SELECT import_id::text,state,manifest_digest,commit,complete,
 created_at,updated_at FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2
   AND ($3::timestamptz IS NULL OR (created_at,import_id::text) < ($3::timestamptz,$4))
 ORDER BY created_at DESC,import_id DESC LIMIT $5`,
		rc.Org.ID, rc.RepoID, nullableTime(after), before, limit+1)
	if err != nil {
		return mgmt.Internal(err)
	}
	defer rows.Close()
	items := []map[string]any{}
	var lastAt time.Time
	var lastID string
	for rows.Next() {
		var id, state, digest string
		var commit *string
		var complete bool
		var createdAt, updatedAt time.Time
		if err = rows.Scan(&id, &state, &digest, &commit, &complete, &createdAt, &updatedAt); err != nil {
			return mgmt.Internal(err)
		}
		// The list carries no per-file detail and no counts: files_truncated
		// says so, and a null count is "not measured here" rather than zero.
		// One import's status endpoint answers the detailed question.
		items = append(items, map[string]any{
			"import_id": id, "state": state, "manifest_digest": digest,
			"commit": commit, "complete": complete, "counts": nil,
			"files": []any{}, "files_truncated": true, "jobs": []any{}, "publication": nil,
			"created_at": createdAt, "updated_at": updatedAt})
		lastAt, lastID = createdAt, id
	}
	if err = rows.Err(); err != nil {
		return mgmt.Internal(err)
	}
	next := ""
	if len(items) > limit {
		items = items[:limit]
		last := items[len(items)-1]
		lastAt = last["created_at"].(time.Time)
		lastID = last["import_id"].(string)
		next = mgmt.EncodeCursor(lastAt.UTC().Format(time.RFC3339Nano), lastID)
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

// importRecord is the row plus its decoded manifest.
type importRecord struct {
	ImportID  string
	State     string
	Digest    string
	Commit    string
	Complete  bool
	Publish   bool
	Manifest  *domain.Manifest
	Raw       []byte
	Error     string
	CreatedAt time.Time
	UpdatedAt time.Time
}

// lockImport takes orgID and repoID directly rather than a *repoContext, so it
// -- and every exported seam built on it, such as FinalizeImport -- is
// reachable from a caller with no *mgmt.Context to hold one.
func (s *Service) lockImport(ctx context.Context, tx pgx.Tx, orgID, repoID, importID string) (*importRecord, error) {
	if _, e := parseUUID(importID); e != nil {
		return nil, mgmt.NotFound("import_not_found", "No such import in this repository.")
	}
	rec := &importRecord{ImportID: importID}
	var commit *string
	var raw string
	var failure *string
	e := tx.QueryRow(ctx, `SELECT state,manifest_digest,commit,complete,publish,manifest::text,error,
 created_at,updated_at FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2 AND import_id=$3::uuid FOR UPDATE`,
		orgID, repoID, importID).
		Scan(&rec.State, &rec.Digest, &commit, &rec.Complete, &rec.Publish, &raw, &failure,
			&rec.CreatedAt, &rec.UpdatedAt)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, mgmt.NotFound("import_not_found", "No such import in this repository.")
	}
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	rec.Commit, rec.Error, rec.Raw = str(commit), str(failure), []byte(raw)
	manifest, err := domain.ParseManifest(rec.Raw)
	if err != nil {
		return nil, mgmt.Internal(err)
	}
	rec.Manifest = manifest
	return rec, nil
}

// asAPIError maps a domain fault to the contract's envelope. The domain names
// the code; only the status belongs to the HTTP layer.
func asAPIError(e error) error {
	var f *domain.Fault
	if !errors.As(e, &f) {
		return mgmt.Internal(e)
	}
	switch f.Code {
	case "limit_exceeded":
		return mgmt.Unprocessable(f.Code, f.Message)
	default:
		return mgmt.Invalid(f.Code, f.Message)
	}
}

func parseUUID(s string) (string, error) {
	if len(s) != 36 {
		return "", errors.New("not_a_uuid")
	}
	for i, c := range s {
		switch i {
		case 8, 13, 18, 23:
			if c != '-' {
				return "", errors.New("not_a_uuid")
			}
		default:
			if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F') {
				return "", errors.New("not_a_uuid")
			}
		}
	}
	return s, nil
}
