package importer

// The one thing another module may ask to happen after an import finished.
//
// `import.parse` is the only code that knows an import actually landed, and
// other modules have work that only makes sense then — today, proposing an
// organisation scope map (ADR-0051). The obvious shortcut is for this package
// to enqueue that job itself, which would make the import module depend on the
// review module's job kind, payload shape and configuration rules. The port
// inverts it: this package declares the moment, the other package decides what
// to do with it, and `package main` introduces them.
//
// It is one method with no return value beyond an error on purpose. A follow-up
// is not allowed to change what the import did — the import has already
// committed — and it is not allowed to fail the parse job either, because an
// import that succeeded did succeed. The worker logs the error into its result
// and moves on.

import "context"

// ImportFollowUp is notified after an import's catalog transaction committed.
//
// `state` is the import's own terminal state, `ready` or `partial`. A partial
// import is still an import: some files failed, the rest are in the catalog,
// and the structure they form is exactly as worth mapping as a complete one.
type ImportFollowUp interface {
	AfterImport(ctx context.Context, orgID, repoID, importID, state string) error
}

// SetFollowUp wires the port. A worker with none does nothing extra, which is
// what every existing deployment and every existing test gets.
func (w *ParseWorker) SetFollowUp(f ImportFollowUp) { w.followUp = f }

// notifyFollowUp runs the hook and returns its error for the job's result. It
// never returns the error to the caller as a job failure: see the package note
// above.
func (w *ParseWorker) notifyFollowUp(ctx context.Context, orgID, repoID, importID, state string) string {
	if w.followUp == nil {
		return ""
	}
	if e := w.followUp.AfterImport(ctx, orgID, repoID, importID, state); e != nil {
		return e.Error()
	}
	return ""
}
