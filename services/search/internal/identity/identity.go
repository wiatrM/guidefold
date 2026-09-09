// Package identity implements authentication, organisations and membership for
// the management API: users and their provider identities, sessions and CSRF,
// personal/installation/CI tokens, the device flow, invitations and the audit
// log.
//
// Two rules shape the whole package. Secrets are shown once and stored only as
// SHA-256, so a database dump cannot be replayed against the API. And nothing
// about identity is cached: memberships, sessions and tokens are re-read on
// every request, so revocation takes effect on the next call rather than after
// a cache expiry.
package identity

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// SessionCookie is the browser session cookie name.
const SessionCookie = "gf_session"

// AuthStateCookie binds one login round trip to the browser that began it.
const AuthStateCookie = "gf_auth_state"

// TokenPrefix marks a Guidefold bearer secret.
const TokenPrefix = "gf_"

// SessionTTL is how long a browser session lasts.
const SessionTTL = 7 * 24 * time.Hour

// DeviceTTL and DeviceInterval govern the CLI device flow.
const (
	DeviceTTL      = 10 * time.Minute
	DeviceInterval = 5
	// AuthStateTTL bounds one login round trip.
	AuthStateTTL = 10 * time.Minute
	// InvitationTTL bounds an invitation.
	InvitationTTL = 14 * 24 * time.Hour
)

// Modes.
const (
	ModeDev    = "dev"
	ModeWorkOS = "workos"
)

// Providers the API offers. The dev provider mints these same identities
// locally; nothing downstream distinguishes them by mode.
var providers = []struct{ ID, Label, WorkOS string }{
	{"google", "Google", "GoogleOAuth"},
	{"github", "GitHub", "GitHubOAuth"},
}

var slugPattern = regexp.MustCompile(`^[a-z0-9-]{2,40}$`)
var repoPattern = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,64}$`)

// InstallationScopes are the scopes an installation token may carry.
var InstallationScopes = []string{"search", "use", "events"}

// Config is the resolved deployment configuration.
type Config struct {
	Mode                string // dev|workos
	PublicURL           string // absolute base URL used to build redirect URIs
	InsecureCookies     bool   // local http development only
	WorkOSAPIKey        string
	WorkOSClientID      string
	WorkOSBase          string // API endpoint base; a test points this at httptest
	GitHubWebhookSecret string
}

// Service holds the identity endpoints and the principal resolver.
type Service struct {
	pool   *pgxpool.Pool
	cfg    Config
	workos *WorkOS
	now    func() time.Time
}

// New builds the service. It refuses a WorkOS deployment without credentials
// rather than silently falling back to the development provider, and it refuses
// an unnamed mode outright: there is no default, because the only value that
// could serve as one is the development provider, which mints a session for any
// e-mail typed into a form.
func New(pool *pgxpool.Pool, cfg Config) (*Service, error) {
	if cfg.Mode == "" {
		return nil, fmt.Errorf("auth_mode_required")
	}
	if cfg.Mode != ModeDev && cfg.Mode != ModeWorkOS {
		return nil, fmt.Errorf("invalid_auth_mode")
	}
	if cfg.PublicURL == "" {
		cfg.PublicURL = "http://127.0.0.1:8080"
	}
	cfg.PublicURL = strings.TrimSuffix(cfg.PublicURL, "/")
	s := &Service{pool: pool, cfg: cfg, now: time.Now}
	if cfg.Mode == ModeWorkOS {
		if cfg.WorkOSAPIKey == "" || cfg.WorkOSClientID == "" {
			return nil, fmt.Errorf("workos_requires_api_key_and_client_id")
		}
		s.workos = &WorkOS{APIKey: cfg.WorkOSAPIKey, ClientID: cfg.WorkOSClientID,
			Base: cfg.WorkOSBase, HTTP: &http.Client{Timeout: 10 * time.Second}}
	}
	return s, nil
}

// ConfigFromEnv reads the deployment configuration. GUIDEFOLD_AUTH selects the
// provider and has no default: unset is a configuration error, so a deployment
// that forgets it refuses to serve instead of booting the development provider.
// The development provider is therefore only ever reached by naming it.
func ConfigFromEnv() (Config, error) {
	cfg := Config{
		Mode:            strings.TrimSpace(os.Getenv("GUIDEFOLD_AUTH")),
		PublicURL:       envOr("GUIDEFOLD_PUBLIC_URL", ""),
		InsecureCookies: os.Getenv("GUIDEFOLD_INSECURE_COOKIES") == "true",
		WorkOSClientID:  os.Getenv("WORKOS_CLIENT_ID"),
		WorkOSBase:      os.Getenv("WORKOS_API_BASE"),
	}
	if path := os.Getenv("GITHUB_WEBHOOK_SECRET_FILE"); path != "" {
		b, e := os.ReadFile(path)
		if e != nil {
			return cfg, fmt.Errorf("github_webhook_secret_unreadable: %w", e)
		}
		cfg.GitHubWebhookSecret = strings.TrimSpace(string(b))
	}
	if cfg.Mode == "" {
		return cfg, fmt.Errorf("auth_mode_required: set GUIDEFOLD_AUTH to %q or %q", ModeWorkOS, ModeDev)
	}
	if cfg.Mode != ModeDev && cfg.Mode != ModeWorkOS {
		return cfg, fmt.Errorf("invalid_auth_mode: GUIDEFOLD_AUTH must be %q or %q", ModeWorkOS, ModeDev)
	}
	if path := os.Getenv("WORKOS_API_KEY_FILE"); path != "" {
		b, e := os.ReadFile(path)
		if e != nil {
			return cfg, fmt.Errorf("workos_api_key_unreadable: %w", e)
		}
		cfg.WorkOSAPIKey = strings.TrimSpace(string(b))
	}
	return cfg, nil
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// SetClock replaces the service clock. Tests use it to expire things.
func (s *Service) SetClock(now func() time.Time) { s.now = now }

// Mode reports the configured provider mode.
func (s *Service) Mode() string { return s.cfg.Mode }

func (s *Service) tx(ctx context.Context) (pgx.Tx, error) {
	return s.pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
}

// Resolve turns a request into a principal. It reads, in order, the bearer
// token and the session cookie; a request with neither yields (nil, nil).
func (s *Service) Resolve(ctx context.Context, r *http.Request) (*mgmt.Principal, error) {
	if header := r.Header.Get("Authorization"); strings.HasPrefix(header, "Bearer ") {
		secret := strings.TrimSpace(strings.TrimPrefix(header, "Bearer "))
		if strings.HasPrefix(secret, TokenPrefix) {
			return s.principalFromToken(ctx, secret)
		}
		// Not a Guidefold token: the caller may be using the legacy operator
		// secret, which the delivery endpoints check themselves.
		return nil, nil
	}
	cookie, e := r.Cookie(SessionCookie)
	if e != nil || cookie.Value == "" {
		return nil, nil
	}
	return s.principalFromSession(ctx, cookie.Value)
}

func (s *Service) principalFromToken(ctx context.Context, secret string) (*mgmt.Principal, error) {
	var (
		tokenID, kind         string
		userID, orgID, repoID *string
		email, name           *string
		scopes                []string
		lastSeen, revoked     *time.Time
	)
	e := s.pool.QueryRow(ctx, `SELECT t.token_id::text,t.kind,t.user_id::text,t.org_id::text,t.repo_id,
 t.scopes,t.last_seen_at,t.revoked_at,u.email,u.name
 FROM gfm.tokens t LEFT JOIN gfm.users u ON u.user_id=t.user_id
 WHERE t.token_sha256=$1`, digest(secret)).
		Scan(&tokenID, &kind, &userID, &orgID, &repoID, &scopes, &lastSeen, &revoked, &email, &name)
	if e == pgx.ErrNoRows {
		return nil, mgmt.Unauthenticated("This token is not valid.")
	}
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	if revoked != nil {
		return nil, mgmt.Unauthenticated("This token has been revoked.")
	}
	p := &mgmt.Principal{TokenID: tokenID, Scopes: scopes, Source: kind,
		UserID: str(userID), OrgID: str(orgID), RepoID: str(repoID),
		Email: str(email), Name: str(name)}
	if kind == mgmt.SourcePersonal && p.UserID == "" {
		return nil, mgmt.Unauthenticated("This token is not valid.")
	}
	s.touchToken(ctx, tokenID, lastSeen)
	return p, nil
}

// touchToken records adapter liveness at most once every five minutes, so the
// delivery path does not write on every request.
func (s *Service) touchToken(ctx context.Context, tokenID string, last *time.Time) {
	if last != nil && s.now().Sub(*last) < 5*time.Minute {
		return
	}
	tx, e := s.tx(ctx)
	if e != nil {
		return
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `UPDATE gfm.tokens SET last_seen_at=now() WHERE token_id=$1::uuid`, tokenID); e == nil {
		_ = tx.Commit(ctx)
	}
}

func (s *Service) principalFromSession(ctx context.Context, id string) (*mgmt.Principal, error) {
	var (
		userID, csrf, email, name string
		expires                   time.Time
		revoked                   *time.Time
	)
	e := s.pool.QueryRow(ctx, `SELECT s.user_id::text,s.csrf_token,s.expires_at,s.revoked_at,u.email,u.name
 FROM gfm.sessions s JOIN gfm.users u ON u.user_id=s.user_id WHERE s.id_sha256=$1`, digest(id)).
		Scan(&userID, &csrf, &expires, &revoked, &email, &name)
	if e == pgx.ErrNoRows {
		return nil, nil // a stale cookie is not an error, it is signed out
	}
	if e != nil {
		return nil, mgmt.Internal(e)
	}
	if revoked != nil || !expires.After(s.now()) {
		return nil, nil
	}
	return &mgmt.Principal{UserID: userID, CSRF: csrf, SessionID: digest(id),
		Source: mgmt.SourceSession, Email: email, Name: name}, nil
}

// Membership returns the caller's role in an organisation, or "" when there is
// none. It is re-read per request by design.
func (s *Service) Membership(ctx context.Context, orgID, userID string) (string, error) {
	var role string
	e := s.pool.QueryRow(ctx,
		`SELECT role FROM gfm.memberships WHERE org_id=$1::uuid AND user_id=$2::uuid`, orgID, userID).Scan(&role)
	if e == pgx.ErrNoRows {
		return "", nil
	}
	return role, e
}

// OrgIDForRef maps an org_id or slug to an org_id.
func (s *Service) OrgIDForRef(ctx context.Context, ref string) (string, error) {
	var id string
	e := s.pool.QueryRow(ctx, `SELECT org_id::text FROM gfm.orgs WHERE org_id::text=$1 OR slug=$1`, ref).Scan(&id)
	if e == pgx.ErrNoRows {
		return "", nil
	}
	return id, e
}

// HasRepo reports whether a repository belongs to an organisation.
func (s *Service) HasRepo(ctx context.Context, orgID, repoID string) (bool, error) {
	var ok bool
	e := s.pool.QueryRow(ctx,
		`SELECT EXISTS(SELECT 1 FROM gfm.repos WHERE org_id=$1::uuid AND repo_id=$2)`, orgID, repoID).Scan(&ok)
	return ok, e
}

// Repos lists an organisation's repository identifiers.
func (s *Service) Repos(ctx context.Context, orgID string) ([]string, error) {
	rows, e := s.pool.Query(ctx, `SELECT repo_id FROM gfm.repos WHERE org_id=$1::uuid ORDER BY repo_id`, orgID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var v string
		if e = rows.Scan(&v); e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}

// EnsureRepo registers a repository of an organisation. Imports own this table;
// this entry point exists so an installation token bound to a repository, and
// tests, do not need the import module to be present.
func EnsureRepo(ctx context.Context, tx pgx.Tx, orgID, repoID, name string) error {
	if !repoPattern.MatchString(repoID) {
		return mgmt.Invalid("invalid_repo_id", "repo_id must match [A-Za-z0-9_.-]{1,64}.")
	}
	_, e := tx.Exec(ctx, `INSERT INTO gfm.repos(org_id,repo_id,name) VALUES($1::uuid,$2,$3)
 ON CONFLICT (org_id,repo_id) DO NOTHING`, orgID, repoID, name)
	return e
}

// RegisterRepo is EnsureRepo in its own transaction.
func (s *Service) RegisterRepo(ctx context.Context, orgID, repoID, name string) error {
	tx, e := s.tx(ctx)
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	if e = EnsureRepo(ctx, tx, orgID, repoID, name); e != nil {
		return e
	}
	return tx.Commit(ctx)
}

// digest is the only representation of a secret this service stores.
func digest(secret string) string {
	sum := sha256.Sum256([]byte(secret))
	return hex.EncodeToString(sum[:])
}

// newSecret returns 32 bytes of entropy in URL-safe base64.
func newSecret() string {
	var b [32]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return base64.RawURLEncoding.EncodeToString(b[:])
}

// NewID returns a random RFC 4122 version 4 identifier.
func NewID() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	s := hex.EncodeToString(b[:])
	return s[:8] + "-" + s[8:12] + "-" + s[12:16] + "-" + s[16:20] + "-" + s[20:]
}

// userCode is the short code a person types into the browser during the device
// flow. The alphabet omits characters that are misread out loud or on screen.
func userCode() string {
	const alphabet = "BCDFGHJKLMNPQRSTVWXZ23456789"
	var b [8]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	out := make([]byte, 0, 9)
	for i, v := range b {
		if i == 4 {
			out = append(out, '-')
		}
		out = append(out, alphabet[int(v)%len(alphabet)])
	}
	return string(out)
}

func str(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// OrgIDsOf lists the organisations a person belongs to. The delivery endpoints
// use it to default the tenant when there is only one possible answer.
func (s *Service) OrgIDsOf(ctx context.Context, userID string) ([]string, error) {
	rows, e := s.pool.Query(ctx,
		`SELECT org_id::text FROM gfm.memberships WHERE user_id=$1::uuid ORDER BY org_id`, userID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var v string
		if e = rows.Scan(&v); e != nil {
			return nil, e
		}
		out = append(out, v)
	}
	return out, rows.Err()
}
