package ghapp

import (
	"context"
	"crypto/rsa"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

// tokenRefreshMargin is how far ahead of GitHub's own expiry this package
// treats a cached token as stale. A caller mid-request when the token turned
// invalid would see a 401 partway through a job; refreshing early trades a
// slightly shorter effective lifetime for that never happening.
const tokenRefreshMargin = 5 * time.Minute

// requestTimeout bounds every call this package makes. GitHub's read APIs
// answer in well under a second in normal operation; a job stuck waiting on
// a hung connection is a job that never reaches its own checkpoint or
// cancellation check.
const requestTimeout = 30 * time.Second

// Client is the App's identity plus one process-lifetime cache of
// installation tokens. It is safe for concurrent use: multiple live.repo
// jobs for the same organisation share one installation token instead of
// each exchanging its own.
type Client struct {
	baseURL    string
	appID      string
	privateKey *rsa.PrivateKey
	http       *http.Client
	now        func() time.Time

	mu     sync.Mutex
	tokens map[int64]cachedToken
}

type cachedToken struct {
	token   string
	expires time.Time
}

// New builds a Client from an already-resolved Config. Kept separate from
// NewFromEnv so a caller that already validated configuration elsewhere (or
// that builds a Config in a test with a Client pointed at httptest) does not
// have to round-trip through environment variables.
func New(cfg Config) (*Client, error) {
	if strings.TrimSpace(cfg.AppID) == "" || cfg.PrivateKey == nil {
		return nil, ErrNotConfigured
	}
	base := strings.TrimSuffix(cfg.BaseURL, "/")
	if base == "" {
		base = DefaultBaseURL
	}
	return &Client{
		baseURL:    base,
		appID:      cfg.AppID,
		privateKey: cfg.PrivateKey,
		http:       &http.Client{Timeout: requestTimeout},
		now:        time.Now,
		tokens:     map[int64]cachedToken{},
	}, nil
}

// NewFromEnv is ConfigFromEnv followed by New, for the common case of a
// worker process building its one Client at startup.
func NewFromEnv(env func(string) string) (*Client, error) {
	cfg, err := ConfigFromEnv(env)
	if err != nil {
		return nil, err
	}
	return New(cfg)
}

// SetClock replaces the client's clock. Only a test uses it, to move token
// caching past its expiry without an hour of wall-clock time passing.
func (c *Client) SetClock(now func() time.Time) { c.now = now }

// installationToken returns a valid installation token, from the cache when
// one is fresh enough and from GitHub otherwise. It is unexported on
// purpose: ListSkillFiles and ReadFile are this package's entire surface
// (see doc.go), and a plain string return from an exported method is exactly
// the "returned to a caller outside this package" this package refuses to
// do with the token.
func (c *Client) installationToken(ctx context.Context, installationID int64) (string, error) {
	if cached, ok := c.freshToken(installationID); ok {
		return cached, nil
	}
	token, expires, err := c.exchangeInstallationToken(ctx, installationID)
	if err != nil {
		return "", err
	}
	c.mu.Lock()
	c.tokens[installationID] = cachedToken{token: token, expires: expires}
	c.mu.Unlock()
	return token, nil
}

func (c *Client) freshToken(installationID int64) (string, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	cached, ok := c.tokens[installationID]
	if !ok || !c.now().Before(cached.expires.Add(-tokenRefreshMargin)) {
		return "", false
	}
	return cached.token, true
}

// exchangeInstallationToken is the one write this read-only package makes to
// GitHub: POST /app/installations/{id}/access_tokens, authenticated with the
// App's own JWT rather than an installation token (there is no installation
// token yet — that is what this call produces).
func (c *Client) exchangeInstallationToken(ctx context.Context, installationID int64) (string, time.Time, error) {
	jwt, err := c.appJWT()
	if err != nil {
		return "", time.Time{}, err
	}
	url := c.baseURL + "/app/installations/" + strconv.FormatInt(installationID, 10) + "/access_tokens"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, nil)
	if err != nil {
		return "", time.Time{}, err
	}
	req.Header.Set("Authorization", "Bearer "+jwt)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	resp, err := c.http.Do(req)
	if err != nil {
		return "", time.Time{}, fmt.Errorf("ghapp: installation token request failed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotFound {
		return "", time.Time{}, ErrInstallationNotFound
	}
	if resp.StatusCode != http.StatusCreated {
		// GitHub's own body is not echoed: on other endpoints it can carry
		// back request content, and there is no reason to trust this one not
		// to change that.
		return "", time.Time{}, fmt.Errorf("ghapp: installation token exchange answered %d", resp.StatusCode)
	}
	var body struct {
		Token     string    `json:"token"`
		ExpiresAt time.Time `json:"expires_at"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return "", time.Time{}, fmt.Errorf("ghapp: installation token response is unreadable: %w", err)
	}
	if body.Token == "" {
		return "", time.Time{}, fmt.Errorf("ghapp: installation token response carried no token")
	}
	return body.Token, body.ExpiresAt, nil
}
