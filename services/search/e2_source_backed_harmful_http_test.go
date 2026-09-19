package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const e2SourceManifestSHA256 = "47a145923f1fb256a2d6c03f9a117fbbde9fe99a6ec1d0d419bc9b0c7fa1f3ec"

type e2HTTPSourceManifest struct {
	Records []struct {
		RecordID     string `json:"record_id"`
		FamilyID     string `json:"family_id"`
		Role         string `json:"role"`
		SourceSHA256 string `json:"source_sha256"`
	} `json:"records"`
}

type e2HTTPObservation struct {
	CaseID         string `json:"case_id"`
	Condition      string `json:"condition"`
	Trigger        string `json:"trigger"`
	Stage          string `json:"stage"`
	RequestBase64  string `json:"request_base64,omitempty"`
	ResponseBase64 string `json:"response_base64,omitempty"`
	HTTPStatus     int    `json:"http_status,omitempty"`
	Error          string `json:"error,omitempty"`
	Status         string `json:"status,omitempty"`
	Action         string `json:"action,omitempty"`
	Reason         string `json:"reason,omitempty"`
	BodyBytes      int    `json:"body_bytes"`
	BodySHA256     string `json:"body_sha256,omitempty"`
	ResponseSHA256 string `json:"response_sha256,omitempty"`
}

func TestE2SourceBackedHarmfulMutationsThroughHTTP(t *testing.T) {
	snapshotRoot := os.Getenv("GUIDEFOLD_E2_SNAPSHOTS")
	if snapshotRoot == "" {
		t.Skip("set GUIDEFOLD_E2_SNAPSHOTS to the hash-verified source-disjoint snapshots")
	}
	manifestPath := os.Getenv("GUIDEFOLD_E2_MANIFEST")
	if manifestPath == "" {
		manifestPath = filepath.Join("..", "..", "docs", "reports", "bakeoff", "SOURCE-DISJOINT-URCT-MANIFEST-2026-09-10.json")
	}
	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		t.Fatalf("read frozen source manifest: %v", err)
	}
	manifestDigest := sha256.Sum256(manifestBytes)
	if hex.EncodeToString(manifestDigest[:]) != e2SourceManifestSHA256 {
		t.Fatalf("source manifest hash changed: got %x want %s", manifestDigest, e2SourceManifestSHA256)
	}
	var manifest e2HTTPSourceManifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		t.Fatalf("decode frozen source manifest: %v", err)
	}
	if len(manifest.Records) != 8 {
		t.Fatalf("frozen manifest record count changed: got %d want 8", len(manifest.Records))
	}

	httpMutationKinds := []string{"conflict", "deprecated", "proof_scope", "stale_revision", "body_hash", "source_hash", "missing_source"}
	const closureMutation = "incomplete_closure"
	proofGateAskReasons := map[string]string{
		"conflict":       "proof_conflict",
		"proof_scope":    "proof_scope_incomplete",
		"body_hash":      "proof_body_hash_mismatch",
		"source_hash":    "proof_source_hash_mismatch",
		"missing_source": "proof_source_unavailable",
	}
	if len(httpMutationKinds) != 7 || len(proofGateAskReasons) != 5 {
		t.Fatalf("frozen E2 dimensions changed: http_mutations=%d proof_gate_ASK_reasons=%d", len(httpMutationKinds), len(proofGateAskReasons))
	}

	type prepared struct {
		caseID  string
		trigger string
		skillID string
		cwd     string
	}
	type closurePrepared struct {
		caseID       string
		skillID      string
		cardPath     string
		cardBody     string
		resourcePath string
		source       []byte
	}
	var cases []prepared
	var closureCases []closurePrepared
	e := newPubEnv(t)
	for _, record := range manifest.Records {
		sourcePath := filepath.Join(snapshotRoot, "snapshots", record.FamilyID, record.Role+".SKILL.md")
		source, err := os.ReadFile(sourcePath)
		if err != nil {
			t.Fatalf("read pinned source %s: %v", record.RecordID, err)
		}
		sourceDigest := sha256.Sum256(source)
		if got := hex.EncodeToString(sourceDigest[:]); got != record.SourceSHA256 {
			t.Fatalf("source hash mismatch for %s: got %s want %s", record.RecordID, got, record.SourceSHA256)
		}
		baseName := "e2-" + strings.ReplaceAll(strings.ToLower(record.RecordID), "_", "-")
		variants := []struct {
			name    string
			trigger string
			mutated bool
		}{
			{name: baseName + "-safe", trigger: "none"},
		}
		for _, mutation := range httpMutationKinds {
			name := baseName + "-" + strings.ReplaceAll(mutation, "_", "-")
			variants = append(variants, struct {
				name    string
				trigger string
				mutated bool
			}{name: name, trigger: mutation, mutated: true})
		}
		closureName := baseName + "-incomplete-closure"
		variants = append(variants, struct {
			name    string
			trigger string
			mutated bool
		}{name: closureName, trigger: closureMutation, mutated: true})

		for _, variant := range variants {
			skillNode := "_root"
			skillID := urn(skillNode, variant.name)
			cardDir := filepath.Join(".agents", "skills", variant.name)
			if skillNode != "_root" {
				cardDir = filepath.Join("platforms", "atlas", "geo", cardDir)
			}
			resource := "references/source.md"
			raw := proofSkillFile(variant.name, "platform-engineering", skillID, hex.EncodeToString(sourceDigest[:]))
			raw = strings.ReplaceAll(raw, "references/policy.md", resource)
			raw = strings.Replace(raw, "  layer: team\n", "  layer: team\n  references: \""+resource+"\"\n", 1)
			if variant.mutated {
				switch variant.trigger {
				case "conflict":
					raw = strings.Replace(raw, "source_proof:\n  schema:", "source_proof:\n  conflicts:\n    - unresolved source conflict\n  schema:", 1)
				case "deprecated":
					raw = strings.Replace(raw, "  status: active\n", "  status: deprecated\n", 1)
				case "proof_scope":
					raw = strings.Replace(raw, "  scopes:\n    - _root\n", "  scopes:\n    - atlas.geo\n", 1)
				case "body_hash":
					raw = strings.Replace(raw, "body_sha256: pending", "body_sha256: \""+strings.Repeat("0", 64)+"\"", 1)
				case "source_hash":
					wrong := sha256.Sum256([]byte("not the pinned source"))
					raw = strings.Replace(raw, hex.EncodeToString(sourceDigest[:]), hex.EncodeToString(wrong[:]), 1)
				case "missing_source":
					raw = strings.Replace(raw, "  references: \""+resource+"\"\n", "", 1)
				case "incomplete_closure":
					raw = strings.Replace(raw, "  layer: team\n", "  layer: team\n  requires: \""+urn("_root", "e2-missing-dependency")+"\"\n", 1)
				case "stale_revision":
					// The published card remains intact; the request below is stale.
				default:
					t.Fatalf("unknown frozen mutation %q", variant.trigger)
				}
			}
			cardPath := filepath.ToSlash(filepath.Join(cardDir, "SKILL.md"))
			resourcePath := filepath.ToSlash(filepath.Join(cardDir, resource))
			if variant.trigger == closureMutation {
				closureCases = append(closureCases, closurePrepared{
					caseID: variant.name, skillID: skillID, cardPath: cardPath, cardBody: raw,
					resourcePath: resourcePath, source: source,
				})
				continue
			}
			writeFile(t, e.tree, cardPath, raw)
			if variant.trigger != "missing_source" {
				writeFile(t, e.tree, resourcePath, string(source))
			}
			cases = append(cases, prepared{
				caseID: variant.name, trigger: variant.trigger, skillID: skillID, cwd: ".",
			})
		}
	}
	wantHTTPCases := len(manifest.Records) * (len(httpMutationKinds) + 1)
	if len(cases) != wantHTTPCases || len(closureCases) != len(manifest.Records) {
		t.Fatalf("prepared %d HTTP cases and %d closure cases; want %d HTTP cases and %d isolated admission cases",
			len(cases), len(closureCases), wantHTTPCases, len(manifest.Records))
	}

	e.publishImport(t, "e2-source-backed-http-crossproduct-v4-20260919")
	snapshot := e.head(t)
	if snapshot == "" {
		var state, reason string
		var validation []byte
		_ = e.h.Pool.QueryRow(context.Background(), `SELECT state,error,validation::text
 FROM gfm.publications WHERE org_id=$1::uuid ORDER BY created_at DESC LIMIT 1`, e.orgID).
			Scan(&state, &reason, &validation)
		t.Fatalf("publication did not activate a snapshot: state=%q error=%q validation=%s",
			state, reason, string(validation))
	}
	revisions := e.revisions(t, snapshot)
	var observations []e2HTTPObservation
	var violations []string
	requestNumber := 0
	for _, testCase := range cases {
		revision := revisions[testCase.skillID]
		if revision == "" && testCase.trigger != "deprecated" {
			violations = append(violations, "HTTP case was not published: "+testCase.caseID)
			for _, policy := range []string{"proof_gated", "legacy"} {
				observations = append(observations, e2HTTPObservation{
					CaseID: testCase.caseID, Condition: policy, Trigger: testCase.trigger,
					Stage: "not_published", Error: "skill revision absent from activated snapshot",
				})
			}
			continue
		}
		for _, policy := range []string{"proof_gated", "legacy"} {
			requestNumber++
			requestID := fmt.Sprintf("e2-http-v4-20260919-%03d", requestNumber)
			requestedRevision := revision
			if requestedRevision == "" && testCase.trigger == "deprecated" {
				requestedRevision = "unpublished-" + testCase.skillID
			}
			if testCase.trigger == "stale_revision" {
				requestedRevision = "stale-" + revision
			}
			request, err := json.Marshal(map[string]any{
				"schema_version": "1.2", "request_id": requestID,
				"skill_id": testCase.skillID, "revision": requestedRevision,
				"delivery_policy": policy,
				"workspace":       map[string]any{"repo_id": "meridian", "revision": fixtureCommit, "cwd": testCase.cwd},
			})
			if err != nil {
				t.Fatalf("marshal frozen request %s: %v", requestID, err)
			}
			status, wire, out, err := e.postRaw(t, "/v1/use", request)
			if err != nil {
				t.Fatalf("post %s/%s: %v", testCase.caseID, policy, err)
			}
			body := str(out["body"])
			bodyDigest := sha256.Sum256([]byte(body))
			responseDigest := sha256.Sum256(wire)
			observation := e2HTTPObservation{
				CaseID: testCase.caseID, Condition: policy, Trigger: testCase.trigger,
				Stage: "use_http", RequestBase64: base64.StdEncoding.EncodeToString(request),
				ResponseBase64: base64.StdEncoding.EncodeToString(wire), HTTPStatus: status,
				Status: str(out["status"]), BodyBytes: len([]byte(body)),
				BodySHA256: hex.EncodeToString(bodyDigest[:]), ResponseSHA256: hex.EncodeToString(responseDigest[:]),
			}
			if status != http.StatusOK {
				observation.Error = str(out["error"])
			}
			if delivery := obj(out["delivery"]); delivery != nil {
				observation.Action = str(delivery["action"])
				observation.Reason = str(delivery["reason"])
			} else if status == http.StatusOK && observation.BodyBytes > 0 {
				observation.Action = "LOAD"
			} else if status == http.StatusOK {
				observation.Action = "NO_BODY"
			}
			encoded, _ := json.Marshal(observation)
			t.Logf("E2HTTP_ROW %s", encoded)
			observations = append(observations, observation)

			if testCase.trigger == "none" {
				if status != http.StatusOK || observation.Action != "LOAD" || observation.Status != "hydrated" || observation.BodyBytes == 0 {
					violations = append(violations, "positive control failed for "+policy+": "+testCase.caseID)
				}
				if policy == "proof_gated" && observation.Reason != "source_proof_complete" {
					violations = append(violations, "proof-gated positive control had wrong reason: "+testCase.caseID)
				}
			}
			if wantReason, isProofGateMutation := proofGateAskReasons[testCase.trigger]; isProofGateMutation {
				if policy == "proof_gated" &&
					(status != http.StatusOK || observation.Action != "ASK" || observation.Status != "ask" || observation.Reason != wantReason || observation.BodyBytes != 0) {
					violations = append(violations, fmt.Sprintf("proof-gated %s mutation was not the expected body-free ASK: %s", testCase.trigger, testCase.caseID))
				}
				if policy == "legacy" &&
					(status != http.StatusOK || observation.Action != "LOAD" || observation.Status != "hydrated" || observation.BodyBytes == 0) {
					violations = append(violations, fmt.Sprintf("legacy control did not expose the expected %s body: %s", testCase.trigger, testCase.caseID))
				}
			}
			if testCase.trigger == "stale_revision" &&
				(status != http.StatusConflict || observation.Error != "revision_mismatch" || observation.BodyBytes != 0) {
				violations = append(violations, "stale revision was not denied before body delivery: "+testCase.caseID)
			}
			if testCase.trigger == "deprecated" &&
				(status != http.StatusNotFound || observation.Error != "skill_not_found" || observation.BodyBytes != 0) {
				violations = append(violations, "deprecated skill was not denied before body delivery: "+testCase.caseID)
			}
		}
	}
	safeLoads := map[string]int{}
	proofGatedAsksByTrigger := map[string]int{}
	legacyBodiesByTrigger := map[string]int{}
	proofGatedAsks, proofGatedHarmfulBodies, legacyHarmfulBodies := 0, 0, 0
	for _, observation := range observations {
		if observation.Stage != "use_http" {
			continue
		}
		if observation.Trigger == "none" && observation.Action == "LOAD" && observation.BodyBytes > 0 {
			safeLoads[observation.Condition]++
		}
		if observation.Trigger == "none" {
			continue
		}
		if observation.Condition == "proof_gated" {
			if observation.Action == "ASK" {
				proofGatedAsks++
				proofGatedAsksByTrigger[observation.Trigger]++
			}
			if observation.BodyBytes > 0 {
				proofGatedHarmfulBodies++
			}
		}
		if observation.Condition == "legacy" && observation.BodyBytes > 0 {
			legacyHarmfulBodies++
			legacyBodiesByTrigger[observation.Trigger]++
		}
	}
	wantSafeLoads := len(manifest.Records)
	wantPerGateTrigger := len(manifest.Records)
	wantGateAsks := len(proofGateAskReasons) * wantPerGateTrigger
	if safeLoads["proof_gated"] != wantSafeLoads || safeLoads["legacy"] != wantSafeLoads ||
		proofGatedAsks != wantGateAsks || proofGatedHarmfulBodies != 0 || legacyHarmfulBodies != wantGateAsks {
		violations = append(violations, fmt.Sprintf(
			"HTTP evidence counts changed: safe_gated=%d safe_legacy=%d gated_asks=%d gated_harmful_bodies=%d legacy_harmful_bodies=%d",
			safeLoads["proof_gated"], safeLoads["legacy"], proofGatedAsks, proofGatedHarmfulBodies, legacyHarmfulBodies))
	}
	for trigger := range proofGateAskReasons {
		if proofGatedAsksByTrigger[trigger] != wantPerGateTrigger || legacyBodiesByTrigger[trigger] != wantPerGateTrigger {
			violations = append(violations, fmt.Sprintf("cross-source count changed for %s: gated_asks=%d legacy_bodies=%d want=%d each",
				trigger, proofGatedAsksByTrigger[trigger], legacyBodiesByTrigger[trigger], wantPerGateTrigger))
		}
	}
	httpRows := 0
	for _, observation := range observations {
		if observation.Stage == "use_http" {
			httpRows++
		}
	}
	wantHTTPRequests := len(cases) * 2
	if requestNumber != wantHTTPRequests || httpRows != wantHTTPRequests {
		violations = append(violations, fmt.Sprintf("HTTP denominator mismatch: requests=%d logged_http_rows=%d want=%d/%d",
			requestNumber, httpRows, wantHTTPRequests, wantHTTPRequests))
	}
	closureRejected := 0
	if len(violations) == 0 {
		for _, closureCase := range closureCases {
			activeBefore := e.head(t)
			writeFile(t, e.tree, closureCase.resourcePath, string(closureCase.source))
			writeFile(t, e.tree, closureCase.cardPath, closureCase.cardBody)
			rejectedImport := e.publishImport(t, "e2-http-v4-incomplete-closure-"+closureCase.caseID+"-20260919")
			var state, reason string
			var validation []byte
			err := e.h.Pool.QueryRow(context.Background(), `SELECT state,error,validation::text
 FROM gfm.publications WHERE org_id=$1::uuid AND import_id=$2::uuid
 ORDER BY created_at DESC LIMIT 1`, e.orgID, rejectedImport).
				Scan(&state, &reason, &validation)
			activeAfter := e.head(t)
			activePreserved := activeAfter == activeBefore && activeAfter == snapshot
			validRejection := err == nil && state == "failed" && reason == "missing_dependency" &&
				strings.Contains(string(validation), "missing_dependency") && strings.Contains(string(validation), closureCase.skillID) && activePreserved
			if !validRejection {
				if err != nil {
					violations = append(violations, "could not read isolated dependency-admission result for "+closureCase.caseID+": "+err.Error())
				} else {
					violations = append(violations, fmt.Sprintf("incomplete closure was not rejected safely for %s: state=%q error=%q active_before=%s active_after=%s validation=%s",
						closureCase.caseID, state, reason, activeBefore, activeAfter, string(validation)))
				}
			} else {
				closureRejected++
			}
			t.Logf("E2HTTP_ADMISSION case_id=%s skill_id=%s state=%s error=%s active_head_preserved=%t",
				closureCase.caseID, closureCase.skillID, state, reason, activePreserved)
			for _, path := range []string{closureCase.cardPath, closureCase.resourcePath} {
				if removeErr := os.Remove(filepath.Join(e.tree, filepath.FromSlash(path))); removeErr != nil {
					violations = append(violations, "could not remove temporary closure fixture "+path+": "+removeErr.Error())
				}
			}
		}
	}
	if len(violations) == 0 && closureRejected != len(manifest.Records) {
		violations = append(violations, fmt.Sprintf("closure admission denominator mismatch: rejected=%d want=%d", closureRejected, len(manifest.Records)))
	}
	t.Logf("E2HTTP_SUMMARY rows=%d requests=%d sources=%d snapshot=%s safe_gated=%d safe_legacy=%d gated_asks=%d gated_harmful_bodies=%d legacy_harmful_bodies=%d closure_rejections=%d violations=%d",
		len(observations), requestNumber, len(manifest.Records), snapshot, safeLoads["proof_gated"], safeLoads["legacy"],
		proofGatedAsks, proofGatedHarmfulBodies, legacyHarmfulBodies, closureRejected, len(violations))
	if len(violations) > 0 {
		t.Errorf("source-backed harmful HTTP invariants failed: %s", strings.Join(violations, "; "))
	}
}

func (e *pubEnv) postRaw(t *testing.T, path string, body []byte) (int, []byte, M, error) {
	t.Helper()
	req, err := http.NewRequest(http.MethodPost, e.delivery.URL+path, bytes.NewReader(body))
	if err != nil {
		return 0, nil, nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+e.token)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return 0, nil, nil, err
	}
	defer resp.Body.Close()
	wire, err := io.ReadAll(resp.Body)
	if err != nil {
		return resp.StatusCode, nil, nil, err
	}
	var out M
	if err := json.Unmarshal(wire, &out); err != nil {
		return resp.StatusCode, wire, nil, fmt.Errorf("decode response: %w", err)
	}
	return resp.StatusCode, wire, out, nil
}
