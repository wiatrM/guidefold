package main

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"
)

func proofFixture() (*Catalog, string, []string) {
	id := "urn:guidefold:proof:demo"
	body := "# Source-grounded procedure\nRun the verifier.\n"
	bodySHA := hash([]byte(body))
	c := &Catalog{
		ID:        "snapshot-proof-1",
		Revisions: map[string]string{id: "revision-proof-1"},
		Cards:     map[string]M{},
	}
	c.Cards[id] = M{
		"_body": body,
		"proof": M{
			"schema":      sourceProofSchema,
			"verified":    true,
			"snapshot":    c.ID,
			"skill_id":    id,
			"revision":    c.Revisions[id],
			"body_sha256": bodySHA,
			"scopes":      []any{"platform.api"},
			"claims": []any{M{
				"id":     "operation",
				"status": "supported",
				"source_refs": []any{M{
					"path":      "docs/runbook.md",
					"sha256":    bodySHA,
					"line_from": json.Number("1"),
					"line_to":   json.Number("2"),
				}},
			}},
		},
	}
	return c, id, []string{"platform.api"}
}

func TestProofGateLoadsOnlyACompleteProof(t *testing.T) {
	c, id, scopes := proofFixture()
	decision := proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "complete")
	if str(decision["action"]) != "LOAD" || str(decision["reason"]) != "source_proof_complete" {
		t.Fatalf("expected source-grounded LOAD, got %v", decision)
	}
	if len(decision["missing"].([]M)) != 0 {
		t.Fatalf("a complete proof must have no missing requirements: %v", decision)
	}
	provenance := obj(decision["provenance"])
	if str(provenance["schema"]) != sourceProofSchema || len(provenance["claims"].([]M)) != 1 {
		t.Fatalf("proof provenance was not preserved: %v", provenance)
	}
}

func TestProofGateAsksWhenProofIsAbsent(t *testing.T) {
	c, id, scopes := proofFixture()
	delete(c.Cards[id], "proof")
	decision := proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "complete")
	if str(decision["action"]) != "ASK" || str(decision["reason"]) != "proof_missing" {
		t.Fatalf("missing proof must abstain: %v", decision)
	}
}

func TestProofGateRejectsIdentityBodyScopeAndClosureDrift(t *testing.T) {
	c, id, scopes := proofFixture()
	c.Cards[id]["proof"].(M)["skill_id"] = "urn:guidefold:proof:other"
	decision := proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "complete")
	if str(decision["reason"]) != "proof_identity_mismatch" {
		t.Fatalf("identity drift must abstain: %v", decision)
	}
	c, id, scopes = proofFixture()
	decision = proofGate(c, id, "tampered\n", scopes, "complete")
	if str(decision["reason"]) != "proof_body_hash_mismatch" {
		t.Fatalf("body drift must abstain: %v", decision)
	}
	c, id, scopes = proofFixture()
	decision = proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", []string{"other.scope"}, "complete")
	if str(decision["reason"]) != "proof_scope_incomplete" {
		t.Fatalf("scope drift must abstain: %v", decision)
	}
	c, id, scopes = proofFixture()
	decision = proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "unresolved")
	if str(decision["reason"]) != "closure_incomplete" {
		t.Fatalf("closure drift must abstain: %v", decision)
	}
}

func TestProofGateRejectsPartialClaimsAndConflicts(t *testing.T) {
	c, id, scopes := proofFixture()
	proof := c.Cards[id]["proof"].(M)
	proof["claims"] = []any{M{"id": "operation", "status": "partial", "source_refs": []any{}}}
	decision := proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "complete")
	if str(decision["reason"]) != "proof_claim_incomplete" {
		t.Fatalf("partial claim must abstain: %v", decision)
	}
	c, id, scopes = proofFixture()
	c.Cards[id]["proof"].(M)["conflicts"] = []any{"sibling disagreement"}
	decision = proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "complete")
	if str(decision["reason"]) != "proof_conflict" {
		t.Fatalf("conflicting proof must abstain: %v", decision)
	}
}

func TestProofGateRejectsMalformedNilClaimWithoutPanic(t *testing.T) {
	c, id, scopes := proofFixture()
	c.Cards[id]["proof"].(M)["claims"] = []any{nil}
	decision := proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "complete")
	if str(decision["action"]) != "ASK" || str(decision["reason"]) != "proof_claim_incomplete" {
		t.Fatalf("a malformed nil claim must abstain: %v", decision)
	}
}

func TestProofGateRejectsInvalidSourceLineReference(t *testing.T) {
	c, id, scopes := proofFixture()
	claim := c.Cards[id]["proof"].(M)["claims"].([]any)[0].(M)
	claim["source_refs"] = []any{M{
		"path":      "docs/runbook.md",
		"sha256":    "not-a-digest",
		"line_from": json.Number("3"),
		"line_to":   json.Number("2"),
	}}
	decision := proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "complete")
	if str(decision["reason"]) != "proof_source_ref_invalid" {
		t.Fatalf("invalid source reference must abstain: %v", decision)
	}
}

func TestCardRevisionIgnoresPublisherBoundProof(t *testing.T) {
	card := M{
		"urn":   "urn:guidefold:proof:demo",
		"node":  "platform.api",
		"name":  "demo",
		"_body": "procedure\n",
	}
	withoutProof := cardRevision(card)
	card["proof"] = M{"snapshot": "pending", "revision": "pending"}
	withProof := cardRevision(card)
	if withoutProof != withProof {
		t.Fatalf("publisher-bound proof changed the card revision: %s != %s", withoutProof, withProof)
	}
}

func TestBindProofPlaceholdersIsDeterministicAndDoesNotVerify(t *testing.T) {
	card := M{
		"urn":   "urn:guidefold:proof:demo",
		"node":  "platform.api",
		"name":  "demo",
		"_body": "procedure\n",
		"proof": M{
			"schema":      sourceProofSchema,
			"verified":    false,
			"snapshot":    "pending",
			"revision":    "pending",
			"body_sha256": "pending",
		},
	}
	bindProofPlaceholders(card, "repository:snapshot")
	proof := obj(card["proof"])
	if str(proof["snapshot"]) != "repository:snapshot" || str(proof["revision"]) != cardRevision(card) {
		t.Fatalf("placeholders were not bound: %v", proof)
	}
	if str(proof["body_sha256"]) != hash([]byte("procedure\n")) {
		t.Fatalf("body hash was not bound: %v", proof)
	}
	if proof["verified"] != false {
		t.Fatal("binding must never upgrade an unverified proof")
	}
}

func TestBindProofPlaceholdersDoesNotRepairMalformedFields(t *testing.T) {
	for _, tc := range []struct {
		name, field string
		value       any
		reason      string
	}{
		{name: "numeric body hash", field: "body_sha256", value: 0, reason: "proof_body_hash_mismatch"},
		{name: "empty body hash", field: "body_sha256", value: "", reason: "proof_body_hash_mismatch"},
		{name: "numeric snapshot", field: "snapshot", value: 0, reason: "proof_snapshot_mismatch"},
		{name: "numeric revision", field: "revision", value: 0, reason: "proof_revision_mismatch"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			c, id, scopes := proofFixture()
			proof := c.Cards[id]["proof"].(M)
			proof[tc.field] = tc.value

			bindProofPlaceholders(c.Cards[id], c.ID)
			if got := proof[tc.field]; got != tc.value {
				t.Fatalf("publisher rewrote malformed %s: got %#v want %#v", tc.field, got, tc.value)
			}
			decision := proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "complete")
			if str(decision["action"]) != "ASK" || str(decision["reason"]) != tc.reason {
				t.Fatalf("malformed %s must fail closed after binding: %v", tc.field, decision)
			}
		})
	}
}

func FuzzBindProofPlaceholdersOnlyBindsExactPendingString(f *testing.F) {
	for _, raw := range []string{
		`"pending"`, `""`, `" "`, `"pending "`, `"0"`, `0`, `false`, `null`, `[]`, `{}`,
		`1.25`, `"0000000000000000000000000000000000000000000000000000000000000000"`,
	} {
		for fieldIndex := uint8(0); fieldIndex < 3; fieldIndex++ {
			f.Add(raw, fieldIndex)
		}
	}
	f.Fuzz(func(t *testing.T, raw string, fieldIndex uint8) {
		if len(raw) > 4096 {
			t.Skip()
		}
		var original, value any
		if err := json.Unmarshal([]byte(raw), &original); err != nil {
			return
		}
		if err := json.Unmarshal([]byte(raw), &value); err != nil {
			return
		}

		c, id, _ := proofFixture()
		proof := c.Cards[id]["proof"].(M)
		fields := []string{"snapshot", "revision", "body_sha256"}
		field := fields[int(fieldIndex)%len(fields)]
		proof[field] = value
		proof["verified"] = false

		expected := original
		if placeholder, ok := value.(string); ok && placeholder == "pending" {
			switch field {
			case "snapshot":
				expected = c.ID
			case "revision":
				expected = cardRevision(c.Cards[id])
			case "body_sha256":
				expected = hash([]byte(str(c.Cards[id]["_body"])))
			}
		}

		bindProofPlaceholders(c.Cards[id], c.ID)
		if !reflect.DeepEqual(proof[field], expected) {
			t.Fatalf("binder changed %s unexpectedly: got %#v want %#v (input %s)", field, proof[field], expected, raw)
		}
		if proof["verified"] != false {
			t.Fatal("placeholder binding must never upgrade the verification flag")
		}
	})
}

func TestBoundProofPassesTheDeliveryGate(t *testing.T) {
	c, id, scopes := proofFixture()
	proof := c.Cards[id]["proof"].(M)
	proof["snapshot"], proof["revision"], proof["body_sha256"] = "pending", "pending", "pending"
	bindProofPlaceholders(c.Cards[id], c.ID)
	// Publisher binding derives the proof revision from the card identity. Keep
	// the catalog's published revision in sync with that deterministic value.
	c.Revisions[id] = str(proof["revision"])
	decision := proofGate(c, id, "# Source-grounded procedure\nRun the verifier.\n", scopes, "complete")
	if str(decision["action"]) != "LOAD" {
		t.Fatalf("a verified proof with publisher bindings must load: %v", decision)
	}
}

func TestProofGateVerifiesRecursiveChildClaimCommitment(t *testing.T) {
	parentID := "urn:guidefold:proof:parent"
	childID := "urn:guidefold:proof:child"
	parentBody := "# Abstract\nUse the child operation.\n"
	childBody := "# Child\nRun the operation.\n"
	c := &Catalog{
		ID:            "snapshot-proof-recursive",
		Cards:         map[string]M{},
		Revisions:     map[string]string{parentID: "parent-revision", childID: "child-revision"},
		RefinesParent: map[string]string{childID: parentID},
	}
	childClaim := M{
		"id":     "operation",
		"status": "supported",
		"source_refs": []any{M{
			"path": "SKILL.md", "sha256": hash([]byte(childBody)),
			"line_from": int64(1), "line_to": int64(2),
		}},
	}
	childProof := M{
		"schema": sourceProofSchema, "verified": true, "snapshot": c.ID,
		"skill_id": childID, "revision": c.Revisions[childID],
		"body_sha256": hash([]byte(childBody)), "scopes": []any{"platform.api"},
		"claims": []any{childClaim},
	}
	childDigest, ok := proofClaimDigest(childClaim)
	if !ok {
		t.Fatal("child claim digest")
	}
	childCommitment, ok := proofCommitment(childProof)
	if !ok {
		t.Fatal("child commitment")
	}
	parentClaim := M{
		"id": "abstract-operation", "status": "supported",
		"claim_refs": []any{M{
			"skill_id": childID, "revision": c.Revisions[childID], "claim_id": "operation",
			"claim_digest": childDigest, "commitment": childCommitment,
		}},
	}
	c.Cards[parentID] = M{
		"urn": parentID, "node": "_root", "status": "active", "_body": parentBody,
		"proof": M{
			"schema": sourceProofSchema, "verified": true, "snapshot": c.ID,
			"skill_id": parentID, "revision": c.Revisions[parentID],
			"body_sha256": hash([]byte(parentBody)), "scopes": []any{"platform.api"},
			"claims": []any{parentClaim},
		},
	}
	c.Cards[childID] = M{"urn": childID, "node": "platform.api", "status": "active", "_body": childBody, "proof": childProof}
	decision := proofGate(c, parentID, parentBody, []string{"platform.api"}, "complete")
	if str(decision["action"]) != "LOAD" {
		t.Fatalf("a fresh recursive proof must load: %v", decision)
	}
	parentClaim["claim_refs"].([]any)[0].(M)["commitment"] = strings.Repeat("0", 64)
	decision = proofGate(c, parentID, parentBody, []string{"platform.api"}, "complete")
	if str(decision["action"]) != "ASK" || str(decision["reason"]) != "proof_recursive_invalid" {
		t.Fatalf("a child commitment mutation must ask: %v", decision)
	}
}

func TestProofCommitmentRejectsDuplicateClaimIDs(t *testing.T) {
	claim := M{
		"id": "same-claim", "status": "supported",
		"source_refs": []any{M{
			"path": "docs/runbook.md", "sha256": strings.Repeat("a", 64),
			"line_from": int64(1), "line_to": int64(1),
		}},
	}
	if _, ok := proofCommitment(M{"claims": []any{claim, claim}}); ok {
		t.Fatal("a proof commitment must not make duplicate claim IDs appear unambiguous")
	}
}
