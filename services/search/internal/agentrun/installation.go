package agentrun

import (
	"context"
	"encoding/json"
	"net/url"
	"strings"

	"github.com/jackc/pgx/v5"
)

// installationLookup resolves a Guidefold repo_id to the GitHub App
// installation that covers it. gfm.github_installation_links (ADR-0034's
// explicit link) ties an installation to an organisation, but not to a
// specific repo_id — gfm.repos carries only a free-text git_host_url, so
// this lookup still derives an "owner/repo" full name from it and matches
// that against gfm.github_installations.repositories, restricted to
// installations linked to this organisation. A repository this cannot
// resolve is exactly the "no installation" case API-CONTRACT §4.9 names —
// reported, never dropped.
type installationLookup struct {
	// byFullName maps "owner/repo" (lowercase) to the installation that
	// covers it, built once per live.plan run from the organisation's own
	// gfm.github_installations rows.
	byFullName map[string]int64
}

func loadInstallationLookup(ctx context.Context, q querier, orgID string) (*installationLookup, error) {
	rows, e := q.Query(ctx, `SELECT gi.installation_id, gi.repositories FROM gfm.github_installations gi
 JOIN gfm.github_installation_links l ON l.installation_id=gi.installation_id
 WHERE l.org_id=$1::uuid AND gi.suspended_at IS NULL`, orgID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	lookup := &installationLookup{byFullName: map[string]int64{}}
	for rows.Next() {
		var installationID int64
		var raw []byte
		if e := rows.Scan(&installationID, &raw); e != nil {
			return nil, e
		}
		for _, fullName := range parseRepositoriesJSON(raw) {
			lookup.byFullName[strings.ToLower(fullName)] = installationID
		}
	}
	return lookup, rows.Err()
}

// parseRepositoriesJSON reads gfm.github_installations.repositories, which
// this package does not itself write and therefore cannot pin to one exact
// shape: a plain list of "owner/repo" strings, or GitHub's own richer
// installation_repositories item shape ({"full_name": "owner/repo", ...}).
// Accepting both is cheaper than guessing wrong and silently resolving no
// repository at all.
func parseRepositoriesJSON(raw []byte) []string {
	var plain []string
	if json.Unmarshal(raw, &plain) == nil {
		return plain
	}
	var rich []struct {
		FullName string `json:"full_name"`
	}
	if json.Unmarshal(raw, &rich) == nil {
		out := make([]string, 0, len(rich))
		for _, r := range rich {
			if r.FullName != "" {
				out = append(out, r.FullName)
			}
		}
		return out
	}
	return nil
}

// resolve returns the installation covering gitHostURL and whether one was
// found.
func (l *installationLookup) resolve(gitHostURL string) (int64, string, bool) {
	fullName, ok := fullNameFromGitHostURL(gitHostURL)
	if !ok {
		return 0, "", false
	}
	id, ok := l.byFullName[strings.ToLower(fullName)]
	return id, fullName, ok
}

// fullNameFromGitHostURL extracts "owner/repo" from a repository's stored
// git_host_url (for example "https://github.com/acme/meridian" or
// "https://github.com/acme/meridian.git"). A URL that is not a github.com
// path of at least two segments answers false — this package resolves
// GitHub installations only, never a guess at another host's identity.
func fullNameFromGitHostURL(gitHostURL string) (string, bool) {
	u, e := url.Parse(strings.TrimSpace(gitHostURL))
	if e != nil || u.Host == "" {
		return "", false
	}
	host := strings.ToLower(u.Host)
	if host != "github.com" && !strings.HasSuffix(host, ".github.com") {
		return "", false
	}
	path := strings.Trim(u.Path, "/")
	path = strings.TrimSuffix(path, ".git")
	segments := strings.Split(path, "/")
	if len(segments) != 2 || segments[0] == "" || segments[1] == "" {
		return "", false
	}
	return segments[0] + "/" + segments[1], true
}

// looksLikeSkillFile is a small, deliberate duplicate of
// internal/ghapp's own unexported isSkillFile: AGENTS.md at the repository
// root, or any path under a directory literally named .agents/skills. It is
// copied rather than imported because ghapp exports no such predicate (its
// own matching is folded into ListSkillFiles) and this package's own file
// boundary for this change excludes editing ghapp to add one — the same
// dry-without-wrong-abstraction call internal/review/generate.go makes for
// its own longestLiteralPrefix. Should ghapp ever export this rule, this
// copy should be deleted in favour of it.
func looksLikeSkillFile(path string) bool {
	if path == "AGENTS.md" {
		return true
	}
	segments := strings.Split(path, "/")
	for i := 0; i+1 < len(segments); i++ {
		if segments[i] != ".agents" || segments[i+1] != "skills" {
			continue
		}
		rest := segments[i+2:]
		if len(rest) >= 2 && rest[len(rest)-1] == "SKILL.md" {
			return true
		}
	}
	return false
}

// querier is the narrow read both a *pgxpool.Pool and a pgx.Tx satisfy,
// so loadInstallationLookup runs identically inside live.plan's transaction
// and (if a future caller needs it) outside one.
type querier interface {
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}
