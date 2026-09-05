package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestTEIIdentityAndVectorValidation(t *testing.T) {
	id := strings.Repeat("a", 64)
	var mode atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/info":
			name := id
			if mode.Load() == 1 {
				name = "wrong"
			}
			_ = json.NewEncoder(w).Encode(M{"served_model_name": name, "model_dtype": "float16", "max_input_length": 8192, "max_batch_requests": 1, "model_type": M{"embedding": M{"pooling": "last_token"}}})
		case "/health":
			w.WriteHeader(200)
		case "/embed":
			var p struct {
				Inputs    []string `json:"inputs"`
				Normalize bool     `json:"normalize"`
				Truncate  bool     `json:"truncate"`
			}
			if json.NewDecoder(r.Body).Decode(&p) != nil || len(p.Inputs) != 1 || p.Inputs[0] != "prefix: query" || !p.Normalize || p.Truncate {
				t.Error("incorrect encoder request")
			}
			switch mode.Load() {
			case 2:
				_ = json.NewEncoder(w).Encode([][]float32{{1, 0}})
			case 3:
				w.WriteHeader(429)
			case 4:
				<-r.Context().Done()
			default:
				v := make([]float32, 1024)
				v[0] = 1
				_ = json.NewEncoder(w).Encode([][]float32{v})
			}
		default:
			w.WriteHeader(404)
		}
	}))
	defer server.Close()
	t.Setenv("GUIDEFOLD_RETRIEVAL_MODE", "hybrid")
	t.Setenv("GUIDEFOLD_TEI_URL", server.URL)
	t.Setenv("GUIDEFOLD_ENCODER_ID", id)
	client, e := newDenseClient()
	if e != nil {
		t.Fatal(e)
	}
	if e = client.ready(context.Background()); e != nil {
		t.Fatal(e)
	}
	v, e := client.encode(context.Background(), "query", "prefix: ")
	if e != nil || len(v) != 1024 {
		t.Fatal("valid vector rejected", e)
	}
	client.BatchRequests = 16
	if client.ready(context.Background()) == nil {
		t.Fatal("worker batch profile drift accepted")
	}
	client.BatchRequests = 1
	mode.Store(1)
	if client.ready(context.Background()) == nil {
		t.Fatal("wrong encoder accepted")
	}
	for _, m := range []int32{2, 3} {
		mode.Store(m)
		if _, e = client.encode(context.Background(), "query", "prefix: "); e == nil {
			t.Fatal("invalid/failed encoder accepted")
		}
	}
	mode.Store(4)
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	if _, e = client.encode(ctx, "query", "prefix: "); e == nil {
		t.Fatal("deadline ignored")
	}
	if client.Calls.Load() != 4 {
		t.Fatal("attempt counter", client.Calls.Load())
	}
}
func TestHybridKeepsFullChannelRanks(t *testing.T) {
	var sparse []Candidate
	for i := 1; i <= 60; i++ {
		sparse = append(sparse, Candidate{URN: fmt.Sprintf("skill-%02d", i), BM25Rank: i})
	}
	result := fuseCandidates(sparse, []Candidate{{URN: "skill-60", DenseRank: 1}, {URN: "skill-01", DenseRank: 70}})
	if len(result) != 51 {
		t.Fatal("wrong top-50 union", len(result))
	}
	byID := map[string]Candidate{}
	for _, x := range result {
		byID[x.URN] = x
	}
	if byID["skill-60"].BM25Rank != 60 || byID["skill-01"].DenseRank != 70 {
		t.Fatal("rank outside channel top-50 lost")
	}
	if _, ok := byID["skill-59"]; ok {
		t.Fatal("candidate outside both top-50s admitted")
	}
}
func TestSparseDoesNotRequireGPUConfiguration(t *testing.T) {
	t.Setenv("GUIDEFOLD_RETRIEVAL_MODE", "sparse")
	t.Setenv("GUIDEFOLD_TEI_URL", "invalid")
	c, e := newDenseClient()
	if c != nil || e != nil {
		t.Fatal("sparse depends on GPU", e)
	}
}
