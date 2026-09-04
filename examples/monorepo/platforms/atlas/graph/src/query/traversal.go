// Package query implements bounded graph traversals for the link-analysis API.
package query

import (
	"context"
	"errors"
)

// TraversalLimits bounds a single traversal. Hard caps are enforced here
// regardless of what the caller requested; see the link-analysis-api skill.
type TraversalLimits struct {
	MaxDepth  int // hops from a seed, hard cap 4
	MaxFanOut int // neighbours expanded per node, hard cap 200
	MaxNodes  int // total nodes returned, hard cap 5000
}

// Truncation explains which bound stopped the traversal, if any.
type Truncation string

const (
	TruncNone   Truncation = ""
	TruncDepth  Truncation = "depth"
	TruncFanOut Truncation = "fanOut"
	TruncLimit  Truncation = "limit"
	TruncBudget Truncation = "timeBudget"
)

// Neighbours returns the ids adjacent to id over the requested edge types.
type Neighbours func(ctx context.Context, id string, edgeTypes []string) ([]string, error)

// VisitFilter reports whether the caller may read a node; unreadable nodes
// are neither returned nor expanded (RBAC runs inside the traversal).
type VisitFilter func(id string) bool

var ErrLimits = errors.New("query: traversal limits exceed hard caps")

// BoundedBFS expands seeds breadth-first with a frontier queue (never recursion).
func BoundedBFS(ctx context.Context, seeds, edgeTypes []string, lim TraversalLimits,
	next Neighbours, allowed VisitFilter) (nodes []string, trunc Truncation, err error) {
	if lim.MaxDepth > 4 || lim.MaxFanOut > 200 || lim.MaxNodes > 5000 {
		return nil, TruncNone, ErrLimits
	}
	type item struct {
		id    string
		depth int
	}
	seen := map[string]bool{}
	frontier := make([]item, 0, len(seeds))
	for _, s := range seeds {
		if allowed(s) {
			frontier = append(frontier, item{s, 0})
		}
	}
	for len(frontier) > 0 {
		if ctx.Err() != nil {
			return nodes, TruncBudget, nil
		}
		cur := frontier[0]
		frontier = frontier[1:]
		if seen[cur.id] {
			continue
		}
		seen[cur.id] = true
		nodes = append(nodes, cur.id)
		if len(nodes) >= lim.MaxNodes {
			return nodes, TruncLimit, nil
		}
		if cur.depth >= lim.MaxDepth {
			trunc = TruncDepth
			continue
		}
		adj, err := next(ctx, cur.id, edgeTypes)
		if err != nil {
			return nodes, trunc, err
		}
		if len(adj) > lim.MaxFanOut {
			adj, trunc = adj[:lim.MaxFanOut], TruncFanOut
		}
		for _, n := range adj {
			if !seen[n] && allowed(n) {
				frontier = append(frontier, item{n, cur.depth + 1})
			}
		}
	}
	return nodes, trunc, nil
}
