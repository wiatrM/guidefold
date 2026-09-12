package importer

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"net/http"

	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// PutBlob stores content-addressed bytes for an organisation and reports
// whether they were new, exactly as the HTTP route's own call to the blob
// store does. It carries none of that route's per-import gating (the import
// must be created/uploading, the digest must be in that import's manifest):
// those checks bound what an arbitrary HTTP body may write to storage and
// stay in handlePutBlob (U1.3), whereas a caller that already built the
// manifest and read the bytes it is passing here — a worker with a
// repository's files in memory — has no separate, less-trusted upload phase
// to bound. Two callers may still store the same bytes any number of times
// (U1.4): blobs are content addressed, so the second call is not an error.
func (s *Service) PutBlob(ctx context.Context, orgID, sha256 string, content []byte) (created bool, err error) {
	return s.blobs.Put(ctx, orgID, sha256, content)
}

// handlePutBlob accepts one file of a manifest.
//
// Three rules make this route safe to point at a monorepo. Only a hash the
// manifest listed is accepted, so a file the scan excluded — a private key, an
// ignored directory, a symlink out of the tree — has no route into storage at
// all (U1.3). The body is hashed as it streams and compared with the digest in
// the URL, so the store can never hold bytes under the wrong name. And the same
// bytes may arrive any number of times: an interrupted upload is retried by
// re-sending, and the second attempt answers 200 instead of failing (U1.4).
func (s *Service) handlePutBlob(c *mgmt.Context) error {
	rc, e := s.authorizeRepo(c, mgmt.RoleOwner)
	if e != nil {
		return e
	}
	sha := c.Param("sha256")
	if !domain.IsSHA256(sha) {
		return mgmt.Invalid("invalid_request", "The digest in the path is not 64 lower-case hex characters.")
	}
	importID := c.Param("import_id")
	// The body is read and verified before the transaction opens. Committing
	// `created → uploading` and an `import.blob` audit row first would leave
	// both behind for an upload that then failed its digest check: an audit
	// entry naming a blob that was never stored, and an import advanced by a
	// transfer that did not arrive.
	data, apiErr := readBlob(c, sha)
	if apiErr != nil {
		return apiErr
	}
	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	rec, e := s.lockImport(c.Ctx(), tx, rc.Org.ID, rc.RepoID, importID)
	if e != nil {
		return e
	}
	switch rec.State {
	case StateCreated, StateUploading:
	default:
		return mgmt.Conflict("import_already_finalized",
			"This import is no longer accepting uploads.")
	}
	if !rec.Manifest.Wants(sha) {
		return mgmt.Invalid("blob_not_in_manifest",
			"This digest is not listed in the manifest of this import.")
	}
	// The first upload moves the import out of `created`, which is the state
	// machine's `created → uploading` transition (API-CONTRACT §6).
	if rec.State == StateCreated {
		if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.imports SET state='uploading',updated_at=now()
 WHERE org_id=$1::uuid AND import_id=$2::uuid AND state='created'`, rc.Org.ID, importID); e != nil {
			return mgmt.Internal(e)
		}
	}
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "import.blob", "blob:"+sha, importID); e != nil {
		return mgmt.Internal(e)
	}
	// Stored before the commit, so the audit row and the state transition are
	// never durable ahead of the bytes they describe. Blobs are content
	// addressed, so a failed commit leaves nothing but a re-uploadable object.
	created, err := s.PutBlob(c.Ctx(), rc.Org.ID, sha, data)
	if err != nil {
		return mgmt.Internal(err)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	status := http.StatusOK
	if created {
		status = http.StatusCreated
	}
	return c.JSON(status, map[string]any{
		"schema_version": mgmt.SchemaVersion, "sha256": sha,
		"size": len(data), "stored": created})
}

// readBlob buffers the body under the route's ceiling and verifies the digest
// before anything is written. The hash is computed over exactly the bytes that
// arrived, so a truncated transfer fails the comparison rather than storing a
// short file under a full file's name.
func readBlob(c *mgmt.Context, sha string) ([]byte, error) {
	hasher := sha256.New()
	data, e := io.ReadAll(io.TeeReader(c.R.Body, hasher))
	if e != nil {
		if mgmt.TooLarge(e) {
			return nil, mgmt.Fail(http.StatusRequestEntityTooLarge, "blob_too_large",
				"This file exceeds the 8 MiB per-blob limit.")
		}
		return nil, mgmt.Invalid("invalid_body", "The upload could not be read.")
	}
	if len(data) > domain.MaxBlobBytes {
		return nil, mgmt.Fail(http.StatusRequestEntityTooLarge, "blob_too_large",
			"This file exceeds the 8 MiB per-blob limit.")
	}
	if hex.EncodeToString(hasher.Sum(nil)) != sha {
		return nil, mgmt.Invalid("blob_digest_mismatch",
			"The uploaded bytes do not hash to the digest in the path.")
	}
	return data, nil
}
