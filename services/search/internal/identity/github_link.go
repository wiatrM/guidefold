package identity

import (
	"log/slog"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// githubInstallStateKind names the gfm.auth_states row this flow writes and
// reads (API-CONTRACT §4.7). It reuses the same one-round-trip, single-use
// table the sign-in and identity-link flows already use — auth.go's
// newOrgAuthState/matchAuthStateCookie/consumeAuthState — rather than a
// second state mechanism.
const githubInstallStateKind = "github_install"

func (s *Service) userOAuthConfig() ghapp.UserOAuthConfig {
	return ghapp.UserOAuthConfig{
		ClientID: s.cfg.GitHubAppClientID, ClientSecret: s.cfg.GitHubAppClientSecret,
		AuthBaseURL: s.cfg.GitHubAppAuthBaseURL, APIBaseURL: s.cfg.GitHubAppAPIBaseURL,
	}
}

// handleGitHubInstallStart begins ADR-0034's explicit link. It creates the
// single-use signed state tied to the signed-in owner and this organisation,
// and answers with the URL that sends the browser to GitHub's own
// installation screen — never the reverse: Guidefold starts the flow from
// the organisation, not from a GitHub URL someone pastes in. On that
// screen the owner chooses "All repositories" or a selection; Guidefold
// cannot preselect it, and the console should recommend "All repositories"
// so every future repository the owner adds is covered without a second
// trip through this flow.
func (s *Service) handleGitHubInstallStart(c *mgmt.Context) error {
	org, err := c.Authorize("org", mgmt.RoleOwner)
	if err != nil {
		return err
	}
	if strings.TrimSpace(s.cfg.GitHubAppSlug) == "" {
		return mgmt.Fail(http.StatusServiceUnavailable, "github_app_not_configured", "The GitHub App is not configured.")
	}
	// return_to is stored only for gfm.auth_states' own record (the column
	// is NOT NULL); handleGitHubInstallCallback below never reads it back —
	// it builds the console address it redirects to itself, from org.ID and
	// a closed outcome code, so there is exactly one place that assembles
	// that URL rather than this start route and the callback each
	// contributing a piece of it.
	returnTo := consoleReturn(org.ID, "")
	state, err := s.newOrgAuthState(c.Ctx(), githubInstallStateKind, "github", c.Principal.UserID, org.ID, returnTo)
	if err != nil {
		return err
	}
	s.setAuthStateCookie(c, state)
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion,
		"install_url": "https://github.com/apps/" + url.PathEscape(s.cfg.GitHubAppSlug) +
			"/installations/new?state=" + url.QueryEscape(state),
	})
}

// consoleReturn builds the console's Integrations tab address this callback
// always lands the browser on, success or failure alike (API-CONTRACT
// §4.7): one builder, so no call site concatenates a query parameter onto
// another URL by hand. orgID is the caller's own organisation id, never a
// slug looked up from unproven input — ui/src/app.tsx's `org` query
// parameter already accepts an org_id exactly like a slug (it matches
// either against the signed-in caller's own memberships), so no lookup is
// needed and nothing here can point the redirect at an organisation the
// browser never proved it belongs to. orgID empty (no organisation proven
// yet — before the state cookie matches, or a state that turned out to
// belong to no organisation) omits the parameter entirely; the console then
// falls back to the signed-in caller's own first membership. outcome is one
// of the machine-readable codes §4.7 names, or "" only for the state row's
// own stored return_to, which the callback never reads back.
func consoleReturn(orgID, outcome string) string {
	q := url.Values{}
	q.Set("tab", "integrations")
	if orgID != "" {
		q.Set("org", orgID)
	}
	if outcome != "" {
		q.Set("github", outcome)
	}
	return "/organization?" + q.Encode()
}

// githubCallbackRedirect turns any error from handleGitHubInstallCallback
// into the console address to redirect to — orgID is whatever organisation
// is already proven at the point of failure (see the callback below), never
// looked up from the failing input itself. A closed *mgmt.Error below 500
// contributes its own code verbatim (invalid_callback, invalid_state,
// expired_state, installation_not_owned, provider_unavailable,
// github_app_not_configured — API-CONTRACT §4.7); anything else is a
// genuine unexpected failure. mgmt.Router.render would normally log such a
// cause before writing the JSON envelope (internal/mgmt/router.go), but
// this handler never reaches render — every branch redirects the browser
// instead (Task 1) — so the cause is logged here so it is not silently
// dropped, and the browser gets the closed fallback code, never the cause.
func githubCallbackRedirect(c *mgmt.Context, orgID string, err error) string {
	if api, ok := err.(*mgmt.Error); ok && api.Status < http.StatusInternalServerError {
		return consoleReturn(orgID, api.Code)
	}
	slog.Default().Error("github_install_callback_failure", "request_id", c.RequestID, "error", err)
	return consoleReturn(orgID, "internal_error")
}

// handleGitHubInstallCallback completes ADR-0034's explicit link: GitHub's
// own "Request user authorization (OAuth) during installation" redirect
// carries a one-time code and the installation_id the owner just installed
// (or updated) the App on. installation_id in a query string is
// attacker-controlled, so it is never linked on its own — the code is
// exchanged for a user access token, and the token's own
// GET /user/installations is the only thing that proves the signed-in
// owner can actually see that installation on GitHub.
//
// This is a browser navigation target, not a JSON API call (the owner's
// browser lands here straight from github.com), so every branch below —
// success and every failure alike — ends in a redirect back into the
// console, never in mgmt.Router's JSON error envelope: an owner refused
// here must see the console's own message, never a bare error page.
func (s *Service) handleGitHubInstallCallback(c *mgmt.Context) error {
	if strings.TrimSpace(s.cfg.GitHubAppClientID) == "" || strings.TrimSpace(s.cfg.GitHubAppClientSecret) == "" {
		return c.RedirectTo(consoleReturn("", "github_app_not_configured"))
	}
	authCode := c.Query("code")
	state := c.Query("state")
	rawInstallationID := c.Query("installation_id")
	if authCode == "" || state == "" || rawInstallationID == "" {
		return c.RedirectTo(consoleReturn("", "invalid_callback"))
	}
	installationID, perr := strconv.ParseInt(rawInstallationID, 10, 64)
	if perr != nil || installationID <= 0 {
		return c.RedirectTo(consoleReturn("", "invalid_callback"))
	}
	// Login-CSRF protection, the same reason handleCallback checks this for
	// WorkOS: the state row alone proves someone started this round trip,
	// not that this browser did. No organisation is trustworthy yet at this
	// point — a mismatched cookie means this browser never proved it
	// started the round trip that state names, so its org_id must not be
	// trusted to pick a redirect target either.
	if err := s.matchAuthStateCookie(c, state); err != nil {
		return c.RedirectTo(githubCallbackRedirect(c, "", err))
	}
	claim, err := s.consumeAuthState(c.Ctx(), state)
	if err != nil {
		// consumeAuthState populates claim.orgID before it checks expiry, so
		// an expired_state claim still carries a genuine organisation here —
		// the cookie above already proved this browser started that exact
		// round trip, so trusting it for the redirect (never for linking
		// anything) is safe. A state already used (invalid_state, no row
		// found) or a database failure carries no claim at all.
		return c.RedirectTo(githubCallbackRedirect(c, claim.orgID, err))
	}
	if claim.kind != githubInstallStateKind || claim.orgID == "" {
		return c.RedirectTo(consoleReturn(claim.orgID, "invalid_state"))
	}

	userToken, err := ghapp.ExchangeUserCode(c.Ctx(), s.userOAuthConfig(), authCode)
	if err != nil {
		return c.RedirectTo(consoleReturn(claim.orgID, "provider_unavailable"))
	}
	owned, err := ghapp.ListUserInstallations(c.Ctx(), s.userOAuthConfig(), userToken)
	if err != nil {
		return c.RedirectTo(consoleReturn(claim.orgID, "provider_unavailable"))
	}
	proven := false
	accountLogin, repoSelection := "", ""
	for _, it := range owned {
		if it.ID == installationID {
			proven = true
			accountLogin = it.AccountLogin
			repoSelection = it.RepositorySelection
			break
		}
	}
	if !proven {
		// The whole point of this callback: a claimed installation_id is
		// refused, and nothing is linked, unless GitHub's own
		// /user/installations for this user's token names it.
		return c.RedirectTo(consoleReturn(claim.orgID, "installation_not_owned"))
	}

	tx, err := s.tx(c.Ctx())
	if err != nil {
		return c.RedirectTo(githubCallbackRedirect(c, claim.orgID, err))
	}
	defer func() { _ = tx.Rollback(c.Ctx()) }()
	var selection any
	if v := strings.TrimSpace(repoSelection); v != "" {
		selection = v
	}
	// The mirror row may not exist yet — the "installation" webhook and
	// this callback can arrive in either order (API-CONTRACT §4.7).
	// Whichever runs first creates the mirror row (account and
	// repository_selection already known from /user/installations,
	// repositories filled in by the next webhook event or by the sync job
	// this callback enqueues below); whichever runs second finds the link
	// already there and enqueues its own sync, so both orders converge on
	// one linked installation with a reconciled repository list and a
	// correct account name from the very first read. account is filled in
	// only while still blank (a CASE, not a WHERE gating the whole UPDATE):
	// repository_selection must still get its own chance to fill in even
	// when the webhook already set a real account — a WHERE keyed on
	// account alone would silently skip repository_selection in exactly
	// that case, the order this callback cannot control.
	if _, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.github_installations(installation_id,account,repositories,repository_selection)
 VALUES($1,$2,'[]'::jsonb,$3)
 ON CONFLICT (installation_id) DO UPDATE SET
   account=CASE WHEN gfm.github_installations.account='' THEN excluded.account ELSE gfm.github_installations.account END,
   repository_selection=COALESCE(gfm.github_installations.repository_selection,excluded.repository_selection)`,
		installationID, accountLogin, selection); err != nil {
		return c.RedirectTo(githubCallbackRedirect(c, claim.orgID, err))
	}
	// repositories_synced_at is reset on every (re)link: a stale timestamp
	// from a previous linkage of this same installation_id must never read
	// as "already synced" before the fresh sync job below has actually run
	// (internal/agentrun/github_sync.go is the only writer of a non-NULL
	// value).
	if _, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.github_installation_links(installation_id,org_id,linked_by,linked_at,repositories_synced_at)
 VALUES($1,$2::uuid,$3::uuid,now(),NULL)
 ON CONFLICT (installation_id) DO UPDATE SET org_id=excluded.org_id,linked_by=excluded.linked_by,linked_at=now(),repositories_synced_at=NULL`,
		installationID, claim.orgID, nullable(claim.userID)); err != nil {
		return c.RedirectTo(githubCallbackRedirect(c, claim.orgID, err))
	}
	if _, err := s.enqueueGitHubSync(c.Ctx(), tx, claim.orgID, installationID,
		"github-sync:"+strconv.FormatInt(installationID, 10)+":link:"+state); err != nil {
		return c.RedirectTo(githubCallbackRedirect(c, claim.orgID, err))
	}
	if err := tx.Commit(c.Ctx()); err != nil {
		return c.RedirectTo(githubCallbackRedirect(c, claim.orgID, err))
	}

	return c.RedirectTo(consoleReturn(claim.orgID, "linked"))
}
