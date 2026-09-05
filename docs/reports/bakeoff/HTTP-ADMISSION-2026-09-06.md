# Go HTTP admission — 2026-09-06

The Go API now reserves capacity before reading authenticated request bodies.
Slow uploads previously consumed body parsing work outside the concurrency limit.
The real HTTP regression has **27 failed checks before the fix and 0 after, out of
97 checks**. This is overload/cancellation validation, not retrieval quality or a
new latency admission.

## Change

Eight SEARCH/USE slots and two separate event-ingest slots now cover upload, JSON
parsing, validation and backend work. Authentication precedes admission. A saturated
pool returns the existing 429 error (`overloaded` or `telemetry_overloaded`) before
reading any body bytes. `Retry-After: 1` tells clients when to retry; HTTP/1 closes
the connection to avoid draining an unread slow body before sending the response.
The adapter must retry on a new connection and retain request/event IDs.

A deferred release covers success, malformed/oversized bodies, validation failure
and cancelled uploads. Health probes do not use either pool. The six-second server
read timeout remains unchanged; a payload deadline is only available after parsing,
but is still measured from handler entry. Early overload does not echo correlation
IDs from an unread body, and can precede a body/schema error. Contract 1.1 already
allows early overload replies without correlation fields; its schema is unchanged.

## Reproduction and evidence

The isolated `guidefold-http-admission` Compose project used loopback port 30765,
real Postgres and the committed Meridian fixture. The harness opens eight unfinished
SEARCH uploads or two unfinished event uploads, then checks rejection of an extra
upload, normal SEARCH/USE or ingest under saturation, independent capacity in the
other pool, authentication, health and recovery after closing every held socket.
Each pool is exercised three times. `Expect: 100-continue` proves an admitted server
started reading; a separate plain HTTP upload checks rejection without that header.

| Evidence | Before | After |
|---|---:|---:|
| HTTP checks | 97 | 97 |
| Failed checks | 27 | 0 |
| Admission gate | FAIL | PASS |

[Machine-readable evidence](validation/http-admission-e2e.json.gz) includes every
assertion, observed status and relevant timings, image identifiers and harness hash.
Baseline mode deliberately records failures as `admission_passed: false`; it is not
used in CI. A timed-out plain upload is recorded as status 0, not an HTTP status.
Baseline source is `6b7fbce`; the final source incorporates main `d5dd807` (graph
publication validation) plus this handler fix. The graph merge does not change the
HTTP handler or its slot capacities. The baseline Go unit test independently failed
on SEARCH, USE and telemetry: 429 was returned only after two body-read calls.

The final image also passed `smoke.py --recovery`: 39 contract/recovery checks and
40 concurrent requests, including database/API restart recovery.

The fixed Go suite passes `go test -race ./...` and `go vet ./...`. Unit tests cover
zero reads on rejection, occupying a slot during a blocked body read, release on
read failure, malformed/oversized input, pool isolation and authentication ordering.
The Compose gate runs the HTTP harness before Meridian graph and 1,000-query CLI
parity checks and uploads its JSON as part of the integration evidence.

To reproduce on a dedicated fixture stack:

```sh
python3 tools/search_service/dev.py deploy
python3 tools/search_service/http_admission.py
python3 tools/search_service/smoke.py --recovery
(cd services/search && go test -race ./... && go vet ./...)
```

These tests intentionally occupy capacity. Do not run them against a shared service.
They do not establish a bound on total TCP connections, process RSS, GPU throughput,
WAN/TLS performance or production readiness. Existing ranking, graph, deadline and
300/400 ms admission rules are unchanged. No CLI change or quality-corpus tuning is
part of this fix.
