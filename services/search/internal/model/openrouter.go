package model

import "net/http"

// newOpenRouterClient builds the OpenRouter concern: one account reaching
// many vendors' models through a single OpenAI-compatible endpoint
// (chatcompletions.go), authenticated with a plain Bearer key. Base URL is
// overridable through OPENROUTER_BASE_URL so a test points this at an
// httptest server instead of the real host.
func newOpenRouterClient(env func(string) string, httpClient *http.Client) Client {
	return &chatCompletionsClient{
		provider: ProviderOpenRouter,
		baseURL:  firstNonEmpty(env("OPENROUTER_BASE_URL"), "https://openrouter.ai/api"),
		http:     httpClient,
	}
}
