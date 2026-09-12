package model_test

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/model"
)

// The three providers are tested against fakes, not against a vendor — the
// same reasoning internal/review/generator's own remote_test.go states for
// its HTTP providers: what is being checked is this package's own contract
// (deltas arrive in order, usage is read when present and marked estimated
// when absent, the four named errors come from the status and body that
// causes them, the key never leaks), none of which depends on which vendor
// answered.

const testKey = "sk-test-0123456789-not-a-real-key"

func envFor(provider, base string) func(string) string {
	values := map[string]string{
		"OPENROUTER_BASE_URL": base,
		"OPENAI_BASE_URL":     base,
		"ANTHROPIC_BASE_URL":  base,
	}
	_ = provider
	return func(name string) string { return values[name] }
}

func newClient(t *testing.T, provider, base string) model.Client {
	t.Helper()
	c, e := model.New(provider, envFor(provider, base))
	if e != nil {
		t.Fatal(e)
	}
	return c
}

func request() model.Request {
	return model.Request{APIKey: testKey, Model: "test-model",
		Messages: []model.Message{{Role: model.RoleUser, Content: "hello"}}}
}

func sse(events ...string) string {
	return strings.Join(events, "") + "\n"
}

func dataEvent(payload string) string { return "data: " + payload + "\n\n" }

func namedEvent(name, payload string) string {
	return "event: " + name + "\ndata: " + payload + "\n\n"
}

// --- deltas arrive in order -------------------------------------------------

func TestOpenRouterDeltasArriveInOrder(t *testing.T)   { testChatDeltaOrder(t, model.ProviderOpenRouter) }
func TestOpenAIDeltasArriveInOrder(t *testing.T)        { testChatDeltaOrder(t, model.ProviderOpenAI) }

func testChatDeltaOrder(t *testing.T, provider string) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		body := sse(
			dataEvent(`{"choices":[{"delta":{"content":"one "}}]}`),
			dataEvent(`{"choices":[{"delta":{"content":"two "}}]}`),
			dataEvent(`{"choices":[{"delta":{"content":"three"}}]}`),
			dataEvent(`{"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":3}}`),
			dataEvent(`[DONE]`),
		)
		_, _ = w.Write([]byte(body))
	}))
	defer server.Close()

	c := newClient(t, provider, server.URL)
	var got []string
	usage, e := c.Stream(context.Background(), request(), func(text string) { got = append(got, text) })
	if e != nil {
		t.Fatal(e)
	}
	if strings.Join(got, "") != "one two three" {
		t.Fatalf("deltas out of order or missing: %v", got)
	}
	if usage.Estimated {
		t.Fatalf("usage should be measured, not estimated: %+v", usage)
	}
	if usage.TokensIn != 5 || usage.TokensOut != 3 {
		t.Fatalf("usage not read from the provider's response: %+v", usage)
	}
}

func TestAnthropicDeltasArriveInOrder(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		body := sse(
			namedEvent("message_start", `{"type":"message_start","message":{"usage":{"input_tokens":7}}}`),
			namedEvent("content_block_delta", `{"delta":{"type":"text_delta","text":"one "}}`),
			namedEvent("content_block_delta", `{"delta":{"type":"text_delta","text":"two "}}`),
			namedEvent("content_block_delta", `{"delta":{"type":"text_delta","text":"three"}}`),
			namedEvent("message_delta", `{"usage":{"output_tokens":4}}`),
			namedEvent("message_stop", `{}`),
		)
		_, _ = w.Write([]byte(body))
	}))
	defer server.Close()

	c := newClient(t, model.ProviderAnthropic, server.URL)
	var got []string
	usage, e := c.Stream(context.Background(), request(), func(text string) { got = append(got, text) })
	if e != nil {
		t.Fatal(e)
	}
	if strings.Join(got, "") != "one two three" {
		t.Fatalf("deltas out of order or missing: %v", got)
	}
	if usage.Estimated || usage.TokensIn != 7 || usage.TokensOut != 4 {
		t.Fatalf("usage not read from the provider's response: %+v", usage)
	}
}

// --- usage is estimated, and marked as such, when the provider omits it ---

func TestUsageIsEstimatedWhenProviderOmitsIt(t *testing.T) {
	for _, provider := range []string{model.ProviderOpenRouter, model.ProviderOpenAI} {
		provider := provider
		t.Run(provider, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "text/event-stream")
				_, _ = w.Write([]byte(sse(
					dataEvent(`{"choices":[{"delta":{"content":"some text back"}}]}`),
					dataEvent(`[DONE]`),
				)))
			}))
			defer server.Close()
			c := newClient(t, provider, server.URL)
			usage, e := c.Stream(context.Background(), request(), func(string) {})
			if e != nil {
				t.Fatal(e)
			}
			if !usage.Estimated {
				t.Fatalf("usage without a provider figure must be marked estimated: %+v", usage)
			}
			if usage.TokensOut <= 0 {
				t.Fatalf("an estimate should still be a positive guess, not zero: %+v", usage)
			}
		})
	}
}

func TestAnthropicUsageIsEstimatedWhenProviderOmitsIt(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = w.Write([]byte(sse(
			namedEvent("content_block_delta", `{"delta":{"type":"text_delta","text":"partial"}}`),
		)))
	}))
	defer server.Close()
	c := newClient(t, model.ProviderAnthropic, server.URL)
	usage, e := c.Stream(context.Background(), request(), func(string) {})
	if e != nil {
		t.Fatal(e)
	}
	if !usage.Estimated {
		t.Fatalf("usage without message_delta must be marked estimated: %+v", usage)
	}
}

// --- named errors from status and body -------------------------------------

func openAIErrorBody(kind, message string) string {
	return fmt.Sprintf(`{"error":{"type":%q,"message":%q}}`, kind, message)
}

func TestNamedErrorsFromStatusAndBody(t *testing.T) {
	cases := []struct {
		name     string
		provider string
		status   int
		body     string
		want     error
	}{
		{"openai_402_quota", model.ProviderOpenAI, http.StatusPaymentRequired,
			openAIErrorBody("insufficient_quota", "account has no funds"), model.ErrQuotaExhausted},
		{"openrouter_429_quota_body", model.ProviderOpenRouter, http.StatusTooManyRequests,
			openAIErrorBody("insufficient_quota", "You exceeded your current quota"), model.ErrQuotaExhausted},
		{"openai_429_plain_rate", model.ProviderOpenAI, http.StatusTooManyRequests,
			openAIErrorBody("rate_limit_error", "Too many requests, slow down"), model.ErrRateLimited},
		{"openai_404_model", model.ProviderOpenAI, http.StatusNotFound,
			openAIErrorBody("invalid_request_error", "The model 'nope' does not exist"), model.ErrModelNotAvailable},
		{"openai_401", model.ProviderOpenAI, http.StatusUnauthorized,
			openAIErrorBody("invalid_api_key", "Incorrect API key provided"), model.ErrUnauthorized},
		{"openrouter_402_quota", model.ProviderOpenRouter, http.StatusPaymentRequired,
			openAIErrorBody("insufficient_quota", "no credit"), model.ErrQuotaExhausted},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(tc.status)
				_, _ = w.Write([]byte(tc.body))
			}))
			defer server.Close()
			c := newClient(t, tc.provider, server.URL)
			_, e := c.Stream(context.Background(), request(), func(string) {})
			if !errors.Is(e, tc.want) {
				t.Fatalf("got %v, want %v", e, tc.want)
			}
		})
	}
}

func TestAnthropicNamedErrorsFromStatusAndBody(t *testing.T) {
	cases := []struct {
		name   string
		status int
		body   string
		want   error
	}{
		{"401_unauthorized", http.StatusUnauthorized,
			`{"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}`, model.ErrUnauthorized},
		{"429_plain_rate", http.StatusTooManyRequests,
			`{"type":"error","error":{"type":"rate_limit_error","message":"rate limited"}}`, model.ErrRateLimited},
		{"400_credit_balance_is_quota", http.StatusBadRequest,
			`{"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low"}}`, model.ErrQuotaExhausted},
		{"404_model_not_found", http.StatusNotFound,
			`{"type":"error","error":{"type":"not_found_error","message":"model: no such model"}}`, model.ErrModelNotAvailable},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(tc.status)
				_, _ = w.Write([]byte(tc.body))
			}))
			defer server.Close()
			c := newClient(t, model.ProviderAnthropic, server.URL)
			_, e := c.Stream(context.Background(), request(), func(string) {})
			if !errors.Is(e, tc.want) {
				t.Fatalf("got %v, want %v", e, tc.want)
			}
		})
	}
}

// Anthropic can fail mid-stream, inside an otherwise-200 response, rather
// than with a non-2xx status — the one place this port classifies a failure
// with no HTTP status to key on.
func TestAnthropicMidStreamErrorEvent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = w.Write([]byte(sse(
			namedEvent("content_block_delta", `{"delta":{"type":"text_delta","text":"partial answer"}}`),
			namedEvent("error", `{"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}`),
		)))
	}))
	defer server.Close()
	c := newClient(t, model.ProviderAnthropic, server.URL)
	_, e := c.Stream(context.Background(), request(), func(string) {})
	if e == nil {
		t.Fatal("a mid-stream error event must surface as a failure")
	}
}

// --- the input ceiling is enforced before any request leaves the package --

func TestInputCeilingRefusesBeforeTheRequestLeaves(t *testing.T) {
	called := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
	}))
	defer server.Close()
	c := newClient(t, model.ProviderOpenAI, server.URL)
	req := request()
	req.Messages = []model.Message{{Role: model.RoleUser, Content: strings.Repeat("word ", 1000)}}
	req.MaxInputTokens = 10
	_, e := c.Stream(context.Background(), req, func(string) {})
	if e == nil {
		t.Fatal("an oversize prompt must be refused")
	}
	if called {
		t.Fatal("the ceiling must be enforced before any HTTP request is made")
	}
}

// --- the key never appears in a returned value or an error string ---------

func TestKeyNeverLeaksIntoAnErrorOrUsage(t *testing.T) {
	providers := []struct {
		name string
		base func(*httptest.Server) string
	}{
		{model.ProviderOpenAI, func(s *httptest.Server) string { return s.URL }},
		{model.ProviderOpenRouter, func(s *httptest.Server) string { return s.URL }},
		{model.ProviderAnthropic, func(s *httptest.Server) string { return s.URL }},
	}
	for _, p := range providers {
		p := p
		t.Run(p.name+"_http_error", func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				// Echo the whole request body back, the way a broken proxy
				// or a provider bug might — the key must still not leak
				// because it was never in the body to begin with.
				body := make([]byte, r.ContentLength)
				_, _ = r.Body.Read(body)
				w.WriteHeader(http.StatusInternalServerError)
				_, _ = w.Write([]byte(`{"error":{"type":"server_error","message":"internal error, request: ` +
					string(body) + `"}}`))
			}))
			defer server.Close()
			c := newClient(t, p.name, p.base(server))
			_, e := c.Stream(context.Background(), request(), func(string) {})
			if e == nil {
				t.Fatal("expected an error")
			}
			if strings.Contains(e.Error(), testKey) {
				t.Fatalf("the key leaked into an error string: %v", e)
			}
		})
		t.Run(p.name+"_malformed_stream", func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "text/event-stream")
				_, _ = w.Write([]byte("not a valid sse body at all\n\n"))
			}))
			defer server.Close()
			c := newClient(t, p.name, p.base(server))
			usage, e := c.Stream(context.Background(), request(), func(string) {})
			if e != nil && strings.Contains(e.Error(), testKey) {
				t.Fatalf("the key leaked into an error string: %v", e)
			}
			if fmt.Sprintf("%+v", usage) != "" && strings.Contains(fmt.Sprintf("%+v", usage), testKey) {
				t.Fatalf("the key leaked into a usage value: %+v", usage)
			}
		})
	}
}

// New itself must not echo an unknown provider's caller-supplied string in a
// way that could ever be confused with key material; this also just locks
// down the unknown-provider error shape.
func TestNewRefusesUnknownProvider(t *testing.T) {
	if _, e := model.New("not-a-real-provider", func(string) string { return "" }); e == nil {
		t.Fatal("an unknown provider must be refused")
	}
}
