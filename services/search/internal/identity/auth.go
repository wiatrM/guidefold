package identity

import (
	"context"
	"crypto/subtle"
	"html"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

type providerInfo struct {
	ID       string `json:"id"`
	Label    string `json:"label"`
	LoginURL string `json:"login_url"`
}

func provider(id string) (string, string, bool) {
	for _, p := range providers {
		if p.ID == id {
			return p.Label, p.WorkOS, true
		}
	}
	return "", "", false
}

func (s *Service) handleProviders(c *mgmt.Context) error {
	out := []providerInfo{}
	for _, p := range providers {
		out = append(out, providerInfo{ID: p.ID, Label: p.Label, LoginURL: "/api/v1/auth/login/" + p.ID})
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "providers": out, "mode": s.cfg.Mode})
}

// handleLogin starts a login. The return path must be a same-origin path, so a
// login link cannot be turned into an open redirect.
func (s *Service) handleLogin(c *mgmt.Context) error {
	id := c.Param("provider")
	if _, _, ok := provider(id); !ok {
		return mgmt.NotFound("unknown_provider", "No such sign-in provider.")
	}
	returnTo := c.Query("return_to")
	if returnTo == "" || !mgmt.Relative(returnTo) {
		returnTo = "/"
	}
	state, e := s.newAuthState(c.Ctx(), "login", id, "", returnTo)
	if e != nil {
		return e
	}
	s.setAuthStateCookie(c, state)
	return c.RedirectTo(s.loginURL(id, state))
}

func (s *Service) loginURL(providerID, state string) string {
	if s.cfg.Mode == ModeDev {
		return "/api/v1/auth/dev?state=" + url.QueryEscape(state)
	}
	_, workosProvider, _ := provider(providerID)
	return s.workos.AuthorizeURL(workosProvider, s.cfg.PublicURL+"/api/v1/auth/callback", state)
}

// handleDevForm renders the local sign-in form. It exists only when
// GUIDEFOLD_AUTH=dev and is never reachable in a WorkOS deployment.
func (s *Service) handleDevForm(c *mgmt.Context) error {
	if s.cfg.Mode != ModeDev {
		return mgmt.NotFound("not_found", "No such endpoint.")
	}
	state := c.Query("state")
	returnTo := c.Query("return_to")
	if !mgmt.Relative(returnTo) {
		returnTo = "/"
	}
	page := `<!doctype html><meta charset="utf-8"><title>Guidefold development sign-in</title>
<style>body{font:14px system-ui;margin:3rem auto;max-width:26rem}
label{display:block;margin:.75rem 0 .25rem}input,select{width:100%;padding:.4rem}
button{margin-top:1rem;padding:.5rem 1rem}</style>
<h1>Development sign-in</h1>
<p>This form replaces the identity provider in local development.</p>
<form method="post" action="/api/v1/auth/dev">
<input type="hidden" name="state" value="` + html.EscapeString(state) + `">
<input type="hidden" name="return_to" value="` + html.EscapeString(returnTo) + `">
<label for="provider">Provider</label>
<select id="provider" name="provider"><option value="google">google</option><option value="github">github</option></select>
<label for="subject">Subject</label><input id="subject" name="subject" required>
<label for="email">E-mail</label><input id="email" name="email" type="email" required>
<label for="name">Name</label><input id="name" name="name">
<button type="submit">Sign in</button>
</form>`
	c.W.Header().Set("Content-Type", "text/html; charset=utf-8")
	c.W.WriteHeader(http.StatusOK)
	_, _ = c.W.Write([]byte(page))
	return nil
}

func (s *Service) handleDevSubmit(c *mgmt.Context) error {
	if s.cfg.Mode != ModeDev {
		return mgmt.NotFound("not_found", "No such endpoint.")
	}
	if e := c.R.ParseForm(); e != nil {
		return mgmt.Invalid("invalid_form", "The sign-in form could not be read.")
	}
	form := c.R.PostForm
	providerID := form.Get("provider")
	subject := strings.TrimSpace(form.Get("subject"))
	email := strings.TrimSpace(form.Get("email"))
	name := strings.TrimSpace(form.Get("name"))
	if _, _, ok := provider(providerID); !ok {
		return mgmt.Invalid("unknown_provider", "Choose google or github.")
	}
	if subject == "" || email == "" {
		return mgmt.Invalid("invalid_identity", "subject and email are required.")
	}
	if name == "" {
		name = subject
	}
	returnTo := form.Get("return_to")
	linkUser := ""
	if state := form.Get("state"); state != "" {
		claim, e := s.consumeAuthState(c.Ctx(), state)
		if e != nil {
			return e
		}
		if claim.kind == "link" {
			linkUser = claim.userID
			providerID = claim.provider
		}
		if returnTo == "" {
			returnTo = claim.returnTo
		}
	}
	if !mgmt.Relative(returnTo) {
		returnTo = "/"
	}
	return s.completeSignIn(c, providerID, subject, email, name, linkUser, returnTo)
}

func (s *Service) handleCallback(c *mgmt.Context) error {
	if s.cfg.Mode != ModeWorkOS {
		return mgmt.NotFound("not_found", "No such endpoint.")
	}
	code, state := c.Query("code"), c.Query("state")
	if code == "" || state == "" {
		return mgmt.Invalid("invalid_callback", "The provider returned no code.")
	}
	// Login CSRF. The state row alone proves that *someone* started a login, not
	// that this browser did: an attacker can start one and then feed their own
	// callback URL to a victim, who would be signed into the attacker's account
	// without noticing. The state is therefore also written as an HttpOnly
	// cookie at handleLogin, and the two must agree here.
	if e := s.matchAuthStateCookie(c, state); e != nil {
		return e
	}
	claim, e := s.consumeAuthState(c.Ctx(), state)
	if e != nil {
		return e
	}
	user, err := s.workos.Authenticate(c.Ctx(), code)
	if err != nil {
		return mgmt.Fail(http.StatusBadGateway, "provider_unavailable",
			"The identity provider did not complete the sign-in.")
	}
	linkUser := ""
	if claim.kind == "link" {
		linkUser = claim.userID
	}
	return s.completeSignIn(c, claim.provider, user.ID, user.Email, user.Name(), linkUser, claim.returnTo)
}

// completeSignIn applies the identity rule and starts a session.
//
// A fresh login never merges accounts, even when the e-mail matches an existing
// user: matching addresses are a claim by the provider, not proof that the same
// person controls both. Linking is an explicit, session-bound action.
func (s *Service) completeSignIn(c *mgmt.Context, providerID, subject, email, name, linkUser, returnTo string) error {
	userID, e := s.signIn(c.Ctx(), providerID, subject, email, name, linkUser)
	if e != nil {
		return e
	}
	if linkUser != "" {
		// The link flow keeps the session it was started from.
		return c.Redirect(returnTo)
	}
	if e = s.startSession(c, userID); e != nil {
		return e
	}
	return c.Redirect(returnTo)
}

func (s *Service) signIn(ctx context.Context, providerID, subject, email, name, linkUser string) (string, error) {
	tx, e := s.tx(ctx)
	if e != nil {
		return "", mgmt.Internal(e)
	}
	defer tx.Rollback(ctx)
	var existing string
	e = tx.QueryRow(ctx, `SELECT user_id::text FROM gfm.identities WHERE provider=$1 AND subject=$2`,
		providerID, subject).Scan(&existing)
	switch {
	case e == nil && linkUser != "" && existing != linkUser:
		return "", mgmt.Conflict("identity_already_linked",
			"That provider account is already connected to another Guidefold user.")
	case e == nil:
		if _, e = tx.Exec(ctx, `UPDATE gfm.users SET name=COALESCE(NULLIF($2,''),name) WHERE user_id=$1::uuid`,
			existing, name); e != nil {
			return "", mgmt.Internal(e)
		}
		if e = tx.Commit(ctx); e != nil {
			return "", mgmt.Internal(e)
		}
		return existing, nil
	case e != pgx.ErrNoRows:
		return "", mgmt.Internal(e)
	}
	userID := linkUser
	if userID == "" {
		userID = NewID()
		if _, e = tx.Exec(ctx, `INSERT INTO gfm.users(user_id,email,name) VALUES($1::uuid,$2,$3)`,
			userID, email, name); e != nil {
			return "", mgmt.Internal(e)
		}
	}
	if _, e = tx.Exec(ctx, `INSERT INTO gfm.identities(provider,subject,user_id) VALUES($1,$2,$3::uuid)`,
		providerID, subject, userID); e != nil {
		return "", mgmt.Internal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		return "", mgmt.Internal(e)
	}
	return userID, nil
}

func (s *Service) startSession(c *mgmt.Context, userID string) error {
	id, csrf := newSecret(), newSecret()
	expires := s.now().Add(SessionTTL)
	tx, e := s.tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer tx.Rollback(c.Ctx())
	if _, e = tx.Exec(c.Ctx(), `INSERT INTO gfm.sessions(id_sha256,user_id,csrf_token,expires_at,last_seen_at)
 VALUES($1,$2::uuid,$3,$4,now())`, digest(id), userID, csrf, expires); e != nil {
		return mgmt.Internal(e)
	}
	if e = tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	http.SetCookie(c.W, &http.Cookie{
		Name: SessionCookie, Value: id, Path: "/", HttpOnly: true,
		SameSite: http.SameSiteLaxMode, Secure: !s.cfg.InsecureCookies,
		Expires: expires, MaxAge: int(SessionTTL / time.Second),
	})
	return nil
}

func (s *Service) handleLogout(c *mgmt.Context) error {
	if c.Principal != nil && c.Principal.SessionID != "" {
		tx, e := s.tx(c.Ctx())
		if e != nil {
			return mgmt.Internal(e)
		}
		defer tx.Rollback(c.Ctx())
		if _, e = tx.Exec(c.Ctx(), `UPDATE gfm.sessions SET revoked_at=now()
 WHERE id_sha256=$1 AND revoked_at IS NULL`, c.Principal.SessionID); e != nil {
			return mgmt.Internal(e)
		}
		if e = tx.Commit(c.Ctx()); e != nil {
			return mgmt.Internal(e)
		}
	}
	http.SetCookie(c.W, &http.Cookie{
		Name: SessionCookie, Value: "", Path: "/", HttpOnly: true,
		SameSite: http.SameSiteLaxMode, Secure: !s.cfg.InsecureCookies, MaxAge: -1,
	})
	return c.NoContent()
}

type meIdentity struct {
	Provider  string    `json:"provider"`
	CreatedAt time.Time `json:"created_at"`
}

type meOrg struct {
	OrgID string `json:"org_id"`
	Slug  string `json:"slug"`
	Name  string `json:"name"`
	Role  string `json:"role"`
}

// handleMe always re-reads memberships, so a removed member stops seeing an
// organisation on their next call rather than at the next cache expiry.
func (s *Service) handleMe(c *mgmt.Context) error {
	p := c.Principal
	if !p.IsUser() {
		return mgmt.Forbidden()
	}
	var email, name string
	if e := s.pool.QueryRow(c.Ctx(), `SELECT email,name FROM gfm.users WHERE user_id=$1::uuid`, p.UserID).
		Scan(&email, &name); e != nil {
		return mgmt.Internal(e)
	}
	identities, e := s.identitiesOf(c.Ctx(), p.UserID)
	if e != nil {
		return e
	}
	orgs, e := s.orgsOf(c.Ctx(), p.UserID)
	if e != nil {
		return e
	}
	suggestions, e := s.linkSuggestions(c.Ctx(), p.UserID, email)
	if e != nil {
		return e
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion,
		"user":           map[string]any{"id": p.UserID, "email": email, "name": name},
		"identities":     identities,
		"orgs":           orgs,
		"csrf_token":     p.CSRF,
		"access": map[string]any{
			"checked_at":  s.now().UTC().Format(time.RFC3339),
			"valid_for_s": 45,
		},
		"link_suggestions": suggestions,
	})
}

type profileRequest struct {
	Name           string `json:"name"`
	IdempotencyKey string `json:"idempotency_key"`
}

// handleUpdateProfile changes only the display name owned by Guidefold. Email
// and provider identities remain provider-managed; linking an identity still
// requires the explicit OAuth flow exposed by /me/identities/link/start.
func (s *Service) handleUpdateProfile(c *mgmt.Context) error {
	if c.Principal == nil || !c.Principal.IsUser() {
		return mgmt.Unauthenticated("Sign in before editing your profile.")
	}
	var req profileRequest
	if err := c.Decode(&req); err != nil {
		return err
	}
	req.Name = strings.TrimSpace(req.Name)
	if req.Name == "" || len(req.Name) > 120 {
		return mgmt.Invalid("invalid_profile", "Name must contain 1 to 120 characters.")
	}
	var email string
	if err := s.pool.QueryRow(c.Ctx(), `UPDATE gfm.users SET name=$2 WHERE user_id=$1::uuid RETURNING email`, c.Principal.UserID, req.Name).Scan(&email); err != nil {
		if err == pgx.ErrNoRows {
			return mgmt.Unauthenticated("This account is no longer available.")
		}
		return mgmt.Internal(err)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion,
		"user":           map[string]any{"id": c.Principal.UserID, "email": email, "name": req.Name},
	})
}

func (s *Service) identitiesOf(ctx context.Context, userID string) ([]meIdentity, error) {
	rows, e := s.pool.Query(ctx,
		`SELECT provider,created_at FROM gfm.identities WHERE user_id=$1::uuid ORDER BY provider`, userID)
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	defer rows.Close()
	out := []meIdentity{}
	for rows.Next() {
		var v meIdentity
		if e = rows.Scan(&v.Provider, &v.CreatedAt); e != nil {
			return nil, mgmt.Internal(e)
		}
		out = append(out, v)
	}
	return out, nil
}

func (s *Service) orgsOf(ctx context.Context, userID string) ([]meOrg, error) {
	rows, e := s.pool.Query(ctx, `SELECT o.org_id::text,o.slug,o.name,m.role
 FROM gfm.orgs o JOIN gfm.memberships m ON m.org_id=o.org_id
 WHERE m.user_id=$1::uuid ORDER BY o.name,o.org_id`, userID)
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	defer rows.Close()
	out := []meOrg{}
	for rows.Next() {
		var v meOrg
		if e = rows.Scan(&v.OrgID, &v.Slug, &v.Name, &v.Role); e != nil {
			return nil, mgmt.Internal(e)
		}
		out = append(out, v)
	}
	return out, nil
}

// linkSuggestions names providers where another account shares this address.
// It is a hint for the person to link deliberately, never an automatic merge.
func (s *Service) linkSuggestions(ctx context.Context, userID, email string) ([]map[string]string, error) {
	rows, e := s.pool.Query(ctx, `SELECT DISTINCT i.provider FROM gfm.identities i
 JOIN gfm.users u ON u.user_id=i.user_id
 WHERE lower(u.email)=lower($2) AND i.user_id<>$1::uuid
   AND i.provider NOT IN (SELECT provider FROM gfm.identities WHERE user_id=$1::uuid)
 ORDER BY 1`, userID, email)
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	defer rows.Close()
	out := []map[string]string{}
	for rows.Next() {
		var v string
		if e = rows.Scan(&v); e != nil {
			return nil, mgmt.Internal(e)
		}
		out = append(out, map[string]string{"provider": v})
	}
	return out, nil
}

type linkStartRequest struct {
	Provider string `json:"provider"`
	ReturnTo string `json:"return_to"`
}

func (s *Service) handleLinkStart(c *mgmt.Context) error {
	if c.Principal.Source != mgmt.SourceSession {
		return mgmt.Forbidden()
	}
	var req linkStartRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	if _, _, ok := provider(req.Provider); !ok {
		return mgmt.Invalid("unknown_provider", "Choose google or github.")
	}
	returnTo := req.ReturnTo
	if !mgmt.Relative(returnTo) {
		returnTo = "/"
	}
	state, e := s.newAuthState(c.Ctx(), "link", req.Provider, c.Principal.UserID, returnTo)
	if e != nil {
		return e
	}
	s.setAuthStateCookie(c, state)
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion,
		"login_url":      s.loginURL(req.Provider, state),
	})
}

type authClaim struct {
	kind, provider, userID, orgID, returnTo string
}

func (s *Service) newAuthState(ctx context.Context, kind, providerID, userID, returnTo string) (string, error) {
	return s.newOrgAuthState(ctx, kind, providerID, userID, "", returnTo)
}

// newOrgAuthState is newAuthState plus an organisation id, for a round trip
// that must come back tied to the organisation that started it rather than
// (or in addition to) the signed-in user — "github_install" (API-CONTRACT
// §4.7), which reuses this same one-round-trip, single-use table rather
// than a second state mechanism.
func (s *Service) newOrgAuthState(ctx context.Context, kind, providerID, userID, orgID, returnTo string) (string, error) {
	state := newSecret()
	tx, e := s.tx(ctx)
	if e != nil {
		return "", mgmt.Internal(e)
	}
	defer tx.Rollback(ctx)
	var owner, org any
	if userID != "" {
		owner = userID
	}
	if orgID != "" {
		org = orgID
	}
	if _, e = tx.Exec(ctx, `INSERT INTO gfm.auth_states(state_sha256,kind,provider,user_id,org_id,return_to,expires_at)
 VALUES($1,$2,$3,$4::uuid,$5::uuid,$6,$7)`, digest(state), kind, providerID, owner, org, returnTo,
		s.now().Add(AuthStateTTL)); e != nil {
		return "", mgmt.Internal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		return "", mgmt.Internal(e)
	}
	return state, nil
}

// setAuthStateCookie ties one login round trip to the browser that began it.
// The cookie is HttpOnly, so script on any origin cannot read or forge it, and
// SameSite=Lax still travels on the provider's top-level redirect back here.
func (s *Service) setAuthStateCookie(c *mgmt.Context, state string) {
	http.SetCookie(c.W, &http.Cookie{
		Name: AuthStateCookie, Value: state, Path: "/", HttpOnly: true,
		SameSite: http.SameSiteLaxMode, Secure: !s.cfg.InsecureCookies,
		MaxAge: int(AuthStateTTL / time.Second),
	})
}

func (s *Service) clearAuthStateCookie(c *mgmt.Context) {
	http.SetCookie(c.W, &http.Cookie{
		Name: AuthStateCookie, Value: "", Path: "/", HttpOnly: true,
		SameSite: http.SameSiteLaxMode, Secure: !s.cfg.InsecureCookies, MaxAge: -1,
	})
}

// matchAuthStateCookie requires the callback to arrive in the browser that
// started the login. It always clears the cookie, so one failure cannot be
// retried against the same round trip.
func (s *Service) matchAuthStateCookie(c *mgmt.Context, state string) error {
	cookie, e := c.R.Cookie(AuthStateCookie)
	s.clearAuthStateCookie(c)
	if e != nil || cookie.Value == "" ||
		subtle.ConstantTimeCompare([]byte(cookie.Value), []byte(state)) != 1 {
		return mgmt.Invalid("invalid_state", "This sign-in did not start in this browser.")
	}
	return nil
}

// consumeAuthState deletes the state as it reads it: one round trip, one use.
func (s *Service) consumeAuthState(ctx context.Context, state string) (authClaim, error) {
	var claim authClaim
	var owner, org *string
	var expires time.Time
	tx, e := s.tx(ctx)
	if e != nil {
		return claim, mgmt.Internal(e)
	}
	defer tx.Rollback(ctx)
	e = tx.QueryRow(ctx, `DELETE FROM gfm.auth_states WHERE state_sha256=$1
 RETURNING kind,provider,user_id::text,org_id::text,return_to,expires_at`, digest(state)).
		Scan(&claim.kind, &claim.provider, &owner, &org, &claim.returnTo, &expires)
	if e == pgx.ErrNoRows {
		return claim, mgmt.Invalid("invalid_state", "This sign-in link has already been used.")
	}
	if e != nil {
		return claim, mgmt.Internal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		return claim, mgmt.Internal(e)
	}
	if !expires.After(s.now()) {
		return claim, mgmt.Invalid("expired_state", "This sign-in link has expired.")
	}
	claim.userID = str(owner)
	claim.orgID = str(org)
	return claim, nil
}
