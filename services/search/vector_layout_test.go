package main

import (
	"context"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"
)

// Explicit integration benchmark against the two disposable vector-layout projects.
// Ordinary CI skips it. It exercises the production pool and denseSearch function,
// with fixed document vectors instead of a live encoder: no GPU or quality claim.
func TestPersistentVectorLayout(t *testing.T) {
	if os.Getenv("GUIDEFOLD_VECTOR_LAYOUT_TEST") != "1" {
		t.Skip("isolated database benchmark only")
	}
	layout := os.Getenv("GUIDEFOLD_PROBE_LAYOUT")
	if (layout != "external" && layout != "inline") || os.Getenv("PGHOST") != "guidefold-vector-"+layout+"-db-1" {
		t.Fatal("only isolated benchmark databases are allowed")
	}
	output := os.Getenv("GUIDEFOLD_PROBE_OUTPUT")
	if !strings.HasPrefix(output, "/repo/.guidefold/checks/sql-") || strings.Contains(output, "..") || !strings.HasSuffix(output, ".json") {
		t.Fatal("invalid probe output")
	}
	raw, err := os.ReadFile("/repo/.guidefold/compose/benchmark-embeddings-full.json")
	if err != nil {
		t.Fatal(err)
	}
	value, err := strictJSON(raw)
	if err != nil {
		t.Fatal(err)
	}
	envelope := obj(value)
	data := obj(envelope["embeddings"])
	vectors := obj(data["vectors"])
	if hash(canonical(data)) != str(envelope["sha256"]) || len(vectors) != 6006 || str(data["repo_id"]) != "skillret-service-bench" {
		t.Fatal("unexpected benchmark bundle")
	}
	ctx := context.Background()
	pool, err := openPool(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	c := &Catalog{ID: str(data["snapshot_id"]), Cards: map[string]M{}, Order: keys(vectors)}
	allowed := map[string]bool{}
	for _, u := range c.Order {
		c.Cards[u] = M{}
		allowed[u] = true
	}
	s := &Store{Pool: pool, Tenant: "local", Repo: "skillret-service-bench", Dense: &DenseClient{ID: hash(canonical(data["encoder"]))}}
	var count int
	var storage, storedDigest string
	err = pool.QueryRow(ctx, `SELECT count(*),md5(string_agg(urn||':'||md5(embedding::text),'' ORDER BY urn COLLATE "C")) FROM gf.embeddings WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 AND encoder_id=$4`, s.Tenant, s.Repo, c.ID, s.Dense.ID).Scan(&count, &storedDigest)
	if err != nil || count != 6006 {
		t.Fatalf("unexpected catalog: %d %v", count, err)
	}
	err = pool.QueryRow(ctx, `SELECT attstorage FROM pg_attribute WHERE attrelid='gf.embeddings'::regclass AND attname='embedding'`).Scan(&storage)
	if err != nil || (layout == "external" && storage != "e") || (layout == "inline" && storage != "p") {
		t.Fatalf("layout mismatch: %s %v", storage, err)
	}
	sparse := make([]Candidate, 50)
	for i := range sparse {
		sparse[i] = Candidate{URN: c.Order[i], BM25Rank: i + 1}
	}
	inputs := make([][]float32, 200)
	for i := range inputs {
		b, e := base64.StdEncoding.DecodeString(str(obj(vectors[c.Order[i*len(c.Order)/200]])["f32le"]))
		if e != nil || len(b) != 4096 {
			t.Fatal("invalid source vector")
		}
		v := make([]float32, 1024)
		for j := range v {
			v[j] = math.Float32frombits(binary.LittleEndian.Uint32(b[j*4:]))
		}
		inputs[i] = v
	}
	invoke := func(i int) M {
		start := time.Now()
		request, cancel := context.WithTimeout(ctx, 5*time.Second)
		defer cancel()
		rows, e := s.denseSearch(request, c, inputs[i], allowed, sparse)
		elapsedMS := float64(time.Since(start).Microseconds()) / 1000
		result := M{"query_id": fmt.Sprintf("document-vector-%03d", i), "elapsed_ms": elapsedMS, "ok": e == nil, "ranked_sha256": hash(canonical(rows))}
		if e != nil {
			result["error"] = e.Error()
		}
		return result
	}
	for i := 0; i < 20; i++ {
		if !invoke(i)["ok"].(bool) {
			t.Fatal("warmup failed")
		}
	}
	result := M{"kind": "production_denseSearch_persistent_layout", "layout": layout, "snapshot": c.ID, "encoder_id": s.Dense.ID, "vectors": count, "stored_vector_digest": storedDigest, "query_vectors": "200 evenly spaced published document vectors; not natural-language queries", "sparse_union": "first 50 catalog URNs; fixed across both layouts", "gpu_used": false, "quality_evaluated": false, "resources_isolated": false, "production_ready": false}
	arms := M{}
	for _, concurrency := range []int{1, 4} {
		rows := make([]M, 200)
		jobs := make(chan int)
		var wg sync.WaitGroup
		started := time.Now()
		for j := 0; j < concurrency; j++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for i := range jobs {
					rows[i] = invoke(i)
				}
			}()
		}
		for i := range rows {
			jobs <- i
		}
		close(jobs)
		wg.Wait()
		times := []float64{}
		ok := 0
		for _, r := range rows {
			if r["ok"].(bool) {
				ok++
				times = append(times, r["elapsed_ms"].(float64))
			}
		}
		sort.Float64s(times)
		summary := M{}
		if len(times) > 0 {
			for _, p := range []int{50, 95, 99} {
				summary[fmt.Sprintf("p%d", p)] = times[int(math.Ceil(float64(len(times))*float64(p)/100))-1]
			}
		}
		arm := M{"attempted": len(rows), "ok": ok, "concurrency": concurrency, "wall_seconds": time.Since(started).Seconds(), "database_ms": summary, "rows": rows}
		arms[fmt.Sprintf("c%d", concurrency)] = arm
		brief := M{}
		for k, v := range arm {
			if k != "rows" {
				brief[k] = v
			}
		}
		text, _ := json.Marshal(brief)
		t.Log(string(text))
	}
	result["arms"] = arms
	file, err := os.OpenFile(output, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		t.Fatal(err)
	}
	enc := json.NewEncoder(file)
	enc.SetIndent("", "  ")
	err = enc.Encode(result)
	closeErr := file.Close()
	if err != nil {
		t.Fatal(err)
	}
	if closeErr != nil {
		t.Fatal(closeErr)
	}
	for _, a := range arms {
		if obj(a)["ok"].(int) != 200 {
			t.Fatal("database requests failed; see artifact")
		}
	}
}
