// Package worker runs leased jobs. It owns the loop, the heartbeat and the
// terminal write; a handler only does the work and may store checkpoints.
//
// The heartbeat is also the fence detector: when the lease is lost (expired and
// re-leased elsewhere, or the job cancelled), the heartbeat sees ErrFenced and
// cancels the handler's context, so a stale worker stops instead of writing.
package worker

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"sort"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
)

// Task is the handler's view of one leased job.
type Task struct {
	Job   *jobs.Job
	queue *jobs.Queue
	// Result is written to the job row when the handler returns nil.
	Result json.RawMessage
}

// Checkpoint stores resume state and extends the lease.
func (t *Task) Checkpoint(ctx context.Context, data json.RawMessage) error {
	return t.queue.Checkpoint(ctx, t.Job.JobID, t.Job.Generation, data)
}

// Cost records accumulated generator cost.
func (t *Task) Cost(ctx context.Context, cost json.RawMessage) error {
	return t.queue.Cost(ctx, t.Job.JobID, t.Job.Generation, cost)
}

// Handler runs one job of one kind.
type Handler func(ctx context.Context, t *Task) error

// skipError ends a job as deliberately not done.
type skipError struct{ reason string }

func (e skipError) Error() string { return e.reason }

// Skipped marks the job skipped rather than failed, for a job that had nothing
// to do (the brief's `llm_not_configured`, for example).
func Skipped(reason string) error { return skipError{reason} }

// permanentError ends a job without further attempts.
type permanentError struct{ err error }

func (e permanentError) Error() string { return e.err.Error() }
func (e permanentError) Unwrap() error { return e.err }

// Permanent marks a failure as not worth retrying.
func Permanent(err error) error { return permanentError{err} }

// Options tunes the loop. Zero values are replaced by the documented defaults.
type Options struct {
	Once      bool          // process at most one job, then return
	Poll      time.Duration // idle sleep between empty leases (default 1s)
	Lease     time.Duration // lease length (default jobs.DefaultLease)
	Heartbeat time.Duration // heartbeat period (default lease/3, never above 10s)
	Queue     *jobs.Queue   // override, mainly for tests
	Logger    *slog.Logger
}

func (o Options) heartbeat(lease time.Duration) time.Duration {
	if o.Heartbeat > 0 {
		return o.Heartbeat
	}
	d := lease / 3
	if d > 10*time.Second {
		d = 10 * time.Second
	}
	if d < 50*time.Millisecond {
		d = 50 * time.Millisecond
	}
	return d
}

// Run leases and executes jobs until the context ends, or — with Once — until
// one job has been processed or the queue is empty.
func Run(ctx context.Context, pool *pgxpool.Pool, workerID string, handlers map[string]Handler, opts Options) error {
	if workerID == "" {
		return fmt.Errorf("worker_id_required")
	}
	if len(handlers) == 0 && !opts.Once {
		return fmt.Errorf("no_job_handlers_registered")
	}
	q := opts.Queue
	if q == nil {
		q = jobs.New(pool)
	}
	lease := opts.Lease
	if lease <= 0 {
		lease = q.LeaseTTL
	}
	poll := opts.Poll
	if poll <= 0 {
		poll = time.Second
	}
	log := opts.Logger
	if log == nil {
		log = slog.Default()
	}
	kinds := make([]string, 0, len(handlers))
	for kind := range handlers {
		kinds = append(kinds, kind)
	}
	sort.Strings(kinds)
	for {
		if e := ctx.Err(); e != nil {
			return nil
		}
		job, e := q.Lease(ctx, workerID, kinds, lease)
		if e != nil {
			if ctx.Err() != nil {
				return nil
			}
			return e
		}
		if job == nil {
			if opts.Once {
				return nil
			}
			select {
			case <-ctx.Done():
				return nil
			case <-time.After(poll):
			}
			continue
		}
		run(ctx, q, job, handlers[job.Kind], opts.heartbeat(lease), log)
		if opts.Once {
			return nil
		}
	}
}

func run(ctx context.Context, q *jobs.Queue, job *jobs.Job, handler Handler, beat time.Duration, log *slog.Logger) {
	// Allowlist logging: identifiers and state only, never payloads.
	log.Info("job_leased", "job_id", job.JobID, "kind", job.Kind, "attempt", job.Attempts,
		"generation", job.Generation)
	if handler == nil {
		_ = q.Fail(ctx, job.JobID, job.Generation, "no_handler_for_kind", false)
		return
	}
	work, stop := context.WithCancel(ctx)
	defer stop()
	beats := make(chan struct{})
	go func() {
		defer close(beats)
		ticker := time.NewTicker(beat)
		defer ticker.Stop()
		for {
			select {
			case <-work.Done():
				return
			case <-ticker.C:
				// The heartbeat runs on the parent context so a cancelled
				// handler still stops cleanly rather than looping.
				if e := q.Heartbeat(ctx, job.JobID, job.Generation); e != nil {
					if errors.Is(e, jobs.ErrFenced) || errors.Is(e, jobs.ErrNotFound) {
						log.Warn("job_fenced", "job_id", job.JobID, "kind", job.Kind)
						stop()
						return
					}
					log.Warn("job_heartbeat_failed", "job_id", job.JobID, "error", e.Error())
				}
			}
		}
	}()
	task := &Task{Job: job, queue: q}
	err := handler(work, task)
	stop()
	<-beats
	// Terminal writes use the parent context: the work context is already
	// cancelled by the deferred stop and would reject the write.
	finish(ctx, q, job, task, err, log)
}

func finish(ctx context.Context, q *jobs.Queue, job *jobs.Job, task *Task, err error, log *slog.Logger) {
	var write error
	switch {
	case err == nil:
		write = q.Complete(ctx, job.JobID, job.Generation, task.Result)
	case errors.As(err, new(skipError)):
		write = q.Skip(ctx, job.JobID, job.Generation, err.Error())
	case errors.As(err, new(permanentError)):
		write = q.Fail(ctx, job.JobID, job.Generation, err.Error(), false)
	default:
		write = q.Fail(ctx, job.JobID, job.Generation, err.Error(), true)
	}
	if write != nil && !errors.Is(write, jobs.ErrFenced) {
		log.Error("job_write_failed", "job_id", job.JobID, "error", write.Error())
	}
	log.Info("job_finished", "job_id", job.JobID, "kind", job.Kind,
		"outcome", outcome(err), "fenced", errors.Is(write, jobs.ErrFenced))
}

func outcome(err error) string {
	switch {
	case err == nil:
		return "done"
	case errors.As(err, new(skipError)):
		return "skipped"
	default:
		return "failed"
	}
}
