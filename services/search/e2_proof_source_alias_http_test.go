package main

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"
)

func proofSkillWithClaims(name, skillID, claims string) string {
	raw := skillFile(name, "platform-engineering", nil, "Read the cited policy before using this procedure.")
	raw = strings.Replace(raw, "  layer: team\n", "  layer: team\n  references: \"references/valid.md\"\n", 1)
	proof := fmt.Sprintf("source_proof:\n  schema: source-proof-v1\n  verified: true\n  snapshot: pending\n  skill_id: %s\n  revision: pending\n  body_sha256: pending\n  scopes:\n    - _root\n  claims:\n%s", skillID, claims)
	return strings.Replace(raw, "---\n\n# "+name, proof+"---\n\n# "+name, 1)
}

func TestE2ProofSourceRejectsDuplicateClaimIDsAndPathCacheAliases(t *testing.T) {
	e := newPubEnv(t)
	source := "# Policy\nOnly the published source path may satisfy this reference.\n"
	sourceSHA := hash([]byte(source))
	cases := []struct {
		name       string
		claims     string
		wantAction string
	}{
		{
			name: "duplicate-claim-id",
			claims: fmt.Sprintf("    - id: same-id\n      status: supported\n      source_refs:\n"+
				"        - path: references/valid.md\n          sha256: %s\n          line_from: 1\n          line_to: 2\n"+
				"    - id: same-id\n      status: supported\n      source_refs:\n"+
				"        - path: references/missing.md\n          sha256: %s\n          line_from: 1\n          line_to: 2\n", sourceSHA, sourceSHA),
		},
		{
			name: "same-digest-different-path",
			claims: fmt.Sprintf("    - id: first-claim\n      status: supported\n      source_refs:\n"+
				"        - path: references/valid.md\n          sha256: %s\n          line_from: 1\n          line_to: 2\n"+
				"    - id: second-claim\n      status: supported\n      source_refs:\n"+
				"        - path: references/missing.md\n          sha256: %s\n          line_from: 1\n          line_to: 2\n", sourceSHA, sourceSHA),
		},
		{
			name: "same-digest-same-path-positive",
			claims: fmt.Sprintf("    - id: first-claim\n      status: supported\n      source_refs:\n"+
				"        - path: references/valid.md\n          sha256: %s\n          line_from: 1\n          line_to: 2\n"+
				"    - id: second-claim\n      status: supported\n      source_refs:\n"+
				"        - path: references/valid.md\n          sha256: %s\n          line_from: 1\n          line_to: 2\n", sourceSHA, sourceSHA),
			wantAction: "LOAD",
		},
	}
	for _, tc := range cases {
		id := urn("_root", tc.name)
		writeFile(t, e.tree, ".agents/skills/"+tc.name+"/SKILL.md",
			proofSkillWithClaims(tc.name, id, tc.claims))
		writeFile(t, e.tree, ".agents/skills/"+tc.name+"/references/valid.md", source)
	}
	e.publishImport(t, "proof-source-alias-regression-20260919")
	revisions := e.revisions(t, e.head(t))
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			id := urn("_root", tc.name)
			request, err := json.Marshal(M{
				"schema_version":  "1.2",
				"request_id":      "proof-source-alias-" + tc.name,
				"skill_id":        id,
				"revision":        revisions[id],
				"delivery_policy": "proof_gated",
				"workspace": M{
					"repo_id": "meridian", "revision": fixtureCommit, "cwd": ".",
				},
			})
			if err != nil {
				t.Fatal(err)
			}
			status, response := e.post(t, "/v1/use", string(request))
			if status != 200 {
				t.Fatalf("USE returned HTTP %d: %v", status, response)
			}
			delivery := obj(response["delivery"])
			wantAction := tc.wantAction
			if wantAction == "" {
				wantAction = "ASK"
			}
			if str(delivery["action"]) != wantAction {
				t.Fatalf("malformed source proof unexpectedly delivered: %v", response)
			}
			body := str(response["body"])
			if wantAction == "ASK" && body != "" {
				t.Fatalf("ASK response exposed %d body bytes", len([]byte(body)))
			}
			if wantAction == "LOAD" && body == "" {
				t.Fatal("valid same-path source reuse unexpectedly withheld the body")
			}
		})
	}
}
