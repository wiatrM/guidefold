package ghapp

import "errors"

// These are the errors a caller is expected to branch on — for example to
// turn ErrTreeTruncated into `live_run` naming a repository it could not see
// completely, rather than a generic failure. Everything else this package
// returns is wrapped with fmt.Errorf and carries no promise about its text
// or its identity: a caller that needs to branch on something else is a
// caller this package is missing a named error for, not one that should
// start matching strings.
var (
	// ErrNotConfigured means GITHUB_APP_ID or GITHUB_APP_PRIVATE_KEY_FILE is
	// unset, or the key file does not hold a parseable RSA private key. A
	// deployment without the App configured is expected (ADR-0036 point 5,
	// ADR-0046 consequences): the caller turns this into a named "skipped"
	// reason, not a panic or a retry loop.
	ErrNotConfigured = errors.New("ghapp: GitHub App is not configured")

	// ErrInstallationNotFound is GitHub's 404 on the installation-token
	// exchange: the installation was deleted or suspended on GitHub's side
	// after Guidefold's own gfm.github_installations row was written.
	ErrInstallationNotFound = errors.New("ghapp: GitHub installation not found")

	// ErrTreeTruncated means the git trees API set "truncated": true. A short
	// list that looks complete is worse than a job that says it could not see
	// everything (ADR-0046 point 3) — this error exists so a caller cannot
	// mistake a partial tree for the whole repository.
	ErrTreeTruncated = errors.New("ghapp: repository tree came back truncated")

	// ErrFileTooLarge means the file exceeds MaxFileBytes. The alternative —
	// silently truncating — would hand a caller a SKILL.md that parses as
	// something other than what is actually in the repository.
	ErrFileTooLarge = errors.New("ghapp: file exceeds the read size ceiling")

	// ErrPathNotAllowed means CreateBranchCommit was asked to write a path
	// that is neither AGENTS.md nor under a .agents/skills directory. This
	// App proposes skill files and nothing else (ADR-0036 point 1a); the rule
	// lives here, checked before any request leaves this package, rather than
	// in a comment a future caller could read past.
	ErrPathNotAllowed = errors.New("ghapp: write path is outside AGENTS.md and .agents/skills")

	// ErrPermissionRefused is GitHub's 403 on a write call: the installation
	// exists but was not granted the permission (contents, pull_requests,
	// issues write) the operation needs. Distinguished from a plain failure
	// because the fix is different — the organisation must re-approve the
	// App's permissions — and a caller should say that, not retry.
	ErrPermissionRefused = errors.New("ghapp: GitHub refused the request as a missing permission")
)
