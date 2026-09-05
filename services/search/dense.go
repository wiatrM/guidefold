package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5"
)

const denseMigration = `
CREATE TABLE IF NOT EXISTS gf.embedding_sets (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 encoder_id text NOT NULL, manifest jsonb NOT NULL, bundle_sha text NOT NULL,
 n_vectors integer NOT NULL CHECK(n_vectors>0),
 PRIMARY KEY(tenant,repo,snapshot_id,encoder_id),
 FOREIGN KEY(tenant,repo,snapshot_id) REFERENCES gf.snapshots(tenant,repo,snapshot_id)
);
CREATE TABLE IF NOT EXISTS gf.embeddings (
 tenant text NOT NULL, repo text NOT NULL, snapshot_id text NOT NULL,
 encoder_id text NOT NULL, urn text NOT NULL, skill_revision text NOT NULL,
 embedding vector(1024) NOT NULL,
 PRIMARY KEY(tenant,repo,snapshot_id,encoder_id,urn),
 FOREIGN KEY(tenant,repo,snapshot_id,encoder_id) REFERENCES gf.embedding_sets(tenant,repo,snapshot_id,encoder_id),
 FOREIGN KEY(tenant,repo,snapshot_id,urn) REFERENCES gf.skills(tenant,repo,snapshot_id,urn)
);
INSERT INTO gf.schema_version VALUES (6) ON CONFLICT DO NOTHING;
`

// TEI owns the GPU and token-based dynamic batch queue. No model or query cache
// lives in the Go process. The deployment supplies a content-addressed encoder ID.
type DenseClient struct {
	URL, ID, Mode string
	HTTP          *http.Client
	Calls         atomic.Uint64
	Searches      atomic.Uint64
}

func newDenseClient() (*DenseClient, error) {
	mode := env("GUIDEFOLD_RETRIEVAL_MODE", "sparse")
	if mode == "sparse" {
		return nil, nil
	}
	if mode != "hybrid" && mode != "dense" {
		return nil, fmt.Errorf("invalid_retrieval_mode")
	}
	raw := env("GUIDEFOLD_TEI_URL", "")
	u, e := url.Parse(raw)
	if e != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
		return nil, fmt.Errorf("invalid_tei_url")
	}
	id := env("GUIDEFOLD_ENCODER_ID", "")
	if len(id) != 64 || strings.Trim(id, "0123456789abcdef") != "" {
		return nil, fmt.Errorf("invalid_encoder_id")
	}
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.MaxIdleConnsPerHost = 16
	transport.MaxConnsPerHost = 16
	return &DenseClient{URL: strings.TrimRight(raw, "/"), ID: id, Mode: mode,
		HTTP: &http.Client{Transport: transport, Timeout: 2 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}, nil
}
func (d *DenseClient) request(ctx context.Context, path string, payload any) ([]byte, error) {
	var body io.Reader
	method := http.MethodGet
	if payload != nil {
		raw, e := json.Marshal(payload)
		if e != nil {
			return nil, e
		}
		body = bytes.NewReader(raw)
		method = http.MethodPost
	}
	req, e := http.NewRequestWithContext(ctx, method, d.URL+path, body)
	if e != nil {
		return nil, e
	}
	req.Header.Set("Content-Type", "application/json")
	r, e := d.HTTP.Do(req)
	if e != nil {
		return nil, e
	}
	defer r.Body.Close()
	if r.StatusCode != 200 {
		return nil, fail(503, "dense_worker_unavailable")
	}
	raw, e := io.ReadAll(io.LimitReader(r.Body, 128*1024+1))
	if e != nil {
		return nil, e
	}
	if len(raw) > 128*1024 {
		return nil, fail(503, "invalid_dense_response")
	}
	return raw, nil
}
func (d *DenseClient) ready(ctx context.Context) error {
	raw, e := d.request(ctx, "/info", nil)
	if e != nil {
		return e
	}
	var info struct {
		ServedModelName string `json:"served_model_name"`
		ModelDtype      string `json:"model_dtype"`
		MaxInputLength  int    `json:"max_input_length"`
		ModelType       struct {
			Embedding struct {
				Pooling string `json:"pooling"`
			} `json:"embedding"`
		} `json:"model_type"`
	}
	if json.Unmarshal(raw, &info) != nil || info.ServedModelName != d.ID || info.ModelDtype != "float16" || info.MaxInputLength != 8192 || info.ModelType.Embedding.Pooling != "last_token" {
		return fail(503, "dense_worker_identity_mismatch")
	}
	_, e = d.request(ctx, "/health", nil)
	return e
}
func validVector(v []float32) bool {
	if len(v) != 1024 {
		return false
	}
	var n float64
	for _, x := range v {
		f := float64(x)
		if math.IsNaN(f) || math.IsInf(f, 0) {
			return false
		}
		n += f * f
	}
	return math.Abs(n-1) < .002
}
func (d *DenseClient) encode(ctx context.Context, query, prompt string) ([]float32, error) {
	d.Calls.Add(1)
	raw, e := d.request(ctx, "/embed", M{"inputs": []string{prompt + query}, "normalize": true, "truncate": false})
	if e != nil {
		return nil, e
	}
	var rows [][]float32
	if json.Unmarshal(raw, &rows) != nil || len(rows) != 1 || !validVector(rows[0]) {
		return nil, fail(503, "invalid_dense_response")
	}
	return rows[0], nil
}
func (d *DenseClient) verifyCatalog(ctx context.Context, s *Store, c *Catalog) error {
	var raw []byte
	var n int
	e := s.Pool.QueryRow(ctx, `SELECT manifest,n_vectors FROM gf.embedding_sets WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 AND encoder_id=$4`, s.Tenant, s.Repo, c.ID, d.ID).Scan(&raw, &n)
	if e == pgx.ErrNoRows {
		return fail(503, "snapshot_embeddings_unavailable")
	}
	if e != nil {
		return e
	}
	v, e := strictJSON(raw)
	if e != nil {
		return e
	}
	manifest := obj(v)
	if n != len(c.Cards) || hash(canonical(manifest)) != d.ID || !validEncoderManifest(manifest) {
		return fail(503, "snapshot_encoder_mismatch")
	}
	// Store the immutable prompt on the catalog, not the shared client; this is
	// also safe while two requests load a newly published snapshot.
	c.DensePrompt = str(manifest["query_prompt"])
	return nil
}
func validEncoderManifest(m M) bool {
	return str(m["format"]) == "guidefold-encoder-v1" && str(m["model_id"]) == "ThakiCloud/SKILLRET-Embedding-0.6B" &&
		str(m["revision"]) == "0e10886e80a0aacc9efddc28282a258e2ab7eae1" &&
		str(m["weights_sha256"]) == "f73118cac018ffa7ebb5a1ffbdf82034490dfb7f2559558f1e79277f1e8de172" &&
		str(m["query_prompt"]) == "Instruct: Given a skill search query, retrieve relevant skills that match the query\nQuery: " &&
		str(m["document_format"]) == "name | description | skill_md-stripped-v1" &&
		str(m["dtype"]) == "float16" && str(m["pooling"]) == "last_token" &&
		integer(m, "dimensions", 0) == 1024 && integer(m, "max_length", 0) == 8192 && m["normalize"] == true
}
func (s *Store) denseSearch(ctx context.Context, c *Catalog, v []float32, allowed map[string]bool, sparse []Candidate) ([]Candidate, error) {
	if len(allowed) == 0 {
		return []Candidate{}, nil
	}
	if !validVector(v) {
		return nil, fmt.Errorf("invalid_query_vector")
	}
	raw, _ := json.Marshal(v)
	// Exact cosine search: scope/status/negative filters apply before top-k.
	// The B-tree prefix isolates the immutable embedding set. ANN is not needed
	// for the measured 6k/10k pools, and would introduce a separate recall gate.
	sql := `WITH ranked AS (SELECT urn,row_number() OVER (ORDER BY embedding <=> $5::vector,urn COLLATE "C" ASC) AS dense_rank FROM gf.embeddings WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 AND encoder_id=$4`
	args := []any{s.Tenant, s.Repo, c.ID, s.Dense.ID, string(raw)}
	if len(allowed) != len(c.Cards) {
		args = append(args, keys(allowed))
		sql += fmt.Sprintf(` AND urn=ANY($%d::text[])`, len(args))
	}
	sparseTop := []string{}
	for i, x := range sparse {
		if i == 50 {
			break
		}
		sparseTop = append(sparseTop, x.URN)
	}
	args = append(args, sparseTop)
	sql += fmt.Sprintf(`) SELECT urn,dense_rank FROM ranked WHERE dense_rank<=50 OR urn=ANY($%d::text[]) ORDER BY dense_rank`, len(args))
	rows, e := s.Pool.Query(ctx, sql, args...)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []Candidate{}
	for rows.Next() {
		var u string
		var rank int
		if e = rows.Scan(&u, &rank); e != nil {
			return nil, e
		}
		out = append(out, Candidate{URN: u, DenseRank: rank})
	}
	if e = rows.Err(); e == nil {
		s.Dense.Searches.Add(1)
	}
	return out, e
}

// Preserve each channel's full rank for members of the top-50 union, including
// a sparse rank >50 for a dense candidate and vice versa (CLI RRF semantics).
func fuseCandidates(sparse, dense []Candidate) []Candidate {
	all := map[string]Candidate{}
	ranks := map[string]int{}
	for i, x := range sparse {
		ranks[x.URN] = x.BM25Rank
		if i < 50 {
			all[x.URN] = x
		}
	}
	for _, x := range dense {
		v := all[x.URN]
		v.URN = x.URN
		v.BM25Rank = ranks[x.URN]
		v.DenseRank = x.DenseRank
		all[x.URN] = v
	}
	out := make([]Candidate, 0, len(all))
	for _, u := range keys(all) {
		out = append(out, all[u])
	}
	return out
}

func publishEmbeddings(ctx context.Context, s *Store, path string) error {
	st, e := os.Stat(path)
	if e != nil {
		return e
	}
	if st.Size() > 768*1024*1024 {
		return fmt.Errorf("embedding_bundle_too_large")
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
	data := obj(envelope["embeddings"])
	if data == nil || str(data["format"]) != "guidefold-embeddings-v1" || hash(canonical(data)) != str(envelope["sha256"]) {
		return fmt.Errorf("embedding_integrity_mismatch")
	}
	manifest := obj(data["encoder"])
	encoderID := hash(canonical(manifest))
	if !validEncoderManifest(manifest) || str(data["repo_id"]) != s.Repo {
		return fmt.Errorf("embedding_identity_mismatch")
	}
	id := str(data["snapshot_id"])
	vectors := obj(data["vectors"])
	if len(vectors) == 0 || len(vectors) > 100000 {
		return fmt.Errorf("invalid_embedding_count")
	}
	tx, e := s.Pool.Begin(ctx)
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `SELECT pg_advisory_xact_lock(78350003)`); e != nil {
		return e
	}
	var n int
	if e = tx.QueryRow(ctx, `SELECT count(*) FROM gf.skills WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3`, s.Tenant, s.Repo, id).Scan(&n); e != nil {
		return e
	}
	if n != len(vectors) {
		return fmt.Errorf("embedding_snapshot_count_mismatch")
	}
	rows, e := tx.Query(ctx, `SELECT urn,skill_revision FROM gf.skills WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3`, s.Tenant, s.Repo, id)
	if e != nil {
		return e
	}
	revs := map[string]string{}
	for rows.Next() {
		var u, r string
		if e = rows.Scan(&u, &r); e != nil {
			rows.Close()
			return e
		}
		revs[u] = r
	}
	rows.Close()
	if e = rows.Err(); e != nil {
		return e
	}
	values := make([][]any, 0, len(vectors))
	for _, u := range keys(vectors) {
		row := obj(vectors[u])
		revision := str(row["revision"])
		if revs[u] == "" || revs[u] != revision {
			return fmt.Errorf("embedding_skill_revision_mismatch")
		}
		b, e := base64.StdEncoding.DecodeString(str(row["f32le"]))
		if e != nil || len(b) != 4096 {
			return fmt.Errorf("invalid_embedding_bytes")
		}
		v := make([]float32, 1024)
		for i := range v {
			v[i] = math.Float32frombits(binary.LittleEndian.Uint32(b[i*4:]))
		}
		if !validVector(v) {
			return fmt.Errorf("invalid_embedding_vector")
		}
		// COPY uses a portable text representation; pgvector stores float32.
		encoded, _ := json.Marshal(v)
		values = append(values, []any{s.Tenant, s.Repo, id, encoderID, u, revision, string(encoded)})
	}
	var oldSHA string
	e = tx.QueryRow(ctx, `SELECT bundle_sha FROM gf.embedding_sets WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 AND encoder_id=$4`, s.Tenant, s.Repo, id, encoderID).Scan(&oldSHA)
	if e == nil {
		if oldSHA != str(envelope["sha256"]) {
			return fmt.Errorf("immutable_embedding_set_conflict")
		}
		fmt.Println(`{"event":"embeddings_already_published"}`)
		return nil
	}
	if e != pgx.ErrNoRows {
		return e
	}
	if _, e = tx.Exec(ctx, `INSERT INTO gf.embedding_sets(tenant,repo,snapshot_id,encoder_id,manifest,bundle_sha,n_vectors) VALUES($1,$2,$3,$4,$5,$6,$7)`, s.Tenant, s.Repo, id, encoderID, string(canonical(manifest)), str(envelope["sha256"]), n); e != nil {
		return e
	}
	// A temporary text column avoids requiring a driver codec for pgvector COPY.
	if _, e = tx.Exec(ctx, `CREATE TEMP TABLE embedding_import (tenant text,repo text,snapshot_id text,encoder_id text,urn text,skill_revision text,embedding text) ON COMMIT DROP`); e != nil {
		return e
	}
	_, e = tx.CopyFrom(ctx, pgx.Identifier{"embedding_import"}, []string{"tenant", "repo", "snapshot_id", "encoder_id", "urn", "skill_revision", "embedding"}, pgx.CopyFromRows(values))
	if e != nil {
		return e
	}
	if _, e = tx.Exec(ctx, `INSERT INTO gf.embeddings SELECT tenant,repo,snapshot_id,encoder_id,urn,skill_revision,embedding::vector FROM embedding_import`); e != nil {
		return e
	}
	if e = tx.Commit(ctx); e != nil {
		return e
	}
	out, _ := json.Marshal(M{"event": "embeddings_published", "snapshot": id, "encoder_id": encoderID, "vectors": n})
	fmt.Println(string(out))
	return nil
}
