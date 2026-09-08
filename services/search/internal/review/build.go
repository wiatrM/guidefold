package review

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// PublishPayloadVersion labels the publish.build job's payload.
const PublishPayloadVersion = "publish.build-1"

// Publisher writes a built bundle into the serving catalog inside the caller's
// transaction.
//
// It is a port because the snapshot writer is the operator `publish`
// subcommand's own code: one implementation writes `gf.snapshots`, `gf.skills`,
// the router index and `gf.heads`, and the review module must not grow a second
// one that could disagree with the ranker (ADR-0028, module-boundaries-go).
//
// Publish must not activate the head until the caller says so: validation runs
// first, and a failed validation leaves the previous head serving.
type Publisher interface {
	Publish(ctx context.Context, tx pgx.Tx, in PublishInput) (PublishResult, error)
}

// PublishInput is one build ready to be stored.
type PublishInput struct {
	Tenant   string
	Repo     string
	Bundle   []byte
	Activate bool
}

// PublishResult names what was written.
type PublishResult struct {
	SnapshotID string
	Cards      int
	CLISHA     string
	Revision   string
}

// PublishWorker runs publish.build.
type PublishWorker struct {
	pool      *pgxpool.Pool
	blobs     BlobStore
	builder   importer.Builder
	publisher Publisher
	scratch   string
}

// NewPublishWorker wires the job handler. A nil publisher means this deployment
// has no serving catalog behind it, and the job fails loudly rather than
// reporting a publication that never happened.
func NewPublishWorker(pool *pgxpool.Pool, blobs BlobStore, builder importer.Builder,
	publisher Publisher, scratch string) *PublishWorker {
	if builder == nil {
		builder = importer.NewPythonBuilder()
	}
	if scratch == "" {
		scratch = importer.ScratchDir()
	}
	return &PublishWorker{pool: pool, blobs: blobs, builder: builder, publisher: publisher,
		scratch: scratch}
}

// Handlers maps the job kind this worker runs.
func (w *PublishWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{KindPublish: w.Run}
}

// publishPayload is the publish.build job contract (API-CONTRACT §8).
type publishPayload struct {
	SchemaVersion  string `json:"schema_version"`
	OrgID          string `json:"org_id"`
	RepoID         string `json:"repo_id"`
	ImportID       string `json:"import_id"`
	ManifestDigest string `json:"manifest_digest"`
	Commit         string `json:"commit"`
}

// Run builds and publishes one import.
//
// The order is the whole point. Materialise → build → validate → write, and the
// head only moves after validation passed. A build whose graph has a cycle or
// whose package is missing a required resource records its reasons in
// `gfm.publications.validation` and leaves the previous snapshot serving, so a
// bad import degrades nothing (U5, U2.6).
func (w *PublishWorker) Run(ctx context.Context, t *worker.Task) error {
	var payload publishPayload
	if e := json.Unmarshal(t.Job.Payload, &payload); e != nil {
		return worker.Permanent(fmt.Errorf("decode publish.build payload: %w", e))
	}
	// `finalize` writes this job with the import.parse payload version, because
	// both carry the same identity fields; either label is accepted, anything
	// else is refused rather than guessed.
	if payload.SchemaVersion != PublishPayloadVersion && payload.SchemaVersion != importer.PayloadVersion {
		return worker.Permanent(fmt.Errorf("unsupported payload schema_version %q", payload.SchemaVersion))
	}
	orgID, repoID, importID := t.Job.OrgID, t.Job.RepoID, t.Job.ImportID
	if payload.OrgID != orgID || payload.RepoID != repoID || payload.ImportID != importID {
		return worker.Permanent(errors.New("publish.build payload does not match its job row"))
	}
	if w.publisher == nil {
		return worker.Permanent(errors.New("no snapshot publisher is configured"))
	}
	state, commit, e := w.importState(ctx, orgID, repoID, importID)
	if e != nil {
		return e
	}
	switch state {
	case importer.StateCancelled:
		return worker.Skipped("import_cancelled")
	case importer.StateFailed:
		return worker.Skipped("import_failed")
	case importer.StateReady:
	case importer.StatePartial:
		// A partial import is a *known incomplete* catalog: one or more files
		// the repository holds could not be parsed. Its skills are visible in
		// the management catalog immediately, which is what U2.1 promises — but
		// activating a snapshot that is missing skills would silently change
		// what every agent in the organisation reads. The publication fails with
		// the reason, the previous head keeps serving, and an owner fixes the
		// file and imports again.
		publicationID, e := w.beginPublication(ctx, t, orgID, repoID, importID, commit)
		if e != nil {
			return e
		}
		failed, e := w.failedFiles(ctx, orgID, importID)
		if e != nil {
			return e
		}
		return w.fail(ctx, t, publicationID, "import_partial",
			Findings{{Code: "import_partial",
				Message: "the import could not parse every file it carried",
				Missing: failed}})
	default:
		// The parse has not finished. Retrying is right: the two jobs are
		// queued together and the parser may still be running.
		return fmt.Errorf("import %s is %s, not ready to publish", importID, state)
	}
	if commit == "" {
		commit = payload.ManifestDigest
	}

	publicationID, e := w.beginPublication(ctx, t, orgID, repoID, importID, commit)
	if e != nil {
		return e
	}

	files, e := w.publishable(ctx, orgID, repoID, importID)
	if e != nil {
		return e
	}
	if len(files) == 0 {
		return w.fail(ctx, t, publicationID, "no_publishable_files", nil)
	}
	dir := filepath.Join(w.scratch, orgID, importID, "publish")
	tree := filepath.Join(dir, "tree")
	if e := w.materialise(ctx, orgID, tree, files); e != nil {
		return w.fail(ctx, t, publicationID, e.Error(), nil)
	}
	snapshot, inventory, buildErr := w.builder.Build(ctx, tree, repoID, commit, dir)
	if buildErr != nil {
		return w.fail(ctx, t, publicationID, lastLine(buildErr.Error()), nil)
	}
	bundle, e := os.ReadFile(filepath.Join(dir, "snapshot.json"))
	if e != nil {
		return fmt.Errorf("read built snapshot: %w", e)
	}

	// Validation before the transaction that could move the head, over the
	// graph the *build* produced rather than the one the tables hold.
	nodes, known, e := w.builtNodes(ctx, orgID, repoID, inventory)
	if e != nil {
		return e
	}
	owners, e := w.scopeOwners(ctx, orgID, repoID)
	if e != nil {
		return e
	}
	findings := ValidateGraph(nodes, known, owners)
	if len(findings) > 0 {
		return w.fail(ctx, t, publicationID, findings[0].Code, findings)
	}

	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return fmt.Errorf("open publication transaction: %w", e)
	}
	defer tx.Rollback(ctx)
	if e := fence(ctx, tx, t); e != nil {
		return e
	}
	result, e := w.publisher.Publish(ctx, tx, PublishInput{Tenant: orgID, Repo: repoID,
		Bundle: bundle, Activate: true})
	if e != nil {
		// A bundle the catalog refuses is a failed publication, not a crash.
		_ = tx.Rollback(ctx)
		return w.fail(ctx, t, publicationID, lastLine(e.Error()), findings)
	}
	// The same tree builds the same snapshot. When an earlier publication
	// already holds it, this run adopts that row rather than recording a second
	// one for one immutable snapshot: a snapshot has one history, not one per
	// import that happened to rebuild it.
	var existing string
	e = tx.QueryRow(ctx, `SELECT publication_id::text FROM gfm.publications
 WHERE org_id=$1::uuid AND repo_id=$2 AND snapshot_id=$3`, orgID, repoID, result.SnapshotID).
		Scan(&existing)
	if e != nil && !errors.Is(e, pgx.ErrNoRows) {
		return fmt.Errorf("read publication of %s: %w", result.SnapshotID, e)
	}
	if existing != "" && existing != publicationID {
		if _, e := tx.Exec(ctx, `DELETE FROM gfm.publications
 WHERE org_id=$1::uuid AND publication_id=$2::uuid AND snapshot_id IS NULL`,
			orgID, publicationID); e != nil {
			return fmt.Errorf("release duplicate publication: %w", e)
		}
		publicationID = existing
		if _, e := tx.Exec(ctx, `UPDATE gfm.publications SET import_id=$3::uuid,job_id=$4::uuid
 WHERE org_id=$1::uuid AND publication_id=$2::uuid`,
			orgID, publicationID, nullable(importID), t.Job.JobID); e != nil {
			return fmt.Errorf("adopt publication: %w", e)
		}
	}
	if _, e := tx.Exec(ctx, `UPDATE gfm.publications SET state='active',snapshot_id=$3,
 n_skills=$4,builder_sha256=$5,commit=$6,validation=$7::jsonb,error=NULL,
 activated_at=now(),updated_at=now()
 WHERE org_id=$1::uuid AND publication_id=$2::uuid`,
		orgID, publicationID, result.SnapshotID, result.Cards, snapshot.SHA256, commit,
		string(mustJSON(map[string]any{"ok": true, "findings": []any{}}))); e != nil {
		return fmt.Errorf("record publication: %w", e)
	}
	if _, e := tx.Exec(ctx, `UPDATE gfm.publications SET state='superseded',updated_at=now()
 WHERE org_id=$1::uuid AND repo_id=$2 AND state='active' AND publication_id<>$3::uuid`,
		orgID, repoID, publicationID); e != nil {
		return fmt.Errorf("supersede publications: %w", e)
	}
	published, e := w.markPublished(ctx, tx, orgID, repoID, result.SnapshotID, inventory)
	if e != nil {
		return e
	}
	landed, e := w.settleExports(ctx, tx, orgID, repoID, importID)
	if e != nil {
		return e
	}
	if e := mgmt.Audit(ctx, tx, orgID, "worker", "publication.active",
		"snapshot:"+result.SnapshotID, commit, t.Job.JobID); e != nil {
		return e
	}
	if e := tx.Commit(ctx); e != nil {
		return fmt.Errorf("commit publication: %w", e)
	}
	t.Result = mustJSON(map[string]any{"snapshot_id": result.SnapshotID, "cards": result.Cards,
		"skills_published": published, "exports_published": landed,
		"builder_sha256": snapshot.SHA256, "publication_id": publicationID})
	return nil
}

// beginPublication creates or reuses this job's publication row. Re-running the
// same job reuses it, so a restart never leaves two rows claiming one build.
func (w *PublishWorker) beginPublication(ctx context.Context, t *worker.Task,
	orgID, repoID, importID, commit string) (string, error) {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return "", e
	}
	defer tx.Rollback(ctx)
	if e := fence(ctx, tx, t); e != nil {
		return "", e
	}
	var id string
	e = tx.QueryRow(ctx, `SELECT publication_id::text FROM gfm.publications
 WHERE org_id=$1::uuid AND job_id=$2::uuid`, orgID, t.Job.JobID).Scan(&id)
	if errors.Is(e, pgx.ErrNoRows) {
		id = newID()
		if _, e := tx.Exec(ctx, `INSERT INTO gfm.publications
 (org_id,publication_id,repo_id,import_id,job_id,state,commit)
 VALUES($1::uuid,$2::uuid,$3,$4::uuid,$5::uuid,'building',$6)`,
			orgID, id, repoID, nullable(importID), t.Job.JobID, nullable(commit)); e != nil {
			return "", fmt.Errorf("open publication: %w", e)
		}
	} else if e != nil {
		return "", e
	} else if _, e := tx.Exec(ctx, `UPDATE gfm.publications SET state='building',error=NULL,
 updated_at=now() WHERE org_id=$1::uuid AND publication_id=$2::uuid`, orgID, id); e != nil {
		return "", e
	}
	return id, tx.Commit(ctx)
}

// fail records why a build did not publish and leaves the head alone.
func (w *PublishWorker) fail(ctx context.Context, t *worker.Task, publicationID, reason string,
	findings Findings) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	if e := fence(ctx, tx, t); e != nil {
		return e
	}
	if findings == nil {
		findings = Findings{}
	}
	validation := map[string]any{"ok": false, "findings": findings}
	if _, e := tx.Exec(ctx, `UPDATE gfm.publications SET state='failed',error=$3,
 validation=$4::jsonb,updated_at=now()
 WHERE org_id=$1::uuid AND publication_id=$2::uuid`,
		t.Job.OrgID, publicationID, reason, string(mustJSON(validation))); e != nil {
		return e
	}
	if e := mgmt.Audit(ctx, tx, t.Job.OrgID, "worker", "publication.failed",
		"publication:"+publicationID, reason, t.Job.JobID); e != nil {
		return e
	}
	if e := tx.Commit(ctx); e != nil {
		return e
	}
	// Permanent: a graph cycle or a missing resource is not fixed by retrying
	// the same bytes. The previous snapshot keeps serving.
	return worker.Permanent(errors.New(reason))
}

// failedFiles names the paths a partial import could not parse, so the failed
// publication says what is missing rather than only that something is.
func (w *PublishWorker) failedFiles(ctx context.Context, orgID, importID string) ([]string, error) {
	rows, e := w.pool.Query(ctx, `SELECT path FROM gfm.import_files
 WHERE org_id=$1::uuid AND import_id=$2::uuid AND status='failed' ORDER BY path LIMIT 50`,
		orgID, importID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var path string
		if e = rows.Scan(&path); e != nil {
			return nil, e
		}
		out = append(out, path)
	}
	return out, rows.Err()
}

func (w *PublishWorker) importState(ctx context.Context, orgID, repoID, importID string) (string, string, error) {
	var state string
	var commit *string
	e := w.pool.QueryRow(ctx, `SELECT state,commit FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2 AND import_id=$3::uuid`, orgID, repoID, importID).
		Scan(&state, &commit)
	if errors.Is(e, pgx.ErrNoRows) {
		return "", "", worker.Permanent(fmt.Errorf("import %s is not in organisation %s", importID, orgID))
	}
	if e != nil {
		return "", "", e
	}
	return state, str(commit), nil
}

// publishFile is one file of the tree the builder will read.
type publishFile struct {
	Path   string
	SHA256 string
	Mode   string
}

// publishable selects what may go into a snapshot.
//
// Only files this import accepted, and only skills whose source is still
// active. A candidate that has been approved but not committed has no file
// here, which is what makes "a draft never reaches SEARCH or USE" true by
// construction rather than by a filter someone has to remember (U2.6).
func (w *PublishWorker) publishable(ctx context.Context, orgID, repoID, importID string) ([]publishFile, error) {
	rows, e := w.pool.Query(ctx, `SELECT f.path,f.sha256,f.mode
 FROM gfm.import_files f
 LEFT JOIN gfm.skills s ON s.org_id=f.org_id AND s.repo_id=$2 AND s.path=f.path
 WHERE f.org_id=$1::uuid AND f.import_id=$3::uuid
   AND f.status='accepted' AND f.kind IN ('config','skill','resource')
   AND (f.kind<>'skill' OR (s.skill_id IS NOT NULL AND s.source_status='active'))
 ORDER BY f.path`, orgID, repoID, importID)
	if e != nil {
		return nil, fmt.Errorf("select publishable files: %w", e)
	}
	defer rows.Close()
	out := []publishFile{}
	for rows.Next() {
		var f publishFile
		if e = rows.Scan(&f.Path, &f.SHA256, &f.Mode); e != nil {
			return nil, e
		}
		out = append(out, f)
	}
	return out, rows.Err()
}

// materialise writes the selected blobs into a private tree. Every path is
// re-validated: a manifest is client input, and this check is the only thing
// between it and the worker's filesystem.
func (w *PublishWorker) materialise(ctx context.Context, orgID, tree string, files []publishFile) error {
	if e := os.RemoveAll(tree); e != nil {
		return fmt.Errorf("clear publication tree: %w", e)
	}
	if e := os.MkdirAll(tree, 0o700); e != nil {
		return fmt.Errorf("create publication tree: %w", e)
	}
	root, e := filepath.Abs(tree)
	if e != nil {
		return fmt.Errorf("resolve publication tree: %w", e)
	}
	for _, f := range files {
		target, e := safeJoin(root, f.Path)
		if e != nil {
			return e
		}
		if e := os.MkdirAll(filepath.Dir(target), 0o700); e != nil {
			return fmt.Errorf("create %s: %w", filepath.Dir(f.Path), e)
		}
		data, e := w.blobs.Get(ctx, orgID, f.SHA256)
		if e != nil {
			return fmt.Errorf("materialise %s: %w", f.Path, e)
		}
		mode := os.FileMode(0o600)
		if f.Mode == "100755" {
			mode = 0o700
		}
		if e := os.WriteFile(target, data, mode); e != nil {
			return fmt.Errorf("write %s: %w", f.Path, e)
		}
	}
	return nil
}

func safeJoin(root, rel string) (string, error) {
	if rel == "" || strings.HasPrefix(rel, "/") || strings.Contains(rel, `\`) ||
		strings.ContainsRune(rel, 0) {
		return "", fmt.Errorf("unsafe path %q", rel)
	}
	for _, seg := range strings.Split(rel, "/") {
		if seg == "" || seg == "." || seg == ".." {
			return "", fmt.Errorf("unsafe path %q", rel)
		}
	}
	target := filepath.Join(root, filepath.FromSlash(rel))
	if target != root && !strings.HasPrefix(target, root+string(filepath.Separator)) {
		return "", fmt.Errorf("unsafe path %q", rel)
	}
	return target, nil
}

// builtNodes reads the graph out of the inventory the builder produced, and the
// package resources the catalog recorded for those same revisions.
func (w *PublishWorker) builtNodes(ctx context.Context, orgID, repoID string,
	inv *domain.Inventory) ([]Node, map[string]bool, error) {
	nodes := make([]Node, 0, len(inv.Skills))
	known := map[string]bool{}
	byPath := map[string]int{}
	for i := range inv.Skills {
		s := &inv.Skills[i]
		nodes = append(nodes, Node{SkillID: s.URN, Scope: s.Scope, Owner: s.OwnerOrEmpty(),
			Requires: s.Requires, Refines: s.Refines})
		known[s.URN] = true
		byPath[s.Path] = i
	}
	// A skill's identity can differ from its URN when an alias kept it across a
	// move, so the resources are read by the path the import carried.
	rows, e := w.pool.Query(ctx, `SELECT s.path,r.path,r.sha256,r.required,r.available
 FROM gfm.skills s
 JOIN gfm.skill_resources r ON r.org_id=s.org_id AND r.revision_id=s.current_revision_id
 WHERE s.org_id=$1::uuid AND s.repo_id=$2 AND s.source_status='active'`, orgID, repoID)
	if e != nil {
		return nil, nil, fmt.Errorf("read package resources: %w", e)
	}
	defer rows.Close()
	for rows.Next() {
		var skillPath string
		var r Resource
		if e = rows.Scan(&skillPath, &r.Path, &r.SHA256, &r.Required, &r.Available); e != nil {
			return nil, nil, e
		}
		if i, ok := byPath[skillPath]; ok {
			nodes[i].Resources = append(nodes[i].Resources, r)
		}
	}
	if e = rows.Err(); e != nil {
		return nil, nil, e
	}
	// Also accept the identities the catalog holds, so an aliased skill's
	// dependants do not read as missing.
	ids, e := w.pool.Query(ctx, `SELECT skill_id FROM gfm.skills
 WHERE org_id=$1::uuid AND repo_id=$2 AND source_status='active'`, orgID, repoID)
	if e != nil {
		return nil, nil, e
	}
	defer ids.Close()
	for ids.Next() {
		var id string
		if e = ids.Scan(&id); e != nil {
			return nil, nil, e
		}
		known[id] = true
	}
	return nodes, known, ids.Err()
}

func (w *PublishWorker) scopeOwners(ctx context.Context, orgID, repoID string) (map[string]string, error) {
	rows, e := w.pool.Query(ctx, `SELECT scope,COALESCE(owner,'') FROM gfm.scopes
 WHERE org_id=$1::uuid AND repo_id=$2`, orgID, repoID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := map[string]string{}
	for rows.Next() {
		var scope, owner string
		if e = rows.Scan(&scope, &owner); e != nil {
			return nil, e
		}
		out[scope] = owner
	}
	return out, rows.Err()
}

// markPublished records which revision of which skill is now serving, and in
// which snapshot. USE 1.2 answers a revision's resource list from exactly this
// pair, so a resource list can never come from an unpublished revision.
//
// Publishing does not answer a question the owner was asked. `finalize` queues
// import.parse and publish.build for the same import, so the build runs right
// behind the drift pass that raised `needs_review`; flipping every skill in the
// snapshot to `published` would erase that flag before anybody saw it (ACT-01).
// The rule is therefore split in two: the *serving* pair is refreshed for every
// skill the new snapshot carries — Git is canonical and the snapshot really does
// serve them — while the *status* only advances from a state that has no open
// question. `needs_review` and `archived` keep their status until an owner
// decides the queue item (API-CONTRACT §6).
var publishableStatuses = []string{"draft", "approved_for_export", "awaiting_git", "published"}

func (w *PublishWorker) markPublished(ctx context.Context, tx pgx.Tx, orgID, repoID, snapshotID string,
	inv *domain.Inventory) (int, error) {
	paths := make([]string, 0, len(inv.Skills))
	for i := range inv.Skills {
		paths = append(paths, inv.Skills[i].Path)
	}
	if len(paths) == 0 {
		return 0, nil
	}
	tag, e := tx.Exec(ctx, `UPDATE gfm.skills
 SET publication_status='published',published_revision_id=current_revision_id,
     published_snapshot_id=$3,updated_at=now()
 WHERE org_id=$1::uuid AND repo_id=$2 AND source_status='active' AND path=ANY($4::text[])
   AND publication_status=ANY($5::text[])`,
		orgID, repoID, snapshotID, paths, publishableStatuses)
	if e != nil {
		return 0, fmt.Errorf("mark skills published: %w", e)
	}
	// A skill under review is still served by this snapshot, so its serving pair
	// has to move with it. Only the flag stays where the owner's queue put it.
	if _, e := tx.Exec(ctx, `UPDATE gfm.skills
 SET published_revision_id=current_revision_id,published_snapshot_id=$3,updated_at=now()
 WHERE org_id=$1::uuid AND repo_id=$2 AND source_status='active' AND path=ANY($4::text[])
   AND publication_status='needs_review'`,
		orgID, repoID, snapshotID, paths); e != nil {
		return 0, fmt.Errorf("refresh the serving revision of the skills under review: %w", e)
	}
	if e := w.storeCardRevisions(ctx, tx, orgID, repoID, snapshotID); e != nil {
		return 0, e
	}
	return int(tag.RowsAffected()), nil
}

// storeCardRevisions writes the card identifier this snapshot minted for each
// serving revision back onto the catalog row.
//
// The delivery path hands a harness `gf.skills.skill_revision` and adapter
// telemetry echoes it; a judgment recorded in the UI names the catalog revision
// instead. Without this pair the same skill occupies two rows of the usage
// report under two identifiers, which is exactly what the acceptance run
// recorded (U6-3). Reading `gf.skills` here is a read of what this same
// transaction just wrote through the publisher port, not a second writer.
func (w *PublishWorker) storeCardRevisions(ctx context.Context, tx pgx.Tx, orgID, repoID, snapshotID string) error {
	// `tenant` is text and `org_id` is uuid, so the organisation is bound twice
	// rather than once: one placeholder cannot be both types in one statement.
	if _, e := tx.Exec(ctx, `UPDATE gfm.skill_revisions r
 SET card_revision=c.skill_revision
 FROM gfm.skills s, gf.skills c
 WHERE r.org_id=$1::uuid AND s.org_id=r.org_id AND s.skill_id=r.skill_id AND s.repo_id=$2
   AND r.revision_id=s.published_revision_id
   AND c.tenant=$4 AND c.repo=$2 AND c.snapshot_id=$3 AND c.urn=r.skill_id
   AND r.card_revision IS DISTINCT FROM c.skill_revision`,
		orgID, repoID, snapshotID, orgID); e != nil {
		return fmt.Errorf("store card revisions of snapshot %s: %w", snapshotID, e)
	}
	return nil
}

// settleExports closes the loop between a patch and the repository.
//
// An export is `awaiting_git` until the exact bytes it proposed appear in an
// import. Matching on (path, sha256) is what makes "published" mean "the file
// is in the repository", rather than "somebody pressed export": a patch that
// was edited before landing does not close its proposal (U2.8).
func (w *PublishWorker) settleExports(ctx context.Context, tx pgx.Tx, orgID, repoID, importID string) (int, error) {
	rows, e := tx.Query(ctx, `SELECT e.export_id::text,e.proposal_id::text,e.files::text,
 p.target_skill_id
 FROM gfm.exports e JOIN gfm.proposals p ON p.org_id=e.org_id AND p.proposal_id=e.proposal_id
 WHERE e.org_id=$1::uuid AND p.repo_id=$2 AND p.state='awaiting_git'`, orgID, repoID)
	if e != nil {
		return 0, fmt.Errorf("read pending exports: %w", e)
	}
	type pending struct {
		proposalID string
		files      []struct {
			Path   string `json:"path"`
			SHA256 string `json:"sha256"`
		}
		skillID *string
	}
	list := []pending{}
	for rows.Next() {
		var p pending
		var exportID, filesRaw string
		if e = rows.Scan(&exportID, &p.proposalID, &filesRaw, &p.skillID); e != nil {
			rows.Close()
			return 0, e
		}
		if e := json.Unmarshal([]byte(filesRaw), &p.files); e != nil {
			continue
		}
		list = append(list, p)
	}
	rows.Close()
	if e = rows.Err(); e != nil {
		return 0, e
	}
	settled := 0
	for _, p := range list {
		if len(p.files) == 0 {
			continue
		}
		landedAll := true
		for _, f := range p.files {
			var present bool
			if e := tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gfm.import_files
 WHERE org_id=$1::uuid AND import_id=$2::uuid AND path=$3 AND sha256=$4 AND status='accepted')`,
				orgID, importID, f.Path, f.SHA256).Scan(&present); e != nil {
				return 0, e
			}
			if !present {
				landedAll = false
				break
			}
		}
		if !landedAll {
			continue
		}
		if _, e := tx.Exec(ctx, `UPDATE gfm.proposals SET state='published',updated_at=now()
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid`, orgID, p.proposalID); e != nil {
			return 0, e
		}
		if p.skillID != nil && *p.skillID != "" {
			if _, e := tx.Exec(ctx, `UPDATE gfm.skills SET publication_status='published',
 updated_at=now() WHERE org_id=$1::uuid AND skill_id=$2`, orgID, *p.skillID); e != nil {
				return 0, e
			}
		}
		if e := mgmt.Audit(ctx, tx, orgID, "worker", "proposal.published",
			"proposal:"+p.proposalID, importID, importID); e != nil {
			return 0, e
		}
		settled++
	}
	return settled, nil
}

// lastLine keeps an error's final message and drops any stack, so a failed
// publication names its cause without pasting a traceback into an API response.
func lastLine(s string) string {
	lines := strings.Split(strings.TrimRight(s, "\n"), "\n")
	out := strings.TrimSpace(lines[len(lines)-1])
	if len(out) > 300 {
		out = out[:300]
	}
	return out
}
