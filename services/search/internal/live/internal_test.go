package live

// Internal tests: the package's own unexported rules, tested directly rather
// than through the HTTP surface api_test.go (package live_test) already
// covers. The precedent is importer's parse_internal_test.go.

import (
	"context"
	"testing"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/testdb"
)

// terminalState is a pure function, so its precedence rule — the one the task
// calls non-negotiable — is cheapest pinned directly, with no HTTP surface or
// database in the way.
func TestTerminalStatePrecedence(t *testing.T) {
	cases := []struct {
		name                           string
		cancelled, runFailed           bool
		targets, done, failed, skipped int
		want                           string
	}{
		{"cancelled outranks failed targets", true, false, 3, 0, 3, 0, StateCancelled},
		{"a run-level failure outranks healthy targets", false, true, 2, 2, 0, 0, StateFailed},
		{"one failed target is partial, never success", false, false, 3, 2, 1, 0, StatePartial},
		{"one skipped target is partial, never success", false, false, 3, 2, 0, 1, StatePartial},
		{"every target done is success", false, false, 3, 3, 0, 0, StateSucceeded},
		{"no target ever ran is partial, not a vacuous success", false, false, 0, 0, 0, 0, StatePartial},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := terminalState(c.cancelled, c.runFailed, c.targets, c.done, c.failed, c.skipped)
			if got != c.want {
				t.Fatalf("terminalState(%v,%v,%d,%d,%d,%d) = %q, want %q",
					c.cancelled, c.runFailed, c.targets, c.done, c.failed, c.skipped, got, c.want)
			}
		})
	}
}

// The 20,000-event cap (§5.5a) is exercised at the boundary rather than by
// inserting 20,000 rows: Append allocates the next seq from max(seq), so
// seeding one row at seq=maxEventsPerRun is the same starting point as
// 20,000 sequential appends would leave behind. Past the cap, only the two
// events that end something — repo.finished and run.finished — still get
// through; everything else is dropped.
func TestAppendDropsEverythingButFinishedPastCapAndWritesTruncationNoticeOnce(t *testing.T) {
	_, pool := testdb.Start(t)
	ctx := context.Background()
	orgID, runID := jobs.NewID(), jobs.NewID()
	if _, e := pool.Exec(ctx, `INSERT INTO gfm.orgs(org_id,slug,name) VALUES($1::uuid,$2,$2)`,
		orgID, "cap-test-"+runID[:8]); e != nil {
		t.Fatal(e)
	}
	if _, e := pool.Exec(ctx, `INSERT INTO gfm.live_runs(org_id,run_id,state,provider,model)
 VALUES($1::uuid,$2::uuid,'running','openrouter','openrouter/auto')`, orgID, runID); e != nil {
		t.Fatal(e)
	}
	if _, e := pool.Exec(ctx, `INSERT INTO gfm.live_run_events(org_id,run_id,seq,type,payload)
 VALUES($1::uuid,$2::uuid,$3,'repo.started','{}'::jsonb)`, orgID, runID, maxEventsPerRun); e != nil {
		t.Fatal(e)
	}

	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	seq, e := Append(ctx, tx, orgID, runID, "meridian/atlas", EventRepoStarted, "should be dropped", nil)
	if e != nil {
		t.Fatal(e)
	}
	if seq != 0 {
		t.Fatalf("repo.started past the cap returned seq %d, want 0 (dropped, not failure)", seq)
	}

	// The first exempt event past the cap is preceded by the truncation
	// notice, so it lands two seq past the seeded boundary, not one.
	seq, e = Append(ctx, tx, orgID, runID, "meridian/atlas", EventRepoFinished,
		"Repository meridian/atlas finished.", map[string]any{"proposals": 2})
	if e != nil {
		t.Fatal(e)
	}
	if seq != maxEventsPerRun+2 {
		t.Fatalf("repo.finished past the cap got seq %d, want %d", seq, maxEventsPerRun+2)
	}

	// A second exempt event must not write a second truncation notice: the
	// guard is a query against the log, not an in-process flag, so this is
	// the assertion that would catch a regression to the latter.
	seq, e = Append(ctx, tx, orgID, runID, "meridian/graph", EventRepoFinished,
		"Repository meridian/graph finished.", map[string]any{"proposals": 0})
	if e != nil {
		t.Fatal(e)
	}
	if seq != maxEventsPerRun+3 {
		t.Fatalf("second repo.finished got seq %d, want %d (no second truncation notice ahead of it)",
			seq, maxEventsPerRun+3)
	}

	var notices int
	if e := tx.QueryRow(ctx, `SELECT count(*) FROM gfm.live_run_events
 WHERE org_id=$1::uuid AND run_id=$2::uuid AND type=$3 AND payload->>'reason'=$4`,
		orgID, runID, EventError, ErrorLogTruncated).Scan(&notices); e != nil {
		t.Fatal(e)
	}
	if notices != 1 {
		t.Fatalf("wrote %d truncation notices, want exactly 1", notices)
	}
}

// Append requires a non-empty payload.text: it is documented as "hard to
// forget" rather than merely recommended, so an empty one must be a
// programming error the caller sees immediately, not a blank line a second
// reader of the log has to guess the meaning of.
func TestAppendRequiresNonEmptyText(t *testing.T) {
	_, pool := testdb.Start(t)
	ctx := context.Background()
	orgID, runID := jobs.NewID(), jobs.NewID()
	if _, e := pool.Exec(ctx, `INSERT INTO gfm.orgs(org_id,slug,name) VALUES($1::uuid,$2,$2)`,
		orgID, "text-test-"+runID[:8]); e != nil {
		t.Fatal(e)
	}
	if _, e := pool.Exec(ctx, `INSERT INTO gfm.live_runs(org_id,run_id,state,provider,model)
 VALUES($1::uuid,$2::uuid,'running','openrouter','openrouter/auto')`, orgID, runID); e != nil {
		t.Fatal(e)
	}
	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	if _, e := Append(ctx, tx, orgID, runID, "", EventRunStarted, "  ", nil); e == nil {
		t.Fatal("Append with blank text succeeded, want an error")
	}
}
