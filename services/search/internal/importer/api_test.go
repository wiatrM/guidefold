package importer_test

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

func TestMain(m *testing.M) { pivottest.Main(m) }

// fixture is one signed-in owner with an organisation, a repository and a
// private copy of the Meridian monorepo.
type fixture struct {
	h     *pivottest.Harness
	owner *pivottest.Client
	org   string
	repo  string
	tree  string
	base  string
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	owner.CreateRepo(t, org, "meridian", "https://github.example/acme/meridian")
	return &fixture{h: h, owner: owner, org: org, repo: "meridian",
		tree: pivottest.Monorepo(t), base: pivottest.RepoBase(org, "meridian")}
}

func (f *fixture) manifest(t *testing.T, complete bool) map[string]any {
	return pivottest.Manifest(t, f.tree, "acme", f.repo, complete)
}

// U1.3 — the upload route accepts a digest only because the manifest listed it.
// Content the scan excluded on purpose has no route into storage at all.
func TestBlobUploadRejectsAHashTheManifestDoesNotList(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	status, created, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "k1", "manifest": manifest}, Key: "k1"})
	if status != http.StatusCreated {
		t.Fatalf("create import: %d %v", status, created)
	}
	importID := created["import_id"].(string)

	secret := []byte("-----BEGIN PRIVATE KEY-----\nnot in the manifest\n")
	sum := sha256.Sum256(secret)
	digest := hex.EncodeToString(sum[:])
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: f.base + "/imports/" + importID + "/blobs/" + digest,
		Raw:  secret, ContentType: "application/octet-stream"})
	if status != http.StatusBadRequest || body["error"] != "blob_not_in_manifest" {
		t.Fatalf("excluded content was accepted: %d %v", status, body)
	}
	var stored int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.blobs WHERE sha256=$1`, digest).Scan(&stored); e != nil {
		t.Fatal(e)
	}
	if stored != 0 {
		t.Fatalf("the refused blob was stored anyway (%d rows)", stored)
	}
}

// The digest in the path is checked against the bytes, so a truncated transfer
// cannot store a short file under a full file's name.
func TestBlobUploadRejectsBytesThatDoNotHashToTheDigest(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	_, created, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "k1", "manifest": manifest}, Key: "k1"})
	importID := created["import_id"].(string)
	wanted := created["missing_blobs"].([]any)[0].(string)

	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPut,
		Path: f.base + "/imports/" + importID + "/blobs/" + wanted,
		Raw:  []byte("different bytes"), ContentType: "application/octet-stream"})
	if status != http.StatusBadRequest || body["error"] != "blob_digest_mismatch" {
		t.Fatalf("mismatched bytes were accepted: %d %v", status, body)
	}
	// G2 — and it leaves nothing behind. The state transition and the audit row
	// used to be committed before the body was read, so a rejected upload still
	// advanced the import to `uploading` and wrote an `import.blob` entry naming
	// a blob that was never stored.
	var state string
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT state FROM gfm.imports WHERE org_id=$1::uuid AND import_id=$2::uuid`,
		f.org, importID).Scan(&state); e != nil {
		t.Fatal(e)
	}
	if state != "created" {
		t.Fatalf("a rejected upload advanced the import to %q", state)
	}
	var audited int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.audit WHERE org_id=$1::uuid AND action='import.blob'`,
		f.org).Scan(&audited); e != nil {
		t.Fatal(e)
	}
	if audited != 0 {
		t.Fatalf("a rejected upload wrote %d import.blob audit rows", audited)
	}
	var stored int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.blobs WHERE org_id=$1::uuid AND sha256=$2`,
		f.org, wanted).Scan(&stored); e != nil {
		t.Fatal(e)
	}
	if stored != 0 {
		t.Fatalf("a rejected upload stored %d blobs", stored)
	}
}

// U1.4 — an interrupted upload is resumed by re-sending. The second PUT of the
// same bytes answers 200 and stores nothing new.
func TestReUploadingTheSameBlobIsIdempotent(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	_, created, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "k1", "manifest": manifest}, Key: "k1"})
	importID := created["import_id"].(string)
	digest := created["missing_blobs"].([]any)[0].(string)
	path := pathOfDigest(t, manifest, digest)
	data, e := os.ReadFile(filepath.Join(f.tree, filepath.FromSlash(path)))
	if e != nil {
		t.Fatal(e)
	}
	url := f.base + "/imports/" + importID + "/blobs/" + digest

	status, first, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: url,
		Raw: data, ContentType: "application/octet-stream"})
	if status != http.StatusCreated || first["stored"] != true {
		t.Fatalf("first upload: %d %v", status, first)
	}
	status, second, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPut, Path: url,
		Raw: data, ContentType: "application/octet-stream"})
	if status != http.StatusOK || second["stored"] != false {
		t.Fatalf("re-upload: %d %v", status, second)
	}
	var rows int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.blobs WHERE sha256=$1`, digest).Scan(&rows); e != nil {
		t.Fatal(e)
	}
	if rows != 1 {
		t.Fatalf("the same bytes are stored %d times", rows)
	}
}

func pathOfDigest(t *testing.T, manifest map[string]any, digest string) string {
	t.Helper()
	for _, f := range manifest["files"].([]map[string]any) {
		if f["sha256"] == digest {
			return f["path"].(string)
		}
	}
	t.Fatalf("digest %s is not in the manifest", digest)
	return ""
}

// U1.4 — the same manifest twice is the same import: nothing is missing the
// second time and the second finalize queues no second parse.
func TestTheSameManifestIsReusedAndFinalizedOnlyOnce(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	importID := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, manifest, "first")

	// A second client (a different principal, so a different idempotency scope)
	// sends the same tree.
	other := f.h.SignIn(t, "second", "second@example.test")
	inviteInto(t, f, other, "owner")
	status, again, _ := other.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "second", "manifest": manifest}, Key: "second"})
	if status != http.StatusCreated {
		t.Fatalf("second create: %d %v", status, again)
	}
	if again["import_id"] != importID || again["reused_import_id"] != importID {
		t.Fatalf("the same manifest made a second import: %v", again)
	}
	if missing := again["missing_blobs"].([]any); len(missing) != 0 {
		t.Fatalf("the second import wants %d blobs it already has", len(missing))
	}
	status, finalized, _ := other.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports/" + importID + "/finalize",
		Body: map[string]any{"idempotency_key": "second:finalize"}, Key: "second:finalize"})
	if status != http.StatusOK {
		t.Fatalf("second finalize: %d %v", status, finalized)
	}
	var parses int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.jobs WHERE import_id=$1::uuid AND kind='import.parse'`,
		importID).Scan(&parses); e != nil {
		t.Fatal(e)
	}
	if parses != 1 {
		t.Fatalf("finalizing twice queued %d parse jobs", parses)
	}
}

func inviteInto(t *testing.T, f *fixture, guest *pivottest.Client, role string) {
	t.Helper()
	status, invitation, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/orgs/" + f.org + "/invitations",
		Body: map[string]any{"email": "second@example.test", "role": role},
		Key:  "invite-" + role + "-" + guest.User["id"].(string)})
	if status != http.StatusCreated {
		t.Fatalf("invite: %d %v", status, invitation)
	}
	accept := invitation["accept_url"].(string)
	accept = accept[strings.Index(accept, "/api/v1/"):]
	status, body, _ := guest.Call(t, pivottest.Call{Method: http.MethodPost, Path: accept,
		Key: "accept-" + guest.User["id"].(string)})
	if status != http.StatusOK {
		t.Fatalf("accept: %d %v", status, body)
	}
}

// Finalizing before every blob has arrived names exactly what is missing.
func TestFinalizeRefusesAnIncompleteUpload(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	_, created, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "k1", "manifest": manifest}, Key: "k1"})
	importID := created["import_id"].(string)
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports/" + importID + "/finalize",
		Body: map[string]any{"idempotency_key": "k1:finalize"}, Key: "k1:finalize"})
	if status != http.StatusConflict || body["error"] != "blobs_missing" {
		t.Fatalf("finalize: %d %v", status, body)
	}
	details, _ := body["details"].(map[string]any)
	missing, _ := details["missing"].([]any)
	if len(missing) != len(created["missing_blobs"].([]any)) {
		t.Fatalf("the error does not name what is missing: %v", body)
	}
}

// A manifest above the per-blob ceiling is refused with a named limit rather
// than silently truncated.
func TestManifestOverTheBlobLimitIsRefused(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	files := manifest["files"].([]map[string]any)
	files[0]["size"] = 9 << 20
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "k1", "manifest": manifest}, Key: "k1"})
	if status != http.StatusUnprocessableEntity || body["error"] != "limit_exceeded" {
		t.Fatalf("oversized file accepted: %d %v", status, body)
	}
}

// A manifest in an unknown format is refused before anything else is read.
func TestUnknownManifestFormatIsRefused(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	manifest["format"] = "guidefold-import-manifest-v2"
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "k1", "manifest": manifest}, Key: "k1"})
	if status != http.StatusBadRequest || body["error"] != "unsupported_manifest_format" {
		t.Fatalf("%d %v", status, body)
	}
}

// A field this server does not model is a client bug, not a setting to drop.
func TestUnknownManifestFieldIsRefused(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	manifest["unexpected"] = true
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "k1", "manifest": manifest}, Key: "k1"})
	if status != http.StatusBadRequest || body["error"] != "invalid_json" {
		t.Fatalf("%d %v", status, body)
	}
}

// Members read, owners mutate.
func TestAMemberCannotCreateAnImport(t *testing.T) {
	f := newFixture(t)
	member := f.h.SignIn(t, "second", "second@example.test")
	inviteInto(t, f, member, "member")
	status, body, _ := member.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports",
		Body: map[string]any{"idempotency_key": "k1", "manifest": f.manifest(t, true)}, Key: "k1"})
	if status != http.StatusForbidden || body["error"] != "forbidden" {
		t.Fatalf("a member created an import: %d %v", status, body)
	}
	status, list, _ := member.Call(t, pivottest.Call{Method: http.MethodGet, Path: f.base + "/imports"})
	if status != http.StatusOK {
		t.Fatalf("a member cannot list imports: %d %v", status, list)
	}
}

// U3.3 — organisation B gets exactly the answer it would get for an
// organisation that does not exist. Same status, same body, byte for byte.
func TestAnotherOrganisationSeesTheSameForbiddenBody(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	importID := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, manifest, "first")
	digest := manifest["files"].([]map[string]any)[0]["sha256"].(string)

	stranger := f.h.SignIn(t, "stranger", "stranger@example.test")
	stranger.CreateOrg(t, "other")
	for _, probe := range []struct{ method, path string }{
		{http.MethodGet, f.base + "/imports"},
		{http.MethodGet, f.base + "/imports/" + importID},
		{http.MethodPut, f.base + "/imports/" + importID + "/blobs/" + digest},
		{http.MethodGet, f.base + "/skills"},
		{http.MethodGet, f.base + "/skills/facets?field=scope"},
		{http.MethodGet, f.base + "/map/repository"},
		{http.MethodGet, f.base + "/map/scopes"},
		{http.MethodGet, f.base + "/map/layers"},
		{http.MethodGet, f.base + "/map/relations"},
	} {
		call := pivottest.Call{Method: probe.method, Path: probe.path}
		if probe.method == http.MethodPut {
			call.Raw = []byte("stolen")
			call.ContentType = "application/octet-stream"
		}
		_, denied, _ := stranger.Call(t, call)
		call.Path = strings.Replace(probe.path, "/orgs/"+f.org+"/", "/orgs/does-not-exist/", 1)
		_, unknown, _ := stranger.Call(t, call)
		if denied["error"] != "forbidden" {
			t.Fatalf("%s %s answered %v to another organisation", probe.method, probe.path, denied)
		}
		if denied["message"] != unknown["message"] || unknown["error"] != "forbidden" {
			t.Fatalf("%s distinguishes a foreign organisation from a missing one:\n %v\n %v",
				probe.path, denied, unknown)
		}
	}
	// Nothing of organisation A's content reached organisation B's store.
	var leaked int
	if e := f.h.Pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.blobs b
 JOIN gfm.orgs o ON o.org_id=b.org_id WHERE o.slug='other'`).Scan(&leaked); e != nil {
		t.Fatal(e)
	}
	if leaked != 0 {
		t.Fatalf("the other organisation ended up holding %d blobs", leaked)
	}
}

// Cancelling stops the queued work and moves the job generation, so a worker
// still holding the old lease is fenced rather than finishing into it.
func TestCancelStopsTheQueuedJobs(t *testing.T) {
	f := newFixture(t)
	importID := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, f.manifest(t, true), "first")
	status, body, _ := f.owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: f.base + "/imports/" + importID + "/cancel",
		Body: map[string]any{"idempotency_key": "cancel"}, Key: "cancel"})
	if status != http.StatusOK || body["state"] != "cancelled" {
		t.Fatalf("cancel: %d %v", status, body)
	}
	rows, e := f.h.Pool.Query(context.Background(),
		`SELECT kind,state FROM gfm.jobs WHERE import_id=$1::uuid`, importID)
	if e != nil {
		t.Fatal(e)
	}
	defer rows.Close()
	for rows.Next() {
		var kind, state string
		if e := rows.Scan(&kind, &state); e != nil {
			t.Fatal(e)
		}
		if state != "cancelled" {
			t.Fatalf("%s is %s after the import was cancelled", kind, state)
		}
	}
}

// The publication job is queued at finalize even though no worker handles it
// yet: the decision belongs to the manifest, and an unknown kind waits.
func TestFinalizeQueuesTheParseAndThePublication(t *testing.T) {
	f := newFixture(t)
	importID := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, f.manifest(t, true), "first")
	kinds := map[string]string{}
	rows, e := f.h.Pool.Query(context.Background(),
		`SELECT kind,state FROM gfm.jobs WHERE import_id=$1::uuid`, importID)
	if e != nil {
		t.Fatal(e)
	}
	defer rows.Close()
	for rows.Next() {
		var kind, state string
		if e := rows.Scan(&kind, &state); e != nil {
			t.Fatal(e)
		}
		kinds[kind] = state
	}
	if kinds["import.parse"] != "queued" || kinds["publish.build"] != "queued" {
		t.Fatalf("finalize queued %v", kinds)
	}
}

// publish:false finalizes without queueing a publication.
func TestAManifestThatDoesNotPublishQueuesOnlyTheParse(t *testing.T) {
	f := newFixture(t)
	manifest := f.manifest(t, true)
	manifest["publish"] = false
	importID := pivottest.Push(t, f.owner, f.org, f.repo, f.tree, manifest, "first")
	var builds int
	if e := f.h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.jobs WHERE import_id=$1::uuid AND kind='publish.build'`,
		importID).Scan(&builds); e != nil {
		t.Fatal(e)
	}
	if builds != 0 {
		t.Fatalf("publish:false still queued %d publication jobs", builds)
	}
}

// Registering a repository twice is success; `created` says which happened.
func TestRegisteringARepositoryTwiceIsSuccess(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	status, first, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/orgs/" + org + "/repos",
		Body: map[string]any{"repo_id": "mono"}, Key: "a"})
	if status != http.StatusCreated || first["created"] != true {
		t.Fatalf("first: %d %v", status, first)
	}
	status, second, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/orgs/" + org + "/repos",
		Body: map[string]any{"repo_id": "mono"}, Key: "b"})
	if status != http.StatusOK || second["created"] != false {
		t.Fatalf("second: %d %v", status, second)
	}
}
