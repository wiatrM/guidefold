package main

import (
	"fmt"
	"testing"
)

func graphCards() map[string]M {
	return map[string]M{
		"a":   {"node": "alpha", "status": "active", "requires": []any{"b", "b", "c"}, "refines": []any{"b"}},
		"b":   {"node": "_root", "status": "active", "requires": []any{"c"}},
		"c":   {"node": "_root", "status": "active"},
		"old": {"node": "_root", "status": "deprecated", "replaced_by": "b"},
	}
}

func TestGraphAdmission(t *testing.T) {
	cases := []struct {
		name string
		edit func(map[string]M)
		want string
	}{
		{"valid_diamond_duplicates_and_refines", func(c map[string]M) {}, ""},
		{"requires_missing", func(c map[string]M) { c["a"]["requires"] = []any{"missing"} }, "invalid_graph_requires_target_missing"},
		{"requires_cycle", func(c map[string]M) { c["c"]["requires"] = []any{"a"} }, "invalid_graph_requires_cycle"},
		{"requires_self", func(c map[string]M) { c["c"]["requires"] = []any{"c"} }, "invalid_graph_requires_cycle"},
		{"requires_string", func(c map[string]M) { c["a"]["requires"] = "b" }, "invalid_graph_requires_type"},
		{"requires_number", func(c map[string]M) { c["a"]["requires"] = []any{1} }, "invalid_graph_requires_type"},
		{"refines_missing", func(c map[string]M) { c["a"]["refines"] = []any{"missing"} }, "invalid_graph_refines_target_missing"},
		{"refines_cycle", func(c map[string]M) { c["b"]["refines"] = []any{"c"}; c["c"]["refines"] = []any{"b"} }, "invalid_graph_refines_cycle"},
		{"refines_deeper", func(c map[string]M) { c["c"]["refines"] = []any{"a"} }, "invalid_graph_refines_deeper_target"},
		{"replacement_missing", func(c map[string]M) { c["old"]["replaced_by"] = "missing" }, "invalid_graph_replaced_by_target_missing"},
		{"replacement_required", func(c map[string]M) { delete(c["old"], "replaced_by") }, "invalid_graph_replacement_required"},
		{"replacement_type", func(c map[string]M) { c["old"]["replaced_by"] = []any{"b"} }, "invalid_graph_replaced_by_type"},
		{"replacement_cycle", func(c map[string]M) { c["b"]["replaced_by"] = "old" }, "invalid_graph_replaced_by_cycle"},
	}
	for _, x := range cases {
		t.Run(x.name, func(t *testing.T) {
			cards := graphCards()
			x.edit(cards)
			err := validateGraph(cards)
			got := ""
			if err != nil {
				got = err.Error()
			}
			if got != x.want {
				t.Fatalf("got %q, want %q", got, x.want)
			}
		})
	}
}

func TestGraphAdmissionLongChainAndDisconnectedCycle(t *testing.T) {
	cards := make(map[string]M, 10000)
	for i := 0; i < 10000; i++ {
		card := M{"node": "_root", "status": "active"}
		if i > 0 {
			card["requires"] = []any{fmt.Sprint(i - 1)}
		}
		cards[fmt.Sprint(i)] = card
	}
	if err := validateGraph(cards); err != nil {
		t.Fatal(err)
	}
	cards["x"] = M{"node": "_root", "requires": []any{"y"}}
	cards["y"] = M{"node": "_root", "requires": []any{"x"}}
	if err := validateGraph(cards); err == nil || err.Error() != "invalid_graph_requires_cycle" {
		t.Fatal(err)
	}
}
