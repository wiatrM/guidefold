package ghapp

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// UserOAuthConfig is the client credentials for GitHub's user-to-server
// OAuth exchange during App installation ("Request user authorization
// (OAuth) during installation") — ADR-0034's explicit link. It is a
// different GitHub mechanism from the App's own JWT (Config, above) and
// needs no private key, only the client id and secret issued once when the
// App is registered. Kept separate from Config and from *Client because
// linking happens in the API (internal/identity), which never opens the
// App's private key the worker uses for installation tokens.
type UserOAuthConfig struct {
	ClientID     string
	ClientSecret string
	// AuthBaseURL overrides https://github.com for a test.
	AuthBaseURL string
	// APIBaseURL overrides https://api.github.com for a test.
	APIBaseURL string
}

func (c UserOAuthConfig) authBase() string {
	if b := strings.TrimSuffix(strings.TrimSpace(c.AuthBaseURL), "/"); b != "" {
		return b
	}
	return "https://github.com"
}

func (c UserOAuthConfig) apiBase() string {
	if b := strings.TrimSuffix(strings.TrimSpace(c.APIBaseURL), "/"); b != "" {
		return b
	}
	return DefaultBaseURL
}

var userOAuthHTTP = &http.Client{Timeout: 15 * time.Second}

// ExchangeUserCode trades the "code" GitHub's installation redirect carries
// for a short-lived user access token (POST /login/oauth/access_token). The
// client secret and the returned token never appear in a returned error.
func ExchangeUserCode(ctx context.Context, cfg UserOAuthConfig, code string) (string, error) {
	if strings.TrimSpace(cfg.ClientID) == "" || strings.TrimSpace(cfg.ClientSecret) == "" {
		return "", ErrNotConfigured
	}
	if strings.TrimSpace(code) == "" {
		return "", fmt.Errorf("ghapp: empty authorization code")
	}
	form := url.Values{"client_id": {cfg.ClientID}, "client_secret": {cfg.ClientSecret}, "code": {code}}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, cfg.authBase()+"/login/oauth/access_token",
		strings.NewReader(form.Encode()))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Accept", "application/json")
	resp, err := userOAuthHTTP.Do(req)
	if err != nil {
		return "", fmt.Errorf("ghapp: user code exchange: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<16))
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("ghapp: user code exchange answered %d", resp.StatusCode)
	}
	var out struct {
		AccessToken string `json:"access_token"`
		Error       string `json:"error"`
	}
	if err := json.Unmarshal(body, &out); err != nil {
		return "", fmt.Errorf("ghapp: user code exchange: unreadable response")
	}
	if out.Error != "" {
		return "", fmt.Errorf("ghapp: user code exchange refused: %s", out.Error)
	}
	if out.AccessToken == "" {
		return "", fmt.Errorf("ghapp: user code exchange returned no token")
	}
	return out.AccessToken, nil
}

// UserInstallation is one entry of GET /user/installations: an id the
// linking callback checks a claimed installation_id against, and the
// account login the callback writes into gfm.github_installations so a
// linked installation never shows a blank account before its own
// "installation" webhook happens to arrive.
type UserInstallation struct {
	ID           int64
	AccountLogin string
	// RepositorySelection is GitHub's own "all"|"selected" (API-CONTRACT
	// §5.1) — carried by GET /user/installations exactly as it is by the
	// "installation" webhook, so the callback can populate a brand new
	// gfm.github_installations row even when it runs before any webhook
	// delivery arrives (API-CONTRACT §4.7's documented either-order case).
	RepositorySelection string
}

// ListUserInstallations returns the installations visible to the given
// user access token (GET /user/installations, paginated) — the proof set
// ADR-0034's link checks a claimed installation_id against. An
// installation_id arriving in a query string is attacker-controlled; only
// one present in this list may be linked.
func ListUserInstallations(ctx context.Context, cfg UserOAuthConfig, userAccessToken string) ([]UserInstallation, error) {
	if strings.TrimSpace(userAccessToken) == "" {
		return nil, fmt.Errorf("ghapp: empty user access token")
	}
	var installations []UserInstallation
	rawURL := cfg.apiBase() + "/user/installations?per_page=100"
	for page := 0; rawURL != "" && page < maxInstallationRepositoryPages; page++ {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "Bearer "+userAccessToken)
		req.Header.Set("Accept", "application/vnd.github+json")
		req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
		resp, err := userOAuthHTTP.Do(req)
		if err != nil {
			return nil, fmt.Errorf("ghapp: list user installations: %w", err)
		}
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
		_ = resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			return nil, fmt.Errorf("ghapp: list user installations answered %d", resp.StatusCode)
		}
		var out struct {
			Installations []struct {
				ID      int64 `json:"id"`
				Account struct {
					Login string `json:"login"`
				} `json:"account"`
				RepositorySelection string `json:"repository_selection"`
			} `json:"installations"`
		}
		if err := json.Unmarshal(body, &out); err != nil {
			return nil, fmt.Errorf("ghapp: list user installations: unreadable response")
		}
		for _, it := range out.Installations {
			installations = append(installations, UserInstallation{
				ID: it.ID, AccountLogin: it.Account.Login, RepositorySelection: it.RepositorySelection,
			})
		}
		rawURL = parseNextLink(resp.Header.Get("Link"))
	}
	return installations, nil
}
