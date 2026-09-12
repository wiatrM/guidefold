package model

import "net/http"

// newOpenAIClient builds the OpenAI concern: the same
// /v1/chat/completions streaming shape chatcompletions.go implements once,
// against OpenAI's own host. Base URL is overridable through
// OPENAI_BASE_URL — the same environment variable name
// internal/review/generator already reads for its own OpenAI calls, so the
// two packages agree on where "OpenAI" points in a given deployment.
func newOpenAIClient(env func(string) string, httpClient *http.Client) Client {
	return &chatCompletionsClient{
		provider: ProviderOpenAI,
		baseURL:  firstNonEmpty(env("OPENAI_BASE_URL"), "https://api.openai.com"),
		http:     httpClient,
	}
}
