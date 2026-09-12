package importer_test

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
	"github.com/wiatrM/guidefold/services/search/internal/jobs"
	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

// A worker that reads a repository's files itself — the Live Agent's own
// reason for existing (internal/README.md, "The import pipeline") — has no
// *mgmt.Context and no HTTP request to drive through. This test proves the
// three exported seam methods alone take the same manifest from nothing to a
// queued import.parse job, without ever calling an HTTP handler.
func TestImportEndToEndThroughTheServiceMethodsWithoutHTTP(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	const repo = "meridian"
	owner.CreateRepo(t, org, repo, "https://github.example/acme/meridian")
	tree := pivottest.Monorepo(t)
	manifestMap := pivottest.Manifest(t, tree, "acme", repo, true)
	raw, e := json.Marshal(manifestMap)
	if e != nil {
		t.Fatal(e)
	}
	manifest, e := domain.ParseManifest(raw)
	if e != nil {
		t.Fatal(e)
	}
	ctx := context.Background()

	// CreateImport: a fresh manifest gets a fresh row, still missing every blob.
	tx, e := h.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	created, e := h.Importer.CreateImport(ctx, tx, org, repo, manifest, importer.CreateImportOptions{
		RawManifest: raw, CreatedBy: owner.User["id"].(string),
		Actor: "worker", RequestID: "live-run-1"})
	if e != nil {
		t.Fatal(e)
	}
	if e := tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	if created.Reused {
		t.Fatalf("a fresh manifest was reported as reused: %+v", created)
	}
	if created.State != importer.StateCreated {
		t.Fatalf("a fresh import has state %q, not %q", created.State, importer.StateCreated)
	}
	files := manifestMap["files"].([]map[string]any)
	if len(created.Missing) != len(files) {
		t.Fatalf("expected every one of %d files missing, got %d", len(files), len(created.Missing))
	}
	byDigest := map[string]string{}
	for _, f := range files {
		byDigest[f["sha256"].(string)] = f["path"].(string)
	}

	// PutBlob: fill every blob the create step named missing.
	for _, sha := range created.Missing {
		path, ok := byDigest[sha]
		if !ok {
			t.Fatalf("CreateImport asked for %s, which is not in the manifest", sha)
		}
		data, e := os.ReadFile(filepath.Join(tree, filepath.FromSlash(path)))
		if e != nil {
			t.Fatal(e)
		}
		stored, e := h.Importer.PutBlob(ctx, org, sha, data)
		if e != nil {
			t.Fatalf("PutBlob %s: %v", path, e)
		}
		if !stored {
			t.Fatalf("PutBlob %s reported an existing blob on a first write", path)
		}
	}

	// FinalizeImport: every blob is in, so this queues the same work the HTTP
	// route's finalize would.
	tx2, e := h.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	finalized, e := h.Importer.FinalizeImport(ctx, tx2, org, repo, created.ImportID,
		importer.FinalizeOptions{Actor: "worker", RequestID: "live-run-1"})
	if e != nil {
		t.Fatal(e)
	}
	if e := tx2.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	if finalized.State != importer.StateQueued {
		t.Fatalf("finalize left state %q, not %q", finalized.State, importer.StateQueued)
	}
	if len(finalized.QueuedJobIDs) == 0 {
		t.Fatalf("finalize queued no jobs: %+v", finalized)
	}

	// The rows a worker-driven import must land, exactly like the HTTP path.
	var state string
	if e := h.Pool.QueryRow(ctx, `SELECT state FROM gfm.imports
 WHERE org_id=$1::uuid AND import_id=$2::uuid`, org, created.ImportID).Scan(&state); e != nil {
		t.Fatal(e)
	}
	if state != importer.StateQueued {
		t.Fatalf("gfm.imports.state is %q after finalize", state)
	}
	var fileRows int
	if e := h.Pool.QueryRow(ctx, `SELECT count(*) FROM gfm.import_files
 WHERE org_id=$1::uuid AND import_id=$2::uuid`, org, created.ImportID).Scan(&fileRows); e != nil {
		t.Fatal(e)
	}
	if fileRows != len(files) {
		t.Fatalf("gfm.import_files has %d rows, manifest named %d", fileRows, len(files))
	}
	var blobRows int
	if e := h.Pool.QueryRow(ctx, `SELECT count(*) FROM gfm.blobs WHERE org_id=$1::uuid AND sha256=ANY($2::text[])`,
		org, created.Missing).Scan(&blobRows); e != nil {
		t.Fatal(e)
	}
	if blobRows != len(created.Missing) {
		t.Fatalf("gfm.blobs holds %d of the %d blobs PutBlob stored", blobRows, len(created.Missing))
	}

	// The same job the HTTP finalize route enqueues: kind, idempotency key and
	// queued state all match API-CONTRACT §8, not a worker-specific shape.
	parse := h.JobOf(t, created.ImportID, importer.KindParse)
	if parse.State != jobs.StateQueued {
		t.Fatalf("import.parse job state is %q, not %q", parse.State, jobs.StateQueued)
	}
	if parse.IdempotencyKey != importer.KindParse+":"+created.ImportID {
		t.Fatalf("import.parse job has idempotency key %q", parse.IdempotencyKey)
	}
	var payload struct {
		SchemaVersion  string `json:"schema_version"`
		OrgID          string `json:"org_id"`
		RepoID         string `json:"repo_id"`
		ImportID       string `json:"import_id"`
		ManifestDigest string `json:"manifest_digest"`
	}
	if e := json.Unmarshal(parse.Payload, &payload); e != nil {
		t.Fatal(e)
	}
	if payload.SchemaVersion != importer.PayloadVersion || payload.OrgID != org ||
		payload.RepoID != repo || payload.ImportID != created.ImportID {
		t.Fatalf("import.parse payload does not name the import it belongs to: %+v", payload)
	}

	// A second FinalizeImport is the no-op U1.4 promises: no second parse job.
	tx3, e := h.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	again, e := h.Importer.FinalizeImport(ctx, tx3, org, repo, created.ImportID,
		importer.FinalizeOptions{Actor: "worker", RequestID: "live-run-1"})
	if e != nil {
		t.Fatal(e)
	}
	if e := tx3.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	if len(again.QueuedJobIDs) != 0 {
		t.Fatalf("finalizing an already-queued import queued %d more jobs", len(again.QueuedJobIDs))
	}
	var parses int
	if e := h.Pool.QueryRow(ctx, `SELECT count(*) FROM gfm.jobs
 WHERE import_id=$1::uuid AND kind=$2`, created.ImportID, importer.KindParse).Scan(&parses); e != nil {
		t.Fatal(e)
	}
	if parses != 1 {
		t.Fatalf("finalizing twice left %d import.parse jobs", parses)
	}
}
