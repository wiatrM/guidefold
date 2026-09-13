package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/agentrun"
	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/schema"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
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
	// Loaded here, ahead of the generate worker, because proposal.generate
	// needs it to prefer an organisation's own stored key over this
	// deployment's key file (ADR-0045); a nil keyring is still valid and the
	// generator falls back to its file exactly as it did before this existed.
	keyring, keyringErr := secrets.LoadKeyring(os.Getenv)
	if keyringErr != nil {
		return nil, fmt.Errorf("secret keyring: %w", keyringErr)
	}
	generate, e := review.NewGenerateWorker(pool, blobs, keyring)
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

	// The Live Agent (ADR-0046) and the GitHub App's pull-request coverage
	// report (ADR-0036 points 1a, 4a). Both degrade to a named "skipped"
	// reason rather than refusing to start the worker: GITHUB_APP_ID /
	// GITHUB_APP_PRIVATE_KEY_FILE is optional per deployment (the same "a
	// module whose jobs stay queued with a stated reason, not the same as a
	// module that failed to start" distinction import.parse's own generator
	// selection draws above), and nothing about the queue or the API
	// depends on it being present. live.repo no longer opens the
	// organisation's model key itself (that happens inside
	// proposal.generate, under its own preferred credential — ADR-0046
	// point 9), so GUIDEFOLD_SECRET_KEY_FILE only gates pr.report's own
	// model call now.
	gh, ghErr := ghapp.NewFromEnv(os.Getenv)
	if ghErr != nil && !errors.Is(ghErr, ghapp.ErrNotConfigured) {
		return nil, fmt.Errorf("github app configuration: %w", ghErr)
	}
	var ghCfg ghapp.Config
	if gh != nil {
		if cfg, cfgErr := ghapp.ConfigFromEnv(os.Getenv); cfgErr == nil {
			ghCfg = cfg
		}
	}
	if gh == nil {
		slog.Warn("github_app_not_configured",
			"detail", "GITHUB_APP_ID/GITHUB_APP_PRIVATE_KEY_FILE unset; live.repo and pr.report end skipped")
	}
	if keyring == nil {
		slog.Warn("secret_keyring_absent",
			"detail", "GUIDEFOLD_SECRET_KEY_FILE unset; pr.report ends skipped for want of a model key")
	}

	livePlan := agentrun.NewLivePlanWorker(pool)
	for kind, h := range livePlan.Handlers() {
		handlers[kind] = h
	}
	// liveRepo's own consolidation step runs through the same review.Service
	// the API mounts, over internal/review's exported GenerateProposals seam
	// (API-CONTRACT §8, ADR-0046 point 9), so a live run's proposals land
	// under the same recipe and cache key an HTTP-driven
	// proposals:generate call would.
	reviewer, e := review.New(pool, blobs)
	if e != nil {
		return nil, e
	}
	liveRepo := agentrun.NewLiveRepoWorker(pool, gh, importer.New(pool, blobs)).
		WithProposalGenerator(agentrun.NewReviewProposalGenerator(pool, reviewer))
	for kind, h := range liveRepo.Handlers() {
		handlers[kind] = h
	}
	prReport := agentrun.NewPRReportWorker(pool, gh, ghCfg, keyring, os.Getenv)
	for kind, h := range prReport.Handlers() {
		handlers[kind] = h
	}
	// github.sync_repositories reconciles gfm.repos for a linked GitHub App
	// installation (ADR-0034's explicit link, API-CONTRACT §4.7/§8). Same
	// "skipped" degradation as pr.report/live.repo when gh is nil.
	githubSync := agentrun.NewGitHubSyncWorker(pool, gh)
	for kind, h := range githubSync.Handlers() {
		handlers[kind] = h
	}

	return handlers, nil
}
