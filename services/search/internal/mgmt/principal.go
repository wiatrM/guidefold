package mgmt

// Principal is who is making one request, resolved before any handler runs.
// It is deliberately a value: nothing about a request's identity is looked up
// twice or cached across requests, so revoking a token or a membership takes
// effect on the next request.
type Principal struct {
	UserID    string   // empty for installation, CI and legacy operator tokens
	OrgID     string   // the tenant of this request
	RepoID    string   // set when a token is bound to one repository
	Role      string   // owner|member, when the source implies a membership
	Scopes    []string // token scopes; empty for a session
	Source    string   // session|personal|installation|ci|operator
	TokenID   string
	SessionID string
	CSRF      string
	Email     string // never logged, never returned outside /me
	Name      string
}

// Sources.
const (
	SourceSession      = "session"
	SourcePersonal     = "personal"
	SourceInstallation = "installation"
	SourceCI           = "ci"
	SourceOperator     = "operator"
)

// HasScope reports whether a token carries a scope. A session and a personal
// token act for a person, so they implicitly carry the delivery scopes; an
// installation or CI token only has what it was issued with.
func (p *Principal) HasScope(scope string) bool {
	if p == nil {
		return false
	}
	if p.Source == SourceSession || p.Source == SourceOperator {
		return true
	}
	if p.Source == SourcePersonal {
		switch scope {
		case "search", "use", "events", "user":
			return true
		}
	}
	for _, s := range p.Scopes {
		if s == scope {
			return true
		}
	}
	return false
}

// IsUser reports whether a human is behind the request.
func (p *Principal) IsUser() bool {
	return p != nil && (p.Source == SourceSession || p.Source == SourcePersonal) && p.UserID != ""
}

// ID identifies the principal for idempotency scoping and audit entries.
func (p *Principal) ID() string {
	switch {
	case p == nil:
		return "anonymous"
	case p.UserID != "":
		return "user:" + p.UserID
	case p.TokenID != "":
		return "token:" + p.TokenID
	default:
		return p.Source
	}
}
