// Package schema owns every DDL statement of the search service: the immutable
// catalog in schema gf and the management tables in schema gfm. It is a package
// (rather than a file next to the queries) so tests can migrate a throwaway
// PostgreSQL cluster without linking the whole service binary.
//
// Plain PostgreSQL profile: pg_search and pgvector are optional. Their CREATE
// EXTENSION runs inside an exception block, the vector column and the dense
// tables are only created when the type exists, and the ParadeDB BM25 index is
// only created when the extension is installed. The default `router` lexical
// engine never reads either, so a stock server runs the full product path.
package schema

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

// PgSearchAbsent is reported by Version and by /health/ready when the ParadeDB
// extension is not installed. It is a state, not an error.
const PgSearchAbsent = "absent"

const migrationLock = 78350001

// Capabilities describes what the connected server can actually do.
type Capabilities struct {
	PgSearch string // extension version, or PgSearchAbsent
	Vector   bool
}

// HasPgSearch reports whether the ParadeDB extension is installed.
func (c Capabilities) HasPgSearch() bool { return c.PgSearch != PgSearchAbsent && c.PgSearch != "" }

type queryer interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// Detect reads the installed extensions. It never fails on a plain server.
func Detect(ctx context.Context, db queryer) (Capabilities, error) {
	c := Capabilities{PgSearch: PgSearchAbsent}
	var version *string
	if e := db.QueryRow(ctx, `SELECT extversion FROM pg_extension WHERE extname='pg_search'`).Scan(&version); e != nil {
		if e != pgx.ErrNoRows {
			return c, e
		}
	} else if version != nil {
		c.PgSearch = *version
	}
	if e := db.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM pg_type WHERE typname='vector')`).Scan(&c.Vector); e != nil {
		return c, e
	}
	return c, nil
}

// Migrate brings one database to the current schema. It holds the same
// transaction-scoped advisory lock as before, so concurrent deployments
// serialise, and it creates or repairs the guidefold_api login role.
func Migrate(ctx context.Context, pool *pgxpool.Pool, appPassword string) error {
	if strings.TrimSpace(appPassword) == "" {
		return fmt.Errorf("app_password_required")
	}
	tx, e := pool.Begin(ctx)
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `SELECT pg_advisory_xact_lock($1)`, migrationLock); e != nil {
		return e
	}
	if _, e = tx.Exec(ctx, extensionsSQL, pgx.QueryExecModeSimpleProtocol); e != nil {
		return e
	}
	caps, e := Detect(ctx, tx)
	if e != nil {
		return e
	}
	if _, e = tx.Exec(ctx, catalogSQL, pgx.QueryExecModeSimpleProtocol); e != nil {
		return e
	}
	if caps.Vector {
		if _, e = tx.Exec(ctx, vectorSQL, pgx.QueryExecModeSimpleProtocol); e != nil {
			return e
		}
	}
	if _, e = tx.Exec(ctx, managementSQL, pgx.QueryExecModeSimpleProtocol); e != nil {
		return e
	}
	// After managementSQL: the import tables reference gfm.orgs and gfm.repos.
	if _, e = tx.Exec(ctx, importerSQL, pgx.QueryExecModeSimpleProtocol); e != nil {
		return e
	}
	// After catalogSQL and managementSQL: the projection references gfm.orgs and
	// the ledger indexes reference gf.events.
	if _, e = tx.Exec(ctx, usageSQL, pgx.QueryExecModeSimpleProtocol); e != nil {
		return e
	}
	// After importerSQL: the review tables reference gfm.repos and add a column
	// to gfm.skills.
	if _, e = tx.Exec(ctx, reviewSQL, pgx.QueryExecModeSimpleProtocol); e != nil {
		return e
	}
	// Role and database names are constants; the password is quoted, never concatenated raw.
	escaped := "'" + strings.ReplaceAll(appPassword, "'", "''") + "'"
	if _, e = tx.Exec(ctx, `DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='guidefold_api') THEN CREATE ROLE guidefold_api LOGIN; END IF; END $$`); e != nil {
		return e
	}
	if _, e = tx.Exec(ctx, `ALTER ROLE guidefold_api PASSWORD `+escaped); e != nil {
		return e
	}
	if _, e = tx.Exec(ctx, grantsSQL, pgx.QueryExecModeSimpleProtocol); e != nil {
		return e
	}
	// Upgrade already published snapshots as well as empty, first-time installs.
	rows, e := tx.Query(ctx, `SELECT tenant,repo,snapshot_id FROM gf.snapshots ORDER BY tenant,repo,snapshot_id`)
	if e != nil {
		return e
	}
	var snapshots [][3]string
	for rows.Next() {
		var v [3]string
		if e = rows.Scan(&v[0], &v[1], &v[2]); e != nil {
			rows.Close()
			return e
		}
		snapshots = append(snapshots, v)
	}
	rows.Close()
	if e = rows.Err(); e != nil {
		return e
	}
	for _, v := range snapshots {
		if e = EnsureSearchIndex(ctx, tx, caps, v[0], v[1], v[2]); e != nil {
			return e
		}
	}
	return tx.Commit(ctx)
}

// SearchTable names the physical BM25 table of one snapshot. Names are derived
// from trusted server identity and the immutable DB head, never from a request.
// One physical index per snapshot keeps BM25 IDF isolated.
func SearchTable(tenant, repo, snapshot string) string {
	sum := sha256.Sum256([]byte(tenant + "\x00" + repo + "\x00" + snapshot))
	return "search_" + hex.EncodeToString(sum[:])[:48]
}

type execer interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// EnsureSearchIndex materialises the per-snapshot ParadeDB table. Without the
// extension there is nothing to build: the `router` engine reads gf.router_terms
// and `paradedb-experimental` refuses to start, so a plain server skips the copy
// entirely rather than duplicating every body for an index it cannot create.
// A later migrate re-runs this for every published snapshot once pg_search exists.
func EnsureSearchIndex(ctx context.Context, tx execer, caps Capabilities, tenant, repo, snapshot string) error {
	if !caps.HasPgSearch() {
		return nil
	}
	table := pgx.Identifier{"gf", SearchTable(tenant, repo, snapshot)}.Sanitize()
	var exists bool
	if e := tx.QueryRow(ctx, `SELECT to_regclass($1) IS NOT NULL`, table).Scan(&exists); e != nil {
		return e
	}
	if exists {
		return nil
	} // table, rows and index become visible in the same transaction
	if _, e := tx.Exec(ctx, `CREATE TABLE `+table+` (
 id bigint PRIMARY KEY, tenant text NOT NULL, repo text NOT NULL,
 snapshot_id text NOT NULL, urn text NOT NULL, search_text text NOT NULL
)`); e != nil {
		return e
	}
	if _, e := tx.Exec(ctx, `INSERT INTO `+table+` SELECT id,tenant,repo,snapshot_id,urn,search_text
 FROM gf.skills WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3`, tenant, repo, snapshot); e != nil {
		return e
	}
	if _, e := tx.Exec(ctx, `CREATE INDEX ON `+table+` USING bm25
 (id,search_text,(tenant::pdb.literal),(repo::pdb.literal),(snapshot_id::pdb.literal),(urn::pdb.literal))
 WITH(key_field='id')`); e != nil {
		return e
	}
	_, e := tx.Exec(ctx, `GRANT SELECT ON `+table+` TO guidefold_api`)
	return e
}
