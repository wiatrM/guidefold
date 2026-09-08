package importer

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// importFileView is the `ImportFile` DTO.
type importFileView struct {
	Path    string  `json:"path"`
	SHA256  string  `json:"sha256"`
	Size    int64   `json:"size"`
	Kind    string  `json:"kind"`
	Status  string  `json:"status"`
	Reason  *string `json:"reason"`
	SkillID *string `json:"skill_id"`
}

// jobView is the `Job` DTO.
type jobView struct {
	JobID      string          `json:"job_id"`
	Kind       string          `json:"kind"`
	State      string          `json:"state"`
	Attempts   int             `json:"attempts"`
	Generation int             `json:"generation"`
	Error      *string         `json:"error"`
	Cost       json.RawMessage `json:"cost"`
	StartedAt  *time.Time      `json:"started_at"`
	FinishedAt *time.Time      `json:"finished_at"`
	// Abstentions is why a generation job produced less than the plan suggested.
	// A run that declined to consolidate two runbooks has done its job; a client
	// that can only see "3 proposals" cannot tell that from a run that failed
	// quietly, so the reason travels with the job (API-CONTRACT §5.2, P08).
	Abstentions []jobAbstention `json:"abstentions"`
}

// jobAbstention is one named refusal out of a job's result.
type jobAbstention struct {
	Reason string   `json:"reason"`
	Skills []string `json:"skills"`
	Detail string   `json:"detail"`
}

// maxJobAbstentions bounds what the status view carries. The full list stays in
// the job row; this is a summary a CLI prints, not an audit log.
const maxJobAbstentions = 20

// abstentionsOf reads the named refusals out of a finished job's result. A job
// with no result, or a result shaped differently, contributes nothing rather
// than an error: the status view must not fail because a worker wrote something
// this reader does not know.
func abstentionsOf(result json.RawMessage) []jobAbstention {
	out := []jobAbstention{}
	if len(result) == 0 {
		return out
	}
	var parsed struct {
		Abstentions []jobAbstention `json:"abstentions"`
	}
	if e := json.Unmarshal(result, &parsed); e != nil {
		return out
	}
	for _, a := range parsed.Abstentions {
		if len(out) >= maxJobAbstentions {
			break
		}
		if a.Skills == nil {
			a.Skills = []string{}
		}
		out = append(out, a)
	}
	return out
}

// respondStatus writes the `ImportStatus` DTO: what the import promised, what
// the parse made of each file, which jobs ran and whether a publication
// followed. `state: ready` is deliberately not `published` — the publication
// has its own field, because an import that parsed is not an import that is
// serving (API-CONTRACT §5.2).
func (s *Service) respondStatus(c *mgmt.Context, rc *repoContext, importID string) error {
	if _, e := parseUUID(importID); e != nil {
		return mgmt.NotFound("import_not_found", "No such import in this repository.")
	}
	var state, digest string
	var commit, failure *string
	var complete, publish bool
	var createdAt, updatedAt time.Time
	var finalizedAt *time.Time
	var reused *string
	e := s.pool.QueryRow(c.Ctx(), `SELECT state,manifest_digest,commit,complete,publish,error,
 reused_import_id::text,created_at,updated_at,finalized_at FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2 AND import_id=$3::uuid`,
		rc.Org.ID, rc.RepoID, importID).
		Scan(&state, &digest, &commit, &complete, &publish, &failure, &reused,
			&createdAt, &updatedAt, &finalizedAt)
	if errors.Is(e, pgx.ErrNoRows) {
		return mgmt.NotFound("import_not_found", "No such import in this repository.")
	}
	if e != nil {
		return mgmt.Internal(e)
	}

	files, truncated, err := s.statusFiles(c.Ctx(), rc.Org.ID, importID)
	if err != nil {
		return mgmt.Internal(err)
	}
	counts, err := s.statusCounts(c.Ctx(), rc.Org.ID, importID, createdAt)
	if err != nil {
		return mgmt.Internal(err)
	}
	list, err := s.queue.List(c.Ctx(), rc.Org.ID, importID, 50)
	if err != nil {
		return mgmt.Internal(err)
	}
	views := make([]jobView, 0, len(list))
	publication := map[string]any{"snapshot_id": nil, "state": "none", "error": nil}
	for i := range list {
		j := &list[i]
		var jobError *string
		if j.Error != "" {
			v := j.Error
			jobError = &v
		}
		views = append(views, jobView{JobID: j.JobID, Kind: j.Kind, State: j.State,
			Attempts: j.Attempts, Generation: j.Generation, Error: jobError,
			Cost: j.Cost, StartedAt: j.StartedAt, FinishedAt: j.FinishedAt,
			Abstentions: abstentionsOf(j.Result)})
		if j.Kind == KindPublish {
			publication["state"] = publicationState(j.State)
			publication["error"] = jobError
		}
	}

	body := map[string]any{
		"schema_version":  mgmt.SchemaVersion,
		"org_id":          rc.Org.ID,
		"repo_id":         rc.RepoID,
		"import_id":       importID,
		"state":           state,
		"manifest_digest": digest,
		"commit":          commit,
		"complete":        complete,
		"publish":         publish,
		"counts":          counts,
		"files":           files,
		"files_truncated": truncated,
		"jobs":            views,
		"publication":     publication,
		"error":           failure,
		"created_at":      createdAt,
		"updated_at":      updatedAt,
		"finalized_at":    finalizedAt,
	}
	if reused != nil {
		body["reused_import_id"] = *reused
	} else {
		body["reused_import_id"] = nil
	}
	return c.JSON(http.StatusOK, body)
}

// publicationState maps a publish.build job to the `ImportPublication` domain.
// A queued or leased build is `building`; a job that never ran because the
// publication module is not deployed stays `building` rather than claiming a
// snapshot exists.
func publicationState(jobState string) string {
	switch jobState {
	case jobs.StateQueued, jobs.StateLeased:
		return "building"
	case jobs.StateDone:
		return "published"
	case jobs.StateFailed:
		return "failed"
	default:
		return "none"
	}
}

func (s *Service) statusFiles(ctx context.Context, orgID, importID string) ([]importFileView, bool, error) {
	rows, e := s.pool.Query(ctx, `SELECT path,sha256,size_bytes,kind,status,reason,skill_id
 FROM gfm.import_files WHERE org_id=$1::uuid AND import_id=$2::uuid
 ORDER BY path LIMIT $3`, orgID, importID, maxStatusFiles+1)
	if e != nil {
		return nil, false, e
	}
	defer rows.Close()
	out := []importFileView{}
	for rows.Next() {
		var v importFileView
		if e = rows.Scan(&v.Path, &v.SHA256, &v.Size, &v.Kind, &v.Status, &v.Reason, &v.SkillID); e != nil {
			return nil, false, e
		}
		out = append(out, v)
	}
	if e = rows.Err(); e != nil {
		return nil, false, e
	}
	if len(out) > maxStatusFiles {
		return out[:maxStatusFiles], true, nil
	}
	return out, false, nil
}

// statusCounts is the `ImportCounts` DTO.
//
// new_blobs counts the manifest's distinct digests whose blob was stored at or
// after this import was created; the rest were already held. A repeat of the
// same tree reuses its import row, so its counts keep describing the run that
// actually uploaded (API-CONTRACT §5.2).
func (s *Service) statusCounts(ctx context.Context, orgID, importID string, createdAt time.Time) (map[string]int, error) {
	counts := map[string]int{"files": 0, "accepted": 0, "omitted": 0, "failed": 0,
		"new_blobs": 0, "reused_blobs": 0, "skills": 0, "documents": 0}
	rows, e := s.pool.Query(ctx, `SELECT status,count(*),
 count(*) FILTER (WHERE kind='skill' AND status='accepted')
 FROM gfm.import_files WHERE org_id=$1::uuid AND import_id=$2::uuid GROUP BY status`,
		orgID, importID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	for rows.Next() {
		var status string
		var n, skills int
		if e = rows.Scan(&status, &n, &skills); e != nil {
			return nil, e
		}
		counts["files"] += n
		counts["skills"] += skills
		if _, known := counts[status]; known {
			counts[status] += n
		}
	}
	if e = rows.Err(); e != nil {
		return nil, e
	}
	var newBlobs, allBlobs, documents int
	if e = s.pool.QueryRow(ctx, `SELECT
 (SELECT count(DISTINCT b.sha256) FROM gfm.blobs b
   WHERE b.org_id=$1::uuid AND b.created_at>=$3
     AND b.sha256 IN (SELECT sha256 FROM gfm.import_files
                      WHERE org_id=$1::uuid AND import_id=$2::uuid)),
 (SELECT count(DISTINCT sha256) FROM gfm.import_files
   WHERE org_id=$1::uuid AND import_id=$2::uuid),
 (SELECT count(*) FROM gfm.documents WHERE org_id=$1::uuid AND import_id=$2::uuid)`,
		orgID, importID, createdAt).Scan(&newBlobs, &allBlobs, &documents); e != nil {
		return nil, e
	}
	counts["new_blobs"] = newBlobs
	counts["reused_blobs"] = allBlobs - newBlobs
	counts["documents"] = documents
	return counts, nil
}
