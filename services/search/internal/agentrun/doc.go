// Package agentrun is the worker half of the Live Agent (ADR-0046) and of
// the GitHub App's pull-request coverage report (ADR-0036 points 1a, 4a).
//
// Three job kinds live here:
//
//   - live.plan resolves which repositories one run covers, writes their
//     gfm.live_run_targets rows and enqueues one live.repo per target.
//     internal/live owns the run's own tables and API; this package only
//     ever writes what that job kind is responsible for.
//   - live.repo reads one repository's guidefold.yaml, AGENTS.md and
//     SKILL.md files through internal/ghapp — a repository with no
//     guidefold.yaml declares no scope hierarchy for import.parse to build
//     from, so its target ends skipped with guidefold_yaml_missing before
//     anything is imported — builds an import from the rest through
//     internal/importer's own in-process seam
//     (CreateImport/PutBlob/FinalizeImport), waits for import.parse to
//     refresh the catalog, then enqueues and waits for proposal.generate
//     (kind consolidation) through internal/review's own GenerateProposals
//     seam. It never calls a model itself: that happens inside
//     proposal.generate, under the organisation's own key (ADR-0046 point
//     9). One job owns one repository end to end, polling the child job it
//     is waiting on and renewing its own lease as it goes; every transition
//     is appended to the run's log through
//     live.Append/SetTargetPhase/SetTargetState.
//   - pr.report answers one pull request: which of the organisation's
//     published rules apply to the paths it touched, and whether the model
//     thinks the diff contradicts one of them — then upserts one sticky
//     comment through ghapp and, when the diff touched a skill file,
//     enqueues ascend.run. This is the one job kind here that still calls a
//     model directly, and still opens the organisation's key through
//     internal/secrets.OpenFor for exactly the one call it authenticates:
//     never placed in a job payload, a checkpoint, a job result, a log line
//     or an error.
package agentrun
