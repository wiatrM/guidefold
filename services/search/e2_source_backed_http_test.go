package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// This integration replay is opt-in because the public snapshots are fetched outside the
// repository. It exercises the actual publication worker and HTTP USE path; the deterministic
// source-backed matrix remains the evaluator for the full mutation set.
func TestE2SourceBackedSnapshotsThroughHTTP(t *testing.T) {
	root := os.Getenv("GUIDEFOLD_E2_SNAPSHOTS")
	if root == "" {
		t.Skip("set GUIDEFOLD_E2_SNAPSHOTS to a verified source-disjoint snapshot replay")
	}
	e := newPubEnv(t)
	for _, target := range []struct {
		family string
		role   string
	}{
		{family: "engineering", role: "C"},
		{family: "engineering", role: "C_prime"},
		{family: "documentation", role: "C"},
		{family: "documentation", role: "C_prime"},
	} {
		sourcePath := filepath.Join(root, "snapshots", target.family, target.role+".SKILL.md")
		source, err := os.ReadFile(sourcePath)
		if err != nil {
			t.Fatalf("read %s: %v", sourcePath, err)
		}
		name := fmt.Sprintf("source-%s-%s", target.family, strings.ToLower(target.role))
		skillID := urn("_root", name)
		resourcePath := ".agents/skills/" + name + "/references/source.md"
		cardPath := ".agents/skills/" + name + "/SKILL.md"
		writeFile(t, e.tree, resourcePath, string(source))
		raw := proofSkillFile(name, "platform-engineering", skillID, hash(source))
		raw = strings.ReplaceAll(raw, "references/policy.md", "references/source.md")
		raw = strings.Replace(raw, "  layer: team\n", "  layer: team\n  references: \"references/source.md\"\n", 1)
		writeFile(t, e.tree, cardPath, raw)

		e.publishImport(t, "source-backed-"+target.family+"-"+target.role)
		snapshot := e.head(t)
		revisions := e.revisions(t, snapshot)
		revision := revisions[skillID]
		if revision == "" {
			t.Fatalf("published source-backed skill has no revision: %s", skillID)
		}
		request := fmt.Sprintf(`{"schema_version":"1.2","request_id":"req-source-%s-%s",
 "skill_id":%q,"revision":%q,"delivery_policy":"proof_gated",
 "workspace":{"repo_id":"meridian","revision":"%s","cwd":"."}}`,
			target.family, strings.ToLower(target.role), skillID, revision, fixtureCommit)
		status, out := e.post(t, "/v1/use", request)
		if status != 200 {
			t.Fatalf("source-backed use %s/%s: %d %v", target.family, target.role, status, out)
		}
		delivery := obj(out["delivery"])
		if str(delivery["action"]) != "LOAD" || str(delivery["reason"]) != "source_proof_complete" {
			t.Fatalf("source-backed proof should LOAD %s/%s: %v", target.family, target.role, delivery)
		}
		if str(out["status"]) != "hydrated" || str(out["body"]) == "" {
			t.Fatalf("source-backed proof returned no body %s/%s: %v", target.family, target.role, out)
		}
	}
}
