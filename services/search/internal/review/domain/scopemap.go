// Package domain holds the review module's rules that need no I/O: today, the
// shape of a proposed organisation scope map, what makes one valid, and what it
// would change about the scopes an organisation already has (ADR-0051).
//
// Nothing here opens a database, a socket or a file. That is the point: the
// answer to "is this map sound" must be the same in a worker deciding whether
// to store a proposal and in an API handler deciding whether to apply it, and
// the only way to guarantee that is for both to call the same pure function.
package domain

import (
	"fmt"
	"sort"
	"strings"
)

// RootScope is the node every path falls back to when no other node claims it.
// It is the one node name that is not a dotted path (CONVENTIONS §1).
const RootScope = "_root"

// MaxScopeDepth bounds how deep a proposed hierarchy may go. Six levels is
// already more than the organisation → platform → team → component chain the
// product describes; past that the map is describing directories, not an
// organisation.
const MaxScopeDepth = 6

// MaxReasonLen bounds the one-line justification a node carries. It is a
// sentence for a person reading a diff, not a place for a model to write an
// essay the reviewer will skip.
const MaxReasonLen = 200

// ScopePath is one repository path claimed by a node. The repository is part of
// the identity, never implied: a scope identifier is unique per repository, not
// per organisation (ADR-0047 decision 4, API-CONTRACT §4.10 point 6), so a map
// that carried bare paths would silently merge two repositories' directories.
type ScopePath struct {
	RepoID string `json:"repo_id"`
	Path   string `json:"path"`
}

// ScopeMapNode is one node of a proposed hierarchy.
type ScopeMapNode struct {
	Scope      string      `json:"scope"`
	Parent     string      `json:"parent,omitempty"`
	Owner      string      `json:"owner,omitempty"`
	Paths      []ScopePath `json:"paths"`
	Confidence float64     `json:"confidence"`
	Reason     string      `json:"reason"`
}

// ScopeMap is the whole proposal: the organisation's structure as one model (or
// one deterministic rule) would draw it.
type ScopeMap struct {
	Origin string         `json:"origin"`
	Model  string         `json:"model,omitempty"`
	Repos  []string       `json:"repos"`
	Nodes  []ScopeMapNode `json:"nodes"`
}

// Origins a map can have. `OriginInferred` is the deterministic map built from
// directories, existing nodes and CODEOWNERS with no model involved; it is what
// the flow proposes when the deployment's generator is `deterministic`, so the
// whole review path is provable without a provider (ADR-0051 decision 7).
const (
	OriginInferred = "inferred"
	OriginModel    = "model"
)

// ExistingScope is one row of gfm.scopes as the diff sees it. The domain does
// not know it is a row; it knows it is what the organisation has now.
type ExistingScope struct {
	RepoID string
	Scope  string
	Parent string
	Owner  string
	Paths  []string
	Source string
}

// ScopeChange is one node's move in a diff: a reparent or an owner change.
type ScopeChange struct {
	Scope  string `json:"scope"`
	RepoID string `json:"repo_id"`
	From   string `json:"from,omitempty"`
	To     string `json:"to,omitempty"`
}

// PathChange names what a node would gain and lose in one repository.
type PathChange struct {
	Scope   string   `json:"scope"`
	RepoID  string   `json:"repo_id"`
	Added   []string `json:"added"`
	Removed []string `json:"removed"`
}

// ScopeMapDiff is what approving would change, against what the organisation
// has now. There is deliberately no `removed` list: approving a map never
// deletes a scope row (API-CONTRACT §6), because a node vanishing without a
// decision would take skills out of view with nobody having chosen that.
type ScopeMapDiff struct {
	Added        []string      `json:"added"`
	Reparented   []ScopeChange `json:"reparented"`
	OwnerChanged []ScopeChange `json:"owner_changed"`
	PathsChanged []PathChange  `json:"paths_changed"`
	Unchanged    int           `json:"unchanged"`
}

// ValidateScopeMap returns every reason the map may not become a proposal or be
// applied, in a stable order. An empty slice means the map is sound.
//
// It returns *all* the findings rather than the first, because a person looking
// at a rejected map wants to know what is wrong with it, not to discover the
// next problem on the next attempt.
//
// `owners` maps a repository id to the set of team names its CODEOWNERS file
// names. A repository absent from the map has no CODEOWNERS the importer could
// read, and then any owner on its nodes is unverifiable — which is a finding,
// not a silent pass: an owner nobody can check is exactly the "uncertain owner
// becoming policy" PRODUCT-PIVOT U1 forbids.
func ValidateScopeMap(m ScopeMap, repos []string, owners map[string]map[string]bool) []string {
	var findings []string
	switch m.Origin {
	case OriginInferred, OriginModel:
	default:
		findings = append(findings, fmt.Sprintf("origin %q is neither %q nor %q", m.Origin, OriginInferred, OriginModel))
	}
	if len(m.Nodes) == 0 {
		return append(findings, "map has no nodes")
	}
	known := map[string]bool{}
	allowedRepo := map[string]bool{}
	for _, r := range repos {
		allowedRepo[r] = true
	}
	for _, n := range m.Nodes {
		if known[n.Scope] {
			findings = append(findings, fmt.Sprintf("node %q appears twice", n.Scope))
		}
		known[n.Scope] = true
	}
	// claimed maps (repo, path) to the node that claims it, so the same path
	// under two nodes is named once with both claimants.
	claimed := map[ScopePath]string{}
	for _, n := range m.Nodes {
		if e := ValidateScopeName(n.Scope); e != "" {
			findings = append(findings, e)
		}
		if n.Parent != "" && !known[n.Parent] {
			findings = append(findings, fmt.Sprintf("node %q names parent %q, which is not in the map", n.Scope, n.Parent))
		}
		if n.Parent == n.Scope && n.Parent != "" {
			findings = append(findings, fmt.Sprintf("node %q is its own parent", n.Scope))
		}
		if n.Confidence < 0 || n.Confidence > 1 {
			findings = append(findings, fmt.Sprintf("node %q has confidence %v outside [0,1]", n.Scope, n.Confidence))
		}
		if strings.TrimSpace(n.Reason) == "" {
			findings = append(findings, fmt.Sprintf("node %q has no reason", n.Scope))
		}
		if len(n.Reason) > MaxReasonLen {
			findings = append(findings, fmt.Sprintf("node %q has a reason longer than %d characters", n.Scope, MaxReasonLen))
		}
		if n.Owner != "" {
			for _, p := range n.Paths {
				if !owners[p.RepoID][n.Owner] {
					findings = append(findings, fmt.Sprintf("node %q names owner %q, which is not in CODEOWNERS of repository %q", n.Scope, n.Owner, p.RepoID))
					break
				}
			}
		}
		for _, p := range n.Paths {
			if p.RepoID == "" || p.Path == "" {
				findings = append(findings, fmt.Sprintf("node %q has a path with an empty repository or path", n.Scope))
				continue
			}
			if !allowedRepo[p.RepoID] {
				findings = append(findings, fmt.Sprintf("node %q claims a path in repository %q, which is not part of this organisation's map", n.Scope, p.RepoID))
				continue
			}
			// Containment is per (repo, path). Computing it over a flat, global
			// path set would validate happily and then write wrong rows, because
			// two repositories may legitimately both have `services/api`.
			if other, taken := claimed[p]; taken {
				findings = append(findings, fmt.Sprintf("path %s/%s is claimed by both %q and %q", p.RepoID, p.Path, other, n.Scope))
				continue
			}
			claimed[p] = n.Scope
		}
	}
	if cycle := FindScopeCycle(m.Nodes); len(cycle) > 0 {
		findings = append(findings, "parent cycle: "+strings.Join(cycle, " -> "))
	}
	sort.Strings(findings)
	return findings
}

// ValidateScopeName returns a finding, or "" when the name is a usable node
// path.
//
// The `--` rule is not cosmetic. ADR-0008 decision 1 maps a node to a registry
// resource id by replacing `.` with `-` and joining the parts with `--`, so a
// segment that itself contains `--` makes the mapping non-injective: two
// different nodes would produce one resource id, and the reverse mapping would
// pick the wrong one.
func ValidateScopeName(scope string) string {
	if scope == RootScope {
		return ""
	}
	if scope == "" {
		return "a node has an empty name"
	}
	parts := strings.Split(scope, ".")
	if len(parts) > MaxScopeDepth {
		return fmt.Sprintf("node %q is %d levels deep, more than %d", scope, len(parts), MaxScopeDepth)
	}
	for _, seg := range parts {
		if seg == "" {
			return fmt.Sprintf("node %q has an empty segment", scope)
		}
		if strings.Contains(seg, "--") {
			return fmt.Sprintf("node %q has a segment containing `--`, which is the registry id separator (ADR-0008)", scope)
		}
		if seg[0] == '-' || seg[len(seg)-1] == '-' {
			return fmt.Sprintf("node %q has a segment starting or ending with a hyphen", scope)
		}
		for _, r := range seg {
			if (r < 'a' || r > 'z') && (r < '0' || r > '9') && r != '-' {
				return fmt.Sprintf("node %q has a segment that is not kebab-case", scope)
			}
		}
	}
	return ""
}

// FindScopeCycle names one parent loop, or returns nil. It names the loop
// rather than reporting a boolean for the same reason the snapshot validator
// does: a rejection has to tell the owner *which* nodes form it.
func FindScopeCycle(nodes []ScopeMapNode) []string {
	parent := map[string]string{}
	order := make([]string, 0, len(nodes))
	for _, n := range nodes {
		parent[n.Scope] = n.Parent
		order = append(order, n.Scope)
	}
	sort.Strings(order)
	const (
		unvisited = 0
		onStack   = 1
		done      = 2
	)
	state := map[string]int{}
	for _, start := range order {
		if state[start] != unvisited {
			continue
		}
		var stack []string
		cur := start
		for cur != "" {
			switch state[cur] {
			case onStack:
				// Cut the prefix that leads into the loop, so the returned slice
				// is the loop itself and not the walk that found it.
				for i, s := range stack {
					if s == cur {
						return append(append([]string{}, stack[i:]...), cur)
					}
				}
				return append(stack, cur)
			case done:
				cur = ""
				continue
			}
			state[cur] = onStack
			stack = append(stack, cur)
			next, ok := parent[cur]
			if !ok {
				next = ""
			}
			cur = next
		}
		for _, s := range stack {
			state[s] = done
		}
	}
	return nil
}

// DiffScopeMap says what applying the map would change about the scopes the
// organisation has now.
//
// It is computed at read time, never frozen at write time: a proposal left in
// the queue for a week has to show what approving it would do *today*
// (API-CONTRACT §5.4).
func DiffScopeMap(m ScopeMap, existing []ExistingScope) ScopeMapDiff {
	diff := ScopeMapDiff{Added: []string{}, Reparented: []ScopeChange{},
		OwnerChanged: []ScopeChange{}, PathsChanged: []PathChange{}}
	type key struct{ repo, scope string }
	have := map[key]ExistingScope{}
	for _, e := range existing {
		have[key{e.RepoID, e.Scope}] = e
	}
	// A node spans repositories; a row does not. The diff is therefore per
	// (repository, node) pair, which is also the primary key it will be written
	// under.
	for _, n := range sortedNodes(m.Nodes) {
		byRepo := map[string][]string{}
		for _, p := range n.Paths {
			byRepo[p.RepoID] = append(byRepo[p.RepoID], p.Path)
		}
		for _, repo := range sortedKeys(byRepo) {
			paths := byRepo[repo]
			sort.Strings(paths)
			old, existed := have[key{repo, n.Scope}]
			if !existed {
				diff.Added = append(diff.Added, repo+"/"+n.Scope)
				continue
			}
			changed := false
			if old.Parent != n.Parent {
				diff.Reparented = append(diff.Reparented,
					ScopeChange{Scope: n.Scope, RepoID: repo, From: old.Parent, To: n.Parent})
				changed = true
			}
			if old.Owner != n.Owner {
				diff.OwnerChanged = append(diff.OwnerChanged,
					ScopeChange{Scope: n.Scope, RepoID: repo, From: old.Owner, To: n.Owner})
				changed = true
			}
			added, removed := diffStrings(old.Paths, paths)
			if len(added) > 0 || len(removed) > 0 {
				diff.PathsChanged = append(diff.PathsChanged,
					PathChange{Scope: n.Scope, RepoID: repo, Added: added, Removed: removed})
				changed = true
			}
			if !changed {
				diff.Unchanged++
			}
		}
	}
	return diff
}

func diffStrings(before, after []string) (added, removed []string) {
	was, is := map[string]bool{}, map[string]bool{}
	for _, s := range before {
		was[s] = true
	}
	for _, s := range after {
		is[s] = true
		if !was[s] {
			added = append(added, s)
		}
	}
	for _, s := range before {
		if !is[s] {
			removed = append(removed, s)
		}
	}
	sort.Strings(added)
	sort.Strings(removed)
	if added == nil {
		added = []string{}
	}
	if removed == nil {
		removed = []string{}
	}
	return added, removed
}

func sortedNodes(nodes []ScopeMapNode) []ScopeMapNode {
	out := append([]ScopeMapNode{}, nodes...)
	sort.Slice(out, func(i, j int) bool { return out[i].Scope < out[j].Scope })
	return out
}

func sortedKeys[V any](m map[string]V) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
