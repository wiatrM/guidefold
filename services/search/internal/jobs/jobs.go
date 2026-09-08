// Package jobs is the API–worker contract: a PostgreSQL work queue where the
// API enqueues inside its own transaction and workers lease with fencing.
//
// Fencing is the whole point. A lease bumps the row's generation; every later
// write from that worker carries the generation it was handed. When a lease
// expires and another worker takes over, the generation moves again and the old
// holder's writes are rejected with ErrFenced without changing anything.
package jobs

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

// ErrFenced means the job moved on: the lease expired, the job was cancelled,
// or another worker owns it now. The write changed nothing.
var ErrFenced = errors.New("job_fenced")

// ErrNotFound means no such job row.
var ErrNotFound = errors.New("job_not_found")

// States.
const (
	StateQueued    = "queued"
	StateLeased    = "leased"
	StateDone      = "done"
	StateFailed    = "failed"
	StateSkipped   = "skipped"
	StateCancelled = "cancelled"
)

// DefaultLease matches the brief: 30 s lease, heartbeat at most every 10 s.
const DefaultLease = 30 * time.Second

// Job is one row of gfm.jobs.
type Job struct {
	OrgID          string
	JobID          string
	RepoID         string
	ImportID       string
	Kind           string
	State          string
	Payload        json.RawMessage
	InputDigest    string
	RecipeVersion  string
	IdempotencyKey string
	Attempts       int
	MaxAttempts    int
	LeaseUntil     *time.Time
	WorkerID       string
	Generation     int
	Checkpoint     json.RawMessage
	Limits         json.RawMessage
	Cost           json.RawMessage
	Result         json.RawMessage
	Error          string
	CreatedAt      time.Time
	StartedAt      *time.Time
	FinishedAt     *time.Time
}

// Tx is the caller's open transaction; Enqueue must join it so a job never
// exists without the rows that justify it.
type Tx interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// Queue reads and writes gfm.jobs.
type Queue struct {
	Pool *pgxpool.Pool
	// LeaseTTL is the default lease granted by Lease and extended by Heartbeat.
	LeaseTTL time.Duration
	// Backoff maps the attempt count to the delay before the next lease.
	Backoff func(attempts int) time.Duration
}

// New builds a queue with the documented defaults.
func New(pool *pgxpool.Pool) *Queue {
	return &Queue{Pool: pool, LeaseTTL: DefaultLease, Backoff: ExponentialBackoff}
}

// ExponentialBackoff is 5 s, 10 s, 20 s ... capped at five minutes.
func ExponentialBackoff(attempts int) time.Duration {
	d := 5 * time.Second
	for i := 1; i < attempts && d < 5*time.Minute; i++ {
		d *= 2
	}
	if d > 5*time.Minute {
		d = 5 * time.Minute
	}
	return d
}

func (q *Queue) lease() time.Duration {
	if q.LeaseTTL <= 0 {
		return DefaultLease
	}
	return q.LeaseTTL
}
func (q *Queue) backoff(attempts int) time.Duration {
	if q.Backoff == nil {
		return ExponentialBackoff(attempts)
	}
	return q.Backoff(attempts)
}

// Every read casts uuid to text so the same SQL works under the extended
// protocol used by tests and the simple-exec mode used by the service pool.
const columns = `org_id::text,job_id::text,repo_id,import_id::text,kind,state,payload::text,
 input_digest,recipe_version,idempotency_key,attempts,max_attempts,lease_until,worker_id,
 generation,checkpoint::text,limits::text,cost::text,result::text,error,created_at,started_at,finished_at`

func scanJob(row pgx.Row) (*Job, error) {
	var j Job
	var repo, importID, digest, recipe, key, worker, failure *string
	var payload, checkpoint, limits, cost, result *string
	e := row.Scan(&j.OrgID, &j.JobID, &repo, &importID, &j.Kind, &j.State, &payload,
		&digest, &recipe, &key, &j.Attempts, &j.MaxAttempts, &j.LeaseUntil, &worker,
		&j.Generation, &checkpoint, &limits, &cost, &result, &failure,
		&j.CreatedAt, &j.StartedAt, &j.FinishedAt)
	if e != nil {
		return nil, e
	}
	j.RepoID, j.ImportID = deref(repo), deref(importID)
	j.InputDigest, j.RecipeVersion, j.IdempotencyKey = deref(digest), deref(recipe), deref(key)
	j.WorkerID, j.Error = deref(worker), deref(failure)
	j.Payload, j.Checkpoint = raw(payload), raw(checkpoint)
	j.Limits, j.Cost, j.Result = raw(limits), raw(cost), raw(result)
	return &j, nil
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
func raw(s *string) json.RawMessage {
	if s == nil {
		return nil
	}
	return json.RawMessage(*s)
}
func nilable(s string) any {
	if s == "" {
		return nil
	}
	return s
}
func nilableJSON(b json.RawMessage) any {
	if len(b) == 0 {
		return nil
	}
	return string(b)
}

// Enqueue inserts a job inside the caller's transaction. When the job carries
// an idempotency key that the organisation already used, the existing job is
// returned unchanged and nothing new is queued.
func (q *Queue) Enqueue(ctx context.Context, tx Tx, j Job) (*Job, error) {
	if j.OrgID == "" || j.Kind == "" {
		return nil, fmt.Errorf("job_requires_org_and_kind")
	}
	if j.JobID == "" {
		j.JobID = NewID()
	}
	if j.MaxAttempts <= 0 {
		j.MaxAttempts = 3
	}
	const insert = `INSERT INTO gfm.jobs
 (org_id,job_id,repo_id,import_id,kind,payload,input_digest,recipe_version,idempotency_key,max_attempts,limits)
 VALUES($1::uuid,$2::uuid,$3,$4::uuid,$5,COALESCE($6::jsonb,'{}'::jsonb),$7,$8,$9,$10,$11::jsonb)
 ON CONFLICT (org_id,idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
 RETURNING ` + columns
	out, e := scanJob(tx.QueryRow(ctx, insert, j.OrgID, j.JobID, nilable(j.RepoID), nilable(j.ImportID),
		j.Kind, nilableJSON(j.Payload), nilable(j.InputDigest), nilable(j.RecipeVersion),
		nilable(j.IdempotencyKey), j.MaxAttempts, nilableJSON(j.Limits)))
	if e == nil {
		return out, nil
	}
	if !errors.Is(e, pgx.ErrNoRows) || j.IdempotencyKey == "" {
		return nil, e
	}
	return scanJob(tx.QueryRow(ctx,
		`SELECT `+columns+` FROM gfm.jobs WHERE org_id=$1::uuid AND idempotency_key=$2`,
		j.OrgID, j.IdempotencyKey))
}

// Lease claims one runnable job of the given kinds (all kinds when empty):
// queued and due, or leased with an expired lease. It returns nil when the
// queue is empty. The returned job carries the new generation.
func (q *Queue) Lease(ctx context.Context, workerID string, kinds []string, lease time.Duration) (*Job, error) {
	if workerID == "" {
		return nil, fmt.Errorf("worker_id_required")
	}
	if lease <= 0 {
		lease = q.lease()
	}
	var filter any
	if len(kinds) > 0 {
		filter = kinds
	}
	const claim = `UPDATE gfm.jobs SET
 state='leased', worker_id=$1, generation=generation+1, attempts=attempts+1,
 lease_until=now()+make_interval(secs=>$2::float8), started_at=COALESCE(started_at,now())
 WHERE job_id=(
  SELECT job_id FROM gfm.jobs
  WHERE ($3::text[] IS NULL OR kind=ANY($3::text[]))
    AND ((state='queued' AND (lease_until IS NULL OR lease_until<=now()))
      OR (state='leased' AND lease_until<=now()))
  ORDER BY created_at,job_id FOR UPDATE SKIP LOCKED LIMIT 1)
 RETURNING ` + columns
	j, e := q.writeRow(ctx, claim, workerID, lease.Seconds(), filter)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, nil
	}
	return j, e
}

// Heartbeat extends the lease. A stale generation returns ErrFenced.
func (q *Queue) Heartbeat(ctx context.Context, jobID string, generation int) error {
	return q.fenced(ctx, jobID, generation,
		`UPDATE gfm.jobs SET lease_until=now()+make_interval(secs=>$3::float8)
 WHERE job_id=$1::uuid AND generation=$2 AND state='leased'`, q.lease().Seconds())
}

// Checkpoint stores resume state and extends the lease in the same write.
func (q *Queue) Checkpoint(ctx context.Context, jobID string, generation int, data json.RawMessage) error {
	return q.fenced(ctx, jobID, generation,
		`UPDATE gfm.jobs SET checkpoint=$3::jsonb, lease_until=now()+make_interval(secs=>$4::float8)
 WHERE job_id=$1::uuid AND generation=$2 AND state='leased'`, nilableJSON(data), q.lease().Seconds())
}

// Cost records accumulated generator cost without ending the job.
func (q *Queue) Cost(ctx context.Context, jobID string, generation int, cost json.RawMessage) error {
	return q.fenced(ctx, jobID, generation,
		`UPDATE gfm.jobs SET cost=$3::jsonb WHERE job_id=$1::uuid AND generation=$2 AND state='leased'`,
		nilableJSON(cost))
}

// Complete finishes the job successfully.
func (q *Queue) Complete(ctx context.Context, jobID string, generation int, result json.RawMessage) error {
	return q.fenced(ctx, jobID, generation,
		`UPDATE gfm.jobs SET state='done', result=$3::jsonb, error=NULL, worker_id=NULL,
 lease_until=NULL, finished_at=now(), generation=generation+1
 WHERE job_id=$1::uuid AND generation=$2 AND state='leased'`, nilableJSON(result))
}

// Skip ends the job as deliberately not done (for example a generator that is
// not configured). It is terminal and is never retried.
func (q *Queue) Skip(ctx context.Context, jobID string, generation int, reason string) error {
	return q.fenced(ctx, jobID, generation,
		`UPDATE gfm.jobs SET state='skipped', error=$3, worker_id=NULL, lease_until=NULL,
 finished_at=now(), generation=generation+1
 WHERE job_id=$1::uuid AND generation=$2 AND state='leased'`, nilable(reason))
}

// Fail records an error. A retryable failure below max_attempts returns the job
// to the queue after a backoff delay; otherwise the job ends failed.
func (q *Queue) Fail(ctx context.Context, jobID string, generation int, cause string, retryable bool) error {
	tx, e := q.begin(ctx)
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	var attempts, maxAttempts int
	e = tx.QueryRow(ctx, `SELECT attempts,max_attempts FROM gfm.jobs WHERE job_id=$1::uuid`, jobID).
		Scan(&attempts, &maxAttempts)
	if errors.Is(e, pgx.ErrNoRows) {
		return ErrNotFound
	}
	if e != nil {
		return e
	}
	retry := retryable && attempts < maxAttempts
	const update = `UPDATE gfm.jobs SET
 state=CASE WHEN $3::bool THEN 'queued' ELSE 'failed' END,
 error=$4, worker_id=NULL, generation=generation+1,
 lease_until=CASE WHEN $3::bool THEN now()+make_interval(secs=>$5::float8) ELSE NULL END,
 finished_at=CASE WHEN $3::bool THEN NULL ELSE now() END
 WHERE job_id=$1::uuid AND generation=$2 AND state='leased'`
	tag, e := tx.Exec(ctx, update, jobID, generation, retry, nilable(cause), q.backoff(attempts).Seconds())
	if e != nil {
		return e
	}
	if tag.RowsAffected() == 0 {
		return ErrFenced
	}
	return tx.Commit(ctx)
}

// Cancel stops a queued or leased job. The generation moves, so a worker still
// holding the old lease is fenced at its next write.
func (q *Queue) Cancel(ctx context.Context, orgID, jobID string) error {
	tx, e := q.begin(ctx)
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	tag, e := tx.Exec(ctx, `UPDATE gfm.jobs SET state='cancelled', worker_id=NULL, lease_until=NULL,
 finished_at=now(), generation=generation+1
 WHERE org_id=$1::uuid AND job_id=$2::uuid AND state IN ('queued','leased')`, orgID, jobID)
	if e != nil {
		return e
	}
	if tag.RowsAffected() == 0 {
		var exists bool
		if e = tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gfm.jobs WHERE org_id=$1::uuid AND job_id=$2::uuid)`,
			orgID, jobID).Scan(&exists); e != nil {
			return e
		}
		if !exists {
			return ErrNotFound
		}
		return nil // already terminal; cancelling twice is not an error
	}
	return tx.Commit(ctx)
}

// Get reads one job of an organisation.
func (q *Queue) Get(ctx context.Context, orgID, jobID string) (*Job, error) {
	j, e := scanJob(q.Pool.QueryRow(ctx,
		`SELECT `+columns+` FROM gfm.jobs WHERE org_id=$1::uuid AND job_id=$2::uuid`, orgID, jobID))
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return j, e
}

// List returns an organisation's jobs, newest first. An import id narrows it.
func (q *Queue) List(ctx context.Context, orgID, importID string, limit int) ([]Job, error) {
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	rows, e := q.Pool.Query(ctx, `SELECT `+columns+` FROM gfm.jobs
 WHERE org_id=$1::uuid AND ($2::uuid IS NULL OR import_id=$2::uuid)
 ORDER BY created_at DESC,job_id DESC LIMIT $3`, orgID, nilable(importID), limit)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []Job{}
	for rows.Next() {
		j, e := scanJob(rows)
		if e != nil {
			return nil, e
		}
		out = append(out, *j)
	}
	return out, rows.Err()
}

// The management role runs read-only by default, so every write opens an
// explicit read-write transaction — the same rule the telemetry ingest follows.
func (q *Queue) begin(ctx context.Context) (pgx.Tx, error) {
	return q.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
}

func (q *Queue) writeRow(ctx context.Context, sql string, args ...any) (*Job, error) {
	tx, e := q.begin(ctx)
	if e != nil {
		return nil, e
	}
	defer tx.Rollback(ctx)
	j, e := scanJob(tx.QueryRow(ctx, sql, args...))
	if e != nil {
		return nil, e
	}
	if e = tx.Commit(ctx); e != nil {
		return nil, e
	}
	return j, nil
}

func (q *Queue) fenced(ctx context.Context, jobID string, generation int, sql string, args ...any) error {
	tx, e := q.begin(ctx)
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	tag, e := tx.Exec(ctx, sql, append([]any{jobID, generation}, args...)...)
	if e != nil {
		return e
	}
	if tag.RowsAffected() == 0 {
		var exists bool
		if e = tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gfm.jobs WHERE job_id=$1::uuid)`, jobID).
			Scan(&exists); e != nil {
			return e
		}
		if !exists {
			return ErrNotFound
		}
		return ErrFenced
	}
	return tx.Commit(ctx)
}

// NewID returns a random RFC 4122 version 4 identifier.
func NewID() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	s := hex.EncodeToString(b[:])
	return s[:8] + "-" + s[8:12] + "-" + s[12:16] + "-" + s[16:20] + "-" + s[20:]
}
