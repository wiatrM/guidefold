package main

import (
	"context"
	"encoding/json"
	"reflect"
	"testing"
)

// The family view of 1.2: what it says, and what it must not disturb.
//
// The load-bearing test in this file is the last one. P06–P08 may enrich the
// catalog but may not move production ranking; if enriched metadata is ever to
// influence retrieval it needs its own bounded, pre-declared evaluation
// (PIVOT-BACKLOG, "Zasady prowadzenia"). So `ranked` and `cards` are compared
// element by element with and without the family decoration.

// pyramidCatalog is a three-scope family: one abstraction in the parent scope
// and two children that refine it, plus an unrelated card.
func pyramidCatalog(t *testing.T) *Catalog {
	t.Helper()
	cards := map[string]M{
		"urn:skill:m:atlas:rotate-cache": {"urn": "urn:skill:m:atlas:rotate-cache", "node": "atlas",
			"name": "rotate-cache", "description": "[atlas] Shared rotation procedure.",
			"triggers": "rotate cache generation", "status": "active"},
		"urn:skill:m:atlas.geo:rotate-tiles": {"urn": "urn:skill:m:atlas.geo:rotate-tiles",
			"node": "atlas.geo", "name": "rotate-tiles", "description": "[atlas.geo] Tile cache.",
			"triggers": "rotate tile cache", "status": "active",
			"refines": []any{"urn:skill:m:atlas:rotate-cache"}},
		"urn:skill:m:atlas.graph:rotate-links": {"urn": "urn:skill:m:atlas.graph:rotate-links",
			"node": "atlas.graph", "name": "rotate-links", "description": "[atlas.graph] Link cache.",
			"triggers": "rotate link cache", "status": "active",
			"refines": []any{"urn:skill:m:atlas:rotate-cache"}},
		"urn:skill:m:_root:unrelated": {"urn": "urn:skill:m:_root:unrelated", "node": "_root",
			"name": "unrelated", "description": "[m] Nothing to do with caches.",
			"status": "active",
			// An edge that leaves the snapshot is not a family tie.
			"refines": []any{"urn:skill:m:gone:missing"}},
	}
	c := &Catalog{ID: "fixture", Tenant: "operator", Repo: "repo", Revision: "abc",
		Nodes: M{"_root": M{"paths": []any{"**"}}, "atlas": M{"paths": []any{"platforms/atlas/**"}},
			"atlas.geo":   M{"paths": []any{"platforms/atlas/geo/**"}},
			"atlas.graph": M{"paths": []any{"platforms/atlas/graph/**"}}},
		Cards: cards,
		Revisions: map[string]string{
			"urn:skill:m:atlas:rotate-cache":       "r-parent",
			"urn:skill:m:atlas.geo:rotate-tiles":   "r-geo",
			"urn:skill:m:atlas.graph:rotate-links": "r-graph",
			"urn:skill:m:_root:unrelated":          "r-other",
		}}
	if e := c.prepare(); e != nil {
		t.Fatal(e)
	}
	return c
}

func TestFamilyReadsTheApprovedRefinesEdgesInBothDirections(t *testing.T) {
	c := pyramidCatalog(t)
	parent := c.familyFor("urn:skill:m:atlas:rotate-cache", map[string]string{
		"urn:skill:m:atlas:rotate-cache":     "abstract",
		"urn:skill:m:atlas.geo:rotate-tiles": "task",
	})
	if parent["parent"] != nil {
		t.Errorf("the abstraction has no parent, got %v", parent["parent"])
	}
	children, _ := parent["children"].([]M)
	if len(children) != 2 {
		t.Fatalf("both children must be listed, got %v", children)
	}
	// Deterministic order: a card that changes the order of its own family on
	// every request cannot be diffed or cached.
	if str(children[0]["skill_id"]) != "urn:skill:m:atlas.geo:rotate-tiles" ||
		str(children[1]["skill_id"]) != "urn:skill:m:atlas.graph:rotate-links" {
		t.Errorf("children must be in id order, got %v", children)
	}
	if str(children[0]["scope"]) != "atlas.geo" || str(children[0]["revision"]) != "r-geo" {
		t.Errorf("a child carries the scope and revision an agent would load: %v", children[0])
	}
	if children[0]["layer"] != "task" {
		t.Errorf("a known layer must be reported, got %v", children[0]["layer"])
	}
	if children[1]["layer"] != nil {
		t.Errorf("an unknown layer is null, not a guess, got %v", children[1]["layer"])
	}
	if parent["layer"] != "abstract" {
		t.Errorf("the card's own layer, got %v", parent["layer"])
	}

	child := c.familyFor("urn:skill:m:atlas.geo:rotate-tiles", map[string]string{
		"urn:skill:m:atlas:rotate-cache": "abstract"})
	p, _ := child["parent"].(M)
	if p == nil || str(p["skill_id"]) != "urn:skill:m:atlas:rotate-cache" {
		t.Fatalf("the child must name its parent, got %v", child["parent"])
	}
	if str(p["revision"]) != "r-parent" || p["layer"] != "abstract" {
		t.Errorf("the parent carries its revision and layer, got %v", p)
	}
	if kids, _ := child["children"].([]M); len(kids) != 0 {
		t.Errorf("a leaf has no children, got %v", kids)
	}
}

func TestFamilyIgnoresAnEdgeThatLeavesTheSnapshot(t *testing.T) {
	c := pyramidCatalog(t)
	f := c.familyFor("urn:skill:m:_root:unrelated", map[string]string{})
	if f["parent"] != nil {
		t.Errorf("a refines target that is not in this snapshot is not a parent, got %v", f["parent"])
	}
}

func TestFamilyChildrenAreCappedAndSayNothingAboutCompleteness(t *testing.T) {
	cards := map[string]M{"p": {"urn": "p", "node": "root", "name": "p", "description": "d",
		"status": "active"}}
	revisions := map[string]string{"p": "rp"}
	for _, id := range []string{"c01", "c02", "c03", "c04", "c05", "c06", "c07", "c08", "c09", "c10"} {
		cards[id] = M{"urn": id, "node": "root." + id, "name": id, "description": "d",
			"status": "active", "refines": []any{"p"}}
		revisions[id] = "r-" + id
	}
	c := &Catalog{ID: "f", Tenant: "operator", Repo: "repo", Nodes: M{"_root": M{"paths": []any{"**"}}},
		Cards: cards, Revisions: revisions}
	if e := c.prepare(); e != nil {
		t.Fatal(e)
	}
	kids, _ := c.familyFor("p", map[string]string{})["children"].([]M)
	if len(kids) != familyChildLimit {
		t.Fatalf("children are capped at %d, got %d", familyChildLimit, len(kids))
	}
	if str(kids[0]["skill_id"]) != "c01" || str(kids[familyChildLimit-1]["skill_id"]) != "c08" {
		t.Errorf("the cap keeps the first %d in id order, got %v", familyChildLimit, kids)
	}
	// The layer lookup must not ask for more skills than the response will show.
	ids := c.familyIDs([]string{"p"})
	if len(ids) != familyChildLimit+1 {
		t.Errorf("the layer lookup is bounded by what is rendered, got %d ids", len(ids))
	}
}

func TestFamilyDecorationLeavesRankingAndCardsBitIdentical(t *testing.T) {
	c := pyramidCatalog(t)
	build := func() ([]M, []M) {
		ranked, cards := []M{}, []M{}
		for _, u := range c.Order {
			ranked = append(ranked, c.card(u, map[string][]string{}, true))
		}
		for _, u := range c.Order[:2] {
			cards = append(cards, c.card(u, map[string][]string{}, true))
		}
		return ranked, cards
	}
	plainRanked, plainCards := build()
	before, e := json.Marshal(M{"ranked": plainRanked, "cards": plainCards})
	if e != nil {
		t.Fatal(e)
	}

	decoratedRanked, decoratedCards := build()
	store := &Store{}
	// Tenant "operator" is not a uuid, so no management catalog is read and every
	// layer is null — the shape still has to be there, and the order untouched.
	store.decorateFamily12(context.Background(), c, decoratedRanked, decoratedCards)

	if len(decoratedRanked) != len(plainRanked) || len(decoratedCards) != len(plainCards) {
		t.Fatal("decoration changed the number of cards")
	}
	for i := range decoratedRanked {
		if decoratedRanked[i]["family"] == nil {
			t.Fatalf("card %d has no family", i)
		}
		delete(decoratedRanked[i], "family")
	}
	for i := range decoratedCards {
		delete(decoratedCards[i], "family")
	}
	after, e := json.Marshal(M{"ranked": decoratedRanked, "cards": decoratedCards})
	if e != nil {
		t.Fatal(e)
	}
	if string(before) != string(after) {
		t.Fatalf("family decoration changed the 1.1 payload\nbefore: %s\nafter:  %s", before, after)
	}
	// And the order of the ids themselves, stated separately so a failure says
	// which of the two things broke.
	ids := func(list []M) []string {
		out := []string{}
		for _, card := range list {
			out = append(out, str(card["skill_id"]))
		}
		return out
	}
	plain, decorated := ids(plainRanked), ids(decoratedRanked)
	if !reflect.DeepEqual(plain, decorated) {
		t.Fatalf("ranking order moved: %v -> %v", plain, decorated)
	}
}

func TestFamilyIsNeverAddedToAnElevenResponse(t *testing.T) {
	// The guard lives in searchCatalog/decorate12: both are entered only when the
	// caller declared 1.2. This test pins the constant those guards compare, so a
	// rename cannot silently start decorating 1.1.
	if schemaVersion12 != "1.2" {
		t.Fatalf("the family guard compares against %q", schemaVersion12)
	}
}
