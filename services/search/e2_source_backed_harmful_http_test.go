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

	mutations := map[string]string{
		"engineering-A":         "conflict",
		"engineering-B":         "deprecated",
		"engineering-C":         "proof_scope",
		"engineering-C_prime":   "stale_revision",
		"documentation-A":       "body_hash",
		"documentation-B":       "source_hash",
		"documentation-C":       "missing_source",
		"documentation-C_prime": "incomplete_closure",
	}
	if len(mutations) != 8 {
		t.Fatal("the frozen mutation assignment must contain eight unique records")
	}

	type prepared struct {
		caseID   string
		trigger  string
		skillID  string
		revision string
		cwd      string
	}
	var cases []prepared
	var incompleteClosurePath, incompleteClosureBody, incompleteClosureResourcePath string
	var incompleteClosureSource []byte
	e := newPubEnv(t)
	for _, record := range manifest.Records {
		mutation, ok := mutations[record.RecordID]
		if !ok {
			t.Fatalf("no frozen mutation assigned to source record %s", record.RecordID)
		}
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
		harmfulCWD := "."

		// Each source has a positive control and a single, preassigned fault variant.
		for _, variant := range []struct {
			name    string
			trigger string
			mutated bool
		}{
			{name: baseName + "-safe", trigger: "none"},
			{name: baseName + "-mutated", trigger: mutation, mutated: true},
		} {
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
				switch mutation {
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
					t.Fatalf("unknown frozen mutation %q", mutation)
				}
			}
			if variant.mutated && mutation == "incomplete_closure" {
				incompleteClosurePath = filepath.ToSlash(filepath.Join(cardDir, "SKILL.md"))
				incompleteClosureBody = raw
				incompleteClosureResourcePath = filepath.ToSlash(filepath.Join(cardDir, resource))
				incompleteClosureSource = source
				continue
			}
			writeFile(t, e.tree, filepath.ToSlash(filepath.Join(cardDir, "SKILL.md")), raw)
			if !(variant.mutated && mutation == "missing_source") {
				writeFile(t, e.tree, filepath.ToSlash(filepath.Join(cardDir, resource)), string(source))
			}
			cases = append(cases, prepared{
				caseID: variant.name, trigger: variant.trigger, skillID: skillID, cwd: harmfulCWD,
			})
		}
	}
	if len(cases) != 15 || incompleteClosurePath == "" || incompleteClosureBody == "" || incompleteClosureResourcePath == "" || len(incompleteClosureSource) == 0 {
		t.Fatalf("prepared %d HTTP cases and missing_closure=%t; want 15 HTTP cases plus one isolated admission case",
			len(cases), incompleteClosurePath != "" && incompleteClosureBody != "" && incompleteClosureResourcePath != "" && len(incompleteClosureSource) > 0)
	}

	e.publishImport(t, "e2-source-backed-http-matrix-v3-20260919")
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
			requestID := fmt.Sprintf("e2-http-v3-20260919-%03d", requestNumber)
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

			if testCase.trigger == "none" && policy == "proof_gated" {
				if status != http.StatusOK || observation.Action != "LOAD" || observation.Reason != "source_proof_complete" || observation.Status != "hydrated" || observation.BodyBytes == 0 {
					violations = append(violations, "positive control failed: "+testCase.caseID)
				}
			}
			if testCase.trigger != "none" && policy == "proof_gated" && observation.BodyBytes != 0 {
				violations = append(violations, "harmful proof-gated request returned body: "+testCase.caseID)
			}
			if testCase.trigger != "none" && policy == "proof_gated" &&
				(testCase.trigger == "conflict" || testCase.trigger == "proof_scope" || testCase.trigger == "body_hash" || testCase.trigger == "source_hash" || testCase.trigger == "missing_source") &&
				(status != http.StatusOK || observation.Action != "ASK") {
				violations = append(violations, "proof-gate trigger did not return HTTP ASK: "+testCase.caseID)
			}
			deprecatedDenied := status == http.StatusNotFound && observation.Error == "skill_not_found" ||
				status == http.StatusConflict && (observation.Error == "skill_not_active" || observation.Error == "revision_mismatch")
			if testCase.trigger == "deprecated" && (!deprecatedDenied || observation.BodyBytes != 0) {
				violations = append(violations, "deprecated skill was not denied before body delivery: "+testCase.caseID)
			}
		}
	}
	httpRows := 0
	for _, observation := range observations {
		if observation.Stage == "use_http" {
			httpRows++
		}
	}
	if requestNumber != 30 || httpRows != 30 {
		violations = append(violations, fmt.Sprintf("HTTP denominator mismatch: requests=%d logged_http_rows=%d want=30/30",
			requestNumber, httpRows))
	}
	if len(violations) == 0 {
		writeFile(t, e.tree, incompleteClosureResourcePath, string(incompleteClosureSource))
		writeFile(t, e.tree, incompleteClosurePath, incompleteClosureBody)
		rejectedImport := e.publishImport(t, "e2-http-v3-incomplete-closure-20260919")
		var state, reason string
		var validation []byte
		err := e.h.Pool.QueryRow(context.Background(), `SELECT state,error,validation::text
 FROM gfm.publications WHERE org_id=$1::uuid AND import_id=$2::uuid
 ORDER BY created_at DESC LIMIT 1`, e.orgID, rejectedImport).
			Scan(&state, &reason, &validation)
		if err != nil {
			violations = append(violations, "could not read isolated dependency-admission result: "+err.Error())
		} else if state != "failed" || reason != "missing_dependency" || !strings.Contains(string(validation), "missing_dependency") {
			violations = append(violations, fmt.Sprintf("incomplete closure was not rejected as expected: state=%q error=%q validation=%s",
				state, reason, string(validation)))
		} else if current := e.head(t); current != snapshot {
			violations = append(violations, fmt.Sprintf("rejected incomplete closure changed active head: before=%s after=%s", snapshot, current))
		}
		t.Logf("E2HTTP_ADMISSION state=%s error=%s validation=%s active_head_preserved=%t",
			state, reason, string(validation), e.head(t) == snapshot)
	}
	t.Logf("E2HTTP_SUMMARY rows=%d requests=%d snapshot=%s violations=%d", len(observations), requestNumber, snapshot, len(violations))
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
