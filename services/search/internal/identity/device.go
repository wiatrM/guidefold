package identity

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// Device flow states.
const (
	devicePending  = "pending"
	deviceApproved = "approved"
	deviceDenied   = "denied"
	deviceExpired  = "expired"
)

// handleDeviceStart begins a CLI sign-in. No credentials are needed: the code
// is worthless until a signed-in person approves it in the browser.
func (s *Service) handleDeviceStart(c *mgmt.Context) error {
	code, user := newSecret(), userCode()
	expires := s.now().Add(DeviceTTL)
	tx, e := s.tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer tx.Rollback(c.Ctx())
	if _, e = tx.Exec(c.Ctx(), `INSERT INTO gfm.device_codes(device_code_sha256,user_code,state,expires_at)
 VALUES($1,$2,'pending',$3)`, digest(code), user, expires); e != nil {
		return mgmt.Internal(e)
	}
	if e = tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version":   mgmt.SchemaVersion,
		"device_code":      code,
		"user_code":        user,
		"verification_uri": "/organization?tab=integrations&device=" + user,
		"expires_in":       int(DeviceTTL / time.Second),
		"interval":         DeviceInterval,
	})
}

type deviceTokenRequest struct {
	DeviceCode string `json:"device_code"`
}

// handleDeviceToken is the CLI's poll. It answers with the OAuth device-flow
// error codes so a client can tell "not yet" from "never".
func (s *Service) handleDeviceToken(c *mgmt.Context) error {
	var req deviceTokenRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	if req.DeviceCode == "" {
		return mgmt.Invalid("invalid_request", "device_code is required.")
	}
	tx, e := s.tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer tx.Rollback(c.Ctx())
	var state string
	var owner *string
	var expires time.Time
	var lastPoll *time.Time
	e = tx.QueryRow(c.Ctx(), `SELECT state,user_id::text,expires_at,last_poll_at
 FROM gfm.device_codes WHERE device_code_sha256=$1 FOR UPDATE`, digest(req.DeviceCode)).
		Scan(&state, &owner, &expires, &lastPoll)
	if e == pgx.ErrNoRows {
		return deviceError("expired_token", "This device code is not valid.")
	}
	if e != nil {
		return mgmt.Internal(e)
	}
	now := s.now()
	if state == deviceExpired || !expires.After(now) {
		return deviceError("expired_token", "This device code has expired. Start again.")
	}
	if state == deviceDenied {
		return deviceError("access_denied", "The sign-in request was denied.")
	}
	tooFast := lastPoll != nil && now.Sub(*lastPoll) < DeviceInterval*time.Second
	if _, e = tx.Exec(c.Ctx(), `UPDATE gfm.device_codes SET last_poll_at=now()
 WHERE device_code_sha256=$1`, digest(req.DeviceCode)); e != nil {
		return mgmt.Internal(e)
	}
	if state == devicePending {
		if e = tx.Commit(c.Ctx()); e != nil {
			return mgmt.Internal(e)
		}
		if tooFast {
			return deviceError("slow_down", "Poll no more often than every 5 seconds.")
		}
		return deviceError("authorization_pending", "Waiting for the browser approval.")
	}
	// Approved: mint the personal token and burn the device code, so one
	// approval yields exactly one secret.
	userID := str(owner)
	secret, tokenID, e := s.issueToken(c.Ctx(), tx, tokenSpec{
		Kind: mgmt.SourcePersonal, UserID: userID, Scopes: []string{"user"}, Name: "CLI login"})
	if e != nil {
		return e
	}
	if _, e = tx.Exec(c.Ctx(), `UPDATE gfm.device_codes SET state='expired'
 WHERE device_code_sha256=$1`, digest(req.DeviceCode)); e != nil {
		return mgmt.Internal(e)
	}
	var email string
	if e = tx.QueryRow(c.Ctx(), `SELECT email FROM gfm.users WHERE user_id=$1::uuid`, userID).Scan(&email); e != nil {
		return mgmt.Internal(e)
	}
	if e = tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	orgs, err := s.orgsOf(c.Ctx(), userID)
	if err != nil {
		return err
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion,
		"token":          secret,
		"token_id":       tokenID,
		"user":           map[string]any{"id": userID, "email": email},
		"orgs":           orgs,
	})
}

// deviceError uses 400 with the OAuth device-flow code, as the brief specifies.
func deviceError(code, message string) error { return mgmt.Invalid(code, message) }

type deviceDecisionRequest struct {
	UserCode string `json:"user_code"`
}

func (s *Service) handleDeviceApprove(c *mgmt.Context) error {
	return s.decideDevice(c, deviceApproved)
}
func (s *Service) handleDeviceDeny(c *mgmt.Context) error {
	return s.decideDevice(c, deviceDenied)
}

func (s *Service) decideDevice(c *mgmt.Context, decision string) error {
	if !c.Principal.IsUser() {
		return mgmt.Forbidden()
	}
	var req deviceDecisionRequest
	if e := c.Decode(&req); e != nil {
		return e
	}
	if req.UserCode == "" {
		return mgmt.Invalid("invalid_request", "user_code is required.")
	}
	tx, e := s.tx(c.Ctx())
	if e != nil {
		return mgmt.Internal(e)
	}
	defer tx.Rollback(c.Ctx())
	tag, e := tx.Exec(c.Ctx(), `UPDATE gfm.device_codes SET state=$2,user_id=$3::uuid
 WHERE user_code=$1 AND state='pending' AND expires_at>now()`, req.UserCode, decision, c.Principal.UserID)
	if e != nil {
		return mgmt.Internal(e)
	}
	if tag.RowsAffected() == 0 {
		return mgmt.NotFound("device_code_not_found", "That code is unknown, already used or expired.")
	}
	if e = tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "user_code": req.UserCode, "state": decision})
}
