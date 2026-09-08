package jobs_test

import (
	"context"
	"encoding/json"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/testdb"
)

func TestMain(m *testing.M) { testdb.Main(m) }

const org = "11111111-1111-4111-8111-111111111111"

func queue(t *testing.T) (*jobs.Queue, *pgxpool.Pool) {
	t.Helper()
	_, pool := testdb.Start(t)
	q := jobs.New(pool)
	q.Backoff = func(int) time.Duration { return 0 }
	return q, pool
}

func enqueue(t *testing.T, q *jobs.Queue, pool *pgxpool.Pool, j jobs.Job) *jobs.Job {
	t.Helper()
	ctx := context.Background()
	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback(ctx)
	out, e := q.Enqueue(ctx, tx, j)
	if e != nil {
		t.Fatal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	return out
}

func TestEnqueueJoinsCallerTransaction(t *testing.T) {
	q, pool := queue(t)
	ctx := context.Background()
	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	if _, e = q.Enqueue(ctx, tx, jobs.Job{OrgID: org, Kind: "import.parse"}); e != nil {
		t.Fatal(e)
	}
	if e = tx.Rollback(ctx); e != nil {
		t.Fatal(e)
	}
	leased, e := q.Lease(ctx, "w1", nil, time.Minute)
	if e != nil {
		t.Fatal(e)
	}
	if leased != nil {
		t.Fatal("a rolled back transaction still queued work")
	}
}

func TestEnqueueIsIdempotentPerOrganisation(t *testing.T) {
	q, pool := queue(t)
	first := enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "publish.build", IdempotencyKey: "k1",
		Payload: json.RawMessage(`{"a":1}`)})
	second := enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "publish.build", IdempotencyKey: "k1",
		Payload: json.RawMessage(`{"a":2}`)})
	if first.JobID != second.JobID {
		t.Fatalf("same key created two jobs: %s %s", first.JobID, second.JobID)
	}
	other := enqueue(t, q, pool, jobs.Job{OrgID: "22222222-2222-4222-8222-222222222222",
		Kind: "publish.build", IdempotencyKey: "k1"})
	if other.JobID == first.JobID {
		t.Fatal("idempotency key leaked across organisations")
	}
}

func TestLeaseIsExclusiveUnderConcurrency(t *testing.T) {
	q, pool := queue(t)
	const n = 24
	for i := 0; i < n; i++ {
		enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "import.parse"})
	}
	var mu sync.Mutex
	seen := map[string]int{}
	var wg sync.WaitGroup
	for w := 0; w < 8; w++ {
		wg.Add(1)
		go func(w int) {
			defer wg.Done()
			ctx := context.Background()
			for {
				j, e := q.Lease(ctx, "worker", nil, time.Minute)
				if e != nil {
					t.Error(e)
					return
				}
				if j == nil {
					return
				}
				mu.Lock()
				seen[j.JobID]++
				mu.Unlock()
			}
		}(w)
	}
	wg.Wait()
	if len(seen) != n {
		t.Fatalf("leased %d of %d jobs", len(seen), n)
	}
	for id, count := range seen {
		if count != 1 {
			t.Fatalf("job %s leased %d times", id, count)
		}
	}
}

func TestExpiredLeaseMovesGenerationAndFencesTheOldHolder(t *testing.T) {
	q, pool := queue(t)
	ctx := context.Background()
	enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "import.parse"})
	first, e := q.Lease(ctx, "worker-a", []string{"import.parse"}, 10*time.Millisecond)
	if e != nil || first == nil {
		t.Fatal("first lease", e, first)
	}
	if first.Generation != 1 || first.Attempts != 1 {
		t.Fatalf("generation=%d attempts=%d", first.Generation, first.Attempts)
	}
	time.Sleep(60 * time.Millisecond)
	second, e := q.Lease(ctx, "worker-b", nil, time.Minute)
	if e != nil || second == nil {
		t.Fatal("re-lease", e, second)
	}
	if second.JobID != first.JobID || second.Generation != first.Generation+1 {
		t.Fatalf("re-lease generation %d after %d", second.Generation, first.Generation)
	}
	for name, call := range map[string]func() error{
		"heartbeat":  func() error { return q.Heartbeat(ctx, first.JobID, first.Generation) },
		"checkpoint": func() error { return q.Checkpoint(ctx, first.JobID, first.Generation, json.RawMessage(`{"x":1}`)) },
		"complete":   func() error { return q.Complete(ctx, first.JobID, first.Generation, nil) },
		"skip":       func() error { return q.Skip(ctx, first.JobID, first.Generation, "stale") },
		"fail":       func() error { return q.Fail(ctx, first.JobID, first.Generation, "stale", false) },
	} {
		if e := call(); !errors.Is(e, jobs.ErrFenced) {
			t.Fatalf("%s from the fenced holder returned %v", name, e)
		}
	}
	row, e := q.Get(ctx, org, first.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if row.State != jobs.StateLeased || row.WorkerID != "worker-b" || row.Generation != second.Generation {
		t.Fatalf("fenced writes changed the row: %+v", row)
	}
	if e = q.Heartbeat(ctx, second.JobID, second.Generation); e != nil {
		t.Fatalf("current holder rejected: %v", e)
	}
}

func TestRetryBackoffAndAttemptCap(t *testing.T) {
	q, pool := queue(t)
	ctx := context.Background()
	delays := []time.Duration{}
	q.Backoff = func(attempts int) time.Duration {
		delays = append(delays, time.Duration(attempts)*time.Millisecond)
		return 0
	}
	enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "proposal.generate", MaxAttempts: 3})
	var last *jobs.Job
	for attempt := 1; attempt <= 3; attempt++ {
		j, e := q.Lease(ctx, "w", nil, time.Minute)
		if e != nil || j == nil {
			t.Fatalf("attempt %d: %v %v", attempt, e, j)
		}
		if j.Attempts != attempt {
			t.Fatalf("attempts=%d on attempt %d", j.Attempts, attempt)
		}
		if e = q.Fail(ctx, j.JobID, j.Generation, "boom", true); e != nil {
			t.Fatal(e)
		}
		last = j
	}
	if len(delays) != 3 {
		t.Fatalf("backoff consulted %d times", len(delays))
	}
	if again, e := q.Lease(ctx, "w", nil, time.Minute); e != nil || again != nil {
		t.Fatalf("a job past max_attempts was leased again: %v %v", e, again)
	}
	row, e := q.Get(ctx, org, last.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if row.State != jobs.StateFailed || row.Error != "boom" || row.FinishedAt == nil {
		t.Fatalf("terminal state %+v", row)
	}
}

func TestRetryableFailureWaitsForTheBackoffWindow(t *testing.T) {
	q, pool := queue(t)
	ctx := context.Background()
	q.Backoff = func(int) time.Duration { return 30 * time.Second }
	enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "import.parse"})
	j, e := q.Lease(ctx, "w", nil, time.Minute)
	if e != nil || j == nil {
		t.Fatal(e, j)
	}
	if e = q.Fail(ctx, j.JobID, j.Generation, "transient", true); e != nil {
		t.Fatal(e)
	}
	again, e := q.Lease(ctx, "w", nil, time.Minute)
	if e != nil {
		t.Fatal(e)
	}
	if again != nil {
		t.Fatal("a backing-off job was leased before its delay elapsed")
	}
	row, e := q.Get(ctx, org, j.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if row.State != jobs.StateQueued {
		t.Fatalf("state=%s", row.State)
	}
}

func TestCheckpointSurvivesReLease(t *testing.T) {
	q, pool := queue(t)
	ctx := context.Background()
	q.LeaseTTL = 10 * time.Millisecond // Checkpoint also extends the lease.
	enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "proposal.generate"})
	first, e := q.Lease(ctx, "a", nil, 10*time.Millisecond)
	if e != nil || first == nil {
		t.Fatal(e, first)
	}
	if e = q.Checkpoint(ctx, first.JobID, first.Generation, json.RawMessage(`{"done":["doc-1"]}`)); e != nil {
		t.Fatal(e)
	}
	time.Sleep(80 * time.Millisecond)
	second, e := q.Lease(ctx, "b", nil, time.Minute)
	if e != nil || second == nil {
		t.Fatal(e, second)
	}
	var resume struct {
		Done []string `json:"done"`
	}
	if e = json.Unmarshal(second.Checkpoint, &resume); e != nil {
		t.Fatal(e)
	}
	if len(resume.Done) != 1 || resume.Done[0] != "doc-1" {
		t.Fatalf("checkpoint lost on re-lease: %s", second.Checkpoint)
	}
	if e = q.Complete(ctx, second.JobID, second.Generation, json.RawMessage(`{"proposals":2}`)); e != nil {
		t.Fatal(e)
	}
	row, e := q.Get(ctx, org, second.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if row.State != jobs.StateDone || string(row.Result) != `{"proposals": 2}` && string(row.Result) != `{"proposals":2}` {
		t.Fatalf("completed row %+v", row)
	}
}

func TestCancelFencesTheRunningWorker(t *testing.T) {
	q, pool := queue(t)
	ctx := context.Background()
	queued := enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "import.parse"})
	running := enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "publish.build"})
	held, e := q.Lease(ctx, "w", []string{"publish.build"}, time.Minute)
	if e != nil || held == nil || held.JobID != running.JobID {
		t.Fatal(e, held)
	}
	if e = q.Cancel(ctx, org, running.JobID); e != nil {
		t.Fatal(e)
	}
	if e = q.Checkpoint(ctx, held.JobID, held.Generation, json.RawMessage(`{}`)); !errors.Is(e, jobs.ErrFenced) {
		t.Fatalf("cancelled job accepted a checkpoint: %v", e)
	}
	if e = q.Cancel(ctx, org, queued.JobID); e != nil {
		t.Fatal(e)
	}
	if again, e := q.Lease(ctx, "w", nil, time.Minute); e != nil || again != nil {
		t.Fatalf("cancelled work stayed leasable: %v %v", e, again)
	}
	if e = q.Cancel(ctx, org, queued.JobID); e != nil {
		t.Fatalf("cancelling twice: %v", e)
	}
	if e = q.Cancel(ctx, "33333333-3333-4333-8333-333333333333", queued.JobID); !errors.Is(e, jobs.ErrNotFound) {
		t.Fatalf("another organisation cancelled the job: %v", e)
	}
}

func TestSkipIsTerminal(t *testing.T) {
	q, pool := queue(t)
	ctx := context.Background()
	enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "proposal.generate"})
	j, e := q.Lease(ctx, "w", nil, time.Minute)
	if e != nil || j == nil {
		t.Fatal(e, j)
	}
	if e = q.Skip(ctx, j.JobID, j.Generation, "llm_not_configured"); e != nil {
		t.Fatal(e)
	}
	row, e := q.Get(ctx, org, j.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if row.State != jobs.StateSkipped || row.Error != "llm_not_configured" {
		t.Fatalf("%+v", row)
	}
	if again, e := q.Lease(ctx, "w", nil, time.Minute); e != nil || again != nil {
		t.Fatalf("skipped job re-leased: %v %v", e, again)
	}
}

func TestGetIsScopedToTheOrganisation(t *testing.T) {
	q, pool := queue(t)
	ctx := context.Background()
	j := enqueue(t, q, pool, jobs.Job{OrgID: org, Kind: "import.parse"})
	if _, e := q.Get(ctx, "44444444-4444-4444-8444-444444444444", j.JobID); !errors.Is(e, jobs.ErrNotFound) {
		t.Fatalf("cross-organisation read returned %v", e)
	}
	list, e := q.List(ctx, org, "", 10)
	if e != nil || len(list) != 1 {
		t.Fatalf("%v %d", e, len(list))
	}
}
