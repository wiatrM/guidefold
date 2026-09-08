package importer

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

// parsePayload is the import.parse job contract (API-CONTRACT §8). The worker
// refuses a schema_version it does not know instead of guessing what the fields
// mean, and it re-checks the organisation before doing any work.
type parsePayload struct {
	SchemaVersion  string `json:"schema_version"`
	OrgID          string `json:"org_id"`
	RepoID         string `json:"repo_id"`
	ImportID       string `json:"import_id"`
	ManifestDigest string `json:"manifest_digest"`
	Commit         string `json:"commit"`
	Complete       bool   `json:"complete"`
}

// checkpoint is what a restarted job reads to know how far the last attempt
// got. It never records "which rows were written": every write below is an
// upsert keyed by a digest, so resuming is safe at any point (U1.5).
type checkpoint struct {
	Stage    string `json:"stage"`
	Tree     string `json:"tree"`
	Snapshot string `json:"snapshot_sha256"`
}

// Checkpoint stages, in order.
const (
	stageMaterialised = "materialised"
	stageBuilt        = "built"
	stageWritten      = "written"
)

// ParseWorker runs import.parse: materialise the manifest's blobs into a
// private tree, run the trusted builder over it, and write the catalog in one
// transaction.
type ParseWorker struct {
	pool    *pgxpool.Pool
	blobs   BlobStore
	builder Builder
	scratch string
}

// NewParseWorker wires the job handler.
func NewParseWorker(pool *pgxpool.Pool, blobs BlobStore, builder Builder, scratch string) *ParseWorker {
	if blobs == nil {
		blobs = NewBlobStore(pool)
	}
	if builder == nil {
		builder = NewPythonBuilder()
	}
	if scratch == "" {
		scratch = ScratchDir()
	}
	return &ParseWorker{pool: pool, blobs: blobs, builder: builder, scratch: scratch}
}

// Handlers maps the job kinds this module runs.
func (w *ParseWorker) Handlers() map[string]worker.Handler {
	return map[string]worker.Handler{KindParse: w.Run}
}

// ScratchDir is where a worker materialises import trees: never /tmp, always a
// directory the operator can point at a disk with room for a monorepo.
func ScratchDir() string {
	if v := os.Getenv("GUIDEFOLD_WORKER_DIR"); v != "" {
		return v
	}
	if home, e := os.UserHomeDir(); e == nil && home != "" {
		return filepath.Join(home, ".cache", "guidefold", "worker")
	}
	return filepath.Join(".guidefold", "worker")
}

// Run executes one import.parse job.
func (w *ParseWorker) Run(ctx context.Context, t *worker.Task) error {
	var payload parsePayload
	if e := json.Unmarshal(t.Job.Payload, &payload); e != nil {
		return worker.Permanent(fmt.Errorf("decode import.parse payload: %w", e))
	}
	if payload.SchemaVersion != PayloadVersion {
		return worker.Permanent(fmt.Errorf("unsupported payload schema_version %q", payload.SchemaVersion))
	}
	orgID, repoID, importID := t.Job.OrgID, t.Job.RepoID, t.Job.ImportID
	// The job carries its own identity claim; it has to agree with the row the
	// queue handed out before anything is read or written for that tenant.
	if payload.OrgID != orgID || payload.ImportID != importID || payload.RepoID != repoID {
		return worker.Permanent(errors.New("import.parse payload does not match its job row"))
	}
	rec, e := w.loadImport(ctx, orgID, repoID, importID)
	if e != nil {
		return e
	}
	dir := filepath.Join(w.scratch, orgID, importID)
	// The materialised tree is scratch: it exists so the builder has files to
	// read, and nothing after this job needs it. A retryable failure keeps it,
	// because the next attempt resumes from the checkpoint that names it; a
	// finished, cancelled or permanently failed import releases the disk here.
	// Without this the tree, snapshot.json and inventory.json of every import
	// ever run stay on /work, and one organisation fills the volume for all.
	settled := false
	defer func() {
		if settled {
			_ = os.RemoveAll(dir)
		}
	}()
	switch rec.State {
	case StateCancelled:
		settled = true
		return worker.Skipped("import_cancelled")
	case StateReady, StatePartial:
		// An earlier attempt already finished; nothing to redo.
		settled = true
		return nil
	}
	if e := w.setState(ctx, t, orgID, importID, StateParsing, ""); e != nil {
		return e
	}

	tree := filepath.Join(dir, "tree")
	var cp checkpoint
	_ = json.Unmarshal(t.Job.Checkpoint, &cp)
	if cp.Stage == "" || !treeIsComplete(tree, rec.Manifest) {
		if e := w.materialise(ctx, orgID, tree, rec.Manifest); e != nil {
			_ = w.setState(ctx, t, orgID, importID, StateFailed, e.Error())
			settled = true
			return worker.Permanent(e)
		}
		cp = checkpoint{Stage: stageMaterialised, Tree: tree}
		if e := t.Checkpoint(ctx, mustJSON(cp)); e != nil {
			return e
		}
	}

	commit := rec.Commit
	if commit == "" {
		// A dirty or git-less scan still needs a revision label; the manifest
		// digest is the only honest one, and it names exactly these bytes.
		commit = rec.Digest
	}
	snapshot, inventory, buildErr := w.build(ctx, tree, dir, repoID, commit)
	if buildErr != nil {
		reason := buildErr.Error()
		if e := w.setState(ctx, t, orgID, importID, StateFailed, reason); e != nil {
			return e
		}
		// A tree the builder cannot read at all leaves the catalog and the
		// active snapshot untouched (API-CONTRACT §6).
		settled = true
		return worker.Permanent(buildErr)
	}
	cp = checkpoint{Stage: stageBuilt, Tree: tree, Snapshot: snapshot.SHA256}
	if e := t.Checkpoint(ctx, mustJSON(cp)); e != nil {
		return e
	}

	result, e := w.write(ctx, t, rec, inventory, snapshot)
	if e != nil {
		return e
	}
	cp.Stage = stageWritten
	if e := t.Checkpoint(ctx, mustJSON(cp)); e != nil {
		return e
	}
	t.Result = mustJSON(result)
	settled = true
	return nil
}

// build runs the trusted builder, and retries once without the files it could
// not parse.
//
// The snapshot builder is strict by design — a card it cannot read must not
// reach the index — so one malformed SKILL.md aborts the whole run. That must
// not sink an import of two hundred good skills (U2.1). The builder writes its
// inventory first, so a failed run still names the offending paths; the worker
// removes exactly those from its own materialised tree and builds again. The
// removed files come back as `failed` in the import's file list, which is what
// makes the import `partial` rather than `ready`.
func (w *ParseWorker) build(ctx context.Context, tree, dir, repoID, commit string) (*domain.Snapshot, *domain.Inventory, error) {
	snapshot, inv, e := w.builder.Build(ctx, tree, repoID, commit, dir)
	if e == nil {
		return snapshot, inv, nil
	}
	partial := &domain.Inventory{}
	if readJSON(filepath.Join(dir, "inventory.json"), partial) != nil || len(partial.Errors) == 0 {
		return nil, nil, e
	}
	root, absErr := filepath.Abs(tree)
	if absErr != nil {
		return nil, nil, e
	}
	for _, bad := range partial.Errors {
		target, safe := safeJoin(root, bad.Path)
		if safe != nil {
			return nil, nil, e
		}
		if rm := os.Remove(target); rm != nil {
			return nil, nil, e
		}
	}
	snapshot, retried, e2 := w.builder.Build(ctx, tree, repoID, commit, dir)
	if e2 != nil {
		// The unparsable files were not the whole problem; report the first
		// failure, which is the one that describes the tree as it arrived.
		return nil, nil, e
	}
	// The retry's inventory has no errors left, because the files that produced
	// them are gone. Carry the original list forward: it is the record of what
	// this import could not read.
	retried.Errors = partial.Errors
	return snapshot, retried, nil
}

// materialise writes the manifest's files out of the blob store into a private
// directory. It re-validates every path: a manifest is client input, and the
// only thing standing between it and the worker's filesystem is this check.
//
// It also re-validates every size. Manifest.Validate bounds the import at
// MaxTotalBytes, but it bounds the sizes the *client declared*; the bytes that
// actually arrive are the blobs, each of which may legitimately be MaxBlobBytes.
// A manifest declaring one byte per file for two thousand files whose blobs are
// 8 MiB passes validation and would write ~16 GB onto a volume sized in
// hundreds of megabytes. So the declared size has to be the real size, and the
// running total has to be checked against the same ceiling as it is written.
func (w *ParseWorker) materialise(ctx context.Context, orgID, tree string, manifest *domain.Manifest) error {
	if e := os.RemoveAll(tree); e != nil {
		return fmt.Errorf("clear worker tree: %w", e)
	}
	if e := os.MkdirAll(tree, 0o700); e != nil {
		return fmt.Errorf("create worker tree: %w", e)
	}
	root, e := filepath.Abs(tree)
	if e != nil {
		return fmt.Errorf("resolve worker tree: %w", e)
	}
	var written int64
	for _, f := range manifest.Files {
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
		if int64(len(data)) != f.Size {
			return fmt.Errorf("manifest declares %d bytes for %s; the blob holds %d",
				f.Size, f.Path, len(data))
		}
		written += int64(len(data))
		if written > domain.MaxTotalBytes {
			return fmt.Errorf("the import writes more than %d bytes", domain.MaxTotalBytes)
		}
		// Always 0600, never the manifest's mode. Nothing in the worker executes a
		// materialised file -- build_tree.py reads SKILL.md bytes and nothing else --
		// so honouring `100755` bought nothing and wrote customer-controlled
		// executables to disk. Compose mounts /work `noexec`; the chart's emptyDir
		// cannot, so the two environments disagreed on the only thing that made it
		// harmless. The manifest keeps the mode; the filesystem does not get it.
		if e := os.WriteFile(target, data, 0o600); e != nil {
			return fmt.Errorf("write %s: %w", f.Path, e)
		}
	}
	return nil
}

// safeJoin refuses anything that would escape the tree.
func safeJoin(root, rel string) (string, error) {
	if rel == "" || strings.HasPrefix(rel, "/") || strings.Contains(rel, `\`) ||
		strings.ContainsRune(rel, 0) {
		return "", fmt.Errorf("unsafe manifest path %q", rel)
	}
	for _, seg := range strings.Split(rel, "/") {
		if seg == "" || seg == "." || seg == ".." {
			return "", fmt.Errorf("unsafe manifest path %q", rel)
		}
	}
	target := filepath.Join(root, filepath.FromSlash(rel))
	if target != root && !strings.HasPrefix(target, root+string(filepath.Separator)) {
		return "", fmt.Errorf("unsafe manifest path %q", rel)
	}
	return target, nil
}

// treeIsComplete reports whether a checkpointed tree can be reused. A worker
// restarted on another host, or after the scratch directory was cleaned, simply
// materialises again.
func treeIsComplete(tree string, manifest *domain.Manifest) bool {
	root, e := filepath.Abs(tree)
	if e != nil {
		return false
	}
	for _, f := range manifest.Files {
		target, e := safeJoin(root, f.Path)
		if e != nil {
			return false
		}
		info, e := os.Stat(target)
		if e != nil || info.Size() != f.Size {
			return false
		}
	}
	return true
}

func (w *ParseWorker) loadImport(ctx context.Context, orgID, repoID, importID string) (*importRecord, error) {
	rec := &importRecord{ImportID: importID}
	var commit, failure *string
	var raw string
	e := w.pool.QueryRow(ctx, `SELECT state,manifest_digest,commit,complete,publish,manifest::text,error,
 created_at,updated_at FROM gfm.imports
 WHERE org_id=$1::uuid AND repo_id=$2 AND import_id=$3::uuid`, orgID, repoID, importID).
		Scan(&rec.State, &rec.Digest, &commit, &rec.Complete, &rec.Publish, &raw, &failure,
			&rec.CreatedAt, &rec.UpdatedAt)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, worker.Permanent(fmt.Errorf("import %s is not in organisation %s", importID, orgID))
	}
	if e != nil {
		return nil, fmt.Errorf("read import %s: %w", importID, e)
	}
	rec.Commit, rec.Error, rec.Raw = str(commit), str(failure), []byte(raw)
	manifest, err := domain.ParseManifest(rec.Raw)
	if err != nil {
		return nil, worker.Permanent(fmt.Errorf("stored manifest of import %s is unreadable: %w", importID, err))
	}
	rec.Manifest = manifest
	return rec, nil
}

// setState moves the import and fences the write: a worker whose lease has
// moved on changes nothing (API-CONTRACT §8).
func (w *ParseWorker) setState(ctx context.Context, t *worker.Task, orgID, importID, state, failure string) error {
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return fmt.Errorf("open import transaction: %w", e)
	}
	defer tx.Rollback(ctx)
	if e := fence(ctx, tx, t); e != nil {
		return e
	}
	if _, e := tx.Exec(ctx, `UPDATE gfm.imports SET state=$3,error=$4,updated_at=now()
 WHERE org_id=$1::uuid AND import_id=$2::uuid AND state<>'cancelled'`,
		orgID, importID, state, nullable(failure)); e != nil {
		return fmt.Errorf("set import %s to %s: %w", importID, state, e)
	}
	return tx.Commit(ctx)
}

// fence refuses to write when the job's generation has moved. The queue bumps
// the generation on every lease and on cancellation, so a worker that lost its
// lease — or whose import was cancelled — writes nothing at all.
func fence(ctx context.Context, tx pgx.Tx, t *worker.Task) error {
	var ok bool
	e := tx.QueryRow(ctx, `SELECT true FROM gfm.jobs
 WHERE job_id=$1::uuid AND generation=$2 AND state='leased' FOR UPDATE`,
		t.Job.JobID, t.Job.Generation).Scan(&ok)
	if errors.Is(e, pgx.ErrNoRows) {
		return jobs.ErrFenced
	}
	if e != nil {
		return fmt.Errorf("check job fence: %w", e)
	}
	return nil
}

func mustJSON(v any) json.RawMessage {
	raw, e := json.Marshal(v)
	if e != nil {
		return json.RawMessage(`{}`)
	}
	return raw
}

// ---------------------------------------------------------------------------
// The catalog write
// ---------------------------------------------------------------------------

// fileOutcome is what the parse made of one manifest file.
type fileOutcome struct {
	Status  string
	Reason  string
	SkillID string
}

// write turns one built tree into catalog rows. Everything is one transaction:
// a half-written import would leave the catalog claiming skills whose revisions
// are missing, and the drift decisions are made from the state the transaction
// itself read.
func (w *ParseWorker) write(ctx context.Context, t *worker.Task, rec *importRecord,
	inv *domain.Inventory, snap *domain.Snapshot) (map[string]any, error) {
	orgID, repoID, importID := t.Job.OrgID, t.Job.RepoID, t.Job.ImportID
	tx, e := w.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return nil, fmt.Errorf("open catalog transaction: %w", e)
	}
	defer tx.Rollback(ctx)
	if e := fence(ctx, tx, t); e != nil {
		return nil, e
	}

	existing, e := readSkills(ctx, tx, orgID, repoID)
	if e != nil {
		return nil, e
	}
	byPath := map[string]domain.SkillState{}
	for _, s := range existing {
		byPath[s.Path] = s
	}
	if e := writeScopes(ctx, tx, orgID, repoID, importID, snap); e != nil {
		return nil, e
	}

	outcomes := map[string]*fileOutcome{}
	for _, f := range rec.Manifest.Files {
		outcomes[f.Path] = &fileOutcome{Status: "accepted"}
	}
	for _, bad := range inv.Errors {
		if o, ok := outcomes[bad.Path]; ok {
			o.Status, o.Reason = "failed", bad.Error
		}
	}
	parsedPaths := map[string]bool{}
	for i := range inv.Skills {
		parsedPaths[inv.Skills[i].Path] = true
	}
	for _, f := range rec.Manifest.Files {
		if f.Kind != domain.KindSkill || parsedPaths[f.Path] || outcomes[f.Path].Status == "failed" {
			continue
		}
		// The builder only reads .agents/skills/*/SKILL.md; anything else the
		// scan labelled a skill is named as omitted rather than silently lost.
		outcomes[f.Path].Status = "omitted"
		outcomes[f.Path].Reason = "not_a_skill_package_directory"
	}

	aliasFrom := rec.Manifest.AliasTargets()
	parsed := make([]domain.ParsedSkill, 0, len(inv.Skills))
	claimed := map[string]string{} // path -> skill_id this import puts there
	identity := make([]string, len(inv.Skills))
	for i := range inv.Skills {
		s := &inv.Skills[i]
		skillID := s.URN
		// An explicit alias keeps a moved SKILL.md's identity instead of
		// letting a rename look like a delete plus an add (U1.5).
		if from, ok := aliasFrom[s.Path]; ok {
			if was, ok := byPath[from]; ok {
				skillID = was.SkillID
			}
		}
		identity[i] = skillID
		claimed[s.Path] = skillID
	}

	// A path held by a *different* identity has to be released first: editing
	// a scope in guidefold.yaml changes a skill's URN while its file stays put.
	// A complete scan proves the old identity is gone; a partial one does not,
	// so it fails that file rather than removing something it cannot see.
	superseded := map[string]bool{}
	for path, id := range claimed {
		was, ok := byPath[path]
		if !ok || was.SkillID == id {
			continue
		}
		if !rec.Manifest.Complete {
			outcomes[path].Status = "failed"
			outcomes[path].Reason = "path_conflict: " + was.SkillID + " still holds this path"
			continue
		}
		superseded[was.SkillID] = true
	}
	if len(superseded) > 0 {
		ids := keysOf(superseded)
		if _, e := tx.Exec(ctx, `UPDATE gfm.skills SET source_status='removed',updated_at=now()
 WHERE org_id=$1::uuid AND repo_id=$2 AND skill_id=ANY($3::text[])`, orgID, repoID, ids); e != nil {
			return nil, fmt.Errorf("release superseded paths: %w", e)
		}
	}
	// Free the paths of skills this import moves, so an upsert never trips the
	// one-live-skill-per-path index halfway through a rename.
	moved := []string{}
	for i := range inv.Skills {
		if was, ok := findByID(existing, identity[i]); ok && was.Path != inv.Skills[i].Path {
			moved = append(moved, identity[i])
		}
	}
	if len(moved) > 0 {
		if _, e := tx.Exec(ctx, `UPDATE gfm.skills SET path='\x01'||skill_id
 WHERE org_id=$1::uuid AND repo_id=$2 AND skill_id=ANY($3::text[])`, orgID, repoID, moved); e != nil {
			return nil, fmt.Errorf("release moved paths: %w", e)
		}
	}

	commit := rec.Commit
	documents := 0
	for i := range inv.Skills {
		s := &inv.Skills[i]
		if outcomes[s.Path] != nil && outcomes[s.Path].Status != "accepted" {
			continue
		}
		skillID := identity[i]
		revisionID := domain.RevisionID(skillID, s.SHA256)
		if e := upsertSkill(ctx, tx, orgID, repoID, importID, skillID, revisionID, s); e != nil {
			return nil, e
		}
		if e := upsertRevision(ctx, tx, orgID, importID, commit, skillID, revisionID, s); e != nil {
			return nil, e
		}
		declared := append(append([]string{}, s.References...), frontmatterScripts(s)...)
		for _, r := range domain.ResourcesFor(s, declared, rec.Manifest.Files) {
			if _, e := tx.Exec(ctx, `INSERT INTO gfm.skill_resources
 (org_id,revision_id,path,sha256,size_bytes,type,required,available)
 VALUES($1::uuid,$2,$3,$4,$5,$6,$7,$8)
 ON CONFLICT (org_id,revision_id,path) DO UPDATE SET
  sha256=EXCLUDED.sha256,size_bytes=EXCLUDED.size_bytes,type=EXCLUDED.type,
  required=EXCLUDED.required,available=EXCLUDED.available`,
				orgID, revisionID, r.Path, r.SHA256, r.Size, r.Type, r.Required, r.Available); e != nil {
				return nil, fmt.Errorf("store resource %s: %w", r.Path, e)
			}
		}
		if e := writeRelations(ctx, tx, orgID, skillID, revisionID, s); e != nil {
			return nil, e
		}
		if o := outcomes[s.Path]; o != nil {
			o.SkillID = skillID
		}
		parsed = append(parsed, domain.ParsedSkill{SkillID: skillID, Path: s.Path,
			ContentSHA256: s.SHA256, RevisionID: revisionID})
	}

	for _, f := range rec.Manifest.Files {
		if f.Kind != domain.KindDocument {
			continue
		}
		scope := domain.ScopeOf(snap.Snapshot.Nodes, f.Path)
		if _, e := tx.Exec(ctx, `INSERT INTO gfm.documents
 (org_id,document_id,repo_id,path,sha256,kind,scope,size_bytes,import_id,commit)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,$9::uuid,$10)
 ON CONFLICT (org_id,repo_id,path,sha256) DO UPDATE SET
  scope=EXCLUDED.scope,import_id=EXCLUDED.import_id,commit=EXCLUDED.commit`,
			orgID, jobs.NewID(), repoID, f.Path, f.SHA256, documentKind(f.Path),
			nullable(scope), f.Size, importID, nullable(commit)); e != nil {
			return nil, fmt.Errorf("store document %s: %w", f.Path, e)
		}
		documents++
	}

	actions := domain.Drift(existing, parsed, rec.Manifest.Complete, importID)
	if e := applyDrift(ctx, tx, orgID, repoID, importID, actions); e != nil {
		return nil, e
	}

	counts, e := writeFileOutcomes(ctx, tx, orgID, importID, rec.Manifest.Files, outcomes)
	if e != nil {
		return nil, e
	}
	state := StateReady
	if counts["failed"] > 0 {
		state = StatePartial
	}
	if _, e := tx.Exec(ctx, `UPDATE gfm.imports SET state=$3,error=NULL,updated_at=now()
 WHERE org_id=$1::uuid AND import_id=$2::uuid AND state<>'cancelled'`,
		orgID, importID, state); e != nil {
		return nil, fmt.Errorf("finish import %s: %w", importID, e)
	}
	if e := mgmt.Audit(ctx, tx, orgID, "worker", "import."+state, "import:"+importID,
		rec.Digest, t.Job.JobID); e != nil {
		return nil, fmt.Errorf("audit import %s: %w", importID, e)
	}
	if e := tx.Commit(ctx); e != nil {
		return nil, fmt.Errorf("commit catalog: %w", e)
	}
	return map[string]any{"state": state, "skills": len(parsed), "documents": documents,
		"accepted": counts["accepted"], "omitted": counts["omitted"], "failed": counts["failed"],
		"owner_queue": len(actions), "snapshot_sha256": snap.SHA256}, nil
}

func readSkills(ctx context.Context, tx pgx.Tx, orgID, repoID string) ([]domain.SkillState, error) {
	rows, e := tx.Query(ctx, `SELECT s.skill_id,s.path,s.publication_status,s.source_status,
 COALESCE(s.current_revision_id,''),COALESCE(r.content_sha256,'')
 FROM gfm.skills s
 LEFT JOIN gfm.skill_revisions r ON r.org_id=s.org_id AND r.revision_id=s.current_revision_id
 WHERE s.org_id=$1::uuid AND s.repo_id=$2 ORDER BY s.skill_id`, orgID, repoID)
	if e != nil {
		return nil, fmt.Errorf("read skills of %s: %w", repoID, e)
	}
	defer rows.Close()
	out := []domain.SkillState{}
	for rows.Next() {
		var s domain.SkillState
		if e = rows.Scan(&s.SkillID, &s.Path, &s.PublicationStatus, &s.SourceStatus,
			&s.CurrentRevisionID, &s.ContentSHA256); e != nil {
			return nil, e
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

func findByID(list []domain.SkillState, id string) (domain.SkillState, bool) {
	for _, s := range list {
		if s.SkillID == id {
			return s, true
		}
	}
	return domain.SkillState{}, false
}

func keysOf(set map[string]bool) []string {
	out := make([]string, 0, len(set))
	for k := range set {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// writeScopes stores the scope map the builder resolved from guidefold.yaml.
// Directories and CODEOWNERS may suggest a scope elsewhere; guidefold.yaml is
// the one that decides, and `source` records which it was (U1).
func writeScopes(ctx context.Context, tx pgx.Tx, orgID, repoID, importID string, snap *domain.Snapshot) error {
	names := make([]string, 0, len(snap.Snapshot.Nodes))
	for name := range snap.Snapshot.Nodes {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		node := snap.Snapshot.Nodes[name]
		paths := node.Paths
		if paths == nil {
			paths = []string{}
		}
		if _, e := tx.Exec(ctx, `INSERT INTO gfm.scopes
 (org_id,repo_id,scope,owner,parent,paths,source,import_id,updated_at)
 VALUES($1::uuid,$2,$3,$4,$5,$6::text[],'guidefold_yaml',$7::uuid,now())
 ON CONFLICT (org_id,repo_id,scope) DO UPDATE SET
  owner=EXCLUDED.owner,parent=EXCLUDED.parent,paths=EXCLUDED.paths,
  source=EXCLUDED.source,import_id=EXCLUDED.import_id,updated_at=now()`,
			orgID, repoID, name, node.Owner, nullable(domain.ParentScope(name)), paths,
			importID); e != nil {
			return fmt.Errorf("store scope %s: %w", name, e)
		}
	}
	return nil
}

func upsertSkill(ctx context.Context, tx pgx.Tx, orgID, repoID, importID, skillID, revisionID string,
	s *domain.InventorySkill) error {
	status := s.StatusOrEmpty()
	if status == "" {
		status = "active"
	}
	// publication_status and knowledge_layer are deliberately not overwritten:
	// publication is the review module's decision and the knowledge layer is a
	// classification, neither of which a re-scan of the same file may reset.
	_, e := tx.Exec(ctx, `INSERT INTO gfm.skills
 (org_id,skill_id,repo_id,name,description,scope,owner,path,source_layer,source_status,
  current_revision_id,first_import_id,last_import_id)
 VALUES($1::uuid,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::uuid,$12::uuid)
 ON CONFLICT (org_id,skill_id) DO UPDATE SET
  name=EXCLUDED.name,description=EXCLUDED.description,scope=EXCLUDED.scope,
  owner=EXCLUDED.owner,path=EXCLUDED.path,source_layer=EXCLUDED.source_layer,
  source_status=EXCLUDED.source_status,current_revision_id=EXCLUDED.current_revision_id,
  last_import_id=EXCLUDED.last_import_id,updated_at=now()`,
		orgID, skillID, repoID, s.Name, s.Description, s.Scope, s.Owner, s.Path,
		s.Layer, status, revisionID, importID)
	if e != nil {
		return fmt.Errorf("store skill %s: %w", skillID, e)
	}
	return nil
}

func upsertRevision(ctx context.Context, tx pgx.Tx, orgID, importID, commit, skillID, revisionID string,
	s *domain.InventorySkill) error {
	frontmatter := sanitizeJSON(s.Frontmatter)
	// DO NOTHING: a revision is immutable, and the same bytes under the same
	// skill are the same revision however often the import runs (U1.5).
	_, e := tx.Exec(ctx, `INSERT INTO gfm.skill_revisions
 (org_id,revision_id,skill_id,content_sha256,blob_sha256,frontmatter,commit,import_id,origin,source_path)
 VALUES($1::uuid,$2,$3,$4,$4,$5::jsonb,$6,$7::uuid,'source',$8)
 ON CONFLICT (org_id,revision_id) DO NOTHING`,
		orgID, revisionID, skillID, s.SHA256, frontmatter, nullable(commit), importID, s.Path)
	if e != nil {
		return fmt.Errorf("store revision of %s: %w", skillID, e)
	}
	return nil
}

func writeRelations(ctx context.Context, tx pgx.Tx, orgID, skillID, revisionID string,
	s *domain.InventorySkill) error {
	for _, edge := range []struct {
		kind    string
		targets []string
	}{{"requires", s.Requires}, {"refines", s.Refines}} {
		for _, to := range edge.targets {
			if to == "" || to == skillID {
				continue
			}
			if _, e := tx.Exec(ctx, `INSERT INTO gfm.relations
 (org_id,relation_id,from_skill_id,to_skill_id,type,provenance,revision_id)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,'source',$6)
 ON CONFLICT (org_id,from_skill_id,to_skill_id,type,revision_id) DO NOTHING`,
				orgID, jobs.NewID(), skillID, to, edge.kind, revisionID); e != nil {
				return fmt.Errorf("store %s edge of %s: %w", edge.kind, skillID, e)
			}
		}
	}
	return nil
}

// applyDrift records what changed for a source that was already in the catalog.
// It never deletes a row: a removed file archives its skill and keeps every
// revision, and the owner queue is what asks a person to decide (U9).
func applyDrift(ctx context.Context, tx pgx.Tx, orgID, repoID, importID string, actions []domain.DriftAction) error {
	for _, a := range actions {
		if a.PublicationStatus != "" {
			if _, e := tx.Exec(ctx, `UPDATE gfm.skills SET publication_status=$3,updated_at=now()
 WHERE org_id=$1::uuid AND skill_id=$2`, orgID, a.SkillID, a.PublicationStatus); e != nil {
				return fmt.Errorf("mark %s %s: %w", a.SkillID, a.PublicationStatus, e)
			}
		}
		if a.SourceStatus != "" {
			if _, e := tx.Exec(ctx, `UPDATE gfm.skills SET source_status=$3,updated_at=now()
 WHERE org_id=$1::uuid AND skill_id=$2`, orgID, a.SkillID, a.SourceStatus); e != nil {
				return fmt.Errorf("mark %s %s: %w", a.SkillID, a.SourceStatus, e)
			}
		}
		// The partial unique index on open items is what makes re-running the
		// same manifest produce no second entry for the same reason (U9).
		if _, e := tx.Exec(ctx, `INSERT INTO gfm.owner_queue
 (org_id,item_id,repo_id,skill_id,revision_id,reason,evidence)
 VALUES($1::uuid,$2::uuid,$3,$4,$5,$6,$7::jsonb)
 ON CONFLICT DO NOTHING`,
			orgID, jobs.NewID(), repoID, a.SkillID, nullable(a.RevisionID), a.Reason,
			string(mustJSON(a.Evidence))); e != nil {
			return fmt.Errorf("queue %s for %s: %w", a.Reason, a.SkillID, e)
		}
		if e := mgmt.Audit(ctx, tx, orgID, "worker", "skill."+a.Reason, "skill:"+a.SkillID,
			a.RevisionID, importID); e != nil {
			return fmt.Errorf("audit %s: %w", a.Reason, e)
		}
	}
	return nil
}

func writeFileOutcomes(ctx context.Context, tx pgx.Tx, orgID, importID string,
	files []domain.File, outcomes map[string]*fileOutcome) (map[string]int, error) {
	counts := map[string]int{"accepted": 0, "omitted": 0, "failed": 0}
	paths := make([]string, 0, len(files))
	statuses := make([]string, 0, len(files))
	reasons := make([]*string, 0, len(files))
	skills := make([]*string, 0, len(files))
	for _, f := range files {
		o := outcomes[f.Path]
		if o == nil {
			o = &fileOutcome{Status: "accepted"}
		}
		counts[o.Status]++
		paths = append(paths, f.Path)
		statuses = append(statuses, o.Status)
		reasons = append(reasons, optional(o.Reason))
		skills = append(skills, optional(o.SkillID))
	}
	if len(paths) == 0 {
		return counts, nil
	}
	if _, e := tx.Exec(ctx, `UPDATE gfm.import_files f SET status=t.status,reason=t.reason,skill_id=t.skill_id
 FROM unnest($3::text[],$4::text[],$5::text[],$6::text[]) AS t(path,status,reason,skill_id)
 WHERE f.org_id=$1::uuid AND f.import_id=$2::uuid AND f.path=t.path`,
		orgID, importID, paths, statuses, reasons, skills); e != nil {
		return nil, fmt.Errorf("record file outcomes: %w", e)
	}
	return counts, nil
}

func optional(s string) *string {
	if s == "" {
		return nil
	}
	v := s
	return &v
}

// frontmatterScripts reads metadata.scripts, which names package scripts the
// same way metadata.references names package files. The builder does not model
// it, so the raw frontmatter is the source.
func frontmatterScripts(s *domain.InventorySkill) []string {
	var fm struct {
		Metadata map[string]any `json:"metadata"`
	}
	if e := json.Unmarshal(s.Frontmatter, &fm); e != nil {
		return nil
	}
	return splitList(fm.Metadata["scripts"])
}

// splitList accepts the two shapes frontmatter uses for a list: a YAML sequence
// and a comma-separated string.
func splitList(value any) []string {
	switch v := value.(type) {
	case []any:
		out := []string{}
		for _, item := range v {
			if s, ok := item.(string); ok && strings.TrimSpace(s) != "" {
				out = append(out, strings.TrimSpace(s))
			}
		}
		return out
	case string:
		out := []string{}
		for _, part := range strings.Split(v, ",") {
			if part = strings.TrimSpace(part); part != "" {
				out = append(out, part)
			}
		}
		return out
	}
	return nil
}

// documentKind labels a repository document by the role its name plays, which
// is what the map view groups by. It is a label, never a permission.
func documentKind(path string) string {
	name := path
	if i := strings.LastIndex(path, "/"); i >= 0 {
		name = path[i+1:]
	}
	switch name {
	case "AGENTS.md", "CLAUDE.md", "GEMINI.md":
		return "agents"
	case "README.md":
		return "readme"
	}
	if strings.Contains(path, "/adr/") {
		return "adr"
	}
	if strings.HasPrefix(path, ".github/instructions/") {
		return "instructions"
	}
	return "document"
}

// sanitizeJSON drops escaped NUL from a JSON document. PostgreSQL's jsonb
// cannot store U+0000 inside a string, and one odd byte in one file's
// frontmatter must not fail an import of two hundred skills.
func sanitizeJSON(raw json.RawMessage) string {
	if len(raw) == 0 {
		return "{}"
	}
	s := strings.ReplaceAll(string(raw), `\u0000`, "")
	s = strings.ReplaceAll(s, "\x00", "")
	if !json.Valid([]byte(s)) {
		return "{}"
	}
	return s
}
