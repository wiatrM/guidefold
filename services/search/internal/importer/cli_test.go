package importer_test

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/pivottest"
)

// TestTheRealCLICompletesAnImport is the first end-to-end proof of the import
// pipeline: the shipped `guidefold` script, run as a subprocess, signs in with a
// personal token from the device flow, scans a copy of the Meridian monorepo,
// uploads its blobs and waits for the parse to finish against this server.
//
// Nothing here is a stand-in. The CLI is the real file the skill ZIP contains,
// the transport is HTTP over a real listener, and the worker runs the real
// Python builder. What it proves is the thing no unit test can: the client and
// the server agree about the wire, down to the manifest digest they compute
// independently on two sides of the connection.
func TestTheRealCLICompletesAnImport(t *testing.T) {
	h := pivottest.New(t)
	owner := h.SignIn(t, "owner", "owner@example.test")
	org := owner.CreateOrg(t, "acme")
	token := deviceToken(t, h, owner)
	tree := pivottest.Monorepo(t)
	scratch := pivottest.Scratch(t, "cli")
	home := pivottest.Scratch(t, "clihome")

	// The worker runs alongside the CLI, because `import --wait` polls until the
	// parse finishes. This is the shape a real deployment has: an API process
	// and a worker process, talking only through the job queue.
	ctx, stop := context.WithCancel(context.Background())
	var workers sync.WaitGroup
	workers.Add(1)
	go func() {
		defer workers.Done()
		for ctx.Err() == nil {
			if h.RunParseOnce(ctx, t, scratch) {
				continue
			}
			select {
			case <-ctx.Done():
			case <-time.After(50 * time.Millisecond):
			}
		}
	}()

	out := runCLI(t, tree, home, []string{
		"GUIDEFOLD_API=" + h.Server.URL,
		"GUIDEFOLD_ORG=" + org,
		"GUIDEFOLD_REPO_ID=meridian",
		"GUIDEFOLD_TOKEN=" + token,
	}, "import", "--wait", "--json")
	stop()
	workers.Wait()

	var result map[string]any
	if e := json.Unmarshal([]byte(out), &result); e != nil {
		t.Fatalf("the CLI did not print a JSON result: %v\n%s", e, out)
	}
	if result["state"] != "ready" {
		t.Fatalf("the CLI reports state %v:\n%s", result["state"], out)
	}
	if result["files"].(float64) < 30 {
		t.Fatalf("the CLI imported %v files", result["files"])
	}
	if result["new_blobs"].(float64) == 0 {
		t.Fatal("the first import uploaded nothing")
	}

	// The digest the CLI computed over its own manifest is the digest the
	// server stored. Two independent canonical-JSON implementations agreeing is
	// what makes `reused_import_id` and idempotent re-sync work at all.
	importID := result["import_id"].(string)
	var digest, state string
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT manifest_digest,state FROM gfm.imports WHERE import_id=$1::uuid`,
		importID).Scan(&digest, &state); e != nil {
		t.Fatal(e)
	}
	if digest != result["manifest_digest"] {
		t.Fatalf("the CLI's manifest digest %v is not the server's %s",
			result["manifest_digest"], digest)
	}
	if state != "ready" {
		t.Fatalf("the import row is %s", state)
	}

	// The catalog holds the fixture, reachable through the read API.
	status, page, _ := owner.Call(t, pivottest.Call{Method: http.MethodGet,
		Path: pivottest.RepoBase(org, "meridian") + "/skills?limit=100"})
	if status != http.StatusOK {
		t.Fatalf("skills: %d %v", status, page)
	}
	if got := len(page["items"].([]any)); got != fixtureSkills {
		t.Fatalf("the CLI's import produced %d of the fixture's %d skills", got, fixtureSkills)
	}

	// U1.4 — running the same import again uploads nothing and reuses the same
	// import row.
	out = runCLI(t, tree, home, []string{
		"GUIDEFOLD_API=" + h.Server.URL,
		"GUIDEFOLD_ORG=" + org,
		"GUIDEFOLD_REPO_ID=meridian",
		"GUIDEFOLD_TOKEN=" + token,
	}, "import", "--json")
	var second map[string]any
	if e := json.Unmarshal([]byte(out), &second); e != nil {
		t.Fatalf("the second run did not print a JSON result: %v\n%s", e, out)
	}
	if second["import_id"] != importID {
		t.Fatalf("the second run made import %v, not %s", second["import_id"], importID)
	}
	if second["new_blobs"].(float64) != 0 || second["uploaded_blobs"].(float64) != 0 {
		t.Fatalf("the second run uploaded %v new blobs", second["new_blobs"])
	}
	var parses int
	if e := h.Pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gfm.jobs WHERE import_id=$1::uuid AND kind='import.parse'`,
		importID).Scan(&parses); e != nil {
		t.Fatal(e)
	}
	if parses != 1 {
		t.Fatalf("two runs of the same tree queued %d parse jobs", parses)
	}
}

// deviceToken drives the CLI's own login path: an unauthenticated device start,
// a browser approval, then the exchange for a personal token.
func deviceToken(t *testing.T, h *pivottest.Harness, owner *pivottest.Client) string {
	t.Helper()
	cli := h.Anonymous()
	status, start, _ := cli.Call(t, pivottest.Call{Method: http.MethodPost, Path: "/api/v1/auth/device"})
	if status != http.StatusOK {
		t.Fatalf("device start: %d %v", status, start)
	}
	status, approved, _ := owner.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/auth/device/approve",
		Body: map[string]any{"user_code": start["user_code"]}})
	if status != http.StatusOK {
		t.Fatalf("device approve: %d %v", status, approved)
	}
	status, exchanged, _ := cli.Call(t, pivottest.Call{Method: http.MethodPost,
		Path: "/api/v1/auth/device/token",
		Body: map[string]any{"device_code": start["device_code"]}})
	if status != http.StatusOK {
		t.Fatalf("device token: %d %v", status, exchanged)
	}
	token, _ := exchanged["token"].(string)
	if !strings.HasPrefix(token, "gf_") {
		t.Fatalf("the device flow returned %q", token)
	}
	return token
}

// runCLI executes the shipped script in the tree, with a private HOME so it can
// never read or write the developer's own credentials.
func runCLI(t *testing.T, tree, home string, env []string, args ...string) string {
	t.Helper()
	script := filepath.Join(pivottest.Root(t), "skills", "guidefold", "scripts", "guidefold")
	cmd := exec.Command(cliPython(), append([]string{script}, args...)...)
	cmd.Dir = tree
	cmd.Env = append(append(os.Environ(),
		"HOME="+home,
		"XDG_CONFIG_HOME="+filepath.Join(home, ".config"),
		"GUIDEFOLD_CREDENTIALS="+filepath.Join(home, "credentials.json"),
	), env...)
	out, e := cmd.CombinedOutput()
	if e != nil {
		t.Fatalf("guidefold %s: %v\n%s", strings.Join(args, " "), e, out)
	}
	text := string(out)
	// --json prints the result last; earlier lines are progress.
	if i := strings.Index(text, "{"); i >= 0 {
		return text[i:]
	}
	return text
}

func cliPython() string {
	if v := os.Getenv("GUIDEFOLD_PYTHON"); v != "" {
		return v
	}
	return "python3"
}
