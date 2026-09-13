package identity_test

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/identity"
)

// githubOAuthStub stands in for github.com's OAuth token endpoint and
// api.github.com's /user/installations — the two calls
// handleGitHubInstallCallback makes to prove a claimed installation_id is
// actually visible to the signed-in owner's own GitHub account (ADR-0034).
// A code of "bad-code" is refused, matching a stale or already-used
// authorization code.
func githubOAuthStub(t *testing.T, owned []int64) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/login/oauth/access_token", func(w http.ResponseWriter, r *http.Request) {
		if e := r.ParseForm(); e != nil {
			t.Fatal(e)
		}
		if r.Form.Get("code") == "bad-code" {
			_ = json.NewEncoder(w).Encode(map[string]any{"error": "bad_verification_code"})
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"access_token": "user-token-for-" + r.Form.Get("code")})
	})
	mux.HandleFunc("/user/installations", func(w http.ResponseWriter, r *http.Request) {
		items := make([]map[string]any, 0, len(owned))
		for _, id := range owned {
			items = append(items, map[string]any{"id": id, "account": map[string]any{"login": "acme"}, "repository_selection": "all"})
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"installations": items})
	})
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return server
}

// newGitHubHarness builds a harness whose GitHub App is configured for both
// the webhook and the OAuth linking flow, with owned naming the
// installation ids the stubbed GitHub account can see on
// GET /user/installations.
func newGitHubHarness(t *testing.T, owned []int64) *harness {
	t.Helper()
	stub := githubOAuthStub(t, owned)
	return newHarnessWith(t, identity.Config{
		Mode: identity.ModeDev, PublicURL: "http://127.0.0.1", InsecureCookies: true,
		GitHubWebhookSecret: "secret", GitHubAppSlug: "guidefold-test",
		GitHubAppClientID: "client-id", GitHubAppClientSecret: "client-secret",
		GitHubAppAuthBaseURL: stub.URL, GitHubAppAPIBaseURL: stub.URL,
	})
}

func signGitHubBody(body []byte) string {
	sum := hmac.New(sha256.New, []byte("secret"))
	_, _ = sum.Write(body)
	return "sha256=" + hex.EncodeToString(sum.Sum(nil))
}

func sendGitHubWebhook(t *testing.T, c *client, event, delivery string, body []byte) (int, map[string]any) {
	t.Helper()
	status, result, _ := c.call(t, call{method: http.MethodPost, path: "/api/v1/github/webhook",
		body: json.RawMessage(body), csrf: "-", headers: map[string]string{
			"X-GitHub-Event": event, "X-GitHub-Delivery": delivery, "X-Hub-Signature-256": signGitHubBody(body),
		}})
	return status, result
}

// startGitHubInstall calls the start route and returns the state GitHub
// would echo back on its installation redirect.
func startGitHubInstall(t *testing.T, owner *client, orgSlug string) string {
	t.Helper()
	status, body, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/" + orgSlug + "/github/installations/start"})
	if status != http.StatusOK {
		t.Fatalf("start install: %d %v", status, body)
	}
	installURL, _ := body["install_url"].(string)
	if installURL == "" {
		t.Fatalf("start install returned no install_url: %v", body)
	}
	state := mustURL(t, installURL).Query().Get("state")
	if state == "" {
		t.Fatalf("install_url carried no state: %q", installURL)
	}
	return state
}

func callbackURL(state, code string, installationID int64) string {
	q := url.Values{"state": {state}, "code": {code}}
	if installationID != 0 {
		q.Set("installation_id", strconv.FormatInt(installationID, 10))
	}
	return "/api/v1/github/installations/callback?" + q.Encode()
}

// linkInstallation drives the whole happy-path flow (start, then callback)
// for an owner already positioned at orgSlug, and fails the test unless the
// callback redirected to the console's real route with the "linked" outcome
// (API-CONTRACT §4.7, Task 1/2) — never JSON.
func linkInstallation(t *testing.T, owner *client, orgSlug string, installationID int64) {
	t.Helper()
	state := startGitHubInstall(t, owner, orgSlug)
	status, body, headers := owner.call(t, call{method: http.MethodGet, path: callbackURL(state, "good-code", installationID)})
	q := githubCallbackLocation(t, status, body, headers)
	if q.Get("github") != "linked" || q.Get("tab") != "integrations" || q.Get("org") == "" {
		t.Fatalf("successful link redirect: %v", q)
	}
}

func installationCount(t *testing.T, c *client, orgSlug string) []map[string]any {
	t.Helper()
	status, listed, _ := c.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/" + orgSlug + "/github/installations"})
	if status != http.StatusOK {
		t.Fatalf("list installations: %d %v", status, listed)
	}
	items := listed["items"].([]any)
	out := make([]map[string]any, len(items))
	for i, it := range items {
		out[i] = it.(map[string]any)
	}
	return out
}

func countJobsOfKind(t *testing.T, h *harness, kind string) int {
	t.Helper()
	var n int
	if err := h.pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.jobs WHERE kind=$1`, kind).Scan(&n); err != nil {
		t.Fatalf("count jobs: %v", err)
	}
	return n
}

// --- linking: the owner-only start route -----------------------------------

func TestGitHubInstallStartIsOwnerOnly(t *testing.T) {
	h := newGitHubHarness(t, []int64{111})
	owner := h.signIn(t, "google", "gh-start-owner", "gh-start-owner@example.test", "Owner")
	owner.createOrg(t, "gh-start", "GitHub Start Org")

	if status, body, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/gh-start/github/installations/start"}); status != http.StatusOK {
		t.Fatalf("owner start: %d %v", status, body)
	}

	member := h.signIn(t, "github", "gh-start-member", "gh-start-member@example.test", "Member")
	_, invitation, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/gh-start/invitations",
		body: map[string]any{"email": "gh-start-member@example.test", "role": "member"}, key: "gh-start-invite"})
	acceptURL := mustURL(t, invitation["accept_url"].(string))
	if status, _, _ := member.call(t, call{method: http.MethodPost, path: acceptURL.Path, key: "gh-start-accept"}); status != http.StatusOK {
		t.Fatalf("accept invitation: %d", status)
	}
	if status, body, _ := member.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/gh-start/github/installations/start"}); status != http.StatusForbidden {
		t.Fatalf("member started a github install link: %d %v", status, body)
	}
}

// --- linking: the callback proves ownership before it links ---------------

func TestGitHubInstallCallbackLinksAnOwnedInstallation(t *testing.T) {
	h := newGitHubHarness(t, []int64{555})
	owner := h.signIn(t, "google", "gh-link-owner", "gh-link-owner@example.test", "Owner")
	owner.createOrg(t, "gh-link", "GitHub Link Org")

	linkInstallation(t, owner, "gh-link", 555)

	items := installationCount(t, owner, "gh-link")
	if len(items) != 1 || items[0]["installation_id"] != float64(555) {
		t.Fatalf("installations after link: %v", items)
	}
	if n := countJobsOfKind(t, h, "github.sync_repositories"); n != 1 {
		t.Fatalf("linking must enqueue exactly one github.sync_repositories job, got %d", n)
	}
}

// Task 3/4: the DTO carries repository_selection and linked_at from the
// proven callback, and registered_repositories/synced from gfm.repos and
// the sync job's own completion — never from the webhook mirror's
// created_at/updated_at. This harness never runs the worker, so the
// enqueued github.sync_repositories job stays queued: reconciliation has
// not actually happened yet, and the DTO must say so honestly rather than
// inferring it from the link having just been created.
func TestGitHubInstallationDTOCarriesSelectionLinkedAtAndSyncState(t *testing.T) {
	h := newGitHubHarness(t, []int64{777})
	owner := h.signIn(t, "google", "gh-dto-owner", "gh-dto-owner@example.test", "Owner")
	owner.createOrg(t, "gh-dto", "GitHub DTO Org")

	linkInstallation(t, owner, "gh-dto", 777)

	items := installationCount(t, owner, "gh-dto")
	if len(items) != 1 {
		t.Fatalf("installations after link: %v", items)
	}
	entry := items[0]
	if entry["repository_selection"] != "all" {
		t.Fatalf("repository_selection not carried from the callback's proof: %v", entry["repository_selection"])
	}
	if entry["linked_at"] == nil || entry["linked_at"] == "" {
		t.Fatalf("linked_at missing from the DTO: %v", entry)
	}
	if entry["registered_repositories"] != float64(0) {
		t.Fatalf("registered_repositories must reflect gfm.repos, not GitHub's own list: %v", entry["registered_repositories"])
	}
	if entry["synced"] != false {
		t.Fatalf("synced must be false before github.sync_repositories has ever run: %v", entry["synced"])
	}

	// Simulate what agentrun.GitHubSyncWorker.Run commits (its own test
	// coverage lives in internal/agentrun): one registered repository and
	// repositories_synced_at set, in the same transaction shape.
	orgID := owner.refresh(t)["orgs"].([]any)[0].(map[string]any)["org_id"].(string)
	if _, err := h.pool.Exec(context.Background(), `INSERT INTO gfm.repos(org_id,repo_id,name,git_host_url,github_installation_id)
 VALUES($1::uuid,'repo-777','acme/repo','https://github.com/acme/repo',777)`, orgID); err != nil {
		t.Fatal(err)
	}
	if _, err := h.pool.Exec(context.Background(), `UPDATE gfm.github_installation_links SET repositories_synced_at=now() WHERE installation_id=777`); err != nil {
		t.Fatal(err)
	}
	items = installationCount(t, owner, "gh-dto")
	entry = items[0]
	if entry["registered_repositories"] != float64(1) {
		t.Fatalf("registered_repositories did not pick up the gfm.repos write: %v", entry["registered_repositories"])
	}
	if entry["synced"] != true {
		t.Fatalf("synced did not pick up repositories_synced_at: %v", entry["synced"])
	}
}

// The webhook can create the mirror row (with a real account) before the
// owner ever reaches the callback (API-CONTRACT §4.7's documented
// either-order case) — and that webhook payload here carries no
// repository_selection at all, the ordinary case for a bare "created"
// fixture. The callback's own INSERT must still fill repository_selection
// in from its /user/installations proof: an UPDATE gated on an empty account
// would silently skip it once the webhook has already set a real account.
func TestGitHubInstallationSelectionFillsInAfterWebhookSetsAccountFirst(t *testing.T) {
	h := newGitHubHarness(t, []int64{888})
	owner := h.signIn(t, "google", "gh-selection-owner", "gh-selection-owner@example.test", "Owner")
	owner.createOrg(t, "gh-selection", "GitHub Selection Order Org")

	installed := []byte(`{"action":"created","installation":{"id":888,"account":{"login":"acme"},"repositories":[{"full_name":"acme/repo"}]}}`)
	if status, result := sendGitHubWebhook(t, owner, "installation", "selection-delivery-1", installed); status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("installation webhook before link: %d %v", status, result)
	}

	linkInstallation(t, owner, "gh-selection", 888)

	items := installationCount(t, owner, "gh-selection")
	if len(items) != 1 {
		t.Fatalf("installations after link: %v", items)
	}
	if items[0]["account"] != "acme" {
		t.Fatalf("account was not the webhook's own value: %v", items[0]["account"])
	}
	if items[0]["repository_selection"] != "all" {
		t.Fatalf("repository_selection must still fill in from the callback's proof even though the webhook already set a real account: %v", items[0]["repository_selection"])
	}
}

// githubCallbackLocation asserts the callback redirected (never JSON, Task
// 1) and returns its Location as query values, so a caller can check the
// outcome code and the organisation carried in it.
func githubCallbackLocation(t *testing.T, status int, body map[string]any, headers http.Header) url.Values {
	t.Helper()
	if status != http.StatusFound {
		t.Fatalf("callback did not redirect: %d %v", status, body)
	}
	if len(body) != 0 {
		t.Fatalf("callback must never answer JSON to the browser: %v", body)
	}
	loc := mustURL(t, headers.Get("Location"))
	if loc.Path != "/organization" {
		t.Fatalf("callback redirect did not land on the console's real route: %v", loc)
	}
	return loc.Query()
}

// A forged installation_id — one the query string names but the signed-in
// owner's own GitHub account cannot see — must be refused and nothing
// linked. This is the whole point of the OAuth-during-install proof
// (ADR-0034): an installation_id in a query string is attacker-controlled.
func TestGitHubInstallCallbackRefusesAForgedInstallationID(t *testing.T) {
	h := newGitHubHarness(t, []int64{111}) // the account only owns 111
	owner := h.signIn(t, "google", "gh-forge-owner", "gh-forge-owner@example.test", "Owner")
	orgID := owner.createOrg(t, "gh-forge", "GitHub Forge Org")

	state := startGitHubInstall(t, owner, "gh-forge")
	status, body, headers := owner.call(t, call{method: http.MethodGet, path: callbackURL(state, "good-code", 999)})
	q := githubCallbackLocation(t, status, body, headers)
	if q.Get("github") != "installation_not_owned" || q.Get("org") != orgID {
		t.Fatalf("forged installation_id redirect: %v", q)
	}
	if items := installationCount(t, owner, "gh-forge"); len(items) != 0 {
		t.Fatalf("a forged installation_id linked something: %v", items)
	}
	if n := countJobsOfKind(t, h, "github.sync_repositories"); n != 0 {
		t.Fatalf("a refused link must enqueue no job, got %d", n)
	}
}

// The callback checks GitHubAppClientID/Secret before it touches any state,
// so an unconfigured deployment redirects straight to the console with no
// organisation attached — there is no state to have decoded one from yet.
func TestGitHubInstallCallbackReportsAppNotConfigured(t *testing.T) {
	h := newHarnessWith(t, identity.Config{Mode: identity.ModeDev, PublicURL: "http://127.0.0.1", InsecureCookies: true})
	status, body, headers := h.newClient().call(t, call{method: http.MethodGet, path: callbackURL("some-state", "some-code", 1)})
	q := githubCallbackLocation(t, status, body, headers)
	if q.Get("github") != "github_app_not_configured" || q.Get("org") != "" {
		t.Fatalf("unconfigured deployment redirect: %v", q)
	}
}

// GitHub itself failing the code exchange (a stale or already-used
// authorization code, or GitHub being unreachable) redirects with
// provider_unavailable, and still carries the organisation: the state was
// already proven to belong to this browser by the time this call is made.
func TestGitHubInstallCallbackRefusesWhenProviderUnavailable(t *testing.T) {
	h := newGitHubHarness(t, []int64{444})
	owner := h.signIn(t, "google", "gh-provider-owner", "gh-provider-owner@example.test", "Owner")
	orgID := owner.createOrg(t, "gh-provider", "GitHub Provider Org")

	state := startGitHubInstall(t, owner, "gh-provider")
	status, body, headers := owner.call(t, call{method: http.MethodGet, path: callbackURL(state, "bad-code", 444)})
	q := githubCallbackLocation(t, status, body, headers)
	if q.Get("github") != "provider_unavailable" || q.Get("org") != orgID {
		t.Fatalf("provider_unavailable redirect: %v", q)
	}
	if items := installationCount(t, owner, "gh-provider"); len(items) != 0 {
		t.Fatalf("a refused exchange linked something: %v", items)
	}
}

// A state already consumed cannot be replayed.
func TestGitHubInstallCallbackRefusesAReplayedState(t *testing.T) {
	h := newGitHubHarness(t, []int64{222})
	owner := h.signIn(t, "google", "gh-replay-owner", "gh-replay-owner@example.test", "Owner")
	owner.createOrg(t, "gh-replay", "GitHub Replay Org")

	state := startGitHubInstall(t, owner, "gh-replay")
	if status, body, _ := owner.call(t, call{method: http.MethodGet, path: callbackURL(state, "good-code", 222)}); status != http.StatusFound {
		t.Fatalf("first callback: %d %v", status, body)
	}
	// The state cookie was cleared by the first callback (matchAuthStateCookie
	// always clears it), so a same-browser replay now fails on the cookie
	// check before it even reaches the "already used" state lookup — still
	// refused either way, and still a redirect (never JSON), with no
	// organisation carried: an unmatched cookie proves nothing about which
	// organisation this browser may see.
	status, body, headers := owner.call(t, call{method: http.MethodGet, path: callbackURL(state, "good-code", 222)})
	q := githubCallbackLocation(t, status, body, headers)
	if q.Get("github") != "invalid_state" || q.Get("org") != "" {
		t.Fatalf("replayed state redirect: %v", q)
	}
}

// A state from a different browser (no matching AuthStateCookie) is
// refused — the same login-CSRF protection the sign-in callback applies.
func TestGitHubInstallCallbackRefusesAForeignBrowserState(t *testing.T) {
	h := newGitHubHarness(t, []int64{333})
	owner := h.signIn(t, "google", "gh-foreign-owner", "gh-foreign-owner@example.test", "Owner")
	owner.createOrg(t, "gh-foreign", "GitHub Foreign Org")
	state := startGitHubInstall(t, owner, "gh-foreign")

	attacker := h.signIn(t, "google", "gh-foreign-attacker", "gh-foreign-attacker@example.test", "Attacker")
	status, body, headers := attacker.call(t, call{method: http.MethodGet, path: callbackURL(state, "good-code", 333)})
	q := githubCallbackLocation(t, status, body, headers)
	// The foreign browser never proved which organisation's round trip this
	// was, so nothing is carried in the redirect — never the victim
	// organisation's id, which would leak it to a browser that never proved
	// anything.
	if q.Get("github") != "invalid_state" || q.Get("org") != "" {
		t.Fatalf("callback from a browser that never started it: %v", q)
	}
	if items := installationCount(t, owner, "gh-foreign"); len(items) != 0 {
		t.Fatalf("a foreign-browser callback linked something: %v", items)
	}
}

// --- both installation/link orderings converge -----------------------------

// The "installation" webhook can arrive before the owner finishes the
// linking callback, or after — API-CONTRACT §4.7 requires both orders to
// converge on the same one linked installation with its mirror populated.
func TestGitHubInstallationAndLinkConvergeRegardlessOfOrder(t *testing.T) {
	t.Run("webhook before callback", func(t *testing.T) {
		h := newGitHubHarness(t, []int64{1001})
		owner := h.signIn(t, "google", "gh-order-a-owner", "gh-order-a-owner@example.test", "Owner")
		owner.createOrg(t, "gh-order-a", "GitHub Order A")

		installed := []byte(`{"action":"created","installation":{"id":1001,"account":{"login":"acme"},"repositories":[{"full_name":"acme/repo"}]}}`)
		status, result := sendGitHubWebhook(t, owner, "installation", "order-a-delivery-1", installed)
		if status != http.StatusAccepted || result["accepted"] != true {
			t.Fatalf("installation webhook before link: %d %v", status, result)
		}
		if result["job_id"] != nil {
			t.Fatalf("an unlinked installation must enqueue no job: %v", result)
		}
		if items := installationCount(t, owner, "gh-order-a"); len(items) != 0 {
			t.Fatalf("an unlinked installation must not be listed for this org: %v", items)
		}

		linkInstallation(t, owner, "gh-order-a", 1001)
		items := installationCount(t, owner, "gh-order-a")
		if len(items) != 1 || items[0]["installation_id"] != float64(1001) {
			t.Fatalf("installations after link: %v", items)
		}
		repos := items[0]["repositories"].([]any)
		if len(repos) != 1 || repos[0].(map[string]any)["full_name"] != "acme/repo" {
			t.Fatalf("mirror repositories not carried through to the link: %v", repos)
		}
		if n := countJobsOfKind(t, h, "github.sync_repositories"); n != 1 {
			t.Fatalf("expected exactly one sync job (from the link), got %d", n)
		}
	})

	t.Run("callback before webhook", func(t *testing.T) {
		h := newGitHubHarness(t, []int64{1002})
		owner := h.signIn(t, "google", "gh-order-b-owner", "gh-order-b-owner@example.test", "Owner")
		owner.createOrg(t, "gh-order-b", "GitHub Order B")

		linkInstallation(t, owner, "gh-order-b", 1002)
		if n := countJobsOfKind(t, h, "github.sync_repositories"); n != 1 {
			t.Fatalf("expected one sync job from the link itself, got %d", n)
		}
		// The callback itself wrote the account from /user/installations, so
		// the console never shows a blank account while waiting for the
		// first "installation" webhook to arrive.
		if linkedItems := installationCount(t, owner, "gh-order-b"); len(linkedItems) != 1 || linkedItems[0]["account"] != "acme" {
			t.Fatalf("account after link but before any webhook: %v", linkedItems)
		}

		installed := []byte(`{"action":"created","installation":{"id":1002,"account":{"login":"acme"},"repositories":[{"full_name":"acme/repo"}]}}`)
		if status, result := sendGitHubWebhook(t, owner, "installation", "order-b-delivery-1", installed); status != http.StatusAccepted || result["accepted"] != true {
			t.Fatalf("installation webhook after link: %d %v", status, result)
		} else if result["job_id"] == nil {
			t.Fatalf("a webhook for an already-linked installation must enqueue a sync job: %v", result)
		}

		items := installationCount(t, owner, "gh-order-b")
		if len(items) != 1 || items[0]["installation_id"] != float64(1002) {
			t.Fatalf("installations after webhook: %v", items)
		}
		if n := countJobsOfKind(t, h, "github.sync_repositories"); n != 2 {
			t.Fatalf("expected a second sync job from the post-link webhook, got %d", n)
		}
	})
}

// --- the webhook keeps its mirror without ever resolving an organisation --

func TestGitHubInstallationWebhookIsVerifiedAndUnlinkable(t *testing.T) {
	h := newGitHubHarness(t, []int64{123})
	owner := h.signIn(t, "google", "github-owner", "github-owner@example.test", "Owner")
	owner.createOrg(t, "github-org", "GitHub Org")
	linkInstallation(t, owner, "github-org", 123)

	body := []byte(`{"action":"suspend","installation":{"id":123,"account":{"login":"acme"}}}`)
	status, result := sendGitHubWebhook(t, owner, "installation", "delivery-1", body)
	if status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("webhook: %d %v", status, result)
	}
	if status, result := sendGitHubWebhook(t, owner, "installation", "delivery-1", body); status != http.StatusAccepted || result["reason"] != "duplicate_delivery" {
		t.Fatalf("duplicate webhook was processed twice: %d %v", status, result)
	}
	status, badSig, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/github/webhook", body: json.RawMessage(body), csrf: "-", headers: map[string]string{
		"X-GitHub-Event": "installation", "X-GitHub-Delivery": "delivery-2", "X-Hub-Signature-256": "sha256=bad",
	}})
	if status != http.StatusUnauthorized || badSig["error"] != "invalid_webhook_signature" {
		t.Fatalf("bad signature accepted: %d %v", status, badSig)
	}
	if status, _, _ := owner.call(t, call{method: http.MethodDelete, path: "/api/v1/orgs/github-org/github/installations/123", key: "github-delete"}); status != http.StatusNoContent {
		t.Fatalf("unlink installation: %d", status)
	}
	if items := installationCount(t, owner, "github-org"); len(items) != 0 {
		t.Fatalf("unlink did not remove the installation from this org's list: %v", items)
	}
}

// A "suspend"/"unsuspend" installation payload does not repeat
// installation.repositories (GitHub populates that field only for
// "created") — the same shape of bug the installation_repositories fix
// addresses on its neighbouring action pair. A handler that wrote an empty
// list here would silently wipe the stored repositories on every suspend.
func TestGitHubInstallationSuspendPreservesRepositories(t *testing.T) {
	h := newGitHubHarness(t, []int64{321})
	owner := h.signIn(t, "google", "gh-suspend-owner", "gh-suspend-owner@example.test", "Owner")
	owner.createOrg(t, "gh-suspend", "GitHub Suspend Org")
	linkInstallation(t, owner, "gh-suspend", 321)

	created := []byte(`{"action":"created","installation":{"id":321,"account":{"login":"acme"},"repositories":[{"full_name":"acme/repo"}]}}`)
	if status, result := sendGitHubWebhook(t, owner, "installation", "suspend-delivery-1", created); status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("installation created: %d %v", status, result)
	}

	suspend := []byte(`{"action":"suspend","installation":{"id":321,"account":{"login":"acme"}}}`)
	if status, result := sendGitHubWebhook(t, owner, "installation", "suspend-delivery-2", suspend); status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("installation suspend: %d %v", status, result)
	}
	items := installationCount(t, owner, "gh-suspend")
	if len(items) != 1 || items[0]["suspended"] != true {
		t.Fatalf("suspend did not mark the installation suspended: %v", items)
	}
	repos := items[0]["repositories"].([]any)
	if len(repos) != 1 || repos[0].(map[string]any)["full_name"] != "acme/repo" {
		t.Fatalf("suspend wiped the stored repository list: %v", repos)
	}

	unsuspend := []byte(`{"action":"unsuspend","installation":{"id":321,"account":{"login":"acme"}}}`)
	if status, result := sendGitHubWebhook(t, owner, "installation", "suspend-delivery-3", unsuspend); status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("installation unsuspend: %d %v", status, result)
	}
	items = installationCount(t, owner, "gh-suspend")
	if len(items) != 1 || items[0]["suspended"] != false {
		t.Fatalf("unsuspend did not clear suspended: %v", items)
	}
	repos = items[0]["repositories"].([]any)
	if len(repos) != 1 || repos[0].(map[string]any)["full_name"] != "acme/repo" {
		t.Fatalf("unsuspend wiped the stored repository list: %v", repos)
	}
}

// TestGitHubInstallationRepositoriesEventMergesTheDelta covers the bug named
// in the task: installation_repositories never repeats the account's full
// repository list, only repositories_added/repositories_removed, so the
// handler must merge the delta into the row's existing list rather than
// overwrite it (or clear it) with an absent installation.repositories field.
func TestGitHubInstallationRepositoriesEventMergesTheDelta(t *testing.T) {
	h := newGitHubHarness(t, []int64{789})
	owner := h.signIn(t, "google", "gh-ir-owner", "gh-ir-owner@example.test", "Owner")
	owner.createOrg(t, "gh-ir", "GitHub Installation Repos Org")
	linkInstallation(t, owner, "gh-ir", 789)

	repoNames := func() []string {
		items := installationCount(t, owner, "gh-ir")
		if len(items) != 1 {
			t.Fatalf("installations: %v", items)
		}
		entry := items[0]
		if entry["account"] != "acme" {
			t.Fatalf("account was clobbered: %v", entry)
		}
		var names []string
		for _, r := range entry["repositories"].([]any) {
			names = append(names, r.(map[string]any)["full_name"].(string))
		}
		return names
	}

	installed := []byte(`{"action":"created","installation":{"id":789,"account":{"login":"acme"},"repositories":[{"full_name":"acme/repo"}]}}`)
	if status, result := sendGitHubWebhook(t, owner, "installation", "ir-delivery-1", installed); status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("installation created: %d %v", status, result)
	}
	if got := repoNames(); len(got) != 1 || got[0] != "acme/repo" {
		t.Fatalf("initial repositories: %v", got)
	}

	added := []byte(`{"action":"added","installation":{"id":789,"account":{"login":"acme"}},"repositories_added":[{"full_name":"acme/second"}]}`)
	status, result := sendGitHubWebhook(t, owner, "installation_repositories", "ir-delivery-2", added)
	if status != http.StatusAccepted || result["accepted"] != true || result["job_id"] == nil {
		t.Fatalf("installation_repositories added: %d %v", status, result)
	}
	got := repoNames()
	if len(got) != 2 {
		t.Fatalf("added did not merge with the existing list: %v", got)
	}

	removed := []byte(`{"action":"removed","installation":{"id":789,"account":{"login":"acme"}},"repositories_removed":[{"full_name":"acme/repo"}]}`)
	if status, result := sendGitHubWebhook(t, owner, "installation_repositories", "ir-delivery-3", removed); status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("installation_repositories removed: %d %v", status, result)
	}
	if got := repoNames(); len(got) != 1 || got[0] != "acme/second" {
		t.Fatalf("removed did not drop the right entry: %v", got)
	}
}

// --- pull_request resolution goes only through the link table -------------

func TestGitHubPullRequestWebhookEnqueuesPRReport(t *testing.T) {
	h := newGitHubHarness(t, []int64{456})
	owner := h.signIn(t, "google", "gh-pr-owner", "gh-pr-owner@example.test", "Owner")
	owner.createOrg(t, "gh-pr", "GitHub PR Org")

	installBody := []byte(`{"action":"created","installation":{"id":456,"account":{"login":"acme"},"repositories":[{"full_name":"acme/repo"}]}}`)
	if status, result := sendGitHubWebhook(t, owner, "installation", "install-delivery-1", installBody); status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("installation webhook: %d %v", status, result)
	}

	// Unlinked: a pull_request for this installation is unknown_installation
	// even though the mirror already has the repository, because no
	// organisation is proven to own it yet.
	prBeforeLink := []byte(`{"action":"opened","installation":{"id":456},"repository":{"full_name":"acme/repo"},"pull_request":{"number":1,"head":{"sha":"pre-link"},"base":{"ref":"main"}}}`)
	if status, result := sendGitHubWebhook(t, owner, "pull_request", "pr-before-link", prBeforeLink); status != http.StatusAccepted || result["reason"] != "unknown_installation" {
		t.Fatalf("pull_request before link: %d %v", status, result)
	}

	linkInstallation(t, owner, "gh-pr", 456)

	if status, body, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/gh-pr/repos",
		body: map[string]any{"repo_id": "monorepo", "git_host_url": "https://github.com/acme/repo"}, key: "gh-pr-repo-create"}); status != http.StatusCreated {
		t.Fatalf("create repo: %d %v", status, body)
	}

	prOpened := []byte(`{"action":"opened","installation":{"id":456},"repository":{"full_name":"acme/repo"},"pull_request":{"number":7,"head":{"sha":"abc123"},"base":{"ref":"main"}}}`)
	status, result := sendGitHubWebhook(t, owner, "pull_request", "pr-delivery-1", prOpened)
	if status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("pull_request opened: %d %v", status, result)
	}
	jobID, ok := result["job_id"].(string)
	if !ok || jobID == "" {
		t.Fatalf("pull_request opened did not enqueue a job: %v", result)
	}
	var kind, idempotencyKey string
	var payload []byte
	if err := h.pool.QueryRow(context.Background(), `SELECT kind,idempotency_key,payload FROM gfm.jobs WHERE job_id=$1::uuid`, jobID).
		Scan(&kind, &idempotencyKey, &payload); err != nil {
		t.Fatalf("read job: %v", err)
	}
	if kind != "pr.report" || idempotencyKey != "pr:456:7:abc123" {
		t.Fatalf("job kind/idempotency: kind=%q key=%q", kind, idempotencyKey)
	}
	var decoded map[string]any
	if err := json.Unmarshal(payload, &decoded); err != nil {
		t.Fatalf("decode payload: %v", err)
	}
	if decoded["schema_version"] != "pr.report-1" || decoded["repo_id"] != "monorepo" ||
		decoded["full_name"] != "acme/repo" || decoded["pr_number"] != float64(7) ||
		decoded["head_sha"] != "abc123" || decoded["base_ref"] != "main" ||
		decoded["installation_id"] != float64(456) {
		t.Fatalf("pr.report payload: %v", decoded)
	}

	// The same delivery again must not enqueue a second job.
	if status, result := sendGitHubWebhook(t, owner, "pull_request", "pr-delivery-1", prOpened); status != http.StatusAccepted || result["reason"] != "duplicate_delivery" {
		t.Fatalf("duplicate delivery: %d %v", status, result)
	}
	if n := countJobsOfKind(t, h, "pr.report"); n != 1 {
		t.Fatalf("duplicate delivery changed job count: %d", n)
	}

	// A synchronize push with a new head sha is a distinct job.
	prSync := []byte(`{"action":"synchronize","installation":{"id":456},"repository":{"full_name":"acme/repo"},"pull_request":{"number":7,"head":{"sha":"def456"},"base":{"ref":"main"}}}`)
	status, result = sendGitHubWebhook(t, owner, "pull_request", "pr-delivery-2", prSync)
	if status != http.StatusAccepted || result["accepted"] != true || result["job_id"] == nil {
		t.Fatalf("pull_request synchronize: %d %v", status, result)
	}
	if n := countJobsOfKind(t, h, "pr.report"); n != 2 {
		t.Fatalf("synchronize did not add a second job: %d", n)
	}

	// A closed pull request is ignored.
	prClosed := []byte(`{"action":"closed","installation":{"id":456},"repository":{"full_name":"acme/repo"},"pull_request":{"number":7,"head":{"sha":"ghi789"},"base":{"ref":"main"}}}`)
	if status, result := sendGitHubWebhook(t, owner, "pull_request", "pr-delivery-3", prClosed); status != http.StatusAccepted || result["reason"] != "event_ignored" {
		t.Fatalf("closed action: %d %v", status, result)
	}
	if n := countJobsOfKind(t, h, "pr.report"); n != 2 {
		t.Fatalf("closed action enqueued a job: %d", n)
	}

	// An unmatched repository never gets a 4xx.
	prUnmatched := []byte(`{"action":"opened","installation":{"id":456},"repository":{"full_name":"acme/unregistered"},"pull_request":{"number":9,"head":{"sha":"zzz999"},"base":{"ref":"main"}}}`)
	if status, result := sendGitHubWebhook(t, owner, "pull_request", "pr-delivery-4", prUnmatched); status != http.StatusAccepted || result["accepted"] != false || result["reason"] != "unknown_installation" {
		t.Fatalf("unmatched repository: %d %v", status, result)
	}
	if n := countJobsOfKind(t, h, "pr.report"); n != 2 {
		t.Fatalf("unmatched repository enqueued a job: %d", n)
	}

	// An installation nobody has linked answers the same way.
	prUnlinkedInstallation := []byte(`{"action":"opened","installation":{"id":999999},"repository":{"full_name":"someone/else"},"pull_request":{"number":1,"head":{"sha":"nope"},"base":{"ref":"main"}}}`)
	if status, result := sendGitHubWebhook(t, owner, "pull_request", "pr-delivery-5", prUnlinkedInstallation); status != http.StatusAccepted || result["reason"] != "unknown_installation" {
		t.Fatalf("unlinked installation: %d %v", status, result)
	}
}
