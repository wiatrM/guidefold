package main

import (
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestMetricsCaptureHTTPWithoutIdentifiers(t *testing.T) {
	a := admissionApp(t)
	r := httptest.NewRequest("POST", "/v1/search", strings.NewReader(`{"query":"private task"}`))
	r.Header.Set("Authorization", "secret-not-a-metric")
	a.ServeHTTP(httptest.NewRecorder(), r)
	a.Slots <- struct{}{}
	w := httptest.NewRecorder()
	a.ServeHTTP(w, httptest.NewRequest("GET", "/metrics", nil))
	for _, want := range []string{
		`guidefold_http_requests_total{endpoint="search",status_class="4xx"} 1`,
		`guidefold_http_inflight{pool="search_use"} 1`,
		`guidefold_http_duration_seconds_count{endpoint="search"} 1`,
	} {
		if !strings.Contains(w.Body.String(), want) {
			t.Fatal(want, w.Body.String())
		}
	}
	for _, forbidden := range []string{"private task", "secret-not-a-metric", "request_id", "skill_id", "tenant"} {
		if strings.Contains(w.Body.String(), forbidden) {
			t.Fatal("metric leaked identifier", forbidden)
		}
	}
}
func TestMetricsConcurrentHistograms(t *testing.T) {
	a := admissionApp(t)
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				a.Metrics.observe(0, 429, 10*time.Millisecond)
				a.serveMetrics(httptest.NewRecorder())
			}
		}()
	}
	wg.Wait()
	w := httptest.NewRecorder()
	a.serveMetrics(w)
	for _, want := range []string{
		`guidefold_http_overloaded_total{endpoint="search"} 800`,
		`guidefold_http_duration_seconds_bucket{endpoint="search",le="0.005"} 0`,
		`guidefold_http_duration_seconds_bucket{endpoint="search",le="0.01"} 800`,
		`guidefold_http_duration_seconds_bucket{endpoint="search",le="+Inf"} 800`,
		`guidefold_http_duration_seconds_count{endpoint="search"} 800`,
		`guidefold_http_duration_seconds_sum{endpoint="search"} 8`,
	} {
		if !strings.Contains(w.Body.String(), want) {
			t.Fatal(want)
		}
	}
}
