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

// WorkOS is a minimal AuthKit client: an authorize URL and one code exchange.
// No OAuth repository scopes are ever requested, and the API key is never
// logged or returned.
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

// Authenticate exchanges an authorization code for the signed-in user.
func (w *WorkOS) Authenticate(ctx context.Context, code string) (WorkOSUser, error) {
	var out struct {
		User WorkOSUser `json:"user"`
	}
	payload, e := json.Marshal(map[string]string{
		"client_id":     w.ClientID,
		"client_secret": w.APIKey,
		"grant_type":    "authorization_code",
		"code":          code,
	})
	if e != nil {
		return out.User, e
	}
	req, e := http.NewRequestWithContext(ctx, http.MethodPost,
		w.base()+"/user_management/authenticate", bytes.NewReader(payload))
	if e != nil {
		return out.User, e
	}
	req.Header.Set("Content-Type", "application/json")
	client := w.HTTP
	if client == nil {
		client = http.DefaultClient
	}
	resp, e := client.Do(req)
	if e != nil {
		return out.User, e
	}
	defer resp.Body.Close()
	body, e := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if e != nil {
		return out.User, e
	}
	if resp.StatusCode != http.StatusOK {
		// The body may echo the client secret back; report the status only.
		return out.User, fmt.Errorf("workos_authenticate_status_%d", resp.StatusCode)
	}
	if e = json.Unmarshal(body, &out); e != nil {
		return out.User, fmt.Errorf("workos_authenticate_invalid_response")
	}
	if out.User.ID == "" || out.User.Email == "" {
		return out.User, fmt.Errorf("workos_authenticate_incomplete_user")
	}
	return out.User, nil
}
