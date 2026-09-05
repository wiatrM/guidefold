package main

import (
	"bytes"
	"context"
	"encoding/json"
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
