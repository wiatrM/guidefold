package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"reflect"
	"testing"
	"time"
)

func TestShadowCannotChangeDeliveredBytesOrWaitForGPU(t *testing.T) {
	payload := M{"schema_version": "1.1", "search_id": "frozen-search-id", "request_id": "frozen-request-id", "backend": "router_bm25f_v1", "degradation_reason": nil, "model": nil, "live_encode_calls": 0, "ranked": []M{{"urn": "u:01", "score": 123}}, "cards": []M{{"urn": "u:01", "revision": "revision-1"}}, "stages_ms": M{"score": 1.25}}
	expected, _ := json.Marshal(payload)
	for _, mode := range []string{"disabled", "queued", "full", "cancelled"} {
		t.Run(mode, func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			var worker *ShadowWorker
			if mode != "disabled" {
				worker = &ShadowWorker{Context: ctx, Queue: make(chan ShadowJob, 1)}
			}
			if mode == "full" {
				worker.Queue <- ShadowJob{SearchID: "already-queued"}
			}
			if mode == "cancelled" {
				cancel()
				worker.Queue <- ShadowJob{SearchID: "already-queued"}
			}
			job := &ShadowJob{SearchID: "frozen-search-id", SparseRanked: []M{{"urn": "u:01", "score": 123}}}
			var wire bytes.Buffer
			done := make(chan struct{})
			go func() {
				deliverThenShadow(func() { body, _ := json.Marshal(payload); _, _ = wire.Write(body) }, worker, job)
				close(done)
			}()
			select {
			case <-done:
			case <-time.After(time.Second):
				t.Fatal("response waited for shadow")
			}
			if !bytes.Equal(wire.Bytes(), expected) {
				t.Fatal("shadow changed response bytes")
			}
			if mode == "queued" {
				if got := <-worker.Queue; got.SearchID != payload["search_id"] {
					t.Fatal("correlation lost")
				}
			}
			if mode == "full" || mode == "cancelled" {
				if worker.Dropped.Load() != 1 {
					t.Fatal("queue loss not counted")
				}
			}
		})
	}
}

func TestSparsePreparationCannotCrossQuerySnapshotOrScope(t *testing.T) {
	p := &SparsePreparation{Snapshot: "snapshot-a", QueryDigest: hash([]byte("exact query")), Scopes: map[string]PreparedScope{"allowed": {Ranks: []uint32{75}}}}
	c := &Catalog{ID: "snapshot-a"}
	if p.verify(c, "exact query", []string{"allowed"}) != nil {
		t.Fatal("valid preparation rejected")
	}
	if p.verify(c, "other query", []string{"allowed"}) == nil {
		t.Fatal("cross-query reuse accepted")
	}
	if p.verify(&Catalog{ID: "other"}, "exact query", []string{"allowed"}) == nil {
		t.Fatal("cross-snapshot reuse accepted")
	}
	if p.verify(c, "exact query", []string{"other"}) == nil {
		t.Fatal("cross-scope reuse accepted")
	}
	if p.Scopes["allowed"].Ranks[0] != 75 {
		t.Fatal("full channel rank truncated")
	}
}

func TestCompactPreparationPreservesFullFusionRanks(t *testing.T) {
	c := &Catalog{}
	full := []Candidate{}
	p := PreparedScope{Ranks: make([]uint32, 70)}
	for i := 0; i < 70; i++ {
		u := fmt.Sprintf("skill-%03d", i)
		c.Order = append(c.Order, u)
		full = append(full, Candidate{URN: u, BM25Rank: i + 1})
		p.Ranks[i] = uint32(i + 1)
	}
	p.Top = full[:50]
	dense := []Candidate{{URN: "skill-060", DenseRank: 1}, {URN: "skill-002", DenseRank: 71}}
	want := fuseCandidates(full, dense)
	if got := fusePrepared(c, p, dense); !reflect.DeepEqual(got, want) {
		t.Fatalf("full-rank fusion changed: %v vs %v", got, want)
	}
	if full[50].URN != "skill-050" || full[50].BM25Rank != 51 {
		t.Fatal("preparation mutated its source")
	}
}
