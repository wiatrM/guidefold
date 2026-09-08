package schema_test

import (
	"context"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/schema"
	"github.com/wiatrM/guidefold/services/search/internal/testdb"
)

func TestMain(m *testing.M) { testdb.Main(m) }

// The test cluster is stock PostgreSQL: no pg_search, no pgvector. Everything
// here is the "plain PostgreSQL profile" the deployment has to tolerate.
func TestMigrateRunsOnPlainPostgres(t *testing.T) {
	_, pool := testdb.Start(t)
	ctx := context.Background()
	caps, e := schema.Detect(ctx, pool)
	if e != nil {
		t.Fatal(e)
	}
	if caps.HasPgSearch() {
		t.Skip("this cluster has pg_search; the plain profile is not what is under test")
	}
	if caps.PgSearch != schema.PgSearchAbsent {
		t.Fatalf("pg_search reported as %q rather than %q", caps.PgSearch, schema.PgSearchAbsent)
	}
	for _, table := range []string{"gf.snapshots", "gf.skills", "gf.heads", "gf.router_indexes",
		"gf.router_terms", "gf.events", "gf.search_shadow",
		"gfm.users", "gfm.identities", "gfm.orgs", "gfm.memberships", "gfm.repos",
		"gfm.invitations", "gfm.sessions", "gfm.tokens", "gfm.device_codes",
		"gfm.auth_states", "gfm.audit", "gfm.idempotency", "gfm.jobs"} {
		var exists bool
		if e := pool.QueryRow(ctx, `SELECT to_regclass($1) IS NOT NULL`, table).Scan(&exists); e != nil {
			t.Fatal(e)
		}
		if !exists {
			t.Errorf("%s was not created", table)
		}
	}
	// Without pgvector there is no embedding column and no dense tables.
	if caps.Vector {
		t.Skip("this cluster has pgvector")
	}
	var embedding bool
	if e := pool.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM information_schema.columns
 WHERE table_schema='gf' AND table_name='skills' AND column_name='embedding')`).Scan(&embedding); e != nil {
		t.Fatal(e)
	}
	if embedding {
		t.Error("the embedding column was created without pgvector")
	}
	for _, table := range []string{"gf.embedding_sets", "gf.embeddings"} {
		var exists bool
		if e := pool.QueryRow(ctx, `SELECT to_regclass($1) IS NOT NULL`, table).Scan(&exists); e != nil {
			t.Fatal(e)
		}
		if exists {
			t.Errorf("%s was created without pgvector", table)
		}
	}
}

func TestMigrateIsRepeatable(t *testing.T) {
	_, pool := testdb.Start(t)
	ctx := context.Background()
	for i := 0; i < 2; i++ {
		if e := schema.Migrate(ctx, pool, testdb.TestAppPassword); e != nil {
			t.Fatalf("migrate %d: %v", i+1, e)
		}
	}
	var versions int
	if e := pool.QueryRow(ctx, `SELECT count(*) FROM gf.schema_version`).Scan(&versions); e != nil {
		t.Fatal(e)
	}
	if versions == 0 {
		t.Fatal("no schema version rows")
	}
}

func TestMigrateRefusesAnEmptyPassword(t *testing.T) {
	_, pool := testdb.Start(t)
	if e := schema.Migrate(context.Background(), pool, "  "); e == nil {
		t.Fatal("an empty application password was accepted")
	}
}

// The API role reads the catalog and owns the management schema.
func TestApiRolePrivileges(t *testing.T) {
	_, pool := testdb.Start(t)
	ctx := context.Background()
	check := func(table, privilege string, want bool) {
		t.Helper()
		var got bool
		if e := pool.QueryRow(ctx, `SELECT has_table_privilege('guidefold_api',$1,$2)`,
			table, privilege).Scan(&got); e != nil {
			t.Fatal(e)
		}
		if got != want {
			t.Errorf("guidefold_api %s on %s: %v, want %v", privilege, table, got, want)
		}
	}
	check("gf.skills", "SELECT", true)
	check("gf.skills", "INSERT", false)
	check("gf.skills", "UPDATE", false)
	check("gf.snapshots", "INSERT", false)
	check("gf.events", "INSERT", true)
	check("gf.events", "DELETE", false)
	check("gf.search_shadow", "INSERT", true)
	for _, table := range []string{"gfm.orgs", "gfm.memberships", "gfm.tokens", "gfm.jobs",
		"gfm.idempotency", "gfm.audit"} {
		for _, privilege := range []string{"SELECT", "INSERT", "UPDATE", "DELETE"} {
			check(table, privilege, true)
		}
	}
	var readOnly bool
	if e := pool.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM pg_roles
 WHERE rolname='guidefold_api' AND 'default_transaction_read_only=on'=ANY(rolconfig))`).Scan(&readOnly); e != nil {
		t.Fatal(e)
	}
	if !readOnly {
		t.Error("the API role no longer defaults to read-only transactions")
	}
}

func TestEnsureSearchIndexIsSkippedWithoutPgSearch(t *testing.T) {
	_, pool := testdb.Start(t)
	ctx := context.Background()
	caps, e := schema.Detect(ctx, pool)
	if e != nil {
		t.Fatal(e)
	}
	if caps.HasPgSearch() {
		t.Skip("this cluster has pg_search")
	}
	tx, e := pool.Begin(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback(ctx)
	if e = schema.EnsureSearchIndex(ctx, tx, caps, "tenant", "repo", "snapshot"); e != nil {
		t.Fatalf("EnsureSearchIndex failed instead of skipping: %v", e)
	}
	var exists bool
	if e = tx.QueryRow(ctx, `SELECT to_regclass($1) IS NOT NULL`,
		"gf."+schema.SearchTable("tenant", "repo", "snapshot")).Scan(&exists); e != nil {
		t.Fatal(e)
	}
	if exists {
		t.Fatal("a ParadeDB table was created without the extension")
	}
}

func TestSearchTableNamesAreDistinctAndStable(t *testing.T) {
	a := schema.SearchTable("tenant", "repo", "snap")
	if a != schema.SearchTable("tenant", "repo", "snap") {
		t.Fatal("the table name is not stable")
	}
	// The separator matters: "a"+"bc" and "ab"+"c" must not collide.
	if schema.SearchTable("a", "bc", "s") == schema.SearchTable("ab", "c", "s") {
		t.Fatal("tenant and repo run together in the table name")
	}
	if len(a) != len("search_")+48 {
		t.Fatalf("unexpected table name %q", a)
	}
}
