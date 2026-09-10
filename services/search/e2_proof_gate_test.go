package main

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"
)

// E2 is a small, deterministic regression gate for the product's safety claim.
// It is intentionally a synthetic fixture: it verifies the service boundary,
// not user value or task success.  A future paper run must replace this matrix
// with real repository snapshots and blinded task judgements.
type e2DeliveryCase struct {
	name       string
	id         string
	requested  []string
	closure    string
	wantAction string
	wantReason string
	harmful    bool
}

func e2Card(id, name, node, status, body, snapshot string) M {
	card := M{
		"urn": id, "name": name, "node": node, "status": status, "_body": body,
	}
	card["proof"] = M{
		"schema": sourceProofSchema, "verified": true, "snapshot": snapshot,
		"skill_id": id, "revision": "pending", "body_sha256": hash([]byte(body)),
		"scopes": []any{node},
		"claims": []any{M{
			"id": "procedure", "status": "supported",
			"source_refs": []any{M{"path": "SKILL.md", "sha256": hash([]byte(body)), "line_from": json.Number("1"), "line_to": json.Number("2")}},
		}},
	}
	bindProofPlaceholders(card, snapshot)
	return card
}

func e2Catalog() *Catalog {
	snapshot := "e2-synthetic-snapshot"
	ids := []string{
		"urn:guidefold:e2:auth-v1",
		"urn:guidefold:e2:auth-v2",
		"urn:guidefold:e2:auth-deprecated",
		"urn:guidefold:e2:auth-narrow",
		"urn:guidefold:e2:db",
	}
	c := &Catalog{ID: snapshot, Cards: map[string]M{}, Revisions: map[string]string{}, RefinesParent: map[string]string{}}
	for _, id := range ids {
		node := "platform.api.auth"
		name := "auth"
		status := "active"
		switch id {
		case "urn:guidefold:e2:auth-narrow":
			node = "platform.api.auth.internal"
		case "urn:guidefold:e2:auth-deprecated":
			status = "deprecated"
		case "urn:guidefold:e2:db":
			node, name = "platform.db", "database"
		}
		body := fmt.Sprintf("# %s\nApply the %s procedure.\n", name, id)
		card := e2Card(id, name, node, status, body, snapshot)
		c.Cards[id] = card
		c.Revisions[id] = str(obj(card["proof"])["revision"])
	}
	// v1 and v2 occupy the same effective family. The older copy carries an
	// explicit publisher conflict, which must fail closed if a flat retriever
	// selects it.
	obj(c.Cards[ids[0]]["proof"])["conflicts"] = []any{"superseded by urn:guidefold:e2:auth-v2"}
	return c
}

// e2Delivery mirrors the checks performed by the 1.2 USE path before it calls
// proofGate. Keeping this helper in the test makes the expected safety policy
// explicit while proofGate itself remains the production implementation under
// test.
func e2Delivery(c *Catalog, id, body, revision string, scopes []string, closure string) M {
	card, ok := c.Cards[id]
	if !ok {
		return M{"action": "ASK", "reason": "skill_not_found"}
	}
	if revision != c.Revisions[id] {
		return M{"action": "ASK", "reason": "revision_mismatch"}
	}
	if str(card["status"]) != "active" {
		return M{"action": "ASK", "reason": "skill_not_active"}
	}
	if len(scopes) == 0 || !proofScopeCovers([]string{str(card["node"])}, scopes) {
		return M{"action": "ASK", "reason": "skill_outside_resolved_scope"}
	}
	return proofGate(c, id, body, scopes, closure)
}

func TestE2ProofGatedDeliveryMatrix(t *testing.T) {
	c := e2Catalog()
	v1 := "urn:guidefold:e2:auth-v1"
	v2 := "urn:guidefold:e2:auth-v2"
	narrow := "urn:guidefold:e2:auth-narrow"
	cases := []e2DeliveryCase{
		{name: "current version loads", id: v2, requested: []string{"platform.api.auth"}, closure: "complete", wantAction: "LOAD", wantReason: "source_proof_complete"},
		{name: "conflicting sibling asks", id: v1, requested: []string{"platform.api.auth"}, closure: "complete", wantAction: "ASK", wantReason: "proof_conflict", harmful: true},
		{name: "deprecated sibling is never loaded", id: "urn:guidefold:e2:auth-deprecated", requested: []string{"platform.api.auth"}, closure: "complete", wantAction: "ASK", wantReason: "skill_not_active", harmful: true},
		{name: "narrow child is accepted only in its scope", id: narrow, requested: []string{"platform.api.auth.internal"}, closure: "complete", wantAction: "LOAD", wantReason: "source_proof_complete"},
		{name: "narrow child is rejected outside its scope", id: narrow, requested: []string{"platform.db"}, closure: "complete", wantAction: "ASK", wantReason: "skill_outside_resolved_scope", harmful: true},
		{name: "published revision drift asks", id: v2, requested: []string{"platform.api.auth"}, closure: "complete", wantAction: "ASK", wantReason: "revision_mismatch", harmful: true},
		{name: "body tamper asks", id: v2, requested: []string{"platform.api.auth"}, closure: "complete", wantAction: "ASK", wantReason: "proof_body_hash_mismatch", harmful: true},
		{name: "incomplete closure asks", id: v2, requested: []string{"platform.api.auth"}, closure: "incomplete", wantAction: "ASK", wantReason: "closure_incomplete", harmful: true},
	}

	flatHarmful, gatedHarmful := 0, 0
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			card := c.Cards[tc.id]
			body := str(card["_body"])
			revision := c.Revisions[tc.id]
			switch tc.wantReason {
			case "revision_mismatch":
				revision = "stale-revision"
			case "proof_body_hash_mismatch":
				body = body + "tampered\n"
			}
			decision := e2Delivery(c, tc.id, body, revision, tc.requested, tc.closure)
			if str(decision["action"]) != tc.wantAction || str(decision["reason"]) != tc.wantReason {
				t.Fatalf("got %s/%s, want %s/%s", str(decision["action"]), str(decision["reason"]), tc.wantAction, tc.wantReason)
			}
			// A flat retriever exposes the selected body even when it is stale,
			// deprecated, conflicting or outside the request scope. This is the
			// harmful-load control that the proof-gated arm must drive to zero.
			if tc.harmful {
				flatHarmful++
				if str(decision["action"]) == "LOAD" {
					t.Fatalf("harmful case unexpectedly loaded: %v", decision)
				}
			}
			if str(decision["action"]) == "LOAD" && tc.harmful {
				gatedHarmful++
			}
		})
	}
	if flatHarmful != 6 || gatedHarmful != 0 {
		t.Fatalf("E2 safety summary: flat harmful=%d, proof-gated harmful=%d", flatHarmful, gatedHarmful)
	}
}

type e2ArmResult struct {
	name         string
	selected     []string
	harmfulLoads int
	askCount     int
}

func e2VisibleInScope(c *Catalog, id, requested string) bool {
	node := str(c.Cards[id]["node"])
	return node == requested || strings.HasPrefix(node, requested+".") || strings.HasPrefix(requested, node+".")
}

func e2HarmfulCandidate(c *Catalog, id, requested string) bool {
	card := c.Cards[id]
	if card == nil || str(card["status"]) != "active" || !e2VisibleInScope(c, id, requested) {
		return true
	}
	proof := obj(card["proof"])
	conflicts, _ := proof["conflicts"].([]any)
	return len(conflicts) > 0
}

func e2RunArm(c *Catalog, name string, selected []string, gated, evolved bool) e2ArmResult {
	result := e2ArmResult{name: name, selected: selected}
	requested := "platform.api.auth"
	for _, id := range selected {
		if !gated {
			if e2HarmfulCandidate(c, id, requested) {
				result.harmfulLoads++
			}
			continue
		}
		if evolved && id == "urn:guidefold:e2:auth-v1" {
			// Evolution replaces the stale map pointer with the current sibling
			// before delivery. The old pointer is never silently hydrated.
			id = "urn:guidefold:e2:auth-v2"
		}
		card := c.Cards[id]
		if card == nil {
			result.askCount++
			continue
		}
		body := str(card["_body"])
		decision := e2Delivery(c, id, body, c.Revisions[id], []string{requested}, "complete")
		if str(decision["action"]) == "LOAD" {
			if e2HarmfulCandidate(c, id, requested) {
				result.harmfulLoads++
			}
		} else {
			result.askCount++
		}
	}
	return result
}

func TestE2AblationArmsKeepTheSafetyBoundaryVisible(t *testing.T) {
	c := e2Catalog()
	v1 := "urn:guidefold:e2:auth-v1"
	v2 := "urn:guidefold:e2:auth-v2"
	deprecated := "urn:guidefold:e2:auth-deprecated"
	narrow := "urn:guidefold:e2:auth-narrow"
	db := "urn:guidefold:e2:db"
	// Every arm receives the same snapshot and candidate pool. Only the
	// selection policy and proof gate differ; there are no model calls.
	arms := []e2ArmResult{
		e2RunArm(c, "flat", []string{v1, v2, deprecated, narrow, db}, false, false),
		e2RunArm(c, "navigate", []string{v1, v2}, false, false),
		e2RunArm(c, "graph", []string{v1, v2, deprecated, narrow, db}, false, false),
		e2RunArm(c, "map", []string{v1}, false, false),
		e2RunArm(c, "map+gate", []string{v1}, true, false),
		e2RunArm(c, "map+gate+evolution", []string{v1}, true, true),
	}
	wantHarmful := map[string]int{"flat": 3, "navigate": 1, "graph": 3, "map": 1, "map+gate": 0, "map+gate+evolution": 0}
	wantASK := map[string]int{"map+gate": 1, "map+gate+evolution": 0}
	for _, arm := range arms {
		if arm.harmfulLoads != wantHarmful[arm.name] {
			t.Errorf("%s harmful loads=%d, want %d", arm.name, arm.harmfulLoads, wantHarmful[arm.name])
		}
		if expected, ok := wantASK[arm.name]; ok && arm.askCount != expected {
			t.Errorf("%s ASK count=%d, want %d", arm.name, arm.askCount, expected)
		}
	}
	if arms[4].harmfulLoads != 0 || arms[5].harmfulLoads != 0 {
		t.Fatal("proof-gated arms must have zero harmful body deliveries")
	}
}

func TestE2TransferAndDriftFailClosed(t *testing.T) {
	const v2 = "urn:guidefold:e2:auth-v2"
	const v1 = "urn:guidefold:e2:auth-v1"
	t.Run("scope transfer", func(t *testing.T) {
		c := e2Catalog()
		card := c.Cards[v2]
		card["node"] = "platform.api.identity"
		decision := e2Delivery(c, v2, str(card["_body"]), c.Revisions[v2], []string{"platform.api.auth"}, "complete")
		if str(decision["action"]) != "ASK" || str(decision["reason"]) != "skill_outside_resolved_scope" {
			t.Fatalf("a moved card must not cross its old scope: %v", decision)
		}
	})
	t.Run("status becomes deprecated", func(t *testing.T) {
		c := e2Catalog()
		c.Cards[v2]["status"] = "deprecated"
		decision := e2Delivery(c, v2, str(c.Cards[v2]["_body"]), c.Revisions[v2], []string{"platform.api.auth"}, "complete")
		if str(decision["action"]) != "ASK" || str(decision["reason"]) != "skill_not_active" {
			t.Fatalf("a newly deprecated card must not load: %v", decision)
		}
	})
	t.Run("map points at old revision after publication", func(t *testing.T) {
		c := e2Catalog()
		oldRevision := c.Revisions[v2]
		c.Revisions[v2] = "published-revision-2"
		decision := e2Delivery(c, v2, str(c.Cards[v2]["_body"]), oldRevision, []string{"platform.api.auth"}, "complete")
		if str(decision["action"]) != "ASK" || str(decision["reason"]) != "revision_mismatch" {
			t.Fatalf("a stale map pointer must not load: %v", decision)
		}
	})
	t.Run("evolution replaces stale sibling pointer", func(t *testing.T) {
		c := e2Catalog()
		result := e2RunArm(c, "map+gate+evolution", []string{v1}, true, true)
		if result.harmfulLoads != 0 || result.askCount != 0 || len(result.selected) != 1 {
			t.Fatalf("evolution should replace the stale pointer before delivery: %+v", result)
		}
	})
}
