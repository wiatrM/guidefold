package agentrun

import (
	"context"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"
)

// rule is one published skill pr.report judged relevant to a changed path —
// "the organisation's rules that apply to those paths" ADR-0036 point 1a
// asks the comment to name.
type rule struct {
	SkillID     string
	Name        string
	Description string
	Scope       string
	Body        string
}

// maxRuleBodyChars bounds how much of one skill's body is fed to the model
// per rule, the same kind of ceiling internal/review/generator's Prompt
// applies per document — a PR can touch a path several rules cover, and an
// unbounded body per rule would let one long SKILL.md crowd out the rest of
// the ceiling a job's limits are supposed to hold.
const maxRuleBodyChars = 1500

// scopePaths reads one repository's declared scope directories the same way
// internal/review/generate.go's own scopeDirs does, from gfm.scopes written
// by import.parse — the source of truth for "which directory does this
// scope own" this package does not otherwise have.
func scopePaths(ctx context.Context, pool *pgxpool.Pool, orgID, repoID string) (map[string]string, error) {
	rows, e := pool.Query(ctx, `SELECT scope, paths FROM gfm.scopes WHERE org_id=$1::uuid AND repo_id=$2`,
		orgID, repoID)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	dirs := map[string]string{}
	for rows.Next() {
		var scope string
		var paths []string
		if e := rows.Scan(&scope, &paths); e != nil {
			return nil, e
		}
		if dir := longestLiteralPrefix(paths); dir != "" {
			dirs[scope] = dir
		}
	}
	return dirs, rows.Err()
}

// longestLiteralPrefix is the same rule internal/review/generate.go applies
// to a node's own globs, duplicated here for the reason its own comment
// gives for duplicating internal/importer/domain.ScopeOf: importing a
// cross-module package for a few lines of glob-prefix matching would add a
// dependency this small, stable logic does not earn.
func longestLiteralPrefix(globs []string) string {
	best := ""
	for _, g := range globs {
		prefix := g
		if i := strings.IndexAny(g, "*?["); i >= 0 {
			prefix = g[:i]
		}
		prefix = strings.TrimSuffix(prefix, "/")
		if len(prefix) > len(best) {
			best = prefix
		}
	}
	return best
}

// scopeForPath picks the most specific scope whose directory contains path
// — the longest matching prefix, the same "most specific node owns the
// file" rule domain.ScopeOf applies at import time. "" means no declared
// scope claims the path, which is common for ordinary source files outside
// any .agents/skills tree.
func scopeForPath(path string, dirs map[string]string) string {
	best, bestLen := "", -1
	for scope, dir := range dirs {
		if dir == "" {
			continue
		}
		if path != dir && !strings.HasPrefix(path, dir+"/") {
			continue
		}
		if len(dir) > bestLen {
			best, bestLen = scope, len(dir)
		}
	}
	return best
}

// applicableRules resolves the organisation's published rules that apply to
// a pull request's changed paths: for each path, the most specific scope
// owning it, then every published skill of the scopes actually touched.
// Ancestor scopes (a parent directory's own rules) are deliberately not
// folded in — a simplification, not a claim that a child's changes can
// never contradict a parent's rule, kept because API-CONTRACT does not
// specify a propagation rule and a wrong guess at one would be worse than
// naming none.
func applicableRules(ctx context.Context, pool *pgxpool.Pool, orgID, repoID string, changedPaths []string) ([]rule, error) {
	dirs, e := scopePaths(ctx, pool, orgID, repoID)
	if e != nil {
		return nil, e
	}
	scopes := map[string]bool{}
	for _, p := range changedPaths {
		if s := scopeForPath(p, dirs); s != "" {
			scopes[s] = true
		}
	}
	if len(scopes) == 0 {
		return nil, nil
	}
	names := make([]string, 0, len(scopes))
	for s := range scopes {
		names = append(names, s)
	}
	rows, e := pool.Query(ctx, `SELECT s.skill_id, s.name, s.description, s.scope, b.content
 FROM gfm.skills s
 JOIN gfm.skill_revisions r ON r.org_id=s.org_id AND r.revision_id=s.current_revision_id
 JOIN gfm.blobs b ON b.org_id=s.org_id AND b.sha256=r.blob_sha256
 WHERE s.org_id=$1::uuid AND s.repo_id=$2 AND s.publication_status='published' AND s.scope=ANY($3::text[])
 ORDER BY s.scope, s.name`, orgID, repoID, names)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	rules := []rule{}
	for rows.Next() {
		var r rule
		var body []byte
		if e := rows.Scan(&r.SkillID, &r.Name, &r.Description, &r.Scope, &body); e != nil {
			return nil, e
		}
		text := string(body)
		if len(text) > maxRuleBodyChars {
			text = text[:maxRuleBodyChars] + "\n… truncated …"
		}
		r.Body = text
		rules = append(rules, r)
	}
	return rules, rows.Err()
}
