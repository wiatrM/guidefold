package main

import (
	"encoding/json"
	"fmt"
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
