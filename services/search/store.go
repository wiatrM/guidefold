package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/graph"
	"github.com/wiatrM/guidefold/services/search/internal/schema"
)

type Store struct {
	Pool                             *pgxpool.Pool
	Tenant, Repo, PolicySHA, Version string
	LexicalEngine                    string
	SnapshotID                       string
	Dense                            *DenseClient
	Shadow                           *ShadowWorker
	Caps                             schema.Capabilities
	catalogs                         *catalogCache
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

// catalog loads one tenant's immutable snapshot. Tenant and repo are arguments,
// not server state: one process serves several organisations and the caller has
// already proved which one this request belongs to.
func (s *Store) catalog(ctx context.Context, tenant, repo string) (*Catalog, error) {
	if tenant == "" || repo == "" {
		return nil, fail(400, "tenant_and_repository_required")
	}
	var id string
	query := `SELECT snapshot_id FROM gf.heads WHERE tenant=$1 AND repo=$2`
	args := []any{tenant, repo}
	if s.SnapshotID != "" {
		// Always check the database, even with cached metadata: pinned does not mean
		// offline fallback. The pin cannot escape the operator's tenant/repo.
		query = `SELECT snapshot_id FROM gf.snapshots WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3`
		args = append(args, s.SnapshotID)
	}
	e := s.Pool.QueryRow(ctx, query, args...).Scan(&id)
	if errors.Is(e, pgx.ErrNoRows) {
		return nil, fail(503, "snapshot_not_published")
	}
	if e != nil {
		return nil, e
	}
	key := catalogKey(tenant, repo, id)
	if hit := s.catalogs.get(key); hit != nil {
		return hit, nil
	}
	c := &Catalog{ID: id, Tenant: tenant, Repo: repo, Cards: map[string]M{}, Revisions: map[string]string{}}
	var nodes, weights []byte
	e = s.Pool.QueryRow(ctx, `SELECT revision,cli_sha,nodes,weights FROM gf.snapshots WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3`, tenant, repo, id).Scan(&c.Revision, &c.PolicySHA, &nodes, &weights)
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
	rows, e := s.Pool.Query(ctx, `SELECT urn,skill_revision,metadata FROM gf.skills WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 ORDER BY urn`, tenant, repo, id)
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
	return s.catalogs.put(key, c), nil
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
	statement := strings.Replace(bm25SQL, "FROM gf.skills", "FROM "+pgx.Identifier{"gf", schema.SearchTable(c.Tenant, c.Repo, c.ID)}.Sanitize(), 1)
	args := []any{query, c.Tenant, c.Repo, c.ID}
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
	e := s.Pool.QueryRow(ctx, `SELECT body FROM gf.skills WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 AND urn=$4 AND skill_revision=$5 AND status='active'`, c.Tenant, c.Repo, c.ID, urn, revision).Scan(&body)
	if errors.Is(e, pgx.ErrNoRows) {
		return "", fail(409, "revision_unavailable")
	}
	if e == nil {
		s.Uses.Add(1)
	}
	return string(body), e
}

// publishOptions is who a bundle is published for and under which policy.
//
// Tenant and repository are arguments rather than process state because the
// same writer serves two callers: the operator subcommand, which publishes for
// the configured tenant, and the publication worker, which publishes for the
// organisation whose import it just built (ADR-0001, module-boundaries-go).
type publishOptions struct {
	Tenant, Repo string
	// PolicySHA is the CLI revision this process serves. An empty value means
	// the caller has no configured policy source and accepts the bundle's own
	// `cli_sha256`; the reader then rejects a snapshot it cannot serve with
	// `snapshot_policy_mismatch`, so the check is never simply skipped.
	PolicySHA string
	// SnapshotPin refuses to publish anything but the pinned snapshot.
	SnapshotPin string
	// Activate moves gf.heads. The publication worker sets it only after
	// validation has passed.
	Activate bool
	Caps     schema.Capabilities
}

// publishOutcome names what a publication wrote.
type publishOutcome struct {
	SnapshotID     string
	Cards          int
	AlreadyPresent bool
	PolicySHA      string
	Revision       string
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
	tx, e := s.Pool.Begin(ctx)
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	out, e := publishBundle(ctx, tx, raw, publishOptions{Tenant: s.Tenant, Repo: s.Repo,
		PolicySHA: s.PolicySHA, SnapshotPin: s.SnapshotID, Activate: true, Caps: s.Caps})
	if e != nil {
		return e
	}
	if e = tx.Commit(ctx); e != nil {
		return e
	}
	b, _ := json.Marshal(M{"event": "snapshot_published", "snapshot": out.SnapshotID,
		"cards": out.Cards, "already_present": out.AlreadyPresent, "repo": s.Repo})
	fmt.Println(string(b))
	return nil
}

// publishBundle validates one `guidefold-service-snapshot-v1` envelope and
// writes it into the serving catalog inside the caller's transaction.
//
// Everything that can refuse the bundle runs before the first write: integrity,
// policy revision, repository, dimensions, the policy weights, card identity,
// the graph and the router index. Publication is the one place where a bad
// snapshot can still be stopped without anybody reading it.
func publishBundle(ctx context.Context, tx pgx.Tx, raw []byte, o publishOptions) (publishOutcome, error) {
	out, e := publishBundleInto(ctx, tx, raw, o)
	if e != nil {
		return publishOutcome{}, e
	}
	return out, nil
}

func publishBundleInto(ctx context.Context, tx pgx.Tx, raw []byte, o publishOptions) (publishOutcome, error) {
	var zero publishOutcome
	if len(raw) > 768*1024*1024 {
		return zero, fmt.Errorf("snapshot_too_large")
	}
	value, e := strictJSON(raw)
	if e != nil {
		return zero, e
	}
	envelope := obj(value)
	data := obj(envelope["snapshot"])
	if data == nil || str(data["format"]) != "guidefold-service-snapshot-v1" || str(envelope["sha256"]) != hash(canonical(data)) {
		return zero, fmt.Errorf("snapshot_integrity_mismatch")
	}
	policySHA := o.PolicySHA
	if policySHA == "" {
		// No configured policy source: the bundle's own CLI revision is stored,
		// and a server that serves a different one refuses to read the snapshot
		// rather than ranking it with the wrong policy.
		policySHA = str(data["cli_sha256"])
	}
	if str(data["cli_sha256"]) != policySHA {
		return zero, fmt.Errorf("snapshot_policy_mismatch")
	}
	if str(data["repo_id"]) != o.Repo {
		return zero, fmt.Errorf("snapshot_repo_mismatch")
	}
	nodes, cards, weights := obj(data["nodes"]), obj(data["cards"]), obj(data["weights"])
	if nodes["_root"] == nil || len(cards) == 0 || len(cards) > 100000 {
		return zero, fmt.Errorf("invalid_snapshot_dimensions")
	}
	// Bound the integer-only policy arithmetic. Unsupported operator configurations fail publication.
	for k, v := range weights {
		if k == "ppr_mode" || k == "abstain_mode" || k == "compose_mode" || k == "compose_coverage" {
			continue
		}
		n, ok := v.(json.Number)
		if !ok || strings.ContainsAny(n.String(), ".eE") || number(n) < 0 || number(n) > 1000000 {
			return zero, fmt.Errorf("unsupported_policy_weight_%s", k)
		}
	}
	if integer(weights, "closure_decay_den", 2) == 0 {
		return zero, fmt.Errorf("invalid_closure_denominator")
	}
	if m := text(weights, "ppr_mode", "closure"); m != "closure" && m != "pagerank" {
		return zero, fmt.Errorf("unsupported_ppr_mode")
	}
	if m := text(weights, "abstain_mode", "magnitude"); m != "magnitude" && m != "margin" {
		return zero, fmt.Errorf("unsupported_abstain_mode")
	}
	// compose_mode/compose_tau_pct/compose_coverage (ADR-0022 §4 / ADR-0024 §4): the composer
	// stage is not yet implemented in this service (DENSE-PROGRAM.md §4, family C, dev run
	// 2026-09-05 — no configuration froze), so this only validates shape/value for storage and
	// tier parity; it deliberately does not run composition. compose_tau_pct is a plain bounded
	// integer weight and needs no special case above. Under the shipped default
	// (compose_mode="off"), this service's behaviour (no composition) already matches the CLI's,
	// so ADR-0024 tier parity holds; a value of "on" is accepted for forward-storage but has no
	// runtime effect here yet — same shape as ppr_mode/abstain_mode before their own Go
	// implementation landed.
	if m := text(weights, "compose_mode", "off"); m != "off" && m != "on" {
		return zero, fmt.Errorf("unsupported_compose_mode")
	}
	if v, present := weights["compose_coverage"]; present {
		if _, ok := v.(bool); !ok {
			return zero, fmt.Errorf("unsupported_compose_coverage")
		}
	}
	id := "repository:" + str(envelope["sha256"])
	if o.SnapshotPin != "" && o.SnapshotPin != id {
		return zero, fmt.Errorf("snapshot_pin_mismatch")
	}
	// Generated proof records carry explicit placeholders until the publisher
	// knows the immutable snapshot and card revision. Bind those values before
	// the catalog is written. The envelope digest remains the import artifact's
	// integrity check; the proof fields are delivery metadata derived from it.
	bindAllProofPlaceholders(cards, id)
	check := &Catalog{Nodes: nodes, Cards: map[string]M{}}
	for _, u := range keys(cards) {
		card := obj(cards[u])
		if card == nil || str(card["urn"]) != u || nodes[str(card["node"])] == nil {
			return zero, fmt.Errorf("invalid_card_identity")
		}
		if _, ok := card["_body"].(string); !ok {
			return zero, fmt.Errorf("invalid_card_body")
		}
		check.Cards[u] = card
	}
	if e = graph.Validate(check.Cards); e != nil {
		return zero, e
	}
	if e = check.prepare(); e != nil {
		return zero, e
	}
	terms, e := compileRouterIndex(obj(envelope["router_index"]), cards, weights, str(envelope["sha256"]), policySHA, str(envelope["router_index_sha256"]))
	if e != nil {
		return zero, e
	}
	if _, e = tx.Exec(ctx, `SELECT pg_advisory_xact_lock(78350002)`); e != nil {
		return zero, e
	}
	var exists bool
	if e = tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM gf.snapshots WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3)`, o.Tenant, o.Repo, id).Scan(&exists); e != nil {
		return zero, e
	}
	if !exists {
		if _, e = tx.Exec(ctx, `INSERT INTO gf.snapshots(tenant,repo,snapshot_id,revision,cli_sha,nodes,weights) VALUES($1,$2,$3,$4,$5,$6,$7)`, o.Tenant, o.Repo, id, str(data["revision"]), policySHA, string(canonical(nodes)), string(canonical(weights))); e != nil {
			return zero, e
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
			values = append(values, []any{o.Tenant, o.Repo, id, u, cardRevision(card), str(card["node"]), text(card, "status", "active"), json.RawMessage(canonical(metadata)), []byte(body), strings.ReplaceAll(searchText, "\x00", " ")})
		}
		_, e = tx.CopyFrom(ctx, pgx.Identifier{"gf", "skills"}, []string{"tenant", "repo", "snapshot_id", "urn", "skill_revision", "node", "status", "metadata", "body", "search_text"}, pgx.CopyFromRows(values))
		if e != nil {
			return zero, e
		}
	}
	if e = schema.EnsureSearchIndex(ctx, tx, o.Caps, o.Tenant, o.Repo, id); e != nil {
		return zero, e
	}
	if e = ensureRouterIndex(ctx, tx, o.Tenant, o.Repo, id, str(envelope["router_index_sha256"]), terms, len(cards)); e != nil {
		return zero, e
	}
	if o.Activate {
		if e = activateSnapshot(ctx, tx, o.Tenant, o.Repo, id); e != nil {
			return zero, e
		}
	}
	return publishOutcome{SnapshotID: id, Cards: len(cards), AlreadyPresent: exists,
		PolicySHA: policySHA, Revision: str(data["revision"])}, nil
}
