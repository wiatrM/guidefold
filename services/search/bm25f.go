package main

import (
	"context"
	"encoding/binary"
	"fmt"
	"math/big"
	"sort"

	"github.com/jackc/pgx/v5"
)

const routerMigration = `
CREATE TABLE IF NOT EXISTS gf.router_indexes (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 index_sha text NOT NULL, n_docs integer NOT NULL, n_terms integer NOT NULL,
 PRIMARY KEY(tenant,repo,snapshot_id),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.snapshots(tenant,repo,snapshot_id)
);
CREATE TABLE IF NOT EXISTS gf.router_terms (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 term text NOT NULL, postings bytea NOT NULL,
 PRIMARY KEY(tenant,repo,snapshot_id,term),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.router_indexes(tenant,repo,snapshot_id)
);
INSERT INTO gf.schema_version VALUES (5) ON CONFLICT DO NOTHING;
`

var bm25Fields = []string{"name", "description", "digest", "triggers", "body"}

// Same fixed-point formula as Router._bm25_scores. The CLI provides the only
// floating-point build inputs (rounded IDF/norms). Arbitrary precision here
// preserves Python integer semantics even for unusually large field weights.
func weightedTF(weight, tf, norm int64) *big.Int {
	v := big.NewInt(weight)
	v.Mul(v, big.NewInt(tf))
	v.Lsh(v, 40)
	return v.Quo(v, big.NewInt(norm))
}
func termContribution(idf int64, wtf *big.Int) int64 {
	numerator := new(big.Int).Mul(big.NewInt(idf), wtf)
	denominator := new(big.Int).Add(big.NewInt(1258291), wtf) // round(1.2 * 2**20)
	return numerator.Quo(numerator, denominator).Int64()
}

type compiledTerm struct {
	term     string
	postings []byte
}

func compileRouterIndex(build M, cards M, weights M, snapshot, policy, indexSHA string) ([]compiledTerm, error) {
	if build == nil || str(build["format"]) != "guidefold-bm25f-build-v1" || str(build["snapshot_sha256"]) != snapshot || str(build["policy_sha256"]) != policy || hash(canonical(build)) != indexSHA {
		return nil, fmt.Errorf("router_index_integrity_mismatch")
	}
	order := stringList(build["order"])
	fields := stringList(build["fields"])
	if len(order) != len(cards) || len(fields) != len(bm25Fields) {
		return nil, fmt.Errorf("router_index_dimensions_mismatch")
	}
	want := keys(cards)
	for i, u := range order {
		if u != want[i] {
			return nil, fmt.Errorf("router_index_document_order_mismatch")
		}
	}
	norms := make([][]int64, len(fields))
	posts := make([]M, len(fields))
	for i, f := range fields {
		if f != bm25Fields[i] {
			return nil, fmt.Errorf("router_index_field_order_mismatch")
		}
		a := arr(obj(build["norms"])[f])
		if len(a) != len(order) {
			return nil, fmt.Errorf("invalid_router_norms")
		}
		for _, v := range a {
			n := number(v)
			if n < 1 {
				return nil, fmt.Errorf("invalid_router_norm")
			}
			norms[i] = append(norms[i], n)
		}
		posts[i] = obj(obj(build["postings"])[f])
		if posts[i] == nil {
			return nil, fmt.Errorf("invalid_router_postings")
		}
	}
	idfs := obj(build["idf"])
	out := make([]compiledTerm, 0, len(idfs))
	for _, t := range keys(idfs) {
		idf := number(idfs[t])
		ts := tokens(t)
		if idf < 0 || idf > 64*scale || len(ts) != 1 || ts[0] != t {
			return nil, fmt.Errorf("invalid_router_term")
		}
		weighted := map[int]*big.Int{}
		for f, post := range posts {
			seen := map[int]bool{}
			for _, v := range arr(post[t]) {
				pair := arr(v)
				if len(pair) != 2 {
					return nil, fmt.Errorf("invalid_router_posting")
				}
				doc, tf := number(pair[0]), number(pair[1])
				if doc < 0 || doc >= int64(len(order)) || tf <= 0 || seen[int(doc)] {
					return nil, fmt.Errorf("invalid_router_posting")
				}
				seen[int(doc)] = true
				w := integer(weights, "field."+fields[f], 0)
				contribution := weightedTF(w, tf, norms[f][doc])
				if weighted[int(doc)] == nil {
					weighted[int(doc)] = contribution
				} else {
					weighted[int(doc)].Add(weighted[int(doc)], contribution)
				}
			}
		}
		docs := make([]int, 0, len(weighted))
		for doc := range weighted {
			docs = append(docs, doc)
		}
		sort.Ints(docs)
		packed := make([]byte, len(docs)*12)
		for i, doc := range docs {
			binary.LittleEndian.PutUint32(packed[i*12:], uint32(doc))
			binary.LittleEndian.PutUint64(packed[i*12+4:], uint64(termContribution(idf, weighted[doc])))
		}
		out = append(out, compiledTerm{t, packed})
	}
	// A field term absent from the shared IDF table is malformed, not an OOV term.
	for _, p := range posts {
		for t := range p {
			if _, ok := idfs[t]; !ok {
				return nil, fmt.Errorf("router_posting_missing_idf")
			}
		}
	}
	return out, nil
}
func ensureRouterIndex(ctx context.Context, tx pgx.Tx, s *Store, id, indexSHA string, terms []compiledTerm, nDocs int) error {
	var old string
	e := tx.QueryRow(ctx, `SELECT index_sha FROM gf.router_indexes WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3`, s.Tenant, s.Repo, id).Scan(&old)
	if e == nil {
		if old != indexSHA {
			return fmt.Errorf("immutable_router_index_conflict")
		}
		return nil
	}
	if e != pgx.ErrNoRows {
		return e
	}
	if _, e = tx.Exec(ctx, `INSERT INTO gf.router_indexes(tenant,repo,snapshot_id,index_sha,n_docs,n_terms) VALUES($1,$2,$3,$4,$5,$6)`, s.Tenant, s.Repo, id, indexSHA, nDocs, len(terms)); e != nil {
		return e
	}
	rows := make([][]any, 0, len(terms))
	for _, t := range terms {
		rows = append(rows, []any{s.Tenant, s.Repo, id, t.term, t.postings})
	}
	_, e = tx.CopyFrom(ctx, pgx.Identifier{"gf", "router_terms"}, []string{"tenant", "repo", "snapshot_id", "term", "postings"}, pgx.CopyFromRows(rows))
	return e
}
func (s *Store) verifyRouterIndex(ctx context.Context, c *Catalog) error {
	var n int
	e := s.Pool.QueryRow(ctx, `SELECT index_sha,n_docs FROM gf.router_indexes WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3`, s.Tenant, s.Repo, c.ID).Scan(&c.RouterIndexSHA, &n)
	if e == pgx.ErrNoRows {
		return fail(503, "router_index_not_published")
	}
	if e != nil {
		return e
	}
	if n != len(c.Cards) {
		return fail(503, "router_index_count_mismatch")
	}
	return nil
}
func accumulatePostings(scores map[int]int64, packed []byte, nQuery int64, nDocs int, allowed func(int) bool) error {
	if len(packed)%12 != 0 {
		return fmt.Errorf("invalid_packed_router_postings")
	}
	for i := 0; i < len(packed); i += 12 {
		doc := int(binary.LittleEndian.Uint32(packed[i:]))
		score := binary.LittleEndian.Uint64(packed[i+4:])
		if doc >= nDocs || score > uint64(64*scale) {
			return fmt.Errorf("invalid_packed_router_posting")
		}
		if allowed(doc) {
			scores[doc] += int64(score) * nQuery
		} // zero scores still enter CLI candidate set
	}
	return nil
}
func (s *Store) routerSearch(ctx context.Context, c *Catalog, query string, allowed map[string]bool) ([]Candidate, error) {
	return s.routerCandidates(ctx, c, query, allowed, 50)
}
func (s *Store) routerCandidates(ctx context.Context, c *Catalog, query string, allowed map[string]bool, limit int, rankCapture ...[]uint32) ([]Candidate, error) {
	frequencies := map[string]int64{}
	for _, t := range tokens(query) {
		frequencies[t]++
	}
	if len(frequencies) == 0 || len(allowed) == 0 {
		return []Candidate{}, nil
	}
	rows, e := s.Pool.Query(ctx, `SELECT term,postings FROM gf.router_terms WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 AND term=ANY($4::text[])`, s.Tenant, s.Repo, c.ID, keys(frequencies))
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	scores := map[int]int64{}
	for rows.Next() {
		var term string
		var packed []byte
		if e = rows.Scan(&term, &packed); e != nil {
			return nil, e
		}
		if e = accumulatePostings(scores, packed, frequencies[term], len(c.Order), func(doc int) bool { return allowed[c.Order[doc]] }); e != nil {
			return nil, e
		}
	}
	if e = rows.Err(); e != nil {
		return nil, e
	}
	s.Searches.Add(1)
	docs := make([]int, 0, len(scores))
	for doc := range scores {
		docs = append(docs, doc)
	}
	sort.Slice(docs, func(i, j int) bool {
		a, b := docs[i], docs[j]
		if scores[a] != scores[b] {
			return scores[a] > scores[b]
		}
		return a < b
	})
	if len(rankCapture) != 0 {
		if len(rankCapture[0]) != len(c.Order) {
			return nil, fmt.Errorf("invalid_rank_capture_dimensions")
		}
		for rank, doc := range docs {
			rankCapture[0][doc] = uint32(rank + 1)
		}
	}
	if limit > 0 && len(docs) > limit {
		docs = docs[:limit]
	}
	out := make([]Candidate, 0, len(docs))
	for rank, doc := range docs {
		out = append(out, Candidate{URN: c.Order[doc], BM25Rank: rank + 1})
	}
	return out, nil
}
func (s *Store) backendName() string {
	if s != nil && s.Dense != nil {
		if s.Dense.Mode == "dense" {
			return "skillret_tei_dense_v1"
		}
		return "router_bm25f_skillret_tei_rrf_v1"
	}
	if s != nil && s.LexicalEngine == "paradedb-experimental" {
		return "paradedb_bm25_v1"
	}
	return "router_bm25f_v1"
}
