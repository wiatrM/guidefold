package generator_test

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/review/generator"
)

// The HTTP providers are tested against a fake, not against a vendor. What is
// being checked is the service's own contract with a model — schema validation,
// bounded retries, fabricated-citation rejection and honest cost accounting —
// none of which depends on which vendor answered.

func keyFile(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "key")
	if e := os.WriteFile(path, []byte("sk-test-not-a-real-key\n"), 0o600); e != nil {
		t.Fatal(e)
	}
	return path
}

func remoteFor(t *testing.T, provider, base, key string, extra map[string]string) generator.Generator {
	t.Helper()
	env := map[string]string{
		"GUIDEFOLD_GENERATOR":    provider,
		"OPENAI_BASE_URL":        base,
		"ANTHROPIC_BASE_URL":     base,
		"OPENAI_API_KEY_FILE":    key,
		"ANTHROPIC_API_KEY_FILE": key,
	}
	for k, v := range extra {
		env[k] = v
	}
	g, recipe, e := generator.Select(func(name string) string { return env[name] })
	if e != nil {
		t.Fatal(e)
	}
	if recipe.Generator != provider || recipe.Model == "" {
		t.Fatalf("recipe %+v does not name the provider and its model", recipe)
	}
	return g
}

func answer(provider, text string, in, out int) any {
	if provider == generator.NameAnthropic {
		return map[string]any{
			"content": []any{map[string]any{"type": "text", "text": text}},
			"usage":   map[string]any{"input_tokens": in, "output_tokens": out},
		}
	}
	return map[string]any{
		"choices": []any{map[string]any{"message": map[string]any{"content": text}}},
		"usage":   map[string]any{"prompt_tokens": in, "completion_tokens": out},
	}
}

const doc = "# Rotate\n\n## Steps\n\n1. Pause.\n2. Rotate.\n"

func remoteRequest() generator.Request {
	return generator.Request{Kind: generator.KindExtraction, OrgID: "org", RepoID: "meridian",
		Scope: "atlas", Limits: generator.Limits{MaxProposals: 2, MaxTokens: 4000, MaxCalls: 3},
		Documents: []generator.Document{{Path: "docs/rotate.md", SHA256: sha(doc), Body: doc}}}
}

func goodAnswer() string {
	payload := map[string]any{"candidates": []any{map[string]any{
		"name": "Rotate the broker", "purpose": "Rotate a broker credential.",
		"when_to_use": "Every 90 days.",
		"steps": []any{
			map[string]any{"text": "Pause the consumer.", "source_ref": map[string]any{
				"path": "docs/rotate.md", "sha256": sha(doc), "line_from": 5, "line_to": 5}},
			map[string]any{"text": "Rotate the credential.", "needs_confirmation": true},
		},
	}}}
	raw, _ := json.Marshal(payload)
	return string(raw)
}

func TestRemoteProvidersAcceptSchemaValidOutput(t *testing.T) {
	for _, provider := range []string{generator.NameOpenAI, generator.NameAnthropic} {
		t.Run(provider, func(t *testing.T) {
			var calls atomic.Int32
			var sawKey, sawPrompt string
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				calls.Add(1)
				sawKey = r.Header.Get("Authorization") + r.Header.Get("x-api-key")
				body, _ := json.Marshal(map[string]any{})
				_ = body
				var decoded map[string]any
				_ = json.NewDecoder(r.Body).Decode(&decoded)
				sawPrompt = promptOf(decoded)
				w.Header().Set("Content-Type", "application/json")
				_ = json.NewEncoder(w).Encode(answer(provider, goodAnswer(), 1200, 300))
			}))
			defer server.Close()
			g := remoteFor(t, provider, server.URL, keyFile(t), map[string]string{
				"GUIDEFOLD_GENERATOR_USD_PER_MTOK_IN":  "1",
				"GUIDEFOLD_GENERATOR_USD_PER_MTOK_OUT": "2",
			})
			out, cost, e := g.Generate(context.Background(), remoteRequest())
			if e != nil {
				t.Fatal(e)
			}
			if calls.Load() != 1 {
				t.Fatalf("expected one call, got %d", calls.Load())
			}
			if !strings.Contains(sawKey, "sk-test-not-a-real-key") {
				t.Fatalf("the key file was not used")
			}
			if !strings.Contains(sawPrompt, "1: # Rotate") {
				t.Errorf("the prompt does not carry numbered source lines:\n%s", sawPrompt)
			}
			if len(out.Candidates) != 1 {
				t.Fatalf("expected one candidate, got %d", len(out.Candidates))
			}
			c := out.Candidates[0]
			cited, confirm := 0, 0
			for _, f := range c.Fields {
				if !strings.HasPrefix(f.Field, "steps[") {
					continue
				}
				if f.Ref != nil {
					cited++
					if f.Origin != generator.OriginParsed {
						t.Errorf("a verified citation must be parsed, got %q", f.Origin)
					}
				} else if f.NeedsConfirmation {
					confirm++
				} else {
					t.Errorf("step %q has neither a reference nor needs_confirmation", f.Field)
				}
			}
			if cited != 1 || confirm != 1 {
				t.Fatalf("expected one cited and one unconfirmed step, got %d/%d", cited, confirm)
			}
			if cost.Calls != 1 || cost.TokensIn != 1200 || cost.TokensOut != 300 {
				t.Fatalf("cost %+v does not report the provider's own usage", cost)
			}
			if cost.USDCertain <= 0 {
				t.Fatalf("a priced deployment must report a certain cost, got %+v", cost)
			}
		})
	}
}

func promptOf(body map[string]any) string {
	messages, _ := body["messages"].([]any)
	for _, m := range messages {
		entry, _ := m.(map[string]any)
		if entry != nil && entry["role"] == "user" {
			s, _ := entry["content"].(string)
			return s
		}
	}
	return ""
}

// A model that cites a document it was not given is inventing evidence. The
// citation is dropped and the field falls back to needs_confirmation rather
// than being believed.
func TestRemoteRejectsAFabricatedCitation(t *testing.T) {
	payload := map[string]any{"candidates": []any{map[string]any{
		"name": "Rotate", "purpose": "Rotate.",
		"steps": []any{map[string]any{"text": "Pause.", "source_ref": map[string]any{
			"path": "docs/does-not-exist.md", "sha256": sha("nothing"),
			"line_from": 1, "line_to": 2}}},
	}}}
	raw, _ := json.Marshal(payload)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(answer(generator.NameOpenAI, string(raw), 10, 10))
	}))
	defer server.Close()
	g := remoteFor(t, generator.NameOpenAI, server.URL, keyFile(t), nil)
	out, _, e := g.Generate(context.Background(), remoteRequest())
	if e != nil {
		t.Fatal(e)
	}
	for _, f := range out.Candidates[0].Fields {
		if f.Field == "steps[0]" {
			if f.Ref != nil {
				t.Fatalf("a citation to a document that was never supplied was believed: %+v", f.Ref)
			}
			if !f.NeedsConfirmation {
				t.Fatal("a rejected citation must leave the field needing confirmation")
			}
		}
	}
}

// Malformed output is retried a bounded number of times and then fails the
// group. A candidate without provenance is worse than no candidate.
func TestRemoteRetriesInvalidJSONAtMostTwice(t *testing.T) {
	for name, body := range map[string]string{
		"not_json":       "I am afraid I cannot do that.",
		"missing_steps":  `{"candidates":[{"name":"x","purpose":"y"}]}`,
		"unprovenanced":  `{"candidates":[{"name":"x","purpose":"y","steps":[{"text":"do it"}]}]}`,
		"unknown_field":  `{"candidates":[{"name":"x","purpose":"y","steps":[{"text":"a","needs_confirmation":true}],"extra":1}]}`,
		"bad_sha_in_ref": `{"candidates":[{"name":"x","purpose":"y","steps":[{"text":"a","source_ref":{"path":"p","sha256":"zz","line_from":1,"line_to":1}}]}]}`,
	} {
		t.Run(name, func(t *testing.T) {
			var calls atomic.Int32
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				calls.Add(1)
				_ = json.NewEncoder(w).Encode(answer(generator.NameOpenAI, body, 5, 5))
			}))
			defer server.Close()
			g := remoteFor(t, generator.NameOpenAI, server.URL, keyFile(t), nil)
			_, cost, e := g.Generate(context.Background(), remoteRequest())
			if e == nil {
				t.Fatal("invalid output must not become a proposal")
			}
			if calls.Load() != 3 {
				t.Fatalf("expected 1 attempt plus 2 retries, got %d calls", calls.Load())
			}
			if cost.Calls != 3 {
				t.Fatalf("every attempt is a call that was paid for, got %+v", cost)
			}
		})
	}
}

// A request that left and then timed out may still be billed. The charge is
// recorded as uncertain, never as zero, and the call is not repeated (U2.3).
func TestRemoteTimeoutRecordsUncertainCost(t *testing.T) {
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		time.Sleep(2 * time.Second)
	}))
	defer server.Close()
	g := remoteFor(t, generator.NameOpenAI, server.URL, keyFile(t), map[string]string{
		"GUIDEFOLD_GENERATOR_TIMEOUT_SECONDS":  "1",
		"GUIDEFOLD_GENERATOR_USD_PER_MTOK_IN":  "10",
		"GUIDEFOLD_GENERATOR_USD_PER_MTOK_OUT": "30",
	})
	_, cost, e := g.Generate(context.Background(), remoteRequest())
	if e == nil {
		t.Fatal("a timeout is not a success")
	}
	if calls.Load() != 1 {
		t.Fatalf("a timed-out call must not be retried, got %d calls", calls.Load())
	}
	if cost.USDUncertain <= 0 {
		t.Fatalf("a timed-out call costs an unknown amount, not zero: %+v", cost)
	}
	if cost.USDCertain != 0 {
		t.Fatalf("nothing about a timed-out call is certain: %+v", cost)
	}
}

// ADR-0045: a deployment with no key file is a valid, BYOK-only configuration
// now -- every organisation using it must supply its own stored key. Select
// must not refuse to start for that; only a request that arrives with neither
// a request key nor this file ends its own job, not the worker.
func TestRemoteWithNoKeyFileStartsAndEndsAJobWithNoRequestKey(t *testing.T) {
	engine, _, e := generator.Select(func(name string) string {
		if name == "GUIDEFOLD_GENERATOR" {
			return generator.NameOpenAI
		}
		return ""
	})
	if e != nil {
		t.Fatalf("a deployment with no key file failed to start: %v", e)
	}
	_, _, e = engine.Generate(context.Background(), generator.Request{})
	if !errors.Is(e, generator.ErrCredentialMissing) {
		t.Fatalf("expected ErrCredentialMissing with no request key and no deployment file, got %v", e)
	}
}

// A request that carries its own key is used even though the deployment has
// none configured -- the organisation's key, opened by review.GenerateWorker
// through internal/secrets, is enough on its own (ADR-0045).
func TestRemoteWithNoKeyFileUsesTheRequestsOwnKey(t *testing.T) {
	var sawAuth string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sawAuth = r.Header.Get("Authorization")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"choices": []any{map[string]any{"message": map[string]any{
				"content": `{"candidates":[]}`}}}})
	}))
	defer server.Close()
	engine, _, e := generator.Select(func(name string) string {
		switch name {
		case "GUIDEFOLD_GENERATOR":
			return generator.NameOpenAI
		case "OPENAI_BASE_URL":
			return server.URL
		default:
			return ""
		}
	})
	if e != nil {
		t.Fatal(e)
	}
	_, _, e = engine.Generate(context.Background(), generator.Request{APIKey: "sk-from-the-organisation"})
	if e != nil {
		t.Fatal(e)
	}
	if sawAuth != "Bearer sk-from-the-organisation" {
		t.Fatalf("the provider saw authorization %q, not the request's own key", sawAuth)
	}
}

// The provider's own error text can echo the prompt back. It never reaches the
// caller.
func TestRemoteDoesNotEchoProviderErrorText(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"error": map[string]any{"message": "your prompt said SECRET-CANARY"}})
	}))
	defer server.Close()
	g := remoteFor(t, generator.NameOpenAI, server.URL, keyFile(t), nil)
	_, _, e := g.Generate(context.Background(), remoteRequest())
	if e == nil {
		t.Fatal("a 400 from the provider is not a success")
	}
	if strings.Contains(e.Error(), "SECRET-CANARY") {
		t.Fatalf("the provider's message reached the caller: %v", e)
	}
}

// G3 — the per-group call ceiling was `MaxCalls > 0 && MaxCalls < 1`, which no
// integer satisfies, so nothing bounded the retry loop inside one Generate. The
// caller passes the budget that is *left*; a group given one call must make one
// provider call and then stop, even though its answer never validates.
func TestGenerateStopsAtTheRemainingCallBudget(t *testing.T) {
	for _, provider := range []string{generator.NameOpenAI, generator.NameAnthropic} {
		t.Run(provider, func(t *testing.T) {
			var calls atomic.Int32
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				calls.Add(1)
				w.Header().Set("Content-Type", "application/json")
				_ = json.NewEncoder(w).Encode(answer(provider, "not json at all", 10, 10))
			}))
			defer server.Close()
			g := remoteFor(t, provider, server.URL, keyFile(t), nil)

			req := remoteRequest()
			req.Limits.MaxCalls = 1
			_, cost, e := g.Generate(context.Background(), req)
			if e == nil || !strings.Contains(e.Error(), "generator_call_budget_exhausted") {
				t.Fatalf("the budget did not stop the retries: %v", e)
			}
			if got := calls.Load(); got != 1 {
				t.Fatalf("a one-call budget bought %d provider calls", got)
			}
			if cost.Calls != 1 {
				t.Fatalf("cost reports %d calls", cost.Calls)
			}

			// With no budget left at all, nothing is spent.
			calls.Store(0)
			req.Limits.MaxCalls = 0
			_, _, e = g.Generate(context.Background(), req)
			if e == nil {
				t.Fatal("an invalid answer was accepted")
			}
			if got := calls.Load(); got != int32(3) {
				t.Fatalf("an unlimited budget made %d calls, not the bounded retry count", got)
			}
		})
	}
}
