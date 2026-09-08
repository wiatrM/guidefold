package identity

import (
	"net/http"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// Register mounts the authentication and organisation endpoints.
//
// The route options say what each endpoint is: Public means no credentials are
// required, NoCSRF marks the routes that establish a session rather than act
// with one, and Idempotent marks the organisation mutations that must be safe
// to repeat.
func (s *Service) Register(r *mgmt.Router) {
	r.Handle(http.MethodGet, "/api/v1/auth/providers", s.handleProviders, mgmt.Public())
	r.Handle(http.MethodGet, "/api/v1/auth/login/{provider}", s.handleLogin, mgmt.Public())
	// The development sign-in form mints a session for any e-mail submitted to
	// it. It is not merely gated inside the handler: in any mode but dev the
	// route does not exist, so a mode misconfiguration cannot expose it.
	if s.cfg.Mode == ModeDev {
		r.Handle(http.MethodGet, "/api/v1/auth/dev", s.handleDevForm, mgmt.Public())
		r.Handle(http.MethodPost, "/api/v1/auth/dev", s.handleDevSubmit, mgmt.Public(), mgmt.NoCSRF())
	}
	r.Handle(http.MethodGet, "/api/v1/auth/callback", s.handleCallback, mgmt.Public())
	r.Handle(http.MethodPost, "/api/v1/auth/logout", s.handleLogout)

	r.Handle(http.MethodGet, "/api/v1/me", s.handleMe)
	r.Handle(http.MethodPost, "/api/v1/me/identities/link/start", s.handleLinkStart)

	r.Handle(http.MethodPost, "/api/v1/auth/device", s.handleDeviceStart, mgmt.Public(), mgmt.NoCSRF())
	r.Handle(http.MethodPost, "/api/v1/auth/device/token", s.handleDeviceToken, mgmt.Public(), mgmt.NoCSRF())
	r.Handle(http.MethodPost, "/api/v1/auth/device/approve", s.handleDeviceApprove)
	r.Handle(http.MethodPost, "/api/v1/auth/device/deny", s.handleDeviceDeny)

	r.Handle(http.MethodPost, "/api/v1/orgs", s.handleCreateOrg, mgmt.Idempotent())
	r.Handle(http.MethodGet, "/api/v1/orgs", s.handleListOrgs)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}", s.handleGetOrg)
	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/members", s.handleListMembers)
	r.Handle(http.MethodPatch, "/api/v1/orgs/{org}/members/{user_id}", s.handleSetRole, mgmt.Idempotent())
	r.Handle(http.MethodDelete, "/api/v1/orgs/{org}/members/{user_id}", s.handleRemoveMember, mgmt.Idempotent())
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/invitations", s.handleInvite, mgmt.Idempotent())
	r.Handle(http.MethodPost, "/api/v1/invitations/{token}/accept", s.handleAcceptInvitation,
		mgmt.Idempotent())

	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/installations", s.handleListInstallations)
	r.Handle(http.MethodPost, "/api/v1/orgs/{org}/installations", s.handleCreateInstallation, mgmt.Idempotent())
	r.Handle(http.MethodDelete, "/api/v1/orgs/{org}/installations/{installation_id}",
		s.handleRevokeInstallation, mgmt.Idempotent())

	r.Handle(http.MethodGet, "/api/v1/orgs/{org}/audit", s.handleAudit)
}
