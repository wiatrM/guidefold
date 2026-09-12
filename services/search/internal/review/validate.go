package review

import (
	"context"
	"sort"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/graph"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// The admission rules a candidate has to pass before it becomes a revision, and
// a snapshot has to pass before it becomes the head. The same function runs in
// both places on purpose: a rule that only fires at publication lets an owner
// approve something that will fail hours later, and a rule that only fires at
// approval never sees the graph a whole import produces (PIVOT-ARCHITECTURE,
// gate 3).
//
// `similar` and `conflicts_with` are deliberately absent from the cycle check.
// They are symmetric statements about two skills — "these overlap", "these
// disagree" — so a loop between them is the normal case, not a defect
// (PRODUCT-PIVOT U2.6).

// Finding is one reason a graph is not publishable.
type Finding struct {
	Code    string   `json:"code"`
	Message string   `json:"message"`
	SkillID string   `json:"skill_id,omitempty"`
	Path    []string `json:"path,omitempty"`
	Missing []string `json:"missing,omitempty"`
}

// Findings is what a validation run produces. An empty slice is a pass.
type Findings []Finding

// Err renders the first finding as the contract's 422. The others travel in
// `details.findings`, so an owner sees every problem at once rather than
// fixing them one round trip at a time.
func (f Findings) Err() error {
	if len(f) == 0 {
		return nil
	}
	first := f[0]
	details := map[string]any{}
	if len(first.Path) > 0 {
		details["path"] = first.Path
	}
	if len(first.Missing) > 0 {
		details["missing"] = first.Missing
	}
	if first.SkillID != "" {
		details["skill_id"] = first.SkillID
	}
	if len(f) > 1 {
		details["findings"] = f
	}
	e := mgmt.Unprocessable(first.Code, first.Message)
	if len(details) > 0 {
		return e.WithDetails(details)
	}
	return e
}

// Node is one skill as the validator sees it: its identity, its scope, its
// owner and the edges it declares.
type Node struct {
	SkillID  string
	Scope    string
	Owner    string
	Requires []string
	Refines  []string
	// DerivedFrom is what a consolidation owes its sources.
	DerivedFrom []string
	// Resources are the package files the revision declares.
	Resources []Resource
}

// Resource is one declared package file.
type Resource struct {
	Path      string
	SHA256    string
	Required  bool
	Available bool
}

// ValidateGraph applies every admission rule to a set of nodes.
//
// `known` names the identities the graph may point at — the snapshot's own
// skills. An edge to something outside it is `missing_dependency`, not a cycle:
// the remedy is to import or approve the dependency, not to break a loop.
func ValidateGraph(nodes []Node, known map[string]bool, scopeOwners map[string]string) Findings {
	out := Findings{}
	cards := map[string]graph.M{}
	for _, n := range nodes {
		cards[n.SkillID] = graph.M{
			"node":     scopeOrRoot(n.Scope),
			"status":   "active",
			"requires": anyList(n.Requires),
			"refines":  anyList(n.Refines),
		}
	}
	if path := graph.FindCycle(cards, "requires", "refines"); len(path) > 0 {
		out = append(out, Finding{Code: "graph_cycle",
			Message: "requires/refines must be acyclic: " + strings.Join(path, " → "),
			Path:    path})
	}
	for _, n := range nodes {
		missing := []string{}
		for _, target := range append(append([]string{}, n.Requires...), n.Refines...) {
			if target == "" || target == n.SkillID {
				continue
			}
			if !known[target] && cards[target] == nil {
				missing = append(missing, target)
			}
		}
		if len(missing) > 0 {
			out = append(out, Finding{Code: "missing_dependency",
				Message: n.SkillID + " requires skills that are not in this snapshot.",
				SkillID: n.SkillID, Missing: unique(missing)})
		}
		for _, r := range n.Resources {
			if r.Required && !r.Available {
				out = append(out, Finding{Code: "missing_required_resource",
					Message: n.SkillID + " declares a required resource whose bytes are not stored.",
					SkillID: n.SkillID, Missing: []string{r.Path}})
			}
		}
	}
	out = append(out, validateConsolidation(nodes, scopeOwners)...)
	sort.SliceStable(out, func(i, j int) bool { return codeRank(out[i].Code) < codeRank(out[j].Code) })
	return out
}

// validateConsolidation applies the two rules that only a shared element has to
// satisfy.
//
// A shared element is a claim that two or more procedures do the same thing. It
// therefore needs at least two `derived_from` sources — one source is a rename,
// not a generalisation. And when the sources sit in different scopes, the
// shared skill rises to a scope neither of them owns, which needs that scope's
// owner to be the one proposing it. Several source scopes are not by themselves
// evidence of a general rule (PRODUCT-PIVOT U2.6).
func validateConsolidation(nodes []Node, scopeOwners map[string]string) Findings {
	out := Findings{}
	byID := map[string]Node{}
	for _, n := range nodes {
		byID[n.SkillID] = n
	}
	for _, n := range nodes {
		if len(n.DerivedFrom) == 0 {
			continue
		}
		if len(unique(n.DerivedFrom)) < 2 {
			out = append(out, Finding{Code: "consolidation_sources_insufficient",
				Message: n.SkillID + " is a shared element with fewer than two derived_from sources.",
				SkillID: n.SkillID, Missing: n.DerivedFrom})
			continue
		}
		scopes := map[string]bool{}
		for _, source := range unique(n.DerivedFrom) {
			if src, ok := byID[source]; ok {
				scopes[scopeOrRoot(src.Scope)] = true
			}
		}
		if len(scopes) == 0 {
			continue
		}
		target := scopeOrRoot(n.Scope)
		raised := false
		for scope := range scopes {
			if scope != target {
				raised = true
			}
		}
		if !raised {
			continue
		}
		if len(scopes) < 2 {
			out = append(out, Finding{Code: "scope_widening_not_approved",
				Message: n.SkillID + " raises the scope on the evidence of one source scope.",
				SkillID: n.SkillID})
			continue
		}
		owner, known := scopeOwners[target]
		if !known || owner == "" || n.Owner != owner {
			out = append(out, Finding{Code: "scope_widening_not_approved",
				Message: n.SkillID + " raises the scope to " + target +
					", whose owner must be the proposal's owner.",
				SkillID: n.SkillID})
		}
	}
	return out
}

// codeRank orders findings so the most structural problem is the one the 422
// names. A cycle makes every other reading of the graph unreliable.
func codeRank(code string) int {
	switch code {
	case "graph_cycle":
		return 0
	case "missing_dependency":
		return 1
	case "missing_required_resource":
		return 2
	case "consolidation_sources_insufficient":
		return 3
	}
	return 4
}

func scopeOrRoot(scope string) string {
	if scope == "" {
		return "_root"
	}
	return scope
}

func anyList(values []string) []any {
	out := make([]any, 0, len(values))
	for _, v := range values {
		if v != "" {
			out = append(out, v)
		}
	}
	return out
}

// validateApproval checks one candidate against the graph it would join.
//
// It reads the repository's live graph and adds the candidate's own edges, so
// an approval that would close a cycle, point at a skill nobody has, or widen a
// scope without its owner is refused here rather than at publication.
func (s *Service) validateApproval(ctx context.Context, tx pgxTx, rc *repoContext,
	p *proposal, skillID string) error {
	nodes, known, e := s.repositoryNodes(ctx, tx, rc)
	if e != nil {
		return mgmt.Internal(e)
	}
	owners, e := s.scopeOwners(ctx, rc.Org.ID, rc.RepoID)
	if e != nil {
		return mgmt.Internal(e)
	}
	candidate := Node{SkillID: skillID, Scope: p.Scope, Owner: p.Owner}
	// Edges that arrive at the candidate belong to the skill they leave, not to
	// the candidate. A consolidation proposes `refines` from each source up to
	// the shared element, and unless those are attached to the source nodes the
	// cycle check would look at half the graph the approval actually creates.
	incoming := map[string][]string{}
	placeholder := "proposal:" + p.ProposalID
	rows, e := tx.Query(ctx, `SELECT type,from_skill_id,to_skill_id FROM gfm.relations
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid`, rc.Org.ID, p.ProposalID)
	if e != nil {
		return mgmt.Internal(e)
	}
	for rows.Next() {
		var kind, from, to string
		if e = rows.Scan(&kind, &from, &to); e != nil {
			rows.Close()
			return mgmt.Internal(e)
		}
		if from != placeholder {
			if kind == "refines" || kind == "requires" {
				incoming[from] = append(incoming[from], kind)
			}
			continue
		}
		switch kind {
		case "requires":
			candidate.Requires = append(candidate.Requires, to)
		case "refines":
			candidate.Refines = append(candidate.Refines, to)
		case "derived_from":
			candidate.DerivedFrom = append(candidate.DerivedFrom, to)
		}
	}
	rows.Close()
	if e = rows.Err(); e != nil {
		return mgmt.Internal(e)
	}
	replaced := false
	for i := range nodes {
		if nodes[i].SkillID == skillID {
			// An enrichment replaces the node it targets; validating both would
			// report the old edges as well as the new ones.
			nodes[i] = candidate
			replaced = true
		}
	}
	if !replaced {
		nodes = append(nodes, candidate)
	}
	for i := range nodes {
		for _, kind := range incoming[nodes[i].SkillID] {
			switch kind {
			case "refines":
				nodes[i].Refines = append(nodes[i].Refines, skillID)
			case "requires":
				nodes[i].Requires = append(nodes[i].Requires, skillID)
			}
		}
	}
	known[skillID] = true
	return ValidateGraph(nodes, known, owners).Err()
}

// repositoryNodes reads the repository's live graph: every active skill, the
// edges of its current revision, and the resources that revision declares.
func (s *Service) repositoryNodes(ctx context.Context, tx pgxTx, rc *repoContext) ([]Node, map[string]bool, error) {
	rows, e := tx.Query(ctx, `SELECT s.skill_id,s.scope,COALESCE(s.owner,''),
 COALESCE(s.current_revision_id,'') FROM gfm.skills s
 WHERE s.org_id=$1::uuid AND s.repo_id=$2 AND s.source_status='active'
 ORDER BY s.skill_id`, rc.Org.ID, rc.RepoID)
	if e != nil {
		return nil, nil, e
	}
	nodes := []Node{}
	revisions := map[string]string{}
	for rows.Next() {
		var n Node
		var revision string
		if e = rows.Scan(&n.SkillID, &n.Scope, &n.Owner, &revision); e != nil {
			rows.Close()
			return nil, nil, e
		}
		nodes = append(nodes, n)
		revisions[n.SkillID] = revision
	}
	rows.Close()
	if e = rows.Err(); e != nil {
		return nil, nil, e
	}
	known := make(map[string]bool, len(nodes))
	index := make(map[string]int, len(nodes))
	for i, n := range nodes {
		known[n.SkillID] = true
		index[n.SkillID] = i
	}
	edges, e := tx.Query(ctx, `SELECT r.from_skill_id,r.type,r.to_skill_id FROM gfm.relations r
 JOIN gfm.skills s ON s.org_id=r.org_id AND s.skill_id=r.from_skill_id
 WHERE r.org_id=$1::uuid AND s.repo_id=$2 AND r.proposal_id IS NULL
   AND (r.revision_id IS NULL OR r.revision_id=s.current_revision_id)`, rc.Org.ID, rc.RepoID)
	if e != nil {
		return nil, nil, e
	}
	for edges.Next() {
		var from, kind, to string
		if e = edges.Scan(&from, &kind, &to); e != nil {
			edges.Close()
			return nil, nil, e
		}
		i, ok := index[from]
		if !ok {
			continue
		}
		switch kind {
		case "requires":
			nodes[i].Requires = append(nodes[i].Requires, to)
		case "refines":
			nodes[i].Refines = append(nodes[i].Refines, to)
		case "derived_from":
			nodes[i].DerivedFrom = append(nodes[i].DerivedFrom, to)
		}
	}
	edges.Close()
	if e = edges.Err(); e != nil {
		return nil, nil, e
	}
	return nodes, known, nil
}
