package generator

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/review/domain"
)

// KindScopeMap is the proposal kind a scope map carries. It is deliberately not
// one of the three `Generate` kinds: a scope map is not a skill candidate, so
// it does not travel through `Request`/`Output`, and `proposals:generate` never
// accepts it (API-CONTRACT §4.2, 1.14.0).
const KindScopeMap = "scope_map"

// ScopeMapRequest is everything a proposer is allowed to see (ADR-0051
// decision 3). The closed list is the contract, not a budget: repository code
// and `SKILL.md` bodies are absent because the question is how directories
// group into an organisation, and their contents are not evidence for it.
// ADR-0041 decision 2 forbids source text from leaving as a record at all.
type ScopeMapRequest struct {
	OrgID  string
	APIKey string
	Repos  []ScopeMapRepo
	Limits ScopeMapLimits
}

// ScopeMapRepo is one repository's structure.
type ScopeMapRepo struct {
	RepoID string
	// SkillDirs are the directories that actually contain a SKILL.md, which is
	// the only path set a node has any reason to claim.
	SkillDirs []string
	// Existing is what gfm.scopes already says about this repository.
	Existing []domain.ExistingScope
	// Codeowners is the imported CODEOWNERS file, verbatim. It is the one place
	// a real team name is attached to a real path (CONVENTIONS line 34).
	Codeowners string
	// GuidefoldYAML is the repository's own map, when it has one. A repository
	// that declares its hierarchy is evidence for how the organisation names
	// things, even for the repositories that do not.
	GuidefoldYAML string
	// ReadmeHead and AgentsHead are the first ScopeMapHeadChars characters of
	// the root README.md and AGENTS.md -- enough for "what is this repository
	// for", never the document.
	ReadmeHead string
	AgentsHead string
}

// ScopeMapHeadChars bounds how much of a root README or AGENTS.md is shown.
const ScopeMapHeadChars = 400

// ScopeMapLimits bounds one proposal. `MaxCalls` is 1 by contract: the input is
// structure, so a second call is the same question asked twice.
type ScopeMapLimits struct {
	MaxRepos        int
	MaxPathsPerRepo int
	MaxTokens       int
	MaxCalls        int
	MaxUSD          float64
}

// DefaultScopeMapLimits are the ceilings from API-CONTRACT §8.
func DefaultScopeMapLimits() ScopeMapLimits {
	return ScopeMapLimits{MaxRepos: 50, MaxPathsPerRepo: 500, MaxTokens: 50000,
		MaxCalls: 1, MaxUSD: 0.50}
}

// ScopeMapper is the outbound port for proposing an organisation's structure.
//
// It is a second, narrow port rather than a method on `Generator` because the
// two answer different questions with different inputs and different outputs,
// and folding them together would force every implementation to carry a method
// it cannot answer. A generator that does not implement it simply cannot
// propose a map, which the worker reports rather than hides.
type ScopeMapper interface {
	ProposeScopeMap(ctx context.Context, req ScopeMapRequest) (domain.ScopeMap, Cost, error)
}

// ScopeMapperFor returns the scope-map port of an engine, or ErrNotConfigured
// when that engine has none. `none` has none by construction; `deterministic`
// and the three remote providers have one.
func ScopeMapperFor(g Generator) (ScopeMapper, error) {
	if m, ok := g.(ScopeMapper); ok {
		return m, nil
	}
	return nil, ErrNotConfigured
}

// ProposeScopeMap on the deterministic generator returns the *inferred* map:
// the same structure directories, existing nodes and CODEOWNERS already imply,
// with no model involved and no network.
//
// This is not a stub for tests. It is what makes the whole path -- propose,
// diff, review, approve, write `gfm.scopes` -- provable end to end without a
// provider, so the only thing a model adds is the quality of one structure
// (ADR-0051 decision 7).
func (d *Deterministic) ProposeScopeMap(_ context.Context, req ScopeMapRequest) (domain.ScopeMap, Cost, error) {
	return InferScopeMap(req), Cost{}, nil
}

// InferScopeMap builds a map from structure alone.
//
// The rule is deliberately conservative, because a deterministic guess that
// invents a hierarchy is worse than one that admits it does not know: an
// existing node keeps its name, parent, owner and paths; a skill directory no
// node covers becomes its own node under `_root`, named from its path; an owner
// is taken from CODEOWNERS only when a rule names that exact directory.
func InferScopeMap(req ScopeMapRequest) domain.ScopeMap {
	m := domain.ScopeMap{Origin: domain.OriginInferred, Nodes: []domain.ScopeMapNode{}}
	byScope := map[string]*domain.ScopeMapNode{}
	order := []string{}
	add := func(scope, parent, owner, reason string, confidence float64) *domain.ScopeMapNode {
		if n, ok := byScope[scope]; ok {
			return n
		}
		n := &domain.ScopeMapNode{Scope: scope, Parent: parent, Owner: owner,
			Paths: []domain.ScopePath{}, Confidence: confidence, Reason: reason}
		byScope[scope] = n
		order = append(order, scope)
		return n
	}
	for _, r := range req.Repos {
		m.Repos = append(m.Repos, r.RepoID)
		rules := ParseCodeowners(r.Codeowners)
		covered := map[string]bool{}
		for _, e := range r.Existing {
			n := add(e.Scope, e.Parent, e.Owner,
				"kept from the scope this repository already declares", 1)
			for _, p := range e.Paths {
				n.Paths = append(n.Paths, domain.ScopePath{RepoID: r.RepoID, Path: p})
				covered[p] = true
			}
		}
		for _, dir := range r.SkillDirs {
			if covered[dir] || coveredByPrefix(covered, dir) {
				continue
			}
			scope := scopeFromPath(dir)
			if scope == "" {
				scope = domain.RootScope
			}
			n := add(scope, parentOf(scope), ownerFor(rules, dir),
				"a skill directory no declared scope covers", 0.5)
			n.Paths = append(n.Paths, domain.ScopePath{RepoID: r.RepoID, Path: dir})
		}
	}
	// Every non-root node needs its ancestors present, or `parent` names a node
	// outside the map and validation rejects the whole thing.
	for _, scope := range append([]string{}, order...) {
		for p := parentOf(scope); p != ""; p = parentOf(p) {
			add(p, parentOf(p), "", "an ancestor implied by a deeper node", 0.5)
		}
	}
	sort.Strings(order)
	seen := map[string]bool{}
	names := make([]string, 0, len(byScope))
	for s := range byScope {
		names = append(names, s)
	}
	sort.Strings(names)
	for _, s := range names {
		if seen[s] {
			continue
		}
		seen[s] = true
		n := *byScope[s]
		sort.Slice(n.Paths, func(i, j int) bool {
			if n.Paths[i].RepoID != n.Paths[j].RepoID {
				return n.Paths[i].RepoID < n.Paths[j].RepoID
			}
			return n.Paths[i].Path < n.Paths[j].Path
		})
		m.Nodes = append(m.Nodes, n)
	}
	sort.Strings(m.Repos)
	return m
}

func coveredByPrefix(covered map[string]bool, dir string) bool {
	for p := range covered {
		if p != "" && strings.HasPrefix(dir, strings.TrimSuffix(p, "/")+"/") {
			return true
		}
	}
	return false
}

// parentOf is the dotted-path parent. A one-segment node's parent is `_root`,
// and `_root` has none.
func parentOf(scope string) string {
	if scope == domain.RootScope || scope == "" {
		return ""
	}
	if i := strings.LastIndex(scope, "."); i > 0 {
		return scope[:i]
	}
	return domain.RootScope
}

// scopeFromPath turns a directory into a node name, dropping the segments that
// carry no meaning for a hierarchy. It gives up (returns "") rather than emit a
// name that would fail validation.
func scopeFromPath(dir string) string {
	parts := []string{}
	for _, seg := range strings.Split(strings.Trim(dir, "/"), "/") {
		seg = strings.ToLower(seg)
		switch seg {
		case "", ".", "..", ".agents", "skills", "src", "internal", "pkg", "lib":
			continue
		}
		clean := strings.Map(func(r rune) rune {
			switch {
			case r >= 'a' && r <= 'z', r >= '0' && r <= '9':
				return r
			case r == '-', r == '_', r == ' ':
				return '-'
			}
			return -1
		}, seg)
		for strings.Contains(clean, "--") {
			clean = strings.ReplaceAll(clean, "--", "-")
		}
		clean = strings.Trim(clean, "-")
		if clean == "" {
			continue
		}
		parts = append(parts, clean)
		if len(parts) == domain.MaxScopeDepth {
			break
		}
	}
	return strings.Join(parts, ".")
}

// CodeownersRule is one line of a CODEOWNERS file: a path pattern and the teams
// that own it.
type CodeownersRule struct {
	Pattern string
	Owners  []string
}

// ParseCodeowners reads the subset of the CODEOWNERS format that matters here:
// a path pattern followed by owners, comments and blank lines ignored. It does
// not implement gitignore globbing -- a rule only ever matches a directory it
// names as a prefix -- because an owner assigned by a pattern nobody checked is
// exactly the uncertain owner U1 forbids from becoming policy.
func ParseCodeowners(text string) []CodeownersRule {
	var rules []CodeownersRule
	for _, line := range strings.Split(text, "\n") {
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		rules = append(rules, CodeownersRule{Pattern: fields[0], Owners: fields[1:]})
	}
	return rules
}

// CodeownersTeams is every team name a CODEOWNERS file mentions. Validation
// uses it to refuse an owner the file does not contain.
func CodeownersTeams(text string) map[string]bool {
	out := map[string]bool{}
	for _, r := range ParseCodeowners(text) {
		for _, o := range r.Owners {
			out[o] = true
		}
	}
	return out
}

// ownerFor picks the most specific CODEOWNERS rule that names a prefix of the
// directory. Later lines win at equal specificity, as CODEOWNERS itself
// specifies.
func ownerFor(rules []CodeownersRule, dir string) string {
	best, bestLen := "", -1
	for _, r := range rules {
		p := strings.Trim(r.Pattern, "/")
		if p == "*" {
			p = ""
		}
		if p != "" && dir != p && !strings.HasPrefix(dir, p+"/") {
			continue
		}
		if len(p) >= bestLen && len(r.Owners) > 0 {
			best, bestLen = r.Owners[0], len(p)
		}
	}
	return best
}

// ScopeMapPrompt is the whole instruction a remote provider gets. It is built
// from the request and nothing else, so what the model sees is exactly the
// closed list ADR-0051 decision 3 names.
func ScopeMapPrompt(req ScopeMapRequest) string {
	var b strings.Builder
	b.WriteString("You are given the structure of several code repositories that belong to one organisation.\n")
	b.WriteString("Propose how their directories group into one hierarchy of scopes.\n\n")
	b.WriteString("Rules:\n")
	b.WriteString("- A scope name is a dotted path of kebab-case segments, for example `atlas.identity`. No segment may contain `--`. The single top-level fallback node is named `_root`.\n")
	b.WriteString("- `parent` must name another node you return, or be omitted for a top-level node. The parent graph must have no cycle.\n")
	b.WriteString("- Every directory you are given must appear under exactly one node, and each path carries the repository it belongs to.\n")
	b.WriteString("- `owner` must be a team that appears in that repository's CODEOWNERS, or be omitted. Never invent a team name.\n")
	b.WriteString("- `confidence` is between 0 and 1. `reason` is one sentence of at most 200 characters.\n")
	b.WriteString("- Group by what the code is for, not by how deep its directory sits.\n\n")
	b.WriteString("Answer with one JSON object and nothing else:\n")
	b.WriteString(`{"nodes":[{"scope":"","parent":"","owner":"","paths":[{"repo_id":"","path":""}],"confidence":0.0,"reason":""}]}`)
	b.WriteString("\n\n")
	for _, r := range req.Repos {
		fmt.Fprintf(&b, "## repository %s\n", r.RepoID)
		if len(r.SkillDirs) > 0 {
			b.WriteString("skill directories:\n")
			for _, d := range r.SkillDirs {
				fmt.Fprintf(&b, "- %s\n", d)
			}
		}
		if len(r.Existing) > 0 {
			b.WriteString("scopes already declared:\n")
			for _, e := range r.Existing {
				fmt.Fprintf(&b, "- %s (parent %q, owner %q, paths %s)\n",
					e.Scope, e.Parent, e.Owner, strings.Join(e.Paths, ", "))
			}
		}
		if strings.TrimSpace(r.Codeowners) != "" {
			b.WriteString("CODEOWNERS:\n")
			b.WriteString(r.Codeowners)
			b.WriteString("\n")
		}
		if strings.TrimSpace(r.GuidefoldYAML) != "" {
			b.WriteString("guidefold.yaml:\n")
			b.WriteString(r.GuidefoldYAML)
			b.WriteString("\n")
		}
		if r.ReadmeHead != "" {
			fmt.Fprintf(&b, "README.md begins: %s\n", r.ReadmeHead)
		}
		if r.AgentsHead != "" {
			fmt.Fprintf(&b, "AGENTS.md begins: %s\n", r.AgentsHead)
		}
		b.WriteString("\n")
	}
	return b.String()
}

// DecodeScopeMap reads a provider's answer. It refuses anything it cannot parse
// rather than salvaging part of it: half a hierarchy is not a smaller proposal,
// it is a wrong one.
func DecodeScopeMap(raw string) (domain.ScopeMap, error) {
	text := strings.TrimSpace(raw)
	if i := strings.Index(text, "{"); i > 0 {
		text = text[i:]
	}
	if j := strings.LastIndex(text, "}"); j >= 0 && j < len(text)-1 {
		text = text[:j+1]
	}
	var body struct {
		Nodes []domain.ScopeMapNode `json:"nodes"`
	}
	if e := json.Unmarshal([]byte(text), &body); e != nil {
		return domain.ScopeMap{}, fmt.Errorf("scope map is not the documented JSON object: %w", e)
	}
	if len(body.Nodes) == 0 {
		return domain.ScopeMap{}, fmt.Errorf("scope map has no nodes")
	}
	for i := range body.Nodes {
		if body.Nodes[i].Paths == nil {
			body.Nodes[i].Paths = []domain.ScopePath{}
		}
	}
	return domain.ScopeMap{Origin: domain.OriginModel, Nodes: body.Nodes}, nil
}
