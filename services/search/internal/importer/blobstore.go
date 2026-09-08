package importer

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// ErrBlobNotFound means the organisation holds no blob with that digest.
var ErrBlobNotFound = errors.New("blob_not_found")

// BlobStore is the outbound port for content-addressed bytes. It is defined by
// the import module's need, not by the technology behind it: today a table in
// the same database (one transaction for enqueue plus the rows that justify it,
// one permission model, one retention job — ADR-0033), later an object store
// with `<bucket>/<org_id>/<sha256>` keys and short-lived references. Nothing in
// this package knows which one it is talking to.
//
// Content is addressed per organisation: two tenants that scan the same file
// each hold their own copy, so deleting one organisation can never take bytes
// another one still references, and a digest is never an existence oracle for
// somebody else's repository.
type BlobStore interface {
	// Put stores bytes under their digest and reports whether it created a new
	// object. Storing the same bytes twice is not an error: the second upload
	// of an interrupted transfer must succeed (U1.4).
	Put(ctx context.Context, orgID, sha256 string, data []byte) (created bool, err error)
	// Get returns the exact bytes, or ErrBlobNotFound.
	Get(ctx context.Context, orgID, sha256 string) ([]byte, error)
	// Exists reports which of the digests the organisation already holds.
	Exists(ctx context.Context, orgID string, sha256s []string) (map[string]bool, error)
}

// PostgresBlobStore is the MVP adapter: gfm.blobs in the same database.
type PostgresBlobStore struct{ Pool *pgxpool.Pool }

// NewBlobStore builds the Postgres adapter.
func NewBlobStore(pool *pgxpool.Pool) *PostgresBlobStore { return &PostgresBlobStore{Pool: pool} }

// Put writes the object. The management role runs read-only by default, so the
// write opens an explicit read-write transaction like every other mutation.
func (s *PostgresBlobStore) Put(ctx context.Context, orgID, sha string, data []byte) (bool, error) {
	tx, e := s.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return false, fmt.Errorf("open blob transaction: %w", e)
	}
	defer tx.Rollback(ctx)
	// DO NOTHING rather than DO UPDATE, because the affected-row count is the
	// answer to "was this new?" — which the caller turns into 201 or 200.
	tag, e := tx.Exec(ctx, `INSERT INTO gfm.blobs(org_id,sha256,size_bytes,content)
 VALUES($1::uuid,$2,$3,$4) ON CONFLICT (org_id,sha256) DO NOTHING`,
		orgID, sha, int64(len(data)), data)
	if e != nil {
		return false, fmt.Errorf("store blob %s: %w", sha[:12], e)
	}
	created := tag.RowsAffected() == 1
	if !created {
		if _, e = tx.Exec(ctx, `UPDATE gfm.blobs SET last_referenced_at=now()
 WHERE org_id=$1::uuid AND sha256=$2`, orgID, sha); e != nil {
			return false, fmt.Errorf("touch blob %s: %w", sha[:12], e)
		}
	}
	if e = tx.Commit(ctx); e != nil {
		return false, fmt.Errorf("commit blob %s: %w", sha[:12], e)
	}
	return created, nil
}

// Get reads the exact bytes back.
func (s *PostgresBlobStore) Get(ctx context.Context, orgID, sha string) ([]byte, error) {
	var content []byte
	e := s.Pool.QueryRow(ctx, `SELECT content FROM gfm.blobs
 WHERE org_id=$1::uuid AND sha256=$2`, orgID, sha).Scan(&content)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, ErrBlobNotFound
	}
	if e != nil {
		return nil, fmt.Errorf("read blob %s: %w", sha[:12], e)
	}
	return content, nil
}

// Exists answers the "which of these do you already hold" question in one round
// trip, which is what makes the second sync of an unchanged tree upload nothing.
func (s *PostgresBlobStore) Exists(ctx context.Context, orgID string, shas []string) (map[string]bool, error) {
	out := make(map[string]bool, len(shas))
	if len(shas) == 0 {
		return out, nil
	}
	rows, e := s.Pool.Query(ctx, `SELECT sha256 FROM gfm.blobs
 WHERE org_id=$1::uuid AND sha256=ANY($2::text[])`, orgID, shas)
	if e != nil {
		return nil, fmt.Errorf("list blobs for org %s: %w", orgID, e)
	}
	defer rows.Close()
	for rows.Next() {
		var sha string
		if e = rows.Scan(&sha); e != nil {
			return nil, e
		}
		out[sha] = true
	}
	return out, rows.Err()
}

var _ BlobStore = (*PostgresBlobStore)(nil)
