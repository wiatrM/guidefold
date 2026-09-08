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

// handleCreateImport records one scan and answers with the blobs it still
// needs. It never uploads anything itself: the manifest is the plan, the blobs
// arrive on their own route, and only finalize turns the pair into work.
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
	if err := manifest.Validate(rc.RepoID); err != nil {
		return asAPIError(err)
	}
	digest, err := domain.ManifestDigest(req.Manifest)
	if err != nil {
		return asAPIError(err)
	}

	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())

	// A manifest digest identifies a tree. Sending the same tree twice reuses
	// the import that already exists for it, so an interrupted sync resumes
	// instead of starting a second upload of the same bytes (U1.4).
	var importID, state string
	reused := false
	scan := tx.QueryRow(c.Ctx(), `SELECT import_id::text,state FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2 AND manifest_digest=$3 AND state<>'failed'`,
		rc.Org.ID, rc.RepoID, digest)
	switch e := scan.Scan(&importID, &state); {
	case e == nil:
		reused = true
	case errors.Is(e, pgx.ErrNoRows):
		importID = jobs.NewID()
		state = StateCreated
		if err := s.insertImport(c, tx, rc, importID, digest, manifest, req.Manifest); err != nil {
			return err
		}
	default:
		return mgmt.Internal(e)
	}
	if err := tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}

	missing, err := s.missingBlobs(c.Ctx(), rc.Org.ID, manifest)
	if err != nil {
		return mgmt.Internal(err)
	}
	body := map[string]any{
		"schema_version": mgmt.SchemaVersion,
		"import_id":      importID,
		"state":          state,
		"missing_blobs":  missing,
		"limits": map[string]int64{
			"max_blob_bytes": domain.MaxBlobBytes, "max_total_bytes": domain.MaxTotalBytes,
			"max_files": domain.MaxFiles},
		"reused_import_id": nil,
	}
	if reused {
		body["reused_import_id"] = importID
	}
	return c.JSON(http.StatusCreated, body)
}

func (s *Service) insertImport(c *mgmt.Context, tx pgx.Tx, rc *repoContext, importID, digest string,
	manifest *domain.Manifest, raw []byte) error {
	created := c.Principal.UserID
	if _, e := tx.Exec(c.Ctx(), `INSERT INTO gfm.imports
 (org_id,import_id,repo_id,state,manifest_digest,commit,complete,dirty,cli_version,scan_profile,
  manifest,publish,created_by)
 VALUES($1::uuid,$2::uuid,$3,'created',$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12::uuid)`,
		rc.Org.ID, importID, rc.RepoID, digest, nullable(manifest.CommitOrEmpty()),
		manifest.Complete, manifest.Dirty, manifest.CLIVersion, manifest.ScanProfile,
		string(raw), manifest.Publishes(), nullable(created)); e != nil {
		return mgmt.Internal(e)
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
		if _, e := tx.Exec(c.Ctx(), `INSERT INTO gfm.import_files
 (org_id,import_id,path,sha256,size_bytes,kind,mode)
 SELECT $1::uuid,$2::uuid,p,s,z,k,m
 FROM unnest($3::text[],$4::text[],$5::bigint[],$6::text[],$7::text[]) AS t(p,s,z,k,m)`,
			rc.Org.ID, importID, paths, shas, sizes, kinds, modes); e != nil {
			return mgmt.Internal(e)
		}
	}
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "import.create", "import:"+importID, digest); e != nil {
		return mgmt.Internal(e)
	}
	return nil
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

// handleFinalize turns a complete upload into queued work. The state change and
// both job rows are one transaction, so a job never exists without the import
// that justifies it (API-CONTRACT §8).
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
	rec, e := s.lockImport(c.Ctx(), tx, rc, importID)
	if e != nil {
		return e
	}
	switch rec.State {
	case StateCancelled:
		return mgmt.Conflict("import_already_finalized", "This import was cancelled.")
	case StateQueued, StateParsing, StateReady, StatePartial, StateFailed:
		// Finalizing twice is a no-op: the work is already queued or done.
		// Answering with the current status is what makes a retried CLI run
		// converge instead of queueing a second parse (U1.4).
		if e := tx.Commit(c.Ctx()); e != nil {
			return mgmt.Internal(e)
		}
		return s.respondStatus(c, rc, importID)
	}
	missing, err := s.missingBlobs(c.Ctx(), rc.Org.ID, rec.Manifest)
	if err != nil {
		return mgmt.Internal(err)
	}
	if len(missing) > 0 {
		return mgmt.Conflict("blobs_missing",
			"Upload the listed blobs before finalizing this import.").
			WithDetails(map[string]any{"missing": missing})
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.imports SET state='queued',finalized_at=now(),updated_at=now()
 WHERE org_id=$1::uuid AND import_id=$2::uuid`, rc.Org.ID, importID); e != nil {
		return mgmt.Internal(e)
	}
	payload, _ := json.Marshal(map[string]any{
		"schema_version": PayloadVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"import_id": importID, "manifest_digest": rec.Digest,
		"commit": rec.Commit, "complete": rec.Complete})
	limits, _ := json.Marshal(map[string]int64{
		"max_files": domain.MaxFiles, "max_bytes": domain.MaxTotalBytes})
	parse := jobs.Job{OrgID: rc.Org.ID, RepoID: rc.RepoID, ImportID: importID, Kind: KindParse,
		Payload: payload, InputDigest: rec.Digest, Limits: limits,
		IdempotencyKey: KindParse + ":" + importID}
	if _, e := s.queue.Enqueue(c.Ctx(), tx, parse); e != nil {
		return mgmt.Internal(e)
	}
	if rec.Publish {
		// The publication module is not deployed yet. The job is still written
		// here, because the decision "this import should publish" belongs to
		// the manifest, not to whichever worker happens to be running; the
		// worker leases only the kinds it has handlers for, so this row waits
		// rather than failing.
		build, _ := json.Marshal(map[string]any{
			"schema_version": PayloadVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
			"import_id": importID, "manifest_digest": rec.Digest, "commit": rec.Commit})
		publish := jobs.Job{OrgID: rc.Org.ID, RepoID: rc.RepoID, ImportID: importID,
			Kind: KindPublish, Payload: build, InputDigest: rec.Digest,
			IdempotencyKey: KindPublish + ":" + importID}
		if _, e := s.queue.Enqueue(c.Ctx(), tx, publish); e != nil {
			return mgmt.Internal(e)
		}
	}
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "import.finalize", "import:"+importID, rec.Digest); e != nil {
		return mgmt.Internal(e)
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
	rec, e := s.lockImport(c.Ctx(), tx, rc, importID)
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

func (s *Service) lockImport(ctx context.Context, tx pgx.Tx, rc *repoContext, importID string) (*importRecord, error) {
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
		rc.Org.ID, rc.RepoID, importID).
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
