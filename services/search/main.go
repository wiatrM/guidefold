package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/identity"
	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/knowledge"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/schema"
	"github.com/wiatrM/guidefold/services/search/internal/usage"
	"github.com/wiatrM/guidefold/services/search/internal/worker"
)

type App struct {
	Store      *Store
	Validator  *Validator
	Token      string
	Identity   *identity.Service
	Management http.Handler
	Slots      chan struct{}
	EventSlots chan struct{}
	Metrics    serviceMetrics
}

func uuid() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	b[6] = (b[6] & 15) | 64
	b[8] = (b[8] & 63) | 128
	s := hex.EncodeToString(b[:])
	return s[:8] + "-" + s[8:12] + "-" + s[12:16] + "-" + s[16:20] + "-" + s[20:]
}
func elapsed(t time.Time) float64 { return float64(time.Since(t).Microseconds()) / 1000 }
func (s *Store) searchResponse(ctx context.Context, tenant, repo string, p M) (M, error) {
	return s.searchCaptured(ctx, tenant, repo, p, nil)
}
func (s *Store) searchCaptured(ctx context.Context, tenant, repo string, p M, capture *ShadowJob) (M, error) {
	start := time.Now()
	c, e := s.catalog(ctx, tenant, repo)
	if e != nil {
		return nil, e
	}
	return s.searchCatalog(ctx, c, p, M{"catalog": elapsed(start)}, capture, nil)
}
func (s *Store) searchCatalog(ctx context.Context, c *Catalog, p M, stages M, capture *ShadowJob, prepared *SparsePreparation) (M, error) {
	var e error
	scopes, contextualData, e := c.resolve(p)
	if e != nil {
		return nil, e
	}
	if prepared != nil {
		if e := prepared.verify(c, str(p["query"]), scopes); e != nil {
			return nil, e
		}
	}
	if capture != nil && s.Dense == nil {
		capture.Preparation = &SparsePreparation{Snapshot: c.ID, QueryDigest: hash([]byte(str(p["query"]))), Scopes: map[string]PreparedScope{}}
	}
	version := str(p["schema_version"])
	contextual := version == "1.1" || version == schemaVersion12
	// 1.2 lets a client pin the snapshot SEARCH answered from. A head that moved
	// between SEARCH and USE is a conflict the client has to see, not a silently
	// different catalog (API-CONTRACT §4.5).
	if version == schemaVersion12 {
		if want := str(p["search_snapshot"]); want != "" && want != c.ID {
			return nil, fail(409, "snapshot_changed")
		}
	}
	admissible := map[string]bool{}
	eligible := map[string][]string{}
	merged := map[string]Candidate{}
	dropCount := 0
	type encodedQuery struct {
		vector []float32
		ms     float64
		err    error
	}
	var encodeResult chan encodedQuery
	var vector []float32
	if s.Dense != nil {
		encodeResult = make(chan encodedQuery, 1)
		go func() {
			started := time.Now()
			denseCtx, cancel := context.WithTimeout(ctx, s.Dense.EncodeTimeout)
			defer cancel()
			v, e := s.Dense.encode(denseCtx, str(p["query"]), c.DensePrompt)
			encodeResult <- encodedQuery{v, elapsed(started), e}
		}()
	}
	policyMS, searchMS, scoreMS := float64(0), float64(0), float64(0)
	for _, node := range scopes {
		stage := time.Now()
		var allowed map[string]bool
		var drops int
		if prepared != nil {
			allowed, drops = prepared.Scopes[node].allowed(c), prepared.Scopes[node].Drops
		} else {
			allowed, drops = c.allowed(node, str(p["query"]))
		}
		dropCount += drops
		for u := range allowed {
			admissible[u] = true
			eligible[u] = append(eligible[u], node)
		}
		policyMS += elapsed(stage)
		stage = time.Now()
		var candidates []Candidate
		if s.Dense != nil {
			if s.Dense.Mode == "hybrid" {
				if prepared != nil {
					candidates = prepared.Scopes[node].Top
				} else {
					candidates, e = s.routerCandidates(ctx, c, str(p["query"]), allowed, 0)
				}
			}
		} else if capture != nil && capture.Preparation != nil && s.LexicalEngine == "router" {
			// Capture compact full ranks before the unchanged top-50 truncation.
			prep := prepareScope(c, allowed, drops)
			candidates, e = s.routerCandidates(ctx, c, str(p["query"]), allowed, 50, prep.Ranks)
			prep.Top = candidates
			capture.Preparation.Scopes[node] = prep
		} else {
			candidates, e = s.search(ctx, c, str(p["query"]), allowed)
		}
		if e != nil {
			return nil, e
		}
		searchMS += elapsed(stage)
		if s.Dense != nil {
			if vector == nil {
				waitStart := time.Now()
				select {
				case encoded := <-encodeResult:
					if encoded.err != nil {
						return nil, encoded.err
					}
					vector = encoded.vector
					stages["encode_http"] = encoded.ms
				case <-ctx.Done():
					return nil, ctx.Err()
				}
				stages["encoder_wait_after_sparse"] = elapsed(waitStart)
			}
			denseStart := time.Now()
			dense, e := s.denseSearch(ctx, c, vector, allowed, candidates)
			if e != nil {
				return nil, e
			}
			previous, _ := stages["dense_database"].(float64)
			stages["dense_database"] = previous + elapsed(denseStart)
			if prepared != nil {
				candidates = fusePrepared(c, prepared.Scopes[node], dense)
			} else {
				candidates = fuseCandidates(candidates, dense)
			}
		}
		stage = time.Now()
		for _, row := range c.score(candidates, node) {
			if old, ok := merged[row.URN]; !ok || row.Score > old.Score {
				merged[row.URN] = row
			}
		}
		scoreMS += elapsed(stage)
	}
	scored := make([]Candidate, 0, len(merged))
	for _, v := range merged {
		scored = append(scored, v)
	}
	sortCandidates(scored)
	stages["policy"], stages["candidates"], stages["score"] = policyMS, searchMS, scoreMS
	stage := time.Now()
	budget := obj(p["budget"])
	selected := c.selectCards(scored, int(integer(budget, "max_cards", 4)), admissible)
	stages["select"] = elapsed(stage)
	ranked := []M{}
	for _, row := range scored {
		if len(ranked) >= 10 {
			break
		}
		card := c.card(row.URN, eligible, contextual)
		card["score"] = row.Score
		ranked = append(ranked, card)
	}
	cards := []M{}
	for _, u := range selected {
		cards = append(cards, c.card(u, eligible, contextual))
	}
	rendered := ""
	if contextual {
		loaded := map[string]bool{}
		for _, x := range arr(p["loaded_skills"]) {
			l := obj(x)
			id := str(l["skill_id"])
			if str(l["state"]) == "hydrated" && c.Revisions[id] == str(l["revision"]) {
				loaded[id] = true
			} else {
				appendContext(contextualData, "warnings", "unconfirmed_or_stale_loaded_skill")
			}
		}
		if _, ok := p["loaded_skills"]; ok {
			appendContext(contextualData, "used_fields", "loaded_skills")
		}
		kept := []M{}
		omitted := 0
		for _, card := range cards {
			if loaded[str(card["skill_id"])] {
				omitted++
			} else {
				kept = append(kept, card)
			}
		}
		cards = kept
		contextualData["loaded_cards_omitted"] = omitted
		lines := []string{}
		for _, card := range cards {
			lines = append(lines, "- "+str(card["skill_id"])+"@"+str(card["revision"])+": "+str(card["description"]))
		}
		rendered = strings.Join(lines, "\n")
		used := len([]byte(rendered))
		fits := true
		for _, key := range []string{"max_bytes", "remaining_skill_tokens"} {
			if v, ok := budget[key]; ok && int64(used) > number(v) {
				fits = false
			}
		}
		accounting := M{"candidate_rendered_bytes": used, "returned_rendered_bytes": used, "token_accounting": "not_requested"}
		contextualData["delivery_status"] = "ok"
		if _, ok := budget["remaining_skill_tokens"]; ok {
			accounting["token_accounting"] = "utf8_byte_proxy_adapter_must_verify"
			appendContext(contextualData, "warnings", "verify_final_harness_token_count")
		}
		if len(budget) > 0 {
			appendContext(contextualData, "used_fields", "budget")
		}
		if !fits {
			cards = []M{}
			rendered = ""
			accounting["returned_rendered_bytes"] = 0
			contextualData["delivery_status"] = "cannot_fit"
		}
		contextualData["budget_accounting"] = accounting
		contextualData["fusion"] = "shared_router"
		if len(scopes) > 1 {
			contextualData["fusion"] = "max_score_then_urn"
		}
	}
	if e = ctx.Err(); e != nil {
		return nil, e
	}
	result := M{"search_id": uuid(), "backend": s.backendName(), "snapshot": c.ID, "model": nil, "policy": "go-router-policy-select-v1", "policy_revision": c.PolicySHA, "optimized": true, "pipeline": false, "native_dense_rank": false, "encoder_process": false, "gil_switch_ms_effective": nil, "torch_threads_effective": nil, "profile": text(p, "profile", "hook"), "reranker": false, "ranked": ranked, "cards": cards, "composition": M{"status": "not_evaluated", "incomplete": nil}, "abstained": len(selected) == 0, "policy_drops": dropCount, "stages_ms": stages, "live_encode_calls": 0, "retrieval": M{"engine": "ParadeDB/Tantivy", "pg_search_version": s.Version, "revision": "bm25-concatenated-unicode-v1", "dense": "disabled", "exact_legacy_ranking_parity": false}}
	if s.LexicalEngine != "paradedb-experimental" {
		result["retrieval"] = M{"engine": "Guidefold integer BM25F / Postgres postings", "revision": "router-bm25f-v1", "index_revision": c.RouterIndexSHA, "dense": "disabled", "exact_legacy_ranking_parity": true}
	}
	if s.Dense != nil {
		result["model"] = s.Dense.ID
		result["encoder_batch_requests"] = s.Dense.BatchRequests
		result["encoder_process"] = true
		result["live_encode_calls"] = 1
		result["retrieval"] = M{"engine": "Guidefold BM25F + pgvector exact cosine + TEI GPU", "revision": s.backendName(), "index_revision": c.RouterIndexSHA, "encoder_id": s.Dense.ID, "dense": s.Dense.Mode, "fusion": "rrf-k60-top50-union-full-channel-ranks", "exact_legacy_ranking_parity": false, "quality_admitted": false}
	}
	if contextual {
		result["schema_version"] = version
		result["context"] = contextualData
		result["card_context"] = rendered
	}
	if capture != nil {
		capture.SearchID = str(result["search_id"])
		capture.Catalog = c
		capture.Payload = p
		capture.SparseRanked = compactRanks(scored, 20)
		capture.Selected = compactCards(cards)
		capture.SparseTimings = copyMetrics(stages)
	}
	// 1.2 only, and last: `ranked`, `cards`, `card_context` and every byte of the
	// budget accounting are already final, so the family view cannot move a
	// position or a number. A 1.1 response never reaches this line.
	if version == schemaVersion12 {
		s.decorateFamily12(ctx, c, ranked, cards)
	}
	return result, nil
}
func (s *Store) useResponse(ctx context.Context, tenant, repo string, p M) (M, error) {
	c, e := s.catalog(ctx, tenant, repo)
	if e != nil {
		return nil, e
	}
	scopes, contextData, e := c.resolve(p)
	if e != nil {
		return nil, e
	}
	version := str(p["schema_version"])
	contextual := version == "1.1" || version == schemaVersion12
	if version == schemaVersion12 {
		if want := str(p["search_snapshot"]); want != "" && want != c.ID {
			return nil, fail(409, "snapshot_changed")
		}
	}
	id := str(p["skill_id"])
	card, ok := c.Cards[id]
	if !ok {
		return nil, fail(404, "skill_not_found")
	}
	if str(p["revision"]) != c.Revisions[id] {
		return nil, fail(409, "revision_mismatch")
	}
	if str(card["status"]) != "active" {
		return nil, fail(409, "skill_not_active")
	}
	reachable := map[string]bool{}
	if contextual {
		for _, node := range scopes {
			a, _ := c.allowed(node, "")
			for u := range a {
				reachable[u] = true
			}
		}
		if !reachable[id] {
			return nil, fail(403, "skill_outside_resolved_scope")
		}
	}
	body, e := s.body(ctx, c, id, str(p["revision"]))
	if e != nil {
		return nil, e
	}
	if contextual {
		budget := obj(p["budget"])
		caps := false
		for _, key := range []string{"max_bytes", "remaining_skill_tokens"} {
			if v, ok := budget[key]; ok {
				caps = true
				if int64(len([]byte(body))) > number(v) {
					return nil, fail(413, "skill_body_exceeds_budget")
				}
			}
		}
		contextData["body_bytes"] = len([]byte(body))
		if caps {
			appendContext(contextData, "used_fields", "budget")
		}
		unused := contextData["unused_fields"].([]M)
		for _, k := range []string{"max_cards"} {
			if _, ok := budget[k]; ok {
				unused = append(unused, M{"field": "budget." + k, "reason": "not_applicable_to_use"})
			}
		}
		if _, ok := p["loaded_skills"]; ok {
			unused = append(unused, M{"field": "loaded_skills", "reason": "not_applicable_to_use"})
		}
		contextData["unused_fields"] = unused
		if _, ok := budget["remaining_skill_tokens"]; ok {
			appendContext(contextData, "warnings", "verify_final_harness_token_count")
		}
	}
	result := M{"status": "hydrated", "execution_observed": false, "skill_id": id, "revision": c.Revisions[id], "search_id": p["search_id"], "search_id_verified": false, "current_state": card["status"], "snapshot": c.ID, "body": body, "checksum": hash([]byte(body))}
	if contextual {
		result["schema_version"] = version
		result["context"] = contextData
	}
	if version == schemaVersion12 {
		if e := s.decorate12(ctx, c, p, result, id, reachable); e != nil {
			return nil, e
		}
	}
	return result, nil
}
func (a *App) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	status := 200
	result := M{}
	endpoint := strings.TrimPrefix(r.URL.Path, "/v1/")
	if a.Management != nil && managementRequest(r) {
		a.Management.ServeHTTP(w, r)
		return
	}
	// contract-route: GET /metrics
	if r.Method == http.MethodGet && r.URL.Path == "/metrics" {
		a.serveMetrics(w)
		return
	}
	if r.Method == http.MethodPost {
		if i := metricEndpoint(endpoint); i >= 0 {
			defer func() { a.Metrics.observe(i, status, time.Since(start)) }()
		}
	}
	attempt := uuid()
	var payload M
	send := func() {
		if _, ok := result["backend"]; !ok {
			result["backend"] = a.Store.backendName()
		}
		if _, ok := result["degradation_reason"]; !ok {
			result["degradation_reason"] = result["error"]
		}
		result["request_id"] = attempt
		for _, k := range []string{"request_id", "session_id", "task_id"} {
			if v, ok := payload[k]; ok {
				result[k] = v
			}
		}
		body, e := json.Marshal(result)
		if e != nil {
			status = 500
			body = []byte(`{"error":"serialization_failed"}`)
		}
		ms := elapsed(start)
		// Allowlist only. No raw queries, bodies, paths, token or free-text metadata.
		fields := []any{"event", endpoint, "attempt_id", attempt, "status", status, "duration_ms", ms, "backend", a.Store.backendName()}
		for _, k := range []string{"request_id", "session_id", "task_id"} {
			if v, ok := payload[k]; ok {
				fields = append(fields, k, v)
			}
		}
		for _, k := range []string{"schema_version", "harness", "query_source"} {
			if v, ok := payload[k]; ok {
				fields = append(fields, k, v)
			}
		}
		for _, k := range []string{"search_id", "skill_id", "revision"} {
			if v, ok := result[k]; ok {
				fields = append(fields, k, v)
			}
		}
		if c := obj(result["context"]); c != nil {
			fields = append(fields, "resolved_scopes", c["resolved_scopes"], "scope_map_revision", c["scope_map_revision"])
		}
		if cards := arrM(result["cards"]); len(cards) > 0 {
			revisions := []M{}
			for _, card := range cards {
				revisions = append(revisions, M{"skill_id": card["skill_id"], "revision": card["revision"]})
			}
			fields = append(fields, "card_revisions", revisions)
		}
		if v, ok := result["snapshot"]; ok {
			fields = append(fields, "snapshot", v)
		}
		if r.URL.Path == "/v1/search" {
			fields = append(fields, "cards", len(arrM(result["cards"])))
		}
		if strings.HasPrefix(r.URL.Path, "/v1/") {
			slog.Info("request", fields...)
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("X-Guidefold-Server-Ms", fmt.Sprintf("%.3f", elapsed(start)))
		w.Header().Set("Cache-Control", "no-store")
		w.WriteHeader(status)
		_, _ = w.Write(body)
	}
	respondError := func(e error) {
		var api *APIError
		if errors.As(e, &api) {
			status = api.Status
			result = M{"error": api.Code}
		} else if errors.Is(e, context.DeadlineExceeded) || errors.Is(e, context.Canceled) {
			status = 504
			result = M{"error": "deadline_exceeded"}
		} else {
			status = 503
			result = M{"error": "backend_unavailable"}
		}
		send()
	}
	// contract-route: GET /health/live
	if r.Method == http.MethodGet && r.URL.Path == "/health/live" {
		result = M{"live": true}
		send()
		return
	}
	// contract-route: GET /health/ready
	if r.Method == http.MethodGet && r.URL.Path == "/health/ready" {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		c, e := a.Store.catalog(ctx, a.Store.Tenant, a.Store.Repo)
		if e != nil {
			// A tenant with no published snapshot yet (fresh import, nothing
			// reviewed/published) is a real, valid state, not a failure: the
			// management API (identity/import/knowledge/review/usage) does not
			// read the catalog at all. Only the retrieval surface (SEARCH/USE)
			// needs a snapshot, so report that surface as unconfigured instead
			// of failing the probe and taking the whole pod out of rotation.
			var api *APIError
			if errors.As(e, &api) && api.Code == "snapshot_not_published" {
				result = M{"ready": true, "backend": a.Store.backendName(), "runtime": "go", "retrieval": "not_configured", "api_schema_versions": []string{"legacy-unversioned", "1.1", "1.2"}, "database_search_calls": a.Store.Searches.Load(), "database_use_calls": a.Store.Uses.Load()}
				send()
				return
			}
			respondError(e)
			return
		}
		if a.Store.Dense != nil {
			if e = a.Store.Dense.ready(ctx); e != nil {
				respondError(e)
				return
			}
		}
		result = M{"ready": true, "backend": a.Store.backendName(), "runtime": "go", "pg_search_version": a.Store.Version, "snapshot": c.ID, "repository": M{"repo_id": c.Repo, "revision": c.Revision}, "policy_revision": c.PolicySHA, "n_skills": len(c.Cards), "router_index_revision": c.RouterIndexSHA, "api_schema_versions": []string{"legacy-unversioned", "1.1", "1.2"}, "database_search_calls": a.Store.Searches.Load(), "database_use_calls": a.Store.Uses.Load(), "body_cache": false, "python_runtime": false, "live_encode_calls": 0, "model_load_calls": 0, "production_iam": false}
		if a.Store.Dense != nil {
			result["encoder_id"] = a.Store.Dense.ID
			result["encoder_batch_requests"] = a.Store.Dense.BatchRequests
			result["retrieval_mode"] = a.Store.Dense.Mode
			result["live_encode_calls"] = a.Store.Dense.Calls.Load()
			result["database_dense_calls"] = a.Store.Dense.Searches.Load()
			result["model_load_calls"] = nil
			result["quality_admitted"] = false
		}
		send()
		return
	}
	// The 1.2 package-resource route answers bytes, not JSON, so it is handled
	// before the three JSON endpoints rather than by their envelope.
	// contract-route: GET /v1/skills/{skill_id}/revisions/{revision}/resources/{path}
	if r.Method == http.MethodGet && strings.HasPrefix(r.URL.Path, "/v1/skills/") {
		a.serveResource(w, r)
		return
	}
	// The delivery surface an installation token reaches:
	// contract-route: POST /v1/search
	// contract-route: POST /v1/use
	// contract-route: POST /v1/events:batch
	if r.Method != http.MethodPost || (endpoint != "search" && endpoint != "use" && endpoint != "events:batch") {
		status = 404
		result = M{"error": "not_found"}
		send()
		return
	}
	principal, authErr := a.authenticate(r, endpoint)
	if authErr != nil {
		respondError(authErr)
		return
	}
	// Bound uploads and JSON parsing as well as backend work. Authenticate first;
	// telemetry retains its own capacity so one pool cannot exhaust the other.
	slots, overloadCode := a.Slots, "overloaded"
	if endpoint == "events:batch" {
		slots, overloadCode = a.EventSlots, "telemetry_overloaded"
	}
	select {
	case slots <- struct{}{}:
		defer func() { <-slots }()
	default:
		// Do not let HTTP/1 drain an unread slow/large request before the reply.
		w.Header().Set("Connection", "close")
		w.Header().Set("Retry-After", "1")
		respondError(fail(429, overloadCode))
		return
	}
	bodyLimit := int64(16384)
	if endpoint == "events:batch" {
		bodyLimit = 2 * 1024 * 1024
	}
	r.Body = http.MaxBytesReader(w, r.Body, bodyLimit)
	body, e := io.ReadAll(r.Body)
	if e != nil {
		var limit *http.MaxBytesError
		if errors.As(e, &limit) {
			status = 413
			result = M{"error": "body_too_large"}
			send()
		} else {
			respondError(fail(400, "invalid_body"))
		}
		return
	}
	decoded, e := strictJSON(body)
	if e != nil {
		respondError(fail(400, "invalid_json"))
		return
	}
	p := obj(decoded)
	if endpoint == "events:batch" {
		batch, ok := p["events"].([]any)
		if !ok {
			respondError(fail(400, "missing_events_list"))
			return
		}
		if len(batch) > 500 {
			respondError(fail(413, "batch_too_large"))
			return
		}

		ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
		defer cancel()
		tenant, e := a.resolveTenant(ctx, principal, r)
		if e != nil {
			respondError(e)
			return
		}
		result, e = a.Store.ingestEvents(ctx, tenant, batch)
		if e != nil {
			respondError(e)
			return
		}
		// The adapter-health projection is written from the events this batch
		// actually accepted, for the organisation the principal proved — never
		// for one the client claims. It is a diagnostic: if it fails, the
		// observations are already in the ledger and the batch still succeeded.
		if e := usage.RecordAdapterHealth(ctx, a.Store.Pool, tenant,
			installationOf(principal), batch, result); e != nil {
			slog.Warn("adapter_health_projection", "attempt_id", attempt, "error", e.Error())
		}
		send()
		return
	}
	if e = a.Validator.validate(p, endpoint); e != nil {
		respondError(e)
		return
	}
	payload = p
	ctx, cancel := context.WithDeadline(r.Context(), start.Add(time.Duration(integer(p, "deadline_ms", 1000))*time.Millisecond))
	defer cancel()

	tenant, e := a.resolveTenant(ctx, principal, r)
	if e != nil {
		respondError(e)
		return
	}
	repo, e := a.resolveRepo(ctx, principal, r, p, tenant)
	if e != nil {
		respondError(e)
		return
	}
	var shadowJob *ShadowJob
	if endpoint == "search" {
		if a.Store.Shadow != nil {
			shadowJob = &ShadowJob{}
		}
		result, e = a.Store.searchCaptured(ctx, tenant, repo, p, shadowJob)
	} else {
		result, e = a.Store.useResponse(ctx, tenant, repo, p)
	}
	if e != nil {
		respondError(e)
		return
	}
	if e = ctx.Err(); e != nil {
		respondError(e)
		return
	}
	deliverThenShadow(send, a.Store.Shadow, shadowJob)
}
func arrM(v any) []M { a, _ := v.([]M); return a }
func policySHA() (string, error) {
	p := env("GUIDEFOLD_POLICY_SOURCE", "/app/policy-source")
	b, e := os.ReadFile(p)
	return hash(b), e
}
func run() error {
	shadowEnabled := env("GUIDEFOLD_SHADOW", "false") == "true"
	command := "serve"
	if len(os.Args) > 1 {
		command = os.Args[1]
	}
	if command == "--shadow" {
		command = "serve"
		shadowEnabled = true
	}
	if command == "serve" && len(os.Args) > 2 && os.Args[2] == "--shadow" {
		shadowEnabled = true
	}
	if command == "healthcheck" {
		client := &http.Client{Timeout: 2 * time.Second}
		r, e := client.Get(readyURL(listenAddress()))
		if e != nil {
			return e
		}
		defer r.Body.Close()
		if r.StatusCode != 200 {
			return fmt.Errorf("not_ready")
		}
		return nil
	}
	if command == "verify-model" {
		if len(os.Args) != 3 {
			return fmt.Errorf("verify_model_requires_directory")
		}
		return verifyModelDirectory(os.Args[2], env("GUIDEFOLD_ENCODER_ID", ""))
	}
	root, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	pool, e := openPool(root)
	if e != nil {
		return e
	}
	defer pool.Close()
	sha, e := policySHA()
	if e != nil {
		return e
	}
	store := &Store{Pool: pool, Tenant: env("GUIDEFOLD_TENANT", "local"), Repo: env("GUIDEFOLD_REPO", "meridian"), PolicySHA: sha, SnapshotID: env("GUIDEFOLD_SNAPSHOT_ID", ""), catalogs: newCatalogCache(catalogCacheSize)}
	store.LexicalEngine = env("GUIDEFOLD_LEXICAL_ENGINE", "router")
	if store.LexicalEngine != "router" && store.LexicalEngine != "paradedb-experimental" {
		return fmt.Errorf("invalid_lexical_engine")
	}
	operatorSeconds, e := strconv.Atoi(env("GUIDEFOLD_OPERATOR_TIMEOUT_SECONDS", "120"))
	if e != nil || operatorSeconds < 1 || operatorSeconds > 86400 {
		return fmt.Errorf("invalid_operator_timeout")
	}
	ctx, done := context.WithTimeout(root, time.Duration(operatorSeconds)*time.Second)
	defer done()
	if command == "migrate" {
		password, e := secret(env("APP_PASSWORD_FILE", "/run/secrets/app_password"))
		if e != nil {
			return e
		}
		return schema.Migrate(ctx, pool, password)
	}
	store.Caps, e = schema.Detect(ctx, pool)
	if e != nil {
		return e
	}
	store.Version = store.Caps.PgSearch
	if command == "worker" {
		return runWorker(root, pool, store.Caps, sha)
	}
	if command == "publish" {
		if len(os.Args) != 3 {
			return fmt.Errorf("publish_requires_snapshot_path")
		}
		return publish(ctx, store, os.Args[2])
	}
	if command == "publish-embeddings" {
		if len(os.Args) != 3 {
			return fmt.Errorf("publish_embeddings_requires_path")
		}
		return publishEmbeddings(ctx, store, os.Args[2])
	}
	if command == "shadow-export" {
		if len(os.Args) != 3 {
			return fmt.Errorf("shadow_export_requires_search_id")
		}
		value, e := store.exportShadow(ctx, os.Args[2])
		return printOperatorResult(value, e)
	}
	if command == "telemetry-export" {
		value, e := store.exportEvents(ctx)
		return printOperatorResult(value, e)
	}
	if command == "telemetry-tenants" {
		value, e := store.eventTenants(ctx)
		return printOperatorResult(value, e)
	}
	if command == "telemetry-retain" {
		days := 90
		if len(os.Args) > 2 {
			days, e = strconv.Atoi(os.Args[2])
			if e != nil {
				return e
			}
		}
		now := time.Now()
		if len(os.Args) > 3 {
			now, e = time.Parse(time.RFC3339, os.Args[3])
			if e != nil {
				return e
			}
		}
		n, e := store.retainEvents(ctx, days, now)
		return printOperatorResult(M{"deleted": n}, e)
	}
	if command == "verify-release" {
		return verifyRelease(ctx, store, shadowEnabled)
	}
	if command != "serve" {
		return fmt.Errorf("unknown_command")
	}
	// Plain PostgreSQL profile: the router engine needs no extension, so an
	// absent pg_search is a reported state. The ParadeDB engine is not.
	if store.LexicalEngine == "paradedb-experimental" && !store.Caps.HasPgSearch() {
		return fmt.Errorf("paradedb_engine_requires_pg_search")
	}
	store.Dense, e = newDenseClient()
	if e != nil {
		return e
	}
	if shadowEnabled && store.Dense != nil {
		return fmt.Errorf("shadow_requires_sparse_responses")
	}
	if store.Dense != nil {
		if env("GUIDEFOLD_EXPERIMENTAL_OUTPUT", "false") != "true" {
			return fmt.Errorf("neural_response_requires_explicit_experiment")
		}
		if store.LexicalEngine != "router" {
			return fmt.Errorf("dense_requires_router_baseline")
		}
		if e = store.Dense.ready(ctx); e != nil {
			return e
		}
	}
	if shadowEnabled {
		if store.LexicalEngine != "router" {
			return fmt.Errorf("shadow_requires_router_baseline")
		}
		store.Shadow, e = newShadowWorker(root, store)
		if e != nil {
			return e
		}
	}
	if store.Shadow != nil {
		defer func() { cancel(); store.Shadow.WG.Wait() }()
	}
	validator, e := newValidator(env("GUIDEFOLD_CONTRACT", "/app/contract.json"))
	if e != nil {
		return e
	}
	token, e := secret(env("GUIDEFOLD_TOKEN_FILE", "/run/secrets/api_token"))
	if e != nil {
		return e
	}
	app := &App{Store: store, Validator: validator, Token: token, Slots: make(chan struct{}, 8), EventSlots: make(chan struct{}, 2)}
	if e = mountManagement(app, pool); e != nil {
		return e
	}
	server := &http.Server{Addr: listenAddress(), Handler: app, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 6 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 16384}
	errs := make(chan error, 1)
	go func() { errs <- server.ListenAndServe() }()
	slog.Info("listening", "address", server.Addr, "backend", store.backendName(), "runtime", "go")
	select {
	case <-root.Done():
		stop, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		return server.Shutdown(stop)
	case e := <-errs:
		if errors.Is(e, http.ErrServerClosed) {
			return nil
		}
		return e
	}
}
func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	if e := run(); e != nil {
		slog.Error("service_failed", "error", e.Error())
		os.Exit(1)
	}
}

// mountManagement builds the /api/ surface and the per-request identity the
// delivery endpoints share with it.
func mountManagement(app *App, pool *pgxpool.Pool) error {
	cfg, e := identity.ConfigFromEnv()
	if e != nil {
		return e
	}
	if cfg.Mode == identity.ModeDev {
		// Named explicitly, so this is a choice rather than a default -- but it
		// is the choice that hands a session to whoever can reach the port, and
		// an operator who made it by copying a compose file should see it said.
		slog.Warn("development_sign_in_enabled",
			"mode", cfg.Mode,
			"detail", "GUIDEFOLD_AUTH=dev mounts /api/v1/auth/dev; anyone who can reach this port can sign in as any e-mail")
	}
	svc, e := identity.New(pool, cfg)
	if e != nil {
		return e
	}
	router := mgmt.New(mgmt.Options{Pool: pool, Resolve: svc.Resolve, OpenAPI: managementSpec})
	svc.Register(router)
	blobs := importer.NewBlobStore(pool)
	importer.New(pool, blobs).Register(router)
	// Feedback from the UI goes through the same validator and the same ledger
	// as feedback from an adapter, so one rating is one observation whichever
	// surface produced it (API-CONTRACT §7).
	var sink knowledge.EventSink
	if app.Store != nil {
		sink = func(ctx context.Context, tenantID string, events []any) (map[string]any, error) {
			out, e := app.Store.ingestEvents(ctx, tenantID, events)
			return out, e
		}
	}
	knowledge.New(pool, blobs, sink, env("GUIDEFOLD_ENVIRONMENT", "pilot")).Register(router)
	usage.New(pool).Register(router)
	reviewer, e := review.New(pool, blobs)
	if e != nil {
		return e
	}
	reviewer.Register(router)
	app.Identity, app.Management = svc, router
	return nil
}

// listenAddress is where `serve` binds and where `healthcheck` probes. Both read
// the same variable, so a deployment that moves the port does not end up with a
// health check pointing at the old one (tech-lead decision 16).
func listenAddress() string { return env("GUIDEFOLD_LISTEN", ":8080") }

// readyURL turns a listen address into the readiness URL to probe. A bare
// ":8080" is a wildcard bind, which a client cannot connect to; loopback is the
// address the container itself can always reach.
func readyURL(addr string) string {
	host, port, e := net.SplitHostPort(addr)
	if e != nil {
		return "http://" + addr + "/health/ready"
	}
	switch host {
	case "", "0.0.0.0", "::", "[::]":
		host = "127.0.0.1"
	default:
		if strings.Contains(host, ":") {
			host = "[" + host + "]"
		}
	}
	return "http://" + net.JoinHostPort(host, port) + "/health/ready"
}

// runWorker executes queued jobs. The handler registry is filled by
// RegisterHandlers; a deployment without handlers is a configuration error
// rather than a silent no-op, except under --once where an empty queue is a
// normal exit.
func runWorker(ctx context.Context, pool *pgxpool.Pool, caps schema.Capabilities, policySHA string) error {
	once := false
	for _, arg := range os.Args[2:] {
		if arg == "--once" {
			once = true
			continue
		}
		return fmt.Errorf("unknown_worker_flag")
	}
	id := env("GUIDEFOLD_WORKER_ID", "")
	if id == "" {
		host, _ := os.Hostname()
		id = host + "-" + uuid()
	}
	handlers, e := RegisterHandlers(pool, caps, policySHA)
	if e != nil {
		return e
	}
	return worker.Run(ctx, pool, id, handlers, worker.Options{Once: once})
}
