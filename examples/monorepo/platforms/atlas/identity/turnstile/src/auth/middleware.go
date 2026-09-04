// Package auth is turnstile's request authorization chain:
// Authenticate -> LoadPrincipal -> Authorize -> handler.
package auth

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/open-policy-agent/opa/rego"
)

// Config holds the behaviour flags read once from deploy/deployment.yaml (config.auth).
type Config struct {
	LegacyAuthMode       bool `yaml:"legacyAuthMode"`
	DecisionCacheVersion int  `yaml:"decisionCacheVersion"`
	FailClosed           bool `yaml:"failClosed"`
}

// Verifier validates a bearer token against the auth-sdk key set.
type Verifier interface {
	Verify(ctx context.Context, token string) (principalID string, err error)
}

type Principal struct {
	ID      string   `json:"id"`
	Roles   []string `json:"roles"`
	OrgUnit string   `json:"orgUnit"`
}

// PolicyInput is the OPA input document; its shape is owned by rbac-policies.
type PolicyInput struct {
	Principal Principal         `json:"principal"`
	Action    string            `json:"action"`
	Resource  map[string]string `json:"resource"`
	Context   map[string]string `json:"context"`
}

type Middleware struct {
	cfg      Config
	verifier Verifier
	db       *sql.DB
	policy   rego.PreparedEvalQuery
}

// Authenticate extracts and verifies the bearer token. With cfg.LegacyAuthMode
// it falls back to the atlas_sessions table when no token is present.
func (m *Middleware) Authenticate(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		tok := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
		var pid string
		var err error
		switch {
		case tok != "":
			pid, err = m.verifier.Verify(r.Context(), tok)
		case m.cfg.LegacyAuthMode:
			legacyFallbackTotal.Inc()
			pid, err = m.legacySession(r.Context(), r)
		default:
			err = errNoCredentials
		}
		if err != nil {
			writeForbidden(w, r, "auth_backend_unavailable")
			return
		}
		next.ServeHTTP(w, r.WithContext(withPrincipalID(r.Context(), pid)))
	})
}

// LoadPrincipal resolves roles valid now from Postgres (one query, cached 30 s).
func (m *Middleware) LoadPrincipal(ctx context.Context, pid string) (Principal, error) {
	const q = `SELECT p.org_unit, array_agg(r.role) FROM principals p
	           JOIN principal_roles r USING (principal_id)
	           WHERE p.principal_id = $1 AND now() BETWEEN r.valid_from AND coalesce(r.valid_to, 'infinity')
	           GROUP BY p.org_unit`
	p := Principal{ID: pid}
	err := m.db.QueryRowContext(ctx, q, pid).Scan(&p.OrgUnit, &p.Roles)
	return p, err
}

// Authorize evaluates data.atlas.rbac.allow; any backend error fails closed.
func (m *Middleware) Authorize(ctx context.Context, in PolicyInput) (bool, error) {
	raw, _ := json.Marshal(in)
	var doc map[string]any
	_ = json.Unmarshal(raw, &doc)
	rs, err := m.policy.Eval(ctx, rego.EvalInput(doc))
	if err != nil || len(rs) == 0 {
		return false, err
	}
	return rs.Allowed(), nil
}
