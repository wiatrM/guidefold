package main

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/schema"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// RegisterHandlers is the worker's job registry: it maps a `gfm.jobs.kind` to
// the function that runs it. `guidefold-search worker` leases only the kinds
// listed here, so a job whose module is not deployed — `publish.build` today —
// stays queued rather than failing.
//
// A handler receives the leased job and may store checkpoints through the task;
// the runner owns the lease, the heartbeat and the terminal write. Return nil
// for success, worker.Skipped(reason) for "nothing to do", worker.Permanent(err)
// for a failure that retrying cannot fix, and any other error to be retried
// until max_attempts.
//
// The import parser is the reason the worker image carries Python and the API
// image does not: it runs the repository's own trusted builder over a tree it
// materialised from blobs, and never a script from the imported repository. The
// publication job runs the same builder over the same kind of tree.
//
// A module whose configuration is broken — a generator that names an unknown
// provider, a missing API key file — must not silently disappear from the
// registry: its jobs would stay queued for ever with nothing saying why. The
// error is returned, and the worker refuses to start.
func RegisterHandlers(pool *pgxpool.Pool, caps schema.Capabilities, policySHA string) (map[string]worker.Handler, error) {
	handlers := map[string]worker.Handler{}
	blobs := importer.NewBlobStore(pool)
	parser := importer.NewParseWorker(pool, blobs, importer.NewPythonBuilder(), "")
	for kind, h := range parser.Handlers() {
		handlers[kind] = h
	}
	generate, e := review.NewGenerateWorker(pool, blobs)
	if e != nil {
		return nil, e
	}
	for kind, h := range generate.Handlers() {
		handlers[kind] = h
	}
	publisher := &snapshotPublisher{PolicySHA: policySHA, Caps: caps}
	build := review.NewPublishWorker(pool, blobs, importer.NewPythonBuilder(), publisher, "")
	for kind, h := range build.Handlers() {
		handlers[kind] = h
	}
	// The webhook persists a durable ascend intent even when the GitHub App REST
	// credentials are intentionally absent from a development worker. Keeping
	// the job visible prevents a delivery from being reported as complete while
	// giving operators an explicit terminal reason until the connector is enabled.
	handlers["ascend.run"] = func(_ context.Context, task *worker.Task) error {
		if len(task.Job.Payload) == 0 {
			return worker.Permanent(fmt.Errorf("ascend.run payload is empty"))
		}
		var event map[string]any
		if err := json.Unmarshal(task.Job.Payload, &event); err != nil {
			return worker.Permanent(fmt.Errorf("decode ascend.run payload: %w", err))
		}
		return worker.Skipped("github_app_connector_not_configured")
	}
	return handlers, nil
}
