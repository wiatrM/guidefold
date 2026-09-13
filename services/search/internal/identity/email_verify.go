package identity

import (
	"context"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// emailVerificationStateKind names the gfm.auth_states row this flow writes
// and reads (API-CONTRACT §2, §4.1): WorkOS answered the login/link round
// trip's Authenticate call with email_verification_required. It reuses the
// same table, TTL and gf_auth_state cookie discipline as 'login'/'link'/
// 'github_install' — never a second state mechanism — but, unlike those
// three, the row is read and updated more than once: a wrong code must not
// destroy it (that would make the attempt limit unreachable and "wrong code"
// unreproducible), so this file never calls consumeAuthState or
// matchAuthStateCookie. It reads the gf_auth_state cookie directly as the
// row's own lookup key: there is no separate `state` transmitted back to
// this service to compare it against (unlike the outer login round trip,
// which must put state in the URL because WorkOS has to echo it back), so
// the pending token and the state secret never appear together outside this
// server, and neither ever appears in a URL.
const emailVerificationStateKind = "email_verification"

// maskEmail partly hides an address for display on the console's code
// screen: the redirect that sends the browser there (§4.1) carries this
// masked form in `?email=`, never the address WorkOS returned verbatim.
func maskEmail(email string) string {
	at := strings.IndexByte(email, '@')
	if at <= 0 {
		return "•••"
	}
	local, domain := email[:at], email[at+1:]
	if len(local) <= 1 {
		return "•@" + domain
	}
	hide := len(local) - 1
	if hide > 6 {
		hide = 6
	}
	return local[:1] + strings.Repeat("•", hide) + "@" + domain
}

// newEmailVerificationState opens the pending round trip: WorkOS's own
// pending_authentication_token and the email it names, plus everything the
// original login/link claim already proved (provider, an in-progress link's
// user id, return_to), so the eventual code submission can finish sign-in
// exactly as if email_verification_required had never happened.
//
// pending_token cannot be reduced to a SHA-256 like every other secret this
// package stores (identity.go's package doc): it must be replayed to WorkOS
// verbatim on the next step. It is still short-lived (AuthStateTTL),
// single-use (deleted on success or on exhausting attempts —
// beginEmailVerificationAttempt / consumeEmailVerificationState below),
// never leaves this server, and is never logged.
func (s *Service) newEmailVerificationState(ctx context.Context, claim authClaim, pendingToken, email string) (string, error) {
	state := newSecret()
	linkUser := ""
	if claim.kind == "link" {
		linkUser = claim.userID
	}
	tx, e := s.tx(ctx)
	if e != nil {
		return "", mgmt.Internal(e)
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `INSERT INTO gfm.auth_states
 (state_sha256,kind,provider,user_id,return_to,pending_token,pending_email,attempts,expires_at)
 VALUES($1,$2,$3,$4::uuid,$5,$6,$7,0,$8)`,
		digest(state), emailVerificationStateKind, claim.provider, nullable(linkUser), claim.returnTo,
		pendingToken, email, s.now().Add(AuthStateTTL)); e != nil {
		return "", mgmt.Internal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		return "", mgmt.Internal(e)
	}
	return state, nil
}

// pendingEmailVerification is one row of gfm.auth_states read back by
// beginEmailVerificationAttempt.
type pendingEmailVerification struct {
	provider, linkUser, returnTo, pendingToken, email string
}

// beginEmailVerificationAttempt reads the state the gf_auth_state cookie
// names, reserves one attempt against it, and returns the claim needed to
// call WorkOS and finish sign-in. It never deletes the row for an ordinary
// attempt (that is the whole point: a wrong code must remain retryable up to
// EmailVerificationMaxAttempts) — only an unknown/wrong-kind state, an
// expired row or an exhausted row is terminal, and each of those deletes the
// row and reports its own closed code.
func (s *Service) beginEmailVerificationAttempt(ctx context.Context, stateCookie string) (pendingEmailVerification, error) {
	var out pendingEmailVerification
	tx, e := s.tx(ctx)
	if e != nil {
		return out, mgmt.Internal(e)
	}
	defer tx.Rollback(ctx)
	var kind string
	var userID *string
	var attempts int
	var expires time.Time
	e = tx.QueryRow(ctx, `SELECT kind,provider,user_id::text,return_to,pending_token,pending_email,attempts,expires_at
 FROM gfm.auth_states WHERE state_sha256=$1 FOR UPDATE`, digest(stateCookie)).
		Scan(&kind, &out.provider, &userID, &out.returnTo, &out.pendingToken, &out.email, &attempts, &expires)
	if e == pgx.ErrNoRows {
		return out, mgmt.Invalid("invalid_state", "This verification did not start in this browser, or was already used.")
	}
	if e != nil {
		return out, mgmt.Internal(e)
	}
	if kind != emailVerificationStateKind {
		return out, mgmt.Invalid("invalid_state", "This verification did not start in this browser, or was already used.")
	}
	if !expires.After(s.now()) {
		if _, e = tx.Exec(ctx, `DELETE FROM gfm.auth_states WHERE state_sha256=$1`, digest(stateCookie)); e != nil {
			return out, mgmt.Internal(e)
		}
		if e = tx.Commit(ctx); e != nil {
			return out, mgmt.Internal(e)
		}
		return out, mgmt.Invalid("expired_state", "This verification code has expired. Sign in again.")
	}
	if attempts >= EmailVerificationMaxAttempts {
		if _, e = tx.Exec(ctx, `DELETE FROM gfm.auth_states WHERE state_sha256=$1`, digest(stateCookie)); e != nil {
			return out, mgmt.Internal(e)
		}
		if e = tx.Commit(ctx); e != nil {
			return out, mgmt.Internal(e)
		}
		return out, mgmt.Invalid("email_code_attempts_exceeded", "Too many attempts. Sign in again.")
	}
	if _, e = tx.Exec(ctx, `UPDATE gfm.auth_states SET attempts=attempts+1 WHERE state_sha256=$1`, digest(stateCookie)); e != nil {
		return out, mgmt.Internal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		return out, mgmt.Internal(e)
	}
	out.linkUser = deref(userID)
	return out, nil
}

// consumeEmailVerificationState deletes the row on success: one round trip,
// one use, the same rule consumeAuthState applies to 'login'/'link'/
// 'github_install'.
func (s *Service) consumeEmailVerificationState(ctx context.Context, stateCookie string) error {
	tx, e := s.tx(ctx)
	if e != nil {
		return mgmt.Internal(e)
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `DELETE FROM gfm.auth_states WHERE state_sha256=$1`, digest(stateCookie)); e != nil {
		return mgmt.Internal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		return mgmt.Internal(e)
	}
	return nil
}

// emailCodeRequest is POST /api/v1/auth/verify-email's body (API-CONTRACT §4.1).
type emailCodeRequest struct {
	Code string `json:"code"`
}

// handleVerifyEmailCode completes email_verification_required. Unlike
// handleCallback this is a normal fetch-based JSON route, not a browser
// navigation target: the console's code screen calls it directly and reads
// its closed error codes itself (invalid_state, expired_state,
// email_code_invalid, email_code_attempts_exceeded), the same convention the
// device flow's polling route already uses. On success it finishes sign-in
// exactly like handleCallback and answers `return_to` for the console to
// navigate to, instead of a redirect a fetch call cannot follow into a new
// document.
func (s *Service) handleVerifyEmailCode(c *mgmt.Context) error {
	if s.cfg.Mode != ModeWorkOS {
		return mgmt.NotFound("not_found", "No such endpoint.")
	}
	cookie, ce := c.R.Cookie(AuthStateCookie)
	if ce != nil || cookie.Value == "" {
		return mgmt.Invalid("invalid_state", "This verification did not start in this browser, or was already used.")
	}
	var req emailCodeRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	code := strings.TrimSpace(req.Code)
	if code == "" || len(code) > 32 {
		return mgmt.Invalid("invalid_request", "Enter the code from your email.")
	}
	claim, e := s.beginEmailVerificationAttempt(c.Ctx(), cookie.Value)
	if e != nil {
		// invalid_state/expired_state/email_code_attempts_exceeded are all
		// terminal: nothing to retry this cookie against any more.
		s.clearAuthStateCookie(c)
		return e
	}
	result, werr := s.workos.AuthenticateEmailVerificationCode(c.Ctx(), claim.pendingToken, code)
	if werr != nil {
		// The row survives (its attempt was already reserved above) so a
		// second try can still succeed up to EmailVerificationMaxAttempts.
		// See workos.go's AuthenticateEmailVerificationCode doc for why this
		// service does not try to tell a wrong code apart from WorkOS's own
		// notion of an expired one here — this service's own row expiry and
		// attempt count are what "expired" and "too many attempts" mean.
		return mgmt.Invalid("email_code_invalid", "That code was not accepted. Try again.")
	}
	if e := s.consumeEmailVerificationState(c.Ctx(), cookie.Value); e != nil {
		return e
	}
	s.clearAuthStateCookie(c)
	returnTo := claim.returnTo
	if !mgmt.Relative(returnTo) {
		returnTo = "/"
	}
	if _, e := s.completeSignInCore(c, claim.provider, result.User.ID, result.User.Email, result.User.Name(), claim.linkUser); e != nil {
		return e
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion,
		"return_to":      returnTo,
	})
}
