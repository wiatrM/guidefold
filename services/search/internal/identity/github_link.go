package identity

import (
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
	returnTo := "/orgs/" + org.Slug + "/settings/github"
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

// handleGitHubInstallCallback completes ADR-0034's explicit link: GitHub's
// own "Request user authorization (OAuth) during installation" redirect
// carries a one-time code and the installation_id the owner just installed
// (or updated) the App on. installation_id in a query string is
// attacker-controlled, so it is never linked on its own — the code is
// exchanged for a user access token, and the token's own
// GET /user/installations is the only thing that proves the signed-in
// owner can actually see that installation on GitHub.
func (s *Service) handleGitHubInstallCallback(c *mgmt.Context) error {
	if strings.TrimSpace(s.cfg.GitHubAppClientID) == "" || strings.TrimSpace(s.cfg.GitHubAppClientSecret) == "" {
		return mgmt.Fail(http.StatusServiceUnavailable, "github_app_not_configured", "The GitHub App is not configured.")
	}
	authCode := c.Query("code")
	state := c.Query("state")
	rawInstallationID := c.Query("installation_id")
	if authCode == "" || state == "" || rawInstallationID == "" {
		return mgmt.Invalid("invalid_callback", "GitHub did not return code, state and installation_id.")
	}
	installationID, err := strconv.ParseInt(rawInstallationID, 10, 64)
	if err != nil || installationID <= 0 {
		return mgmt.Invalid("invalid_callback", "GitHub returned an invalid installation_id.")
	}
	// Login-CSRF protection, the same reason handleCallback checks this for
	// WorkOS: the state row alone proves someone started this round trip,
	// not that this browser did.
	if err := s.matchAuthStateCookie(c, state); err != nil {
		return err
	}
	claim, err := s.consumeAuthState(c.Ctx(), state)
	if err != nil {
		return err
	}
	if claim.kind != githubInstallStateKind || claim.orgID == "" {
		return mgmt.Invalid("invalid_state", "This installation link did not start from an organisation.")
	}

	userToken, err := ghapp.ExchangeUserCode(c.Ctx(), s.userOAuthConfig(), authCode)
	if err != nil {
		return mgmt.Fail(http.StatusBadGateway, "provider_unavailable", "GitHub did not complete the installation link.")
	}
	owned, err := ghapp.ListUserInstallations(c.Ctx(), s.userOAuthConfig(), userToken)
	if err != nil {
		return mgmt.Fail(http.StatusBadGateway, "provider_unavailable", "GitHub did not complete the installation link.")
	}
	proven := false
	accountLogin := ""
	for _, it := range owned {
		if it.ID == installationID {
			proven = true
			accountLogin = it.AccountLogin
			break
		}
	}
	if !proven {
		// The whole point of this callback: a claimed installation_id is
		// refused, and nothing is linked, unless GitHub's own
		// /user/installations for this user's token names it.
		return mgmt.Fail(http.StatusForbidden, "installation_not_owned",
			"That GitHub installation is not visible to your GitHub account.")
	}

	tx, err := s.tx(c.Ctx())
	if err != nil {
		return mgmt.Internal(err)
	}
	defer func() { _ = tx.Rollback(c.Ctx()) }()
	// The mirror row may not exist yet — the "installation" webhook and
	// this callback can arrive in either order (API-CONTRACT §4.7).
	// Whichever runs first creates the mirror row (account already known
	// from /user/installations, repositories filled in by the next webhook
	// event or by the sync job this callback enqueues below); whichever
	// runs second finds the link already there and enqueues its own sync,
	// so both orders converge on one linked installation with a reconciled
	// repository list and a correct account name from the very first read.
	if _, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.github_installations(installation_id,account,repositories)
 VALUES($1,$2,'[]'::jsonb)
 ON CONFLICT (installation_id) DO UPDATE SET account=excluded.account WHERE gfm.github_installations.account=''`,
		installationID, accountLogin); err != nil {
		return mgmt.Internal(err)
	}
	if _, err := tx.Exec(c.Ctx(), `INSERT INTO gfm.github_installation_links(installation_id,org_id,linked_by,linked_at)
 VALUES($1,$2::uuid,$3::uuid,now())
 ON CONFLICT (installation_id) DO UPDATE SET org_id=excluded.org_id,linked_by=excluded.linked_by,linked_at=now()`,
		installationID, claim.orgID, nullable(claim.userID)); err != nil {
		return mgmt.Internal(err)
	}
	if _, err := s.enqueueGitHubSync(c.Ctx(), tx, claim.orgID, installationID,
		"github-sync:"+strconv.FormatInt(installationID, 10)+":link:"+state); err != nil {
		return mgmt.Internal(err)
	}
	if err := tx.Commit(c.Ctx()); err != nil {
		return mgmt.Internal(err)
	}

	returnTo := claim.returnTo
	if !mgmt.Relative(returnTo) {
		returnTo = "/"
	}
	return c.RedirectTo(returnTo)
}
