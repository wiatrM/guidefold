package main

import (
	"fmt"
	"net/http"
	"sync"
	"time"
)

var metricEndpoints = [...]string{"search", "use", "events:batch"}
var durationBuckets = [...]float64{.005, .01, .025, .05, .1, .2, .3, .4, .5, 1, 2, 5, 10}

type endpointMetrics struct {
	counts   [6]uint64
	overload uint64
	buckets  [13]uint64
	nanos    uint64
}
type serviceMetrics struct {
	mu        sync.Mutex
	endpoints [3]endpointMetrics
}

func metricEndpoint(endpoint string) int {
	for i, name := range metricEndpoints {
		if name == endpoint {
			return i
		}
	}
	return -1
}
func (m *serviceMetrics) observe(i, status int, elapsed time.Duration) {
	m.mu.Lock()
	defer m.mu.Unlock()
	e := &m.endpoints[i]
	class := status / 100
	if class < 1 || class > 5 {
		class = 5
	}
	e.counts[class]++
	if status == 429 {
		e.overload++
	}
	e.nanos += uint64(elapsed)
	for j, bound := range durationBuckets {
		if elapsed.Seconds() <= bound {
			e.buckets[j]++
		}
	}
}
func (a *App) serveMetrics(w http.ResponseWriter) {
	a.Metrics.mu.Lock()
	metrics := a.Metrics.endpoints
	a.Metrics.mu.Unlock()
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	fmt.Fprintln(w, "# HELP guidefold_http_inflight Authenticated admitted requests including body upload.\n# TYPE guidefold_http_inflight gauge")
	fmt.Fprintf(w, "guidefold_http_inflight{pool=\"search_use\"} %d\nguidefold_http_inflight{pool=\"telemetry\"} %d\n", len(a.Slots), len(a.EventSlots))
	fmt.Fprintln(w, "# HELP guidefold_http_capacity Per-process admission capacity.\n# TYPE guidefold_http_capacity gauge")
	fmt.Fprintf(w, "guidefold_http_capacity{pool=\"search_use\"} %d\nguidefold_http_capacity{pool=\"telemetry\"} %d\n", cap(a.Slots), cap(a.EventSlots))
	fmt.Fprintln(w, "# HELP guidefold_http_requests_total Completed HTTP attempts.\n# TYPE guidefold_http_requests_total counter")
	for i, name := range metricEndpoints {
		for class := 1; class <= 5; class++ {
			fmt.Fprintf(w, "guidefold_http_requests_total{endpoint=\"%s\",status_class=\"%dxx\"} %d\n", name, class, metrics[i].counts[class])
		}
	}
	fmt.Fprintln(w, "# HELP guidefold_http_overloaded_total Rejected HTTP attempts at capacity.\n# TYPE guidefold_http_overloaded_total counter")
	for i, name := range metricEndpoints {
		fmt.Fprintf(w, "guidefold_http_overloaded_total{endpoint=\"%s\"} %d\n", name, metrics[i].overload)
	}
	fmt.Fprintln(w, "# HELP guidefold_http_duration_seconds Handler duration including upload and response write.\n# TYPE guidefold_http_duration_seconds histogram")
	for i, name := range metricEndpoints {
		e := &metrics[i]
		var total uint64
		for j := 1; j <= 5; j++ {
			total += e.counts[j]
		}
		for j, bound := range durationBuckets {
			fmt.Fprintf(w, "guidefold_http_duration_seconds_bucket{endpoint=\"%s\",le=\"%g\"} %d\n", name, bound, e.buckets[j])
		}
		fmt.Fprintf(w, "guidefold_http_duration_seconds_bucket{endpoint=\"%s\",le=\"+Inf\"} %d\n", name, total)
		fmt.Fprintf(w, "guidefold_http_duration_seconds_sum{endpoint=\"%s\"} %g\n", name, float64(e.nanos)/1e9)
		fmt.Fprintf(w, "guidefold_http_duration_seconds_count{endpoint=\"%s\"} %d\n", name, total)
	}
}
