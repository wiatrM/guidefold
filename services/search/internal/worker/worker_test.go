package worker_test

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/testdb"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

func TestMain(m *testing.M) { testdb.Main(m) }

const org = "55555555-5555-4555-8555-555555555555"

func setup(t *testing.T) (*jobs.Queue, *pgxpool.Pool) {
	t.Helper()
	_, pool := testdb.Start(t)
	q := jobs.New(pool)
	q.LeaseTTL = 300 * time.Millisecond
	q.Backoff = func(int) time.Duration { return 0 }
	return q, pool
}

func enqueue(t *testing.T, q *jobs.Queue, pool *pgxpool.Pool, kind string) *jobs.Job {
	t.Helper()
	ctx := context.Background()
	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback(ctx)
	j, e := q.Enqueue(ctx, tx, jobs.Job{OrgID: org, Kind: kind})
	if e != nil {
		t.Fatal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	return j
}

func TestRunOnceCompletesAndStores(t *testing.T) {
	q, pool := setup(t)
	ctx := context.Background()
	j := enqueue(t, q, pool, "demo")
	handlers := map[string]worker.Handler{"demo": func(ctx context.Context, task *worker.Task) error {
		if e := task.Checkpoint(ctx, json.RawMessage(`{"step":1}`)); e != nil {
			return e
		}
		task.Result = json.RawMessage(`{"ok":true}`)
		return nil
	}}
	if e := worker.Run(ctx, pool, "w1", handlers, worker.Options{Once: true, Queue: q}); e != nil {
		t.Fatal(e)
	}
	row, e := q.Get(ctx, org, j.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if row.State != jobs.StateDone || row.Result == nil || row.Checkpoint == nil {
		t.Fatalf("%+v", row)
	}
}

func TestRunOnceReturnsOnEmptyQueue(t *testing.T) {
	q, pool := setup(t)
	handlers := map[string]worker.Handler{"demo": func(context.Context, *worker.Task) error { return nil }}
	done := make(chan error, 1)
	go func() {
		done <- worker.Run(context.Background(), pool, "w1", handlers, worker.Options{Once: true, Queue: q})
	}()
	select {
	case e := <-done:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("--once did not return on an empty queue")
	}
}

func TestFailureIsRetriedThenTerminal(t *testing.T) {
	q, pool := setup(t)
	ctx := context.Background()
	j := enqueue(t, q, pool, "demo")
	handlers := map[string]worker.Handler{"demo": func(context.Context, *worker.Task) error {
		return fmt.Errorf("transient")
	}}
	for i := 0; i < 3; i++ {
		if e := worker.Run(ctx, pool, "w1", handlers, worker.Options{Once: true, Queue: q}); e != nil {
			t.Fatal(e)
		}
	}
	row, e := q.Get(ctx, org, j.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if row.State != jobs.StateFailed || row.Attempts != 3 {
		t.Fatalf("%+v", row)
	}
}

func TestPermanentFailureAndSkipAreNotRetried(t *testing.T) {
	q, pool := setup(t)
	ctx := context.Background()
	permanent := enqueue(t, q, pool, "permanent")
	skipped := enqueue(t, q, pool, "skipped")
	handlers := map[string]worker.Handler{
		"permanent": func(context.Context, *worker.Task) error { return worker.Permanent(errors.New("bad_input")) },
		"skipped":   func(context.Context, *worker.Task) error { return worker.Skipped("llm_not_configured") },
	}
	for i := 0; i < 2; i++ {
		if e := worker.Run(ctx, pool, "w1", handlers, worker.Options{Once: true, Queue: q}); e != nil {
			t.Fatal(e)
		}
	}
	for _, x := range []struct {
		job   *jobs.Job
		state string
		cause string
	}{{permanent, jobs.StateFailed, "bad_input"}, {skipped, jobs.StateSkipped, "llm_not_configured"}} {
		row, e := q.Get(ctx, org, x.job.JobID)
		if e != nil {
			t.Fatal(e)
		}
		if row.State != x.state || row.Error != x.cause || row.Attempts != 1 {
			t.Fatalf("%s: %+v", x.job.Kind, row)
		}
	}
}

func TestHeartbeatCancelsAFencedHandler(t *testing.T) {
	q, pool := setup(t)
	ctx := context.Background()
	j := enqueue(t, q, pool, "demo")
	entered := make(chan struct{})
	cancelled := make(chan error, 1)
	handlers := map[string]worker.Handler{"demo": func(work context.Context, task *worker.Task) error {
		close(entered)
		<-work.Done()
		cancelled <- work.Err()
		return work.Err()
	}}
	done := make(chan error, 1)
	go func() {
		done <- worker.Run(ctx, pool, "w1", handlers,
			worker.Options{Once: true, Queue: q, Heartbeat: 20 * time.Millisecond})
	}()
	<-entered
	if e := q.Cancel(ctx, org, j.JobID); e != nil {
		t.Fatal(e)
	}
	select {
	case e := <-cancelled:
		if !errors.Is(e, context.Canceled) {
			t.Fatalf("handler saw %v", e)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("the heartbeat never noticed the lost lease")
	}
	if e := <-done; e != nil {
		t.Fatal(e)
	}
	row, e := q.Get(ctx, org, j.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if row.State != jobs.StateCancelled {
		t.Fatalf("a fenced worker overwrote the state: %+v", row)
	}
}

func TestUnknownKindIsNotLeased(t *testing.T) {
	q, pool := setup(t)
	ctx := context.Background()
	j := enqueue(t, q, pool, "unregistered")
	handlers := map[string]worker.Handler{"demo": func(context.Context, *worker.Task) error { return nil }}
	if e := worker.Run(ctx, pool, "w1", handlers, worker.Options{Once: true, Queue: q}); e != nil {
		t.Fatal(e)
	}
	row, e := q.Get(ctx, org, j.JobID)
	if e != nil {
		t.Fatal(e)
	}
	if row.State != jobs.StateQueued || row.Attempts != 0 {
		t.Fatalf("a worker without the handler touched the job: %+v", row)
	}
}
