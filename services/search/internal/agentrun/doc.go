// Package agentrun is the worker half of the Live Agent (ADR-0046) and of
// the GitHub App's pull-request coverage report (ADR-0036 points 1a, 4a).
//
// Three job kinds live here:
//
//   - live.plan resolves which repositories one run covers, writes their
//     gfm.live_run_targets rows and enqueues one live.repo per target.
//     internal/live owns the run's own tables and API; this package only
//     ever writes what that job kind is responsible for.
//   - live.repo reads one repository's AGENTS.md and SKILL.md files through
//     internal/ghapp, calls the organisation's own model
//     (internal/model) with the run's prompt, and streams the model's
//     answer into the run's append-only event log through
//     live.Append/SetTargetState/Finish.
//   - pr.report answers one pull request: which of the organisation's
//     published rules apply to the paths it touched, and whether the model
//     thinks the diff contradicts one of them — then upserts one sticky
//     comment through ghapp and, when the diff touched a skill file,
//     enqueues ascend.run.
//
// The organisation's own model key (ADR-0045) is opened once per job,
// through internal/secrets.OpenFor, and lives only in the memory of the one
// call it authenticates. It is never placed in a job payload, a checkpoint,
// a job result, a log line or an error — every handler in this package is
// tested for exactly that.
package agentrun
