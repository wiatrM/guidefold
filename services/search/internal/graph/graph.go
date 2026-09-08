// Package graph holds the admission rules for a snapshot's relation graph.
//
// It was `graph_validation.go` in package main, moved here unchanged so the
// review module and the publication job apply exactly the same rules the
// operator `publish` subcommand already applied (ADR-0028). A second
// implementation of "is this graph publishable" is how a snapshot the ranker
// disagrees with gets published.
package graph

import (
	"fmt"
	"sort"
	"strings"
)

// M is one snapshot card's metadata, the shape the catalog already uses.
type M = map[string]any

// Kinds are the three edge families that must stay acyclic. `similar` and
// `conflicts_with` are deliberately absent: they are symmetric by design and
// exempt from the cycle rule (PRODUCT-PIVOT U2.6).
var Kinds = []string{"requires", "refines", "replaced_by"}

// Validate runs at publication, before any transaction or head change.
// Each authored relation must reference the same snapshot. Traversal still
// tolerates historical bad graphs; successful publication now has stricter rules.
func Validate(cards map[string]M) error {
	order := keys(cards)
	for _, kind := range Kinds {
		edges := make(map[string][]string, len(cards))
		indegree := make(map[string]int, len(cards))
		for _, u := range order {
			card := cards[u]
			targets, e := targetsOf(cards, u, kind)
			if e != nil {
				return e
			}
			for _, v := range targets {
				target, exists := cards[v]
				if !exists {
					return fmt.Errorf("invalid_graph_%s_target_missing", kind)
				}
				if kind == "refines" && depth(str(target["node"])) > depth(str(card["node"])) {
					return fmt.Errorf("invalid_graph_refines_deeper_target")
				}
				edges[u] = append(edges[u], v)
				indegree[v]++
			}
		}
		// Kahn's algorithm bounds work to O(V+E) without recursive stack growth.
		queue := make([]string, 0, len(cards))
		for _, u := range order {
			if indegree[u] == 0 {
				queue = append(queue, u)
			}
		}
		for i := 0; i < len(queue); i++ {
			for _, v := range edges[queue[i]] {
				indegree[v]--
				if indegree[v] == 0 {
					queue = append(queue, v)
				}
			}
		}
		if len(queue) != len(cards) {
			return fmt.Errorf("invalid_graph_%s_cycle", kind)
		}
	}
	return nil
}

// targetsOf reads one edge family off one card, applying the type rules that
// used to be inline in Validate.
func targetsOf(cards map[string]M, u, kind string) ([]string, error) {
	card := cards[u]
	value := card[kind]
	var raw []any
	if kind == "replaced_by" {
		if value != nil {
			target, ok := value.(string)
			if !ok || target == "" {
				return nil, fmt.Errorf("invalid_graph_%s_type", kind)
			}
			raw = []any{target}
		}
		if str(card["status"]) == "deprecated" && len(raw) == 0 {
			return nil, fmt.Errorf("invalid_graph_replacement_required")
		}
	} else if value != nil {
		list, ok := value.([]any)
		if !ok {
			return nil, fmt.Errorf("invalid_graph_%s_type", kind)
		}
		raw = list
	}
	out := make([]string, 0, len(raw))
	for _, value := range raw {
		v, ok := value.(string)
		if !ok || v == "" {
			return nil, fmt.Errorf("invalid_graph_%s_type", kind)
		}
		out = append(out, v)
	}
	return out, nil
}

// FindCycle returns one cycle over the named edge kinds as the path that closes
// it, or nil when there is none. Validate reports *that* a graph is cyclic;
// review has to tell an owner *which* skills form the loop, so the 422 body
// carries `details.path` (API-CONTRACT §3).
//
// Edges whose target is absent from the map are ignored here: a dangling edge is
// `missing_dependency`, a different answer with a different remedy.
func FindCycle(cards map[string]M, kinds ...string) []string {
	if len(kinds) == 0 {
		kinds = Kinds
	}
	edges := map[string][]string{}
	for _, u := range keys(cards) {
		for _, kind := range kinds {
			targets, e := targetsOf(cards, u, kind)
			if e != nil {
				continue
			}
			for _, v := range targets {
				if _, ok := cards[v]; ok {
					edges[u] = append(edges[u], v)
				}
			}
		}
	}
	const (
		white = 0
		grey  = 1
		black = 2
	)
	colour := map[string]int{}
	var stack []string
	var walk func(string) []string
	walk = func(u string) []string {
		colour[u] = grey
		stack = append(stack, u)
		for _, v := range edges[u] {
			switch colour[v] {
			case grey:
				for i, x := range stack {
					if x == v {
						return append(append([]string{}, stack[i:]...), v)
					}
				}
				return []string{v, v}
			case white:
				if path := walk(v); path != nil {
					return path
				}
			}
		}
		stack = stack[:len(stack)-1]
		colour[u] = black
		return nil
	}
	for _, u := range keys(cards) {
		if colour[u] == white {
			if path := walk(u); path != nil {
				return path
			}
		}
	}
	return nil
}

func str(v any) string { s, _ := v.(string); return s }

func keys[V any](m map[string]V) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func depth(node string) int {
	if node == "_root" {
		return 0
	}
	return strings.Count(node, ".") + 1
}
