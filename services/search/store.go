package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const migration = `
CREATE EXTENSION IF NOT EXISTS pg_search;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS gf;
CREATE TABLE IF NOT EXISTS gf.schema_version (version integer PRIMARY KEY);
INSERT INTO gf.schema_version VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS gf.snapshots (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 revision text NOT NULL, cli_sha text NOT NULL, nodes jsonb NOT NULL, weights jsonb NOT NULL,
 published_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant,repo,snapshot_id)
);
CREATE TABLE IF NOT EXISTS gf.skills (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 urn text NOT NULL, skill_revision text NOT NULL, node text NOT NULL,
 status text NOT NULL, metadata json NOT NULL, body bytea NOT NULL, search_text text NOT NULL,
 embedding vector(1024),
 UNIQUE(tenant,repo,snapshot_id,urn),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.snapshots(tenant,repo,snapshot_id)
);
-- v2 preserves arbitrary UTF-8 skill bodies (including NUL) as bytes. JSON, unlike
-- JSONB, also retains escaped NUL in metadata. The search projection maps NUL to space.
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='gf.skills'::regclass AND attname='body' AND atttypid='text'::regtype) THEN
  ALTER TABLE gf.skills ALTER COLUMN body TYPE bytea USING convert_to(body,'UTF8');
 END IF;
 IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='gf.skills'::regclass AND attname='metadata' AND atttypid='jsonb'::regtype) THEN
  ALTER TABLE gf.skills ALTER COLUMN metadata TYPE json USING metadata::json;
 END IF;
END $$;
INSERT INTO gf.schema_version VALUES (2) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS gf.heads (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 PRIMARY KEY(tenant,repo),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.snapshots(tenant,repo,snapshot_id)
);
-- v4: BM25 document frequencies belong to one immutable tenant/repo/snapshot.
-- A global index makes another catalog or old snapshot change this one's scores.
DROP INDEX IF EXISTS gf.skills_search;
INSERT INTO gf.schema_version VALUES (4) ON CONFLICT DO NOTHING;
`

type Store struct {
	Pool                             *pgxpool.Pool
	Tenant, Repo, PolicySHA, Version string
	LexicalEngine                    string
	Dense                            *DenseClient
	mu                               sync.Mutex
	cached                           *Catalog
	Searches, Uses                   atomic.Uint64
}

func openPool(ctx context.Context) (*pgxpool.Pool, error) {
	cfg, e := pgxpool.ParseConfig("")
	if e != nil {
		return nil, e
	}
	cfg.ConnConfig.Password, e = secret(env("PG_PASSWORD_FILE", "/run/secrets/app_password"))
	if e != nil {
		return nil, e
	}
	cfg.ConnConfig.ConnectTimeout = 2 * time.Second
	cfg.ConnConfig.DefaultQueryExecMode = pgx.QueryExecModeExec
	cfg.MaxConns = 8
	cfg.MinConns = 1
	cfg.MaxConnIdleTime = 5 * time.Minute
	cfg.HealthCheckPeriod = 5 * time.Second
	cfg.ConnConfig.RuntimeParams["application_name"] = "guidefold-search"
	cfg.ConnConfig.RuntimeParams["statement_timeout"] = "5000"
	return pgxpool.NewWithConfig(ctx, cfg)
}
func (s *Store) catalog(ctx context.Context) (*Catalog, error) {
	var id string
	e := s.Pool.QueryRow(ctx, `SELECT snapshot_id FROM gf.heads WHERE tenant=$1 AND repo=$2`, s.Tenant, s.Repo).Scan(&id)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, fail(503, "snapshot_not_published")
	}
	if e != nil {
		return nil, e
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.cached != nil && s.cached.ID == id {
		return s.cached, nil
	}
	c := &Catalog{ID: id, Repo: s.Repo, Cards: map[string]M{}, Revisions: map[string]string{}}
	var nodes, weights []byte
	e = s.Pool.QueryRow(ctx, `SELECT revision,cli_sha,nodes,weights FROM gf.snapshots WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3`, s.Tenant, s.Repo, id).Scan(&c.Revision, &c.PolicySHA, &nodes, &weights)
	if e != nil {
		return nil, e
	}
	if c.PolicySHA != s.PolicySHA {
		return nil, fail(503, "snapshot_policy_mismatch")
	}
	n, e := strictJSON(nodes)
	if e != nil {
		return nil, e
	}
	w, e := strictJSON(weights)
	if e != nil {
		return nil, e
	}
	c.Nodes = obj(n)
	c.Weights = obj(w)
	rows, e := s.Pool.Query(ctx, `SELECT urn,skill_revision,metadata FROM gf.skills WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 ORDER BY urn`, s.Tenant, s.Repo, id)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	for rows.Next() {
		var urn, revision string
		var raw []byte
		if e = rows.Scan(&urn, &revision, &raw); e != nil {
			return nil, e
		}
		v, e := strictJSON(raw)
		if e != nil {
			return nil, e
		}
		c.Cards[urn] = obj(v)
		c.Revisions[urn] = revision
	}
	if e = rows.Err(); e != nil {
		return nil, e
	}
	if len(c.Cards) == 0 {
		return nil, fail(503, "empty_snapshot")
	}
	if e = c.prepare(); e != nil {
		return nil, e
	}
	if s.LexicalEngine != "paradedb-experimental" {
		if e = s.verifyRouterIndex(ctx, c); e != nil {
			return nil, e
		}
	}
	if s.Dense != nil {
		if e = s.Dense.verifyCatalog(ctx, s, c); e != nil {
			return nil, e
		}
	}
	s.cached = c
	return c, nil
}

const bm25SQL = `SELECT urn,paradedb.score(id) AS relevance FROM gf.skills
 WHERE search_text ||| $1::text AND tenant=$2 AND repo=$3 AND snapshot_id=$4
 AND urn=ANY($5::text[])
 ORDER BY relevance DESC,urn COLLATE "C" ASC LIMIT 50`

func (s *Store) search(ctx context.Context, c *Catalog, query string, allowed map[string]bool) ([]Candidate, error) {
	if s.LexicalEngine != "paradedb-experimental" {
		return s.routerSearch(ctx, c, query, allowed)
	}
	if len(allowed) == 0 {
		return []Candidate{}, nil
	}
	// Omit the per-URN predicate only when every immutable snapshot card is
	// admissible. Tenant/repo/snapshot constraints remain unconditional.
	statement := strings.Replace(bm25SQL, "FROM gf.skills", "FROM "+pgx.Identifier{"gf", searchTable(s.Tenant, s.Repo, c.ID)}.Sanitize(), 1)
	args := []any{query, s.Tenant, s.Repo, c.ID}
	if len(allowed) == len(c.Cards) {
		statement = strings.Replace(statement, " AND urn=ANY($5::text[])", "", 1)
	} else {
		args = append(args, keys(allowed))
	}
	rows, e := s.Pool.Query(ctx, statement, args...)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []Candidate{}
	for rows.Next() {
		var urn string
		var score float32
		if e = rows.Scan(&urn, &score); e != nil {
			return nil, e
		}
		out = append(out, Candidate{URN: urn, BM25Rank: len(out) + 1})
	}
	if e = rows.Err(); e == nil {
		s.Searches.Add(1)
	}
	return out, e
}
func (s *Store) body(ctx context.Context, c *Catalog, urn, revision string) (string, error) {
	var body []byte
	e := s.Pool.QueryRow(ctx, `SELECT body FROM gf.skills WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 AND urn=$4 AND skill_revision=$5 AND status='active'`, s.Tenant, s.Repo, c.ID, urn, revision).Scan(&body)
	if errors.Is(e, pgx.ErrNoRows) {
		return "", fail(409, "revision_unavailable")
	}
	if e == nil {
		s.Uses.Add(1)
	}
	return string(body), e
}

// Table names are derived from trusted server identity and the immutable DB head,
// never from a request. One physical index per snapshot keeps BM25 IDF isolated.
func searchTable(tenant, repo, snapshot string) string {
	return "search_" + hash([]byte(tenant + "\x00" + repo + "\x00" + snapshot))[:48]
}
func ensureSearchIndex(ctx context.Context, tx pgx.Tx, tenant, repo, snapshot string) error {
	table := pgx.Identifier{"gf", searchTable(tenant, repo, snapshot)}.Sanitize()
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

func migrate(ctx context.Context, pool *pgxpool.Pool) error {
	tx, e := pool.Begin(ctx)
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `SELECT pg_advisory_xact_lock(78350001)`); e != nil {
		return e
	}
	if _, e = tx.Exec(ctx, migration+routerMigration+denseMigration, pgx.QueryExecModeSimpleProtocol); e != nil {
		return e
	}
	password, e := secret(env("APP_PASSWORD_FILE", "/run/secrets/app_password"))
	if e != nil {
		return e
	}
	// Role and database names are constants; the password is quoted, never concatenated raw.
	escaped := "'" + strings.ReplaceAll(password, "'", "''") + "'"
	if _, e = tx.Exec(ctx, `DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='guidefold_api') THEN CREATE ROLE guidefold_api LOGIN; END IF; END $$`); e != nil {
		return e
	}
	if _, e = tx.Exec(ctx, `ALTER ROLE guidefold_api PASSWORD `+escaped); e != nil {
		return e
	}
	if _, e = tx.Exec(ctx, `GRANT CONNECT ON DATABASE guidefold TO guidefold_api; GRANT USAGE ON SCHEMA gf TO guidefold_api; GRANT SELECT ON ALL TABLES IN SCHEMA gf TO guidefold_api; ALTER ROLE guidefold_api SET default_transaction_read_only=on;`, pgx.QueryExecModeSimpleProtocol); e != nil {
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
		if e = ensureSearchIndex(ctx, tx, v[0], v[1], v[2]); e != nil {
			return e
		}
	}
	return tx.Commit(ctx)
}
func publish(ctx context.Context, s *Store, path string) error {
	file, e := os.Open(path)
	if e != nil {
		return e
	}
	defer file.Close()
	st, e := file.Stat()
	if e != nil {
		return e
	}
	if st.Size() > 768*1024*1024 {
		return fmt.Errorf("snapshot_too_large")
	}
	raw, e := os.ReadFile(path)
	if e != nil {
		return e
	}
	value, e := strictJSON(raw)
	if e != nil {
		return e
	}
	envelope := obj(value)
	data := obj(envelope["snapshot"])
	if data == nil || str(data["format"]) != "guidefold-service-snapshot-v1" || str(envelope["sha256"]) != hash(canonical(data)) {
		return fmt.Errorf("snapshot_integrity_mismatch")
	}
	if str(data["cli_sha256"]) != s.PolicySHA {
		return fmt.Errorf("snapshot_policy_mismatch")
	}
	if str(data["repo_id"]) != s.Repo {
		return fmt.Errorf("snapshot_repo_mismatch")
	}
	nodes, cards, weights := obj(data["nodes"]), obj(data["cards"]), obj(data["weights"])
	if nodes["_root"] == nil || len(cards) == 0 || len(cards) > 100000 {
		return fmt.Errorf("invalid_snapshot_dimensions")
	}
	// Bound the integer-only policy arithmetic. Unsupported operator configurations fail publication.
	for k, v := range weights {
		if k == "ppr_mode" || k == "abstain_mode" {
			continue
		}
		n, ok := v.(json.Number)
		if !ok || strings.ContainsAny(n.String(), ".eE") || number(n) < 0 || number(n) > 1000000 {
			return fmt.Errorf("unsupported_policy_weight_%s", k)
		}
	}
	if integer(weights, "closure_decay_den", 2) == 0 {
		return fmt.Errorf("invalid_closure_denominator")
	}
	if m := text(weights, "ppr_mode", "closure"); m != "closure" && m != "pagerank" {
		return fmt.Errorf("unsupported_ppr_mode")
	}
	if m := text(weights, "abstain_mode", "magnitude"); m != "magnitude" && m != "margin" {
		return fmt.Errorf("unsupported_abstain_mode")
	}
	id := "repository:" + str(envelope["sha256"])
	check := &Catalog{Nodes: nodes, Cards: map[string]M{}}
	for _, u := range keys(cards) {
		card := obj(cards[u])
		if card == nil || str(card["urn"]) != u || nodes[str(card["node"])] == nil {
			return fmt.Errorf("invalid_card_identity")
		}
		if _, ok := card["_body"].(string); !ok {
			return fmt.Errorf("invalid_card_body")
		}
		check.Cards[u] = card
	}
	if e = check.prepare(); e != nil {
		return e
	}
	terms, e := compileRouterIndex(obj(envelope["router_index"]), cards, weights, str(envelope["sha256"]), s.PolicySHA, str(envelope["router_index_sha256"]))
	if e != nil {
		return e
	}
	tx, e := s.Pool.Begin(ctx)
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `SELECT pg_advisory_xact_lock(78350002)`); e != nil {
		return e
	}
	var exists bool
	if e = tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gf.snapshots WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3)`, s.Tenant, s.Repo, id).Scan(&exists); e != nil {
		return e
	}
	if !exists {
		if _, e = tx.Exec(ctx, `INSERT INTO gf.snapshots(tenant,repo,snapshot_id,revision,cli_sha,nodes,weights) VALUES($1,$2,$3,$4,$5,$6,$7)`, s.Tenant, s.Repo, id, str(data["revision"]), s.PolicySHA, string(canonical(nodes)), string(canonical(weights))); e != nil {
			return e
		}
		values := make([][]any, 0, len(cards))
		for _, u := range keys(cards) {
			card := obj(cards[u])
			metadata := M{}
			for k, v := range card {
				if k != "_body" {
					metadata[k] = v
				}
			}
			body := str(card["_body"])
			searchText := strings.Join([]string{str(card["name"]), str(card["description"]), str(card["digest"]), strings.Join(stringList(card["triggers"]), " "), body}, "\n")
			values = append(values, []any{s.Tenant, s.Repo, id, u, hash(pythonJSON(card, false)), str(card["node"]), text(card, "status", "active"), json.RawMessage(canonical(metadata)), []byte(body), strings.ReplaceAll(searchText, "\x00", " ")})
		}
		_, e = tx.CopyFrom(ctx, pgx.Identifier{"gf", "skills"}, []string{"tenant", "repo", "snapshot_id", "urn", "skill_revision", "node", "status", "metadata", "body", "search_text"}, pgx.CopyFromRows(values))
		if e != nil {
			return e
		}
	}
	if e = ensureSearchIndex(ctx, tx, s.Tenant, s.Repo, id); e != nil {
		return e
	}
	if e = ensureRouterIndex(ctx, tx, s, id, str(envelope["router_index_sha256"]), terms, len(cards)); e != nil {
		return e
	}
	if e = activateSnapshot(ctx, tx, s, id); e != nil {
		return e
	}
	if e = tx.Commit(ctx); e != nil {
		return e
	}
	b, _ := json.Marshal(M{"event": "snapshot_published", "snapshot": id, "cards": len(cards), "already_present": exists, "repo": s.Repo})
	fmt.Println(string(b))
	return nil
}
