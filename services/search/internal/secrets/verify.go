package secrets

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

// HTTPVerifier checks a key by making the cheapest authenticated call each
// provider offers. It exists so a key that cannot work is refused while the
// owner is still looking at the screen, instead of failing later inside a
// background job (ADR-0045 §5).
//
// Only two answers matter. A 401 or 403 means the provider rejected the key, so
// the write is refused with `credential_invalid`. Anything else -- a timeout, a
// 500, a network error -- means we could not tell, which is reported as the
// provider being unreachable. Reporting "we could not tell" as "your key is
// wrong" would send an owner hunting for a problem in their own account.
type HTTPVerifier struct {
	Client   *http.Client
	Endpoint func(provider string) (method, url string, header func(*http.Request))
}

// NewHTTPVerifier builds the default verifier. Endpoints are overridable so a
// test can point at httptest without a network.
func NewHTTPVerifier() *HTTPVerifier {
	return &HTTPVerifier{Client: &http.Client{Timeout: 10 * time.Second}, Endpoint: defaultEndpoint}
}

func base(provider string) string {
	// Overridable per provider so a self-hosted gateway or a test server can
	// stand in; unset means the provider's own API.
	if v := strings.TrimSpace(os.Getenv("GUIDEFOLD_" + strings.ToUpper(provider) + "_BASE_URL")); v != "" {
		return strings.TrimSuffix(v, "/")
	}
	switch provider {
	case ProviderOpenRouter:
		return "https://openrouter.ai/api/v1"
	case ProviderAnthropic:
		return "https://api.anthropic.com/v1"
	case ProviderOpenAI:
		return "https://api.openai.com/v1"
	}
	return ""
}

func defaultEndpoint(provider string) (string, string, func(*http.Request)) {
	switch provider {
	case ProviderOpenRouter:
		// Key introspection. This path is unverified against the provider's
		// current API (ADR-0045 References), which is safe only because of how
		// Verify reads the answer: a wrong path gives 404, which is neither 401
		// nor 2xx, so it surfaces as "we could not reach the provider" rather
		// than as an invalid key. Nobody is told their good key is bad.
		return http.MethodGet, base(provider) + "/key", func(r *http.Request) {
			r.Header.Set("Authorization", "Bearer "+r.Header.Get("X-Key"))
			r.Header.Del("X-Key")
		}
	case ProviderAnthropic:
		return http.MethodGet, base(provider) + "/models?limit=1", func(r *http.Request) {
			r.Header.Set("x-api-key", r.Header.Get("X-Key"))
			r.Header.Set("anthropic-version", "2023-06-01")
			r.Header.Del("X-Key")
		}
	case ProviderOpenAI:
		return http.MethodGet, base(provider) + "/models", func(r *http.Request) {
			r.Header.Set("Authorization", "Bearer "+r.Header.Get("X-Key"))
			r.Header.Del("X-Key")
		}
	}
	return "", "", nil
}

// Verify reports ErrRejected for a key the provider refuses, nil for one it
// accepts, and any other error when the answer could not be obtained.
func (v *HTTPVerifier) Verify(ctx context.Context, provider, apiKey string) error {
	endpoint := v.Endpoint
	if endpoint == nil {
		endpoint = defaultEndpoint
	}
	method, url, header := endpoint(provider)
	if url == "" || header == nil {
		return fmt.Errorf("secrets: no verification endpoint for provider %q", provider)
	}
	req, e := http.NewRequestWithContext(ctx, method, url, nil)
	if e != nil {
		return e
	}
	req.Header.Set("X-Key", apiKey)
	header(req)
	client := v.Client
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	resp, e := client.Do(req)
	if e != nil {
		return e
	}
	defer func() { _ = resp.Body.Close() }()
	switch {
	case resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden:
		return ErrRejected
	case resp.StatusCode >= 200 && resp.StatusCode < 300:
		return nil
	default:
		return fmt.Errorf("secrets: %s answered %d while checking the key", provider, resp.StatusCode)
	}
}
