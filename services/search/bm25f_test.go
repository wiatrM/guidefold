package main

import (
	"os"
	"testing"
)

func TestBM25FCompiledPostingsMatchCLI(t *testing.T) {
	raw, e := os.ReadFile("testdata/bm25f.json")
	if e != nil {
		t.Fatal(e)
	}
	value, e := strictJSON(raw)
	if e != nil {
		t.Fatal(e)
	}
	fixture := obj(value)
	cli, e := os.ReadFile("../../skills/guidefold/scripts/guidefold")
	if e != nil {
		t.Fatal(e)
	}
	if str(fixture["source_cli_sha256"]) != hash(cli) {
		t.Fatal("BM25F fixture provenance stale; regenerate from CLI")
	}
	for _, group := range arr(fixture["groups"]) {
		g := obj(group)
		bundle := obj(g["bundle"])
		snapshot := obj(bundle["snapshot"])
		build := obj(bundle["router_index"])
		compiled, e := compileRouterIndex(build, obj(snapshot["cards"]), obj(snapshot["weights"]), str(bundle["sha256"]), str(snapshot["cli_sha256"]), str(bundle["router_index_sha256"]))
		if e != nil {
			t.Fatal(e)
		}
		terms := map[string][]byte{}
		for _, term := range compiled {
			terms[term.term] = term.postings
		}
		order := stringList(build["order"])
		for i, v := range arr(g["cases"]) {
			c := obj(v)
			allowed := map[string]bool{}
			for _, u := range stringList(c["allowed"]) {
				allowed[u] = true
			}
			qtf := map[string]int64{}
			for _, term := range tokens(str(c["query"])) {
				qtf[term]++
			}
			scores := map[int]int64{}
			for term, n := range qtf {
				if e = accumulatePostings(scores, terms[term], n, len(order), func(doc int) bool { return allowed[order[doc]] }); e != nil {
					t.Fatal(e)
				}
			}
			expected := obj(c["scores"])
			if len(scores) != len(expected) {
				t.Fatalf("%s case %d: candidate set size %d != %d", str(g["name"]), i, len(scores), len(expected))
			}
			for doc, got := range scores {
				want, ok := expected[order[doc]]
				if !ok || got != number(want) {
					t.Fatalf("%s case %d: %s score %d != %v", str(g["name"]), i, order[doc], got, want)
				}
			}
		}
	}
}
func TestMalformedPostingsFailClosed(t *testing.T) {
	for _, packed := range [][]byte{{1}, make([]byte, 12)} {
		if e := accumulatePostings(map[int]int64{}, packed, 1, 0, func(int) bool { return true }); e == nil {
			t.Fatal("accepted malformed posting")
		}
	}
}
