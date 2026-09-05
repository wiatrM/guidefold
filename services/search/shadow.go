package main

import (
	"context"
	"fmt"
	"log/slog"
	"sort"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5"
)

const shadowMigration = `
CREATE TABLE IF NOT EXISTS gf.search_shadow (
 tenant_id text NOT NULL, search_id text NOT NULL, repo text NOT NULL,
 snapshot_id text NOT NULL, encoder_id text NOT NULL, status text NOT NULL,
 sparse_ranked bytea NOT NULL, hybrid_ranked bytea NOT NULL,
 selected bytea NOT NULL, hybrid_selected bytea NOT NULL,
 timings jsonb NOT NULL, error text,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,search_id)
);
CREATE INDEX IF NOT EXISTS search_shadow_created ON gf.search_shadow(created_at);
INSERT INTO gf.schema_version VALUES (8) ON CONFLICT DO NOTHING;
`

// Per-request immutable work reused only by this request's shadow. No query cache.
type PreparedScope struct {
	Allowed []bool
	Drops   int
	Top     []Candidate
	Ranks   []uint32 // Dense document ordinal -> full BM25 rank; zero means absent.
}

func prepareScope(c *Catalog, allowed map[string]bool, drops int) PreparedScope {
	p := PreparedScope{Allowed: make([]bool, len(c.Order)), Drops: drops, Ranks: make([]uint32, len(c.Order))}
	for i, u := range c.Order {
		p.Allowed[i] = allowed[u]
	}
	return p
}
func (p PreparedScope) allowed(c *Catalog) map[string]bool {
	out := make(map[string]bool, len(c.Order))
	for i, yes := range p.Allowed {
		if yes {
			out[c.Order[i]] = true
		}
	}
	return out
}
func fusePrepared(c *Catalog, p PreparedScope, dense []Candidate) []Candidate {
	sparse := append([]Candidate(nil), p.Top...)
	for _, row := range dense {
		doc := sort.SearchStrings(c.Order, row.URN)
		if doc < len(c.Order) && c.Order[doc] == row.URN && p.Ranks[doc] > 50 {
			sparse = append(sparse, Candidate{URN: row.URN, BM25Rank: int(p.Ranks[doc])})
		}
	}
	return fuseCandidates(sparse, dense)
}

type SparsePreparation struct {
	Snapshot, QueryDigest string
	Scopes                map[string]PreparedScope
}

func (p *SparsePreparation) verify(c *Catalog, query string, scopes []string) error {
	if p.Snapshot != c.ID || p.QueryDigest != hash([]byte(query)) {
		return fmt.Errorf("shadow_preparation_mismatch")
	}
	for _, node := range scopes {
		if _, ok := p.Scopes[node]; !ok {
			return fmt.Errorf("shadow_preparation_scope_mismatch")
		}
	}
	return nil
}

type ShadowJob struct {
	SearchID               string
	Catalog                *Catalog
	Payload                M // Ephemeral request only; query/path text is never persisted.
	SparseRanked, Selected []M
	SparseTimings          M
	Enqueued               time.Time
	Preparation            *SparsePreparation
}
type ShadowWorker struct {
	Store                                 *Store
	Dense                                 *DenseClient
	Queue                                 chan ShadowJob
	Context                               context.Context
	WG                                    sync.WaitGroup
	Submitted, Completed, Failed, Dropped atomic.Uint64
	Process                               func(ShadowJob)
}

func newShadowWorker(ctx context.Context, s *Store) (*ShadowWorker, error) {
	d, e := newDenseClientMode("hybrid")
	if e != nil {
		return nil, e
	}
	// Shadow is off the response path. Its independent encode budget accommodates
	// cold scheduling without relaxing the experimental inline 250 ms deadline.
	d.EncodeTimeout = time.Second
	capacity, e := strconv.Atoi(env("GUIDEFOLD_SHADOW_QUEUE_CAPACITY", "128"))
	if e != nil || capacity < 1 || capacity > 256 {
		return nil, fmt.Errorf("invalid_shadow_queue_capacity")
	}
	worker := &ShadowWorker{Store: s, Dense: d, Queue: make(chan ShadowJob, capacity), Context: ctx}
	worker.Process = worker.process
	worker.start(4)
	return worker, nil
}
func (w *ShadowWorker) start(n int) {
	for i := 0; i < n; i++ {
		w.WG.Add(1)
		go func() {
			defer w.WG.Done()
			for {
				select {
				case <-w.Context.Done():
					return
				case job := <-w.Queue:
					w.Process(job)
				}
			}
		}()
	}
}
func (w *ShadowWorker) submit(job ShadowJob) {
	job.Enqueued = time.Now()
	select {
	case <-w.Context.Done():
		w.Dropped.Add(1)
	case w.Queue <- job:
		w.Submitted.Add(1)
	default:
		w.Dropped.Add(1)
		slog.Warn("shadow_queue_full", "search_id", job.SearchID)
	}
}

// The sparse response is delivered before a nonblocking enqueue. No worker can
// amend its already-serialized bytes, insert neural cards or delay on GPU work.
func deliverThenShadow(deliver func(), w *ShadowWorker, job *ShadowJob) {
	deliver()
	if w != nil && job != nil && job.SearchID != "" {
		w.submit(*job)
	}
}
func compactRanks(scored []Candidate, limit int) []M {
	rows := []M{}
	for i, row := range scored {
		if i >= limit {
			break
		}
		rows = append(rows, M{"urn": row.URN, "score": row.Score})
	}
	return rows
}
func compactCards(cards []M) []M {
	rows := []M{}
	for _, card := range cards {
		rows = append(rows, M{"urn": card["urn"], "revision": card["revision"]})
	}
	return rows
}
func copyMetrics(value M) M {
	out := M{}
	for k, v := range value {
		out[k] = v
	}
	return out
}
func (w *ShadowWorker) process(job ShadowJob) {
	started := time.Now()
	ctx, cancel := context.WithTimeout(w.Context, 2*time.Second)
	defer cancel()
	clone := *job.Catalog // Maps/index metadata are immutable; DensePrompt is per-copy.
	s := &Store{Pool: w.Store.Pool, Tenant: w.Store.Tenant, Repo: w.Store.Repo,
		PolicySHA: w.Store.PolicySHA, Version: w.Store.Version, LexicalEngine: "router", Dense: w.Dense}
	capture := &ShadowJob{}
	var response M
	e := w.Dense.ready(ctx)
	if e == nil {
		e = w.Dense.verifyCatalog(ctx, s, &clone)
	}
	if e == nil {
		response, e = s.searchCatalog(ctx, &clone, job.Payload, M{"catalog": float64(0)}, capture, job.Preparation)
	}
	status := "ok"
	var reason any
	if e != nil {
		status = "error"
		reason = "shadow_backend_unavailable"
		w.Failed.Add(1)
	} else {
		w.Completed.Add(1)
	}
	ranked, selected := []M{}, []M{}
	hybridTimings := M{}
	if response != nil {
		ranked = capture.SparseRanked
		selected = compactCards(arrM(response["cards"]))
		hybridTimings = obj(response["stages_ms"])
	}
	timings := M{"queue_ms": float64(started.Sub(job.Enqueued).Microseconds()) / 1000,
		"compute_ms": elapsed(started), "sparse": job.SparseTimings, "hybrid": hybridTimings,
		"reused_sparse_preparation": job.Preparation != nil, "encoder_batch_requests": w.Dense.BatchRequests}
	persist, persistCancel := context.WithTimeout(w.Context, time.Second)
	defer persistCancel()
	tx, err := s.Pool.BeginTx(persist, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if err == nil {
		defer tx.Rollback(persist)
		_, err = tx.Exec(persist, `INSERT INTO gf.search_shadow(tenant_id,search_id,repo,snapshot_id,encoder_id,status,sparse_ranked,hybrid_ranked,selected,hybrid_selected,timings,error) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) ON CONFLICT(tenant_id,search_id) DO NOTHING`, s.Tenant, job.SearchID, s.Repo, clone.ID, w.Dense.ID, status, canonical(job.SparseRanked), canonical(ranked), canonical(job.Selected), canonical(selected), string(canonical(timings)), reason)
		if err == nil {
			err = tx.Commit(persist)
		}
	}
	if err != nil {
		w.Dropped.Add(1)
		slog.Warn("shadow_record_unavailable", "search_id", job.SearchID)
	}
}
func (s *Store) exportShadow(ctx context.Context, id string) (M, error) {
	var snapshot, encoder, status string
	var sparse, hybrid, selected, hybridSelected, timings []byte
	var reason *string
	e := s.Pool.QueryRow(ctx, `SELECT snapshot_id,encoder_id,status,sparse_ranked,hybrid_ranked,selected,hybrid_selected,timings,error FROM gf.search_shadow WHERE tenant_id=$1 AND search_id=$2`, s.Tenant, id).Scan(&snapshot, &encoder, &status, &sparse, &hybrid, &selected, &hybridSelected, &timings, &reason)
	if e != nil {
		return nil, e
	}
	out := M{"search_id": id, "tenant_id": s.Tenant, "snapshot": snapshot, "encoder_id": encoder, "status": status, "error": reason}
	for k, raw := range map[string][]byte{"sparse_ranked": sparse, "hybrid_ranked": hybrid, "selected": selected, "hybrid_selected": hybridSelected, "timings": timings} {
		v, err := strictJSON(raw)
		if err != nil {
			return nil, fmt.Errorf("invalid_shadow_record")
		}
		out[k] = v
	}
	rows, err := s.Pool.Query(ctx, `SELECT event_type,count(*) FROM gf.events WHERE tenant_id=$1 AND search_id=$2 GROUP BY event_type`, s.Tenant, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	counts := M{}
	for rows.Next() {
		var kind string
		var n int64
		if err = rows.Scan(&kind, &n); err != nil {
			return nil, err
		}
		counts[kind] = n
	}
	if err = rows.Err(); err != nil {
		return nil, err
	}
	out["joined_event_counts"] = counts
	return out, nil
}
