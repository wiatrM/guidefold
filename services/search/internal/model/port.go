package model

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"time"
)

// The closed domain of providers. Matches internal/secrets.Provider* by
// value on purpose — the two packages describe the same three accounts from
// different angles (secrets: where the key is stored; model: how it is
// used) — but model does not import secrets, so a caller with only a
// provider string never has to import the credential package just to make a
// request.
const (
	ProviderOpenRouter = "openrouter"
	ProviderAnthropic  = "anthropic"
	ProviderOpenAI     = "openai"
)

// Chat roles a Message may carry.
const (
	RoleUser      = "user"
	RoleAssistant = "assistant"
)

// Message is one turn of the conversation. System instructions are a
// separate field on Request rather than a role here: Anthropic's wire
// format never accepts "system" as a message role, and folding it in only
// for OpenAI-shaped providers to strip back out would make Request lie
// about what every provider actually receives.
type Message struct {
	Role    string
	Content string
}

// Usage is what one call cost. Estimated is true exactly when the
// provider's own response carried no usage figures and TokensIn/TokensOut
// are this package's own estimate from character counts — a caller must
// never present an estimated Usage as a measurement (ADR-0046 §5).
type Usage struct {
	TokensIn  int
	TokensOut int
	Estimated bool
}

// Request is one streamed chat completion.
type Request struct {
	// APIKey belongs to the organisation (ADR-0045), never to the
	// deployment. It lives in this struct only for the duration of one
	// Stream call: never stored, never logged, never part of a checkpoint,
	// a job payload or an error this package returns.
	APIKey string
	Model  string
	System string

	Messages []Message

	// MaxInputTokens bounds the estimated size of System+Messages, checked
	// before any request leaves this package — no provider accepts a
	// parameter for "refuse a prompt over N tokens", so the ceiling has to
	// be enforced on this side or not at all. Zero means unbounded.
	MaxInputTokens int
	// MaxOutputTokens is passed to the provider as its own completion-length
	// cap. Zero uses the provider's own default.
	MaxOutputTokens int
}

// DeltaFunc receives one text fragment as it streams in, in arrival order.
// A caller batches these into its own event log rather than this package
// doing it: how often a delta becomes a durable row is a policy of the
// caller (internal/agentrun batches at ~500 ms or ~2 KB, ADR-0046 §4), not
// of the transport.
type DeltaFunc func(text string)

// Client streams one chat completion against one provider, authenticated
// with the key the caller supplies on every call.
type Client interface {
	Stream(ctx context.Context, req Request, onDelta DeltaFunc) (Usage, error)
}

// defaultCallTimeout bounds one provider round trip, matching the
// generator package's own DefaultTimeout: a live run's checkpoint interval
// is what makes cancellation prompt, and a call stuck open past that would
// defeat it regardless of what this package's own timeout says — this
// timeout exists to bound a hung connection, not to race the checkpoint.
const defaultCallTimeout = 120 * time.Second

// New builds the client for one provider, reading its base URL override
// through env rather than os.Getenv directly — the same pattern
// internal/ghapp.ConfigFromEnv and internal/review/generator use, so a test
// supplies values without mutating process-wide environment variables other
// parallel tests also read. The organisation's key is never read here: it
// travels on Request, per call, from wherever the caller opened it
// (internal/secrets.OpenFor).
func New(provider string, env func(string) string) (Client, error) {
	if env == nil {
		env = os.Getenv
	}
	httpClient := &http.Client{Timeout: defaultCallTimeout}
	switch provider {
	case ProviderOpenRouter:
		return newOpenRouterClient(env, httpClient), nil
	case ProviderOpenAI:
		return newOpenAIClient(env, httpClient), nil
	case ProviderAnthropic:
		return newAnthropicClient(env, httpClient), nil
	}
	return nil, fmt.Errorf("model: unknown provider %q", provider)
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}
