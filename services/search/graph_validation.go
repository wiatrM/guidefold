package main

import "fmt"

// validateGraph runs at publication, before any transaction or head change.
// Each authored relation must reference the same snapshot. Traversal still
// tolerates historical bad graphs; successful publication now has stricter rules.
func validateGraph(cards map[string]M) error {
	order := keys(cards)
	for _, kind := range []string{"requires", "refines", "replaced_by"} {
		edges := make(map[string][]string, len(cards))
		indegree := make(map[string]int, len(cards))
		for _, u := range order {
			card := cards[u]
			var targets []any
			value := card[kind]
			if kind == "replaced_by" {
				if value != nil {
					target, ok := value.(string)
					if !ok || target == "" {
						return fmt.Errorf("invalid_graph_%s_type", kind)
					}
					targets = []any{target}
				}
				if str(card["status"]) == "deprecated" && len(targets) == 0 {
					return fmt.Errorf("invalid_graph_replacement_required")
				}
			} else if value != nil {
				var ok bool
				targets, ok = value.([]any)
				if !ok {
					return fmt.Errorf("invalid_graph_%s_type", kind)
				}
			}
			for _, value := range targets {
				v, ok := value.(string)
				if !ok || v == "" {
					return fmt.Errorf("invalid_graph_%s_type", kind)
				}
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
