package identity

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
)

// DefaultWorkOSBase is the production endpoint. Tests override it.
const DefaultWorkOSBase = "https://api.workos.com"

// WorkOS is a minimal AuthKit client: an authorize URL and the authenticate
// exchange (an authorization code, or an email-verification code against a
// pending authentication token). No OAuth repository scopes are ever
// requested, and the API key is never logged or returned.
type WorkOS struct {
	APIKey   string
	ClientID string
	Base     string
	HTTP     *http.Client
}

func (w *WorkOS) base() string {
	if w.Base != "" {
		return strings.TrimSuffix(w.Base, "/")
	}
	return DefaultWorkOSBase
}

// AuthorizeURL builds the AuthKit redirect for one provider.
func (w *WorkOS) AuthorizeURL(provider, redirectURI, state string) string {
	q := url.Values{}
	q.Set("client_id", w.ClientID)
	q.Set("redirect_uri", redirectURI)
	q.Set("response_type", "code")
	q.Set("provider", provider)
	q.Set("state", state)
	return w.base() + "/user_management/authorize?" + q.Encode()
}

// WorkOSUser is the subset of the authenticate response this service uses.
type WorkOSUser struct {
	ID        string `json:"id"`
	Email     string `json:"email"`
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name"`
}

// Name is the display name, or the local part of the address when the provider
// returned no name at all.
func (u WorkOSUser) Name() string {
	name := strings.TrimSpace(u.FirstName + " " + u.LastName)
	if name != "" {
		return name
	}
	if i := strings.IndexByte(u.Email, '@'); i > 0 {
		return u.Email[:i]
	}
	return u.Email
}

// OAuthTokens is the third-party provider token WorkOS returns alongside the
// user when a connection has "Return OAuth tokens" enabled (the GitHub App's
// OAuth connection, once switched on, so a person who signs in with GitHub
// can immediately see their GitHub organisations and this App's
// installations). Field presence is confirmed from WorkOS's own reference
// for the email-verification grant ("oauth_tokens (object, optional)"); the
// inner field names below follow WorkOS's documented OAuth-token shape but
// are not independently verified against a live response, so decoding is
// deliberately tolerant (see parseAuthenticateBody): a shape surprise here
// must never fail sign-in. ExpiresAt is kept as raw JSON rather than string
// or a numeric type for the same reason — examples seen for this field
// disagree on whether it is a unix timestamp (number) or RFC3339 (string),
// and typing it wrong would fail this struct's own decode, silently
// discarding the whole object (Provider/AccessToken/RefreshToken/Scopes
// included) rather than only the one field. Nothing in this package uses,
// stores or logs these values yet — a follow-up change consumes them
// through internal/ghapp, and must confirm ExpiresAt's real shape against a
// live response before giving it a concrete type.
type OAuthTokens struct {
	Provider     string          `json:"provider"`
	AccessToken  string          `json:"access_token"`
	RefreshToken string          `json:"refresh_token"`
	ExpiresAt    json.RawMessage `json:"expires_at"`
	Scopes       []string        `json:"scopes"`
}

// AuthenticateResult is the outcome of a successful exchange, whichever grant
// produced it.
type AuthenticateResult struct {
	User        WorkOSUser
	OAuthTokens *OAuthTokens // nil when the connection does not return provider tokens
}

// pendingAuthCodes is the closed set of WorkOS authenticate outcomes this
// service recognises as "not a failure, but not signed in yet" (API-CONTRACT
// §2). Any other non-success response — including WorkOS outcomes this
// service does not (yet) recognise, such as sso_required or the radar
// challenges — falls back to the existing provider_unavailable handling,
// unchanged.
var pendingAuthCodes = map[string]bool{
	"email_verification_required":     true,
	"organization_selection_required": true,
	"mfa_enrollment":                  true,
	"mfa_challenge":                   true,
}

// PendingAuthError is returned by Authenticate (never by
// AuthenticateEmailVerificationCode, whose own rejections are reported as a
// plain error by design — see that method) for one of pendingAuthCodes. It is
// not a failure: WorkOS answered with a recognised next step instead of a
// user. Code is the WorkOS outcome verbatim (already the closed,
// contract-listed value this service reports onward); PendingAuthenticationToken
// and Email are populated only for email_verification_required, the only one
// of the four this service carries forward into a second step.
type PendingAuthError struct {
	Code                       string
	PendingAuthenticationToken string
	Email                      string
}

func (e *PendingAuthError) Error() string { return "workos_pending_" + e.Code }

// Authenticate exchanges an authorization code for the signed-in user.
func (w *WorkOS) Authenticate(ctx context.Context, code string) (AuthenticateResult, error) {
	return w.exchange(ctx, map[string]string{
		"client_id":     w.ClientID,
		"client_secret": w.APIKey,
		"grant_type":    "authorization_code",
		"code":          code,
	})
}

// AuthenticateEmailVerificationCode completes email_verification_required
// with the one-time code WorkOS emailed, against the pending_authentication_token
// captured from that error. WorkOS does not document a stable, distinguishable
// error taxonomy for a wrong code, an expired code or too many attempts on
// this grant, so this service does not try to parse one: any rejection here
// is reported as a plain (non-PendingAuthError) error, and the caller — which
// already tracks its own attempt count and its own short-lived state row —
// decides what that means (identity/email_verify.go).
func (w *WorkOS) AuthenticateEmailVerificationCode(ctx context.Context, pendingToken, code string) (AuthenticateResult, error) {
	return w.exchange(ctx, map[string]string{
		"client_id":                    w.ClientID,
		"client_secret":                w.APIKey,
		"grant_type":                   "urn:workos:oauth:grant-type:email-verification:code",
		"pending_authentication_token": pendingToken,
		"code":                         code,
	})
}

func (w *WorkOS) exchange(ctx context.Context, fields map[string]string) (AuthenticateResult, error) {
	var out AuthenticateResult
	payload, e := json.Marshal(fields)
	if e != nil {
		return out, e
	}
	req, e := http.NewRequestWithContext(ctx, http.MethodPost,
		w.base()+"/user_management/authenticate", bytes.NewReader(payload))
	if e != nil {
		return out, e
	}
	req.Header.Set("Content-Type", "application/json")
	client := w.HTTP
	if client == nil {
		client = http.DefaultClient
	}
	resp, e := client.Do(req)
	if e != nil {
		return out, e
	}
	defer resp.Body.Close()
	body, e := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if e != nil {
		return out, e
	}
	if resp.StatusCode != http.StatusOK {
		// The body may echo the client secret back; nothing from it is
		// returned or logged verbatim, only the recognised outcome code
		// when there is one, or the status otherwise (workos_authenticate_status_%d).
		var perr struct {
			Code                       string `json:"code"`
			PendingAuthenticationToken string `json:"pending_authentication_token"`
			Email                      string `json:"email"`
		}
		if json.Unmarshal(body, &perr) == nil && pendingAuthCodes[perr.Code] {
			return out, &PendingAuthError{Code: perr.Code,
				PendingAuthenticationToken: perr.PendingAuthenticationToken, Email: perr.Email}
		}
		return out, fmt.Errorf("workos_authenticate_status_%d", resp.StatusCode)
	}
	return parseAuthenticateBody(body)
}

// parseAuthenticateBody decodes a 200 authenticate response. oauth_tokens is
// decoded in a second, best-effort pass so an unexpected shape there can
// never fail the user's sign-in — see OAuthTokens.
func parseAuthenticateBody(body []byte) (AuthenticateResult, error) {
	var out AuthenticateResult
	var raw struct {
		User        WorkOSUser      `json:"user"`
		OAuthTokens json.RawMessage `json:"oauth_tokens"`
	}
	if e := json.Unmarshal(body, &raw); e != nil {
		return out, fmt.Errorf("workos_authenticate_invalid_response")
	}
	out.User = raw.User
	if out.User.ID == "" || out.User.Email == "" {
		return out, fmt.Errorf("workos_authenticate_incomplete_user")
	}
	if len(raw.OAuthTokens) > 0 && string(raw.OAuthTokens) != "null" {
		var tokens OAuthTokens
		if json.Unmarshal(raw.OAuthTokens, &tokens) == nil {
			out.OAuthTokens = &tokens
		}
		// A shape this service did not anticipate leaves OAuthTokens nil
		// rather than failing sign-in; nothing consumes the field yet.
	}
	return out, nil
}
