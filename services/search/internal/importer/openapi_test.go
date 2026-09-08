package importer_test

import (
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"os"
	"path/filepath"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

// The import module's responses are validated against the published schemas,
// not against a copy of them in the test: a field that quietly appears or
// disappears has to fail here rather than in a client.
func TestImportResponsesMatchTheOpenAPIComponents(t *testing.T) {
	spec := pivottest.LoadContract(t)
	f := newFixture(t)
	manifest := f.manifest(t, true)

	status, repos, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: "/api/v1/orgs/" + f.org + "/repos"})
	if status != http.StatusOK {
		t.Fatalf("repos: %d %v", status, repos)
	}
	spec.Check(t, "RepoList", repos)

	status, repo, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/orgs/" + f.org + "/repos",
		Body: map[string]any{"repo_id": "second", "name": "Second"}, Key: "repo-second"})
	if status != http.StatusCreated {
		t.Fatalf("create repo: %d %v", status, repo)
	}
	spec.Check(t, "RepoCreated", repo)

	status, created, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "spec", "manifest": manifest}, Key: "spec"})
	if status != http.StatusCreated {
		t.Fatalf("create import: %d %v", status, created)
	}
	spec.Check(t, "ImportCreated", created)
	importID := created["import_id"].(string)

	digest := created["missing_blobs"].([]any)[0].(string)
	data, e := os.ReadFile(filepath.Join(f.tree, filepath.FromSlash(pathOfDigest(t, manifest, digest))))
	if e != nil {
		t.Fatal(e)
	}
	status, stored, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: f.base + "/imports/" + importID + "/blobs/" + digest,
		Raw:  data, ContentType: "application/octet-stream"})
	if status != http.StatusCreated {
		t.Fatalf("upload: %d %v", status, stored)
	}
	spec.Check(t, "BlobStored", stored)

	status, view, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/imports/" + importID})
	if status != http.StatusOK {
		t.Fatalf("status: %d %v", status, view)
	}
	spec.Check(t, "ImportStatus", view)

	status, list, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet, Path: f.base + "/imports"})
	if status != http.StatusOK {
		t.Fatalf("list: %d %v", status, list)
	}
	spec.Check(t, "ImportList", list)
	for _, raw := range list["items"].([]any) {
		spec.Check(t, "ImportStatus", raw.(map[string]any))
	}

	// A finalized import: the queued state, the two jobs and the publication.
	full := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, manifest, "spec-full")
	status, finalized, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: f.base + "/imports/" + full})
	if status != http.StatusOK {
		t.Fatalf("finalized status: %d %v", status, finalized)
	}
	spec.Check(t, "ImportStatus", finalized)
	if finalized["state"] != "queued" {
		t.Fatalf("state %v", finalized["state"])
	}
	if len(finalized["jobs"].([]any)) != 2 {
		t.Fatalf("jobs %v", finalized["jobs"])
	}
	for _, raw := range finalized["jobs"].([]any) {
		spec.Check(t, "Job", raw.(map[string]any))
	}
	spec.Check(t, "ImportPublication", finalized["publication"].(map[string]any))
	spec.Check(t, "ImportCounts", finalized["counts"].(map[string]any))
}

// Every error the import module can answer with renders the one envelope, with
// a request id that matches the header.
func TestImportErrorEnvelopesMatchTheContract(t *testing.T) {
	spec := pivottest.LoadContract(t)
	f := newFixture(t)
	manifest := f.manifest(t, true)
	_, created, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "e", "manifest": manifest}, Key: "e"})
	importID := created["import_id"].(string)
	unknownBytes := []byte("not listed anywhere")
	sum := sha256.Sum256(unknownBytes)

	stranger := f.h.SignIn(t, "stranger", "stranger@example.test")
	for _, x := range []struct {
		name   string
		client *pivottest.Client
		call   pivottest.Call
		status int
		code   string
	}{
		{"forbidden", stranger, pivottest.Call{Method: http.MethodGet, Path: f.base + "/imports"},
			http.StatusForbidden, "forbidden"},
		{"import not found", f.owner, pivottest.Call{Method: http.MethodGet,
			Path: f.base + "/imports/00000000-0000-4000-8000-000000000000"},
			http.StatusNotFound, "import_not_found"},
		{"repo not found", f.owner, pivottest.Call{Method: http.MethodGet,
			Path: pivottest.RepoBase(f.org, "nosuchrepo") + "/imports"},
			http.StatusNotFound, "not_found"},
		{"blob not in manifest", f.owner, pivottest.Call{Method: http.MethodPut,
			Path: f.base + "/imports/" + importID + "/blobs/" + hex.EncodeToString(sum[:]),
			Raw:  unknownBytes, ContentType: "application/octet-stream"},
			http.StatusBadRequest, "blob_not_in_manifest"},
		{"blobs missing", f.owner, pivottest.Call{Method: http.MethodPost,
			Path: f.base + "/imports/" + importID + "/finalize",
			Body: map[string]any{"idempotency_key": "f"}, Key: "f"},
			http.StatusConflict, "blobs_missing"},
		{"idempotency key required", f.owner, pivottest.Call{Method: http.MethodPost,
			Path: f.base + "/imports", Body: map[string]any{"manifest": manifest}},
			http.StatusBadRequest, "idempotency_key_required"},
		{"invalid cursor", f.owner, pivottest.Call{Method: http.MethodGet,
			Path: f.base + "/imports?cursor=nonsense"}, http.StatusBadRequest, "invalid_cursor"},
	} {
		t.Run(x.name, func(t *testing.T) {
			status, body, header := x.client.Call(t, x.call)
			if status != x.status || body["error"] != x.code {
				t.Fatalf("%d %v", status, body)
			}
			if header.Get("X-Request-Id") == "" || body["request_id"] != header.Get("X-Request-Id") {
				t.Fatalf("request id: header %q body %v", header.Get("X-Request-Id"), body["request_id"])
			}
			if header.Get("Cache-Control") != "no-store" {
				t.Fatalf("Cache-Control %q", header.Get("Cache-Control"))
			}
			spec.Check(t, "Error", body)
		})
	}
}
