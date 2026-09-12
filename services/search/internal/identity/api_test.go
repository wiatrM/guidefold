package identity_test

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"net/url"
	"os"
	"strconv"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/identity"
	"github.com/wiatrM/guidefold/services/search/internal/importer"
	"github.com/wiatrM/guidefold/services/search/internal/knowledge"
	"github.com/wiatrM/guidefold/services/search/internal/live"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/review"
	"github.com/wiatrM/guidefold/services/search/internal/secrets"
	"github.com/wiatrM/guidefold/services/search/internal/testdb"
	"github.com/wiatrM/guidefold/services/search/internal/usage"
)

func TestMain(m *testing.M) { testdb.Main(m) }

type harness struct {
	pool   *pgxpool.Pool
	svc    *identity.Service
	router *mgmt.Router
	server *httptest.Server
}

func spec(t *testing.T) []byte {
	t.Helper()
	b, e := os.ReadFile("../../openapi/management-v1.yaml")
	if e != nil {
		t.Fatal(e)
	}
	return b
}

func newHarness(t *testing.T) *harness {
	t.Helper()
	return newHarnessWith(t, identity.Config{Mode: identity.ModeDev,
		PublicURL: "http://127.0.0.1", InsecureCookies: true})
}

func newHarnessWith(t *testing.T, cfg identity.Config) *harness {
	t.Helper()
	_, pool := testdb.Start(t)
	svc, e := identity.New(pool, cfg)
	if e != nil {
		t.Fatal(e)
	}
	router := mgmt.New(mgmt.Options{Pool: pool, Resolve: svc.Resolve, OpenAPI: spec(t)})
	svc.Register(router)
	// The import and knowledge modules are mounted here too, because
	// TestDocumentAndServerDescribeTheSameSurface compares the document with the
	// whole router: a partial mount would report every other module's routes as
	// documented-but-missing.
	blobs := importer.NewBlobStore(pool)
	importer.New(pool, blobs).Register(router)
	knowledge.New(pool, blobs, nil, "dev").Register(router)
	usage.New(pool).Register(router)
	credentials := secrets.New(pool, nil, nil)
	credentials.Register(router)
	live.New(pool, live.NewSecretsCredentialSource(credentials)).Register(router)
	reviewer, e := review.New(pool, blobs)
	if e != nil {
		t.Fatal(e)
	}
	reviewer.Register(router)
	server := httptest.NewServer(router)
	t.Cleanup(server.Close)
	return &harness{pool: pool, svc: svc, router: router, server: server}
}

type client struct {
	h     *harness
	http  *http.Client
	csrf  string
	token string
	user  map[string]any
}

func (h *harness) newClient() *client {
	jar, _ := cookiejar.New(nil)
	return &client{h: h, http: &http.Client{Jar: jar,
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}
}

// signIn drives the development provider exactly as a browser would.
func (h *harness) signIn(t *testing.T, provider, subject, email, name string) *client {
	t.Helper()
	c := h.newClient()
	c.devPost(t, url.Values{"provider": {provider}, "subject": {subject},
		"email": {email}, "name": {name}}, http.StatusFound)
	c.refresh(t)
	return c
}

func (c *client) devPost(t *testing.T, form url.Values, want int) *http.Response {
	t.Helper()
	req, e := http.NewRequest(http.MethodPost, c.h.server.URL+"/api/v1/auth/dev",
		strings.NewReader(form.Encode()))
	if e != nil {
		t.Fatal(e)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, e := c.http.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	if resp.StatusCode != want {
		t.Fatalf("dev sign-in: %d, want %d", resp.StatusCode, want)
	}
	return resp
}

func (c *client) refresh(t *testing.T) map[string]any {
	t.Helper()
	status, body, _ := c.call(t, call{method: http.MethodGet, path: "/api/v1/me"})
	if status != http.StatusOK {
		t.Fatalf("/me: %d %v", status, body)
	}
	c.csrf, _ = body["csrf_token"].(string)
	c.user, _ = body["user"].(map[string]any)
	return body
}

func (c *client) userID(t *testing.T) string {
	t.Helper()
	if c.user == nil {
		c.refresh(t)
	}
	id, _ := c.user["id"].(string)
	return id
}

func TestProfileUpdatePersistsDisplayName(t *testing.T) {
	h := newHarness(t)
	c := h.signIn(t, "google", "profile-user", "profile@example.test", "Old Name")
	status, body, _ := c.call(t, call{method: http.MethodPatch, path: "/api/v1/me/profile",
		body: map[string]any{"name": "Ada Lovelace"}, key: "profile-1"})
	if status != http.StatusOK || body["user"].(map[string]any)["name"] != "Ada Lovelace" {
		t.Fatalf("profile update: %d %v", status, body)
	}
	me := c.refresh(t)
	if me["user"].(map[string]any)["name"] != "Ada Lovelace" {
		t.Fatalf("profile was not persisted: %v", me)
	}
	status, body, _ = c.call(t, call{method: http.MethodPatch, path: "/api/v1/me/profile",
		body: map[string]any{"name": ""}, key: "profile-empty"})
	if status != http.StatusBadRequest || body["error"] != "invalid_profile" {
		t.Fatalf("empty profile name was accepted: %d %v", status, body)
	}
}

type call struct {
	method, path string
	body         any
	key          string // Idempotency-Key
	csrf         string // "-" suppresses the header
	headers      map[string]string
}

func (c *client) call(t *testing.T, x call) (int, map[string]any, http.Header) {
	t.Helper()
	var payload io.Reader
	if x.body != nil {
		raw, e := json.Marshal(x.body)
		if e != nil {
			t.Fatal(e)
		}
		payload = bytes.NewReader(raw)
	}
	req, e := http.NewRequest(x.method, c.h.server.URL+x.path, payload)
	if e != nil {
		t.Fatal(e)
	}
	if x.body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	switch {
	case x.csrf == "-":
	case x.csrf != "":
		req.Header.Set("X-CSRF-Token", x.csrf)
	case c.csrf != "":
		req.Header.Set("X-CSRF-Token", c.csrf)
	}
	if x.key != "" {
		req.Header.Set("Idempotency-Key", x.key)
	}
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	for k, v := range x.headers {
		req.Header.Set(k, v)
	}
	resp, e := c.http.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	out := map[string]any{}
	if len(raw) > 0 && raw[0] == '{' {
		if e := json.Unmarshal(raw, &out); e != nil {
			t.Fatalf("%s %s: %v: %s", x.method, x.path, e, raw)
		}
	}
	return resp.StatusCode, out, resp.Header
}

func (c *client) createOrg(t *testing.T, slug, name string) string {
	t.Helper()
	status, body, _ := c.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": name, "slug": slug}, key: "create-" + slug})
	if status != http.StatusCreated {
		t.Fatalf("create org: %d %v", status, body)
	}
	return body["org_id"].(string)
}

func TestSignInThenMe(t *testing.T) {
	h := newHarness(t)
	c := h.signIn(t, "google", "u-1", "ada@example.test", "Ada")
	body := c.refresh(t)
	if body["schema_version"] != mgmt.SchemaVersion {
		t.Fatalf("schema_version %v", body["schema_version"])
	}
	user := body["user"].(map[string]any)
	if user["email"] != "ada@example.test" || user["name"] != "Ada" {
		t.Fatalf("user %v", user)
	}
	if c.csrf == "" {
		t.Fatal("no csrf token")
	}
	identities := body["identities"].([]any)
	if len(identities) != 1 || identities[0].(map[string]any)["provider"] != "google" {
		t.Fatalf("identities %v", identities)
	}
	if len(body["orgs"].([]any)) != 0 {
		t.Fatal("a new account already has organisations")
	}
	access := body["access"].(map[string]any)
	if access["valid_for_s"].(float64) != 45 {
		t.Fatalf("access %v", access)
	}
}

func TestSessionCookieIsHardened(t *testing.T) {
	h := newHarness(t)
	c := h.newClient()
	resp := c.devPost(t, url.Values{"provider": {"github"}, "subject": {"u-2"},
		"email": {"grace@example.test"}, "name": {"Grace"}}, http.StatusFound)
	var session *http.Cookie
	for _, cookie := range resp.Cookies() {
		if cookie.Name == identity.SessionCookie {
			session = cookie
		}
	}
	if session == nil {
		t.Fatal("no session cookie")
	}
	if !session.HttpOnly || session.SameSite != http.SameSiteLaxMode || session.Path != "/" {
		t.Fatalf("cookie attributes: %+v", session)
	}
	if session.Secure {
		t.Fatal("Secure was set although GUIDEFOLD_INSECURE_COOKIES is on for local http")
	}
	if strings.Contains(resp.Header.Get("Set-Cookie"), "grace@example.test") {
		t.Fatal("the cookie carries the address")
	}
	// Signing out revokes the session server-side, not only in the browser.
	c.refresh(t)
	if status, body, _ := c.call(t, call{method: http.MethodPost, path: "/api/v1/auth/logout"}); status != 204 {
		t.Fatalf("logout: %d %v", status, body)
	}
	c.http.Jar.SetCookies(mustURL(t, c.h.server.URL),
		[]*http.Cookie{{Name: identity.SessionCookie, Value: session.Value}})
	if status, _, _ := c.call(t, call{method: http.MethodGet, path: "/api/v1/me"}); status != 401 {
		t.Fatalf("a revoked session still worked: %d", status)
	}
}

func mustURL(t *testing.T, raw string) *url.URL {
	t.Helper()
	u, e := url.Parse(raw)
	if e != nil {
		t.Fatal(e)
	}
	return u
}

// A second provider with the same address is a different account until the
// person links it deliberately from the session that owns the first one.
func TestMatchingEmailNeverAutoLinks(t *testing.T) {
	h := newHarness(t)
	first := h.signIn(t, "google", "same-1", "shared@example.test", "Shared")
	second := h.signIn(t, "github", "same-2", "shared@example.test", "Shared")
	if first.userID(t) == second.userID(t) {
		t.Fatal("a matching e-mail merged two accounts")
	}
	body := first.refresh(t)
	suggestions := body["link_suggestions"].([]any)
	if len(suggestions) != 1 || suggestions[0].(map[string]any)["provider"] != "github" {
		t.Fatalf("link_suggestions %v", suggestions)
	}

	status, out, _ := first.call(t, call{method: http.MethodPost,
		path: "/api/v1/me/identities/link/start", body: map[string]any{"provider": "github"}})
	if status != 200 {
		t.Fatalf("link start: %d %v", status, out)
	}
	loginURL := out["login_url"].(string)
	state := mustURL(t, loginURL).Query().Get("state")
	if state == "" {
		t.Fatalf("no state in %q", loginURL)
	}
	// A third, unused github identity links to the *current* user.
	first.devPost(t, url.Values{"provider": {"github"}, "subject": {"same-3"},
		"email": {"shared@example.test"}, "name": {"Shared"}, "state": {state}}, http.StatusFound)
	body = first.refresh(t)
	providers := []string{}
	for _, raw := range body["identities"].([]any) {
		providers = append(providers, raw.(map[string]any)["provider"].(string))
	}
	if len(providers) != 2 {
		t.Fatalf("identities after linking: %v", providers)
	}
	if first.userID(t) == second.userID(t) {
		t.Fatal("linking merged the other account")
	}
}

func TestLinkingAnIdentityOwnedByAnotherUserIsRefused(t *testing.T) {
	h := newHarness(t)
	first := h.signIn(t, "google", "own-1", "one@example.test", "One")
	h.signIn(t, "github", "own-2", "two@example.test", "Two")
	status, out, _ := first.call(t, call{method: http.MethodPost,
		path: "/api/v1/me/identities/link/start", body: map[string]any{"provider": "github"}})
	if status != 200 {
		t.Fatal(status, out)
	}
	state := mustURL(t, out["login_url"].(string)).Query().Get("state")
	req, _ := http.NewRequest(http.MethodPost, h.server.URL+"/api/v1/auth/dev",
		strings.NewReader(url.Values{"provider": {"github"}, "subject": {"own-2"},
			"email": {"two@example.test"}, "state": {state}}.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, e := first.http.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusConflict {
		t.Fatalf("claiming another user's identity: %d", resp.StatusCode)
	}
}

func TestOrganisationMembershipLifecycle(t *testing.T) {
	h := newHarness(t)
	owner := h.signIn(t, "google", "own", "owner@example.test", "Owner")
	orgID := owner.createOrg(t, "acme", "Acme")

	status, body, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/acme"})
	if status != 200 || body["my_role"] != "owner" {
		t.Fatalf("get org: %d %v", status, body)
	}
	counts := body["counts"].(map[string]any)
	if counts["members"].(float64) != 1 {
		t.Fatalf("counts %v", counts)
	}

	status, invitation, _ := owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/acme/invitations",
		body: map[string]any{"email": "member@example.test", "role": "member"}, key: "inv-1"})
	if status != http.StatusCreated {
		t.Fatalf("invite: %d %v", status, invitation)
	}
	status, list, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/acme/invitations"})
	if status != http.StatusOK || len(list["items"].([]any)) != 1 || list["items"].([]any)[0].(map[string]any)["status"] != "pending" {
		t.Fatalf("invitation lifecycle list: %d %v", status, list)
	}
	acceptPath := mustURL(t, invitation["accept_url"].(string)).Path
	status, _, header := h.newClient().call(t, call{method: http.MethodGet, path: acceptPath})
	if status != http.StatusFound || header.Get("Location") != "http://127.0.0.1/invitations/"+strings.TrimSuffix(strings.TrimPrefix(acceptPath, "/api/v1/invitations/"), "/accept")+"/accept" {
		t.Fatalf("invitation landing: %d location=%q", status, header.Get("Location"))
	}

	member := h.signIn(t, "github", "mem", "member@example.test", "Member")
	status, body, _ = member.call(t, call{method: http.MethodPost, path: acceptPath, key: "accept-1"})
	if status != 200 || body["role"] != "member" {
		t.Fatalf("accept: %d %v", status, body)
	}
	if status, body, _ = member.call(t, call{method: http.MethodPost, path: acceptPath,
		key: "accept-2"}); status != 409 {
		t.Fatalf("an invitation was accepted twice: %d %v", status, body)
	}
	status, second, _ := owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/acme/invitations",
		body: map[string]any{"email": "revoked@example.test", "role": "member"}, key: "inv-revoke"})
	if status != http.StatusCreated {
		t.Fatalf("second invite: %d %v", status, second)
	}
	status, _, _ = owner.call(t, call{method: http.MethodDelete,
		path: "/api/v1/orgs/acme/invitations/" + second["invitation_id"].(string), key: "revoke-1"})
	if status != http.StatusNoContent {
		t.Fatalf("revoke invitation: %d", status)
	}
	status, list, _ = owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/acme/invitations"})
	if status != http.StatusOK {
		t.Fatalf("lifecycle after revoke: %d %v", status, list)
	}
	items := list["items"].([]any)
	if items[0].(map[string]any)["status"] != "revoked" {
		t.Fatalf("revoked invitation status: %v", items[0])
	}

	status, body, _ = owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/acme/members"})
	if status != 200 || len(body["items"].([]any)) != 2 {
		t.Fatalf("members: %d %v", status, body)
	}

	// A member reads, but does not administer.
	status, body, _ = member.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/acme/invitations",
		body: map[string]any{"email": "third@example.test"}, key: "inv-2"})
	if status != 403 || body["error"] != "forbidden" {
		t.Fatalf("a member invited someone: %d %v", status, body)
	}
	status, body, _ = member.call(t, call{method: http.MethodDelete,
		path: "/api/v1/orgs/" + orgID + "/members/" + owner.userID(t), key: "rm-1"})
	if status != 403 {
		t.Fatalf("a member removed the owner: %d %v", status, body)
	}

	// The last owner cannot be demoted or removed.
	status, body, _ = owner.call(t, call{method: http.MethodPatch,
		path: "/api/v1/orgs/acme/members/" + owner.userID(t),
		body: map[string]any{"role": "member"}, key: "demote-1"})
	if status != 409 || body["error"] != "last_owner_protected" {
		t.Fatalf("the last owner was demoted: %d %v", status, body)
	}
	status, body, _ = owner.call(t, call{method: http.MethodDelete,
		path: "/api/v1/orgs/acme/members/" + owner.userID(t), key: "self-remove"})
	if status != 409 || body["error"] != "last_owner_protected" {
		t.Fatalf("the last owner was removed: %d %v", status, body)
	}

	// Promote the member, then the original owner may step down.
	status, body, _ = owner.call(t, call{method: http.MethodPatch,
		path: "/api/v1/orgs/acme/members/" + member.userID(t),
		body: map[string]any{"role": "owner"}, key: "promote-1"})
	if status != 200 || body["role"] != "owner" {
		t.Fatalf("promote: %d %v", status, body)
	}
	status, body, _ = owner.call(t, call{method: http.MethodDelete,
		path: "/api/v1/orgs/acme/members/" + owner.userID(t), key: "self-remove-2"})
	if status != 204 {
		t.Fatalf("step down: %d %v", status, body)
	}
	if status, _, _ = owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/acme"}); status != 403 {
		t.Fatalf("a removed owner still reads the organisation: %d", status)
	}
}

func TestTeamGroupingLifecycle(t *testing.T) {
	h := newHarness(t)
	owner := h.signIn(t, "google", "team-owner", "team-owner@example.test", "Owner")
	owner.createOrg(t, "teams", "Teams")
	status, created, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/teams/teams", body: map[string]any{"name": "Platform"}, key: "team-1"})
	if status != http.StatusCreated {
		t.Fatalf("create team: %d %v", status, created)
	}
	teamID := created["team_id"].(string)
	member := h.signIn(t, "github", "team-member", "team-member@example.test", "Member")
	inviteStatus, invitation, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/teams/invitations", body: map[string]any{"email": "team-member@example.test", "role": "member"}, key: "team-invite"})
	if inviteStatus != http.StatusCreated {
		t.Fatalf("invite team member: %d %v", inviteStatus, invitation)
	}
	acceptPath := mustURL(t, invitation["accept_url"].(string)).Path
	if status, _, _ := member.call(t, call{method: http.MethodPost, path: acceptPath, key: "team-accept"}); status != http.StatusOK {
		t.Fatalf("accept team invitation: %d", status)
	}
	userID := member.userID(t)
	if status, _, _ := owner.call(t, call{method: http.MethodPut, path: "/api/v1/orgs/teams/teams/" + teamID + "/members/" + userID, key: "team-add"}); status != http.StatusNoContent {
		t.Fatalf("add team member: %d", status)
	}
	status, listed, _ := member.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/teams/teams"})
	if status != http.StatusOK || len(listed["items"].([]any)) != 1 {
		t.Fatalf("list teams: %d %v", status, listed)
	}
	team := listed["items"].([]any)[0].(map[string]any)
	if len(team["members"].([]any)) != 1 || team["members"].([]any)[0].(map[string]any)["user_id"] != userID {
		t.Fatalf("team member missing: %v", team)
	}
	if status, _, _ := member.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/teams/teams", body: map[string]any{"name": "Nope"}, key: "team-deny"}); status != http.StatusForbidden {
		t.Fatalf("member created a team: %d", status)
	}
	if status, _, _ := owner.call(t, call{method: http.MethodDelete, path: "/api/v1/orgs/teams/teams/" + teamID + "/members/" + userID, key: "team-remove"}); status != http.StatusNoContent {
		t.Fatalf("remove team member: %d", status)
	}
}

func TestRepositoryACLAndReviewerAssignmentAreScoped(t *testing.T) {
	h := newHarness(t)
	owner := h.signIn(t, "google", "repo-acl-owner", "repo-acl-owner@example.test", "Owner")
	owner.createOrg(t, "repo-acl", "Repo ACL")
	if status, _, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/repo-acl/repos", body: map[string]any{"repo_id": "monorepo"}, key: "repo-create"}); status != http.StatusCreated {
		t.Fatalf("create repo: %d", status)
	}
	member := h.signIn(t, "github", "repo-acl-member", "repo-acl-member@example.test", "Member")
	_, invitation, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/repo-acl/invitations", body: map[string]any{"email": "repo-acl-member@example.test", "role": "member"}, key: "repo-acl-invite"})
	accept := invitation["accept_url"].(string)
	acceptURL, err := url.Parse(accept)
	if err != nil {
		t.Fatal(err)
	}
	if status, _, _ := member.call(t, call{method: http.MethodPost, path: acceptURL.RequestURI(), key: "repo-acl-accept"}); status != http.StatusOK {
		t.Fatalf("accept: %d", status)
	}
	userID := member.userID(t)
	path := "/api/v1/orgs/repo-acl/repos/monorepo/access/" + userID
	if status, _, _ := owner.call(t, call{method: http.MethodPut, path: path, body: map[string]any{"access": "read"}, key: "repo-acl-grant"}); status != http.StatusOK {
		t.Fatalf("grant access: %d", status)
	}
	if status, _, _ := member.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/repo-acl/repos/monorepo/imports"}); status != http.StatusOK {
		t.Fatalf("explicit read access was denied: %d", status)
	}
	if status, _, _ := owner.call(t, call{method: http.MethodPut, path: "/api/v1/orgs/repo-acl/repos/monorepo/reviewers/" + userID, key: "repo-reviewer"}); status != http.StatusNoContent {
		t.Fatalf("assign reviewer: %d", status)
	}
	status, reviewers, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/repo-acl/repos/monorepo/reviewers"})
	if status != http.StatusOK || len(reviewers["items"].([]any)) != 1 {
		t.Fatalf("reviewer list: %d %v", status, reviewers)
	}
	if status, _, _ := owner.call(t, call{method: http.MethodDelete, path: path, key: "repo-acl-revoke"}); status != http.StatusNoContent {
		t.Fatalf("revoke access: %d", status)
	}
	if status, listed, _ := member.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/repo-acl/repos"}); status != http.StatusOK || len(listed["items"].([]any)) != 0 {
		t.Fatalf("revoked member still saw the repository in the list: %d %v", status, listed)
	}
	if status, _, _ := member.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/repo-acl/repos/monorepo/imports"}); status != http.StatusForbidden {
		t.Fatalf("revoked member retained repository access: %d", status)
	}
}

func TestGitHubInstallationWebhookIsVerifiedAndScoped(t *testing.T) {
	h := newHarnessWith(t, identity.Config{Mode: identity.ModeDev, PublicURL: "http://127.0.0.1", InsecureCookies: true, GitHubWebhookSecret: "secret"})
	owner := h.signIn(t, "google", "github-owner", "github-owner@example.test", "Owner")
	owner.createOrg(t, "github-org", "GitHub Org")
	body := []byte(`{"action":"created","organization":{"login":"github-org"},"installation":{"id":123,"account":{"login":"acme"},"repositories":[{"full_name":"acme/repo"}]}}`)
	sum := hmac.New(sha256.New, []byte("secret"))
	_, _ = sum.Write(body)
	status, result, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/github/webhook", body: json.RawMessage(body), csrf: "-", headers: map[string]string{
		"X-GitHub-Event": "installation", "X-GitHub-Delivery": "delivery-1", "X-Hub-Signature-256": "sha256=" + hex.EncodeToString(sum.Sum(nil)),
	}})
	if status != http.StatusAccepted || result["accepted"] != true {
		t.Fatalf("webhook: %d %v", status, result)
	}
	jobID, ok := result["job_id"].(string)
	if !ok || jobID == "" {
		t.Fatalf("webhook did not enqueue an ascend job: %v", result)
	}
	var kind, state string
	if err := h.pool.QueryRow(context.Background(), `SELECT kind,state FROM gfm.jobs WHERE job_id=$1::uuid`, jobID).Scan(&kind, &state); err != nil || kind != "ascend.run" || state != "queued" {
		t.Fatalf("webhook job: kind=%q state=%q err=%v", kind, state, err)
	}
	if status, result, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/github/webhook", body: json.RawMessage(body), csrf: "-", headers: map[string]string{
		"X-GitHub-Event": "installation", "X-GitHub-Delivery": "delivery-1", "X-Hub-Signature-256": "sha256=" + hex.EncodeToString(sum.Sum(nil)),
	}}); status != http.StatusAccepted || result["reason"] != "duplicate_delivery" {
		t.Fatalf("duplicate webhook was processed twice: %d %v", status, result)
	}
	status, listed, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/github-org/github/installations"})
	if status != http.StatusOK || len(listed["items"].([]any)) != 1 {
		t.Fatalf("installations: %d %v", status, listed)
	}
	if status, body, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/github/webhook", body: json.RawMessage(body), csrf: "-", headers: map[string]string{
		"X-GitHub-Event": "installation", "X-GitHub-Delivery": "delivery-2", "X-Hub-Signature-256": "sha256=bad",
	}}); status != http.StatusUnauthorized || body["error"] != "invalid_webhook_signature" {
		t.Fatalf("bad signature accepted: %d %v", status, body)
	}
	if status, _, _ := owner.call(t, call{method: http.MethodDelete, path: "/api/v1/orgs/github-org/github/installations/123", key: "github-delete"}); status != http.StatusNoContent {
		t.Fatalf("delete installation: %d", status)
	}
}

// Access to another organisation and to one that does not exist must be
// indistinguishable.
func TestCrossOrganisationAccessLeaksNothing(t *testing.T) {
	h := newHarness(t)
	insider := h.signIn(t, "google", "in", "in@example.test", "In")
	insider.createOrg(t, "private-org", "Private")
	outsider := h.signIn(t, "github", "out", "out@example.test", "Out")

	strip := func(m map[string]any) map[string]any {
		delete(m, "request_id")
		return m
	}
	statusReal, real, _ := outsider.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/private-org"})
	statusGhost, ghost, _ := outsider.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/no-such-org"})
	if statusReal != 403 || statusGhost != 403 {
		t.Fatalf("statuses %d %d", statusReal, statusGhost)
	}
	a, _ := json.Marshal(strip(real))
	b, _ := json.Marshal(strip(ghost))
	if string(a) != string(b) {
		t.Fatalf("the two 403 bodies differ:\n%s\n%s", a, b)
	}
	for _, path := range []string{"/api/v1/orgs/private-org/members",
		"/api/v1/orgs/private-org/installations", "/api/v1/orgs/private-org/audit"} {
		status, body, _ := outsider.call(t, call{method: http.MethodGet, path: path})
		if status != 403 {
			t.Fatalf("%s: %d %v", path, status, body)
		}
		if strings.Contains(strings.ToLower(mustJSON(t, body)), "private") {
			t.Fatalf("%s leaked the organisation name: %v", path, body)
		}
	}
	if status, body, _ := outsider.call(t, call{method: http.MethodGet, path: "/api/v1/orgs"}); status != 200 ||
		len(body["items"].([]any)) != 0 {
		t.Fatalf("outsider's org list: %d %v", status, body)
	}
}

func mustJSON(t *testing.T, v any) string {
	t.Helper()
	b, e := json.Marshal(v)
	if e != nil {
		t.Fatal(e)
	}
	return string(b)
}

func TestCSRFIsRequiredForSessionMutations(t *testing.T) {
	h := newHarness(t)
	owner := h.signIn(t, "google", "csrf", "csrf@example.test", "C")
	status, body, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "N", "slug": "no-csrf"}, key: "k", csrf: "-"})
	if status != 403 || body["error"] != "csrf_token_mismatch" {
		t.Fatalf("mutation without the token: %d %v", status, body)
	}
	status, body, _ = owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "N", "slug": "bad-csrf"}, key: "k2", csrf: "not-the-token"})
	if status != 403 {
		t.Fatalf("mutation with a wrong token: %d %v", status, body)
	}
	// A GET needs no token, and the right token works.
	if status, _, _ = owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs", csrf: "-"}); status != 200 {
		t.Fatalf("GET required a csrf token: %d", status)
	}
	if status, body, _ = owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "N", "slug": "with-csrf"}, key: "k3"}); status != 201 {
		t.Fatalf("mutation with the token: %d %v", status, body)
	}
}

func TestIdempotencyReplaysAndDetectsMismatch(t *testing.T) {
	h := newHarness(t)
	owner := h.signIn(t, "google", "idem", "idem@example.test", "I")
	body := map[string]any{"name": "Repeat", "slug": "repeat-org"}
	status, first, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: body, key: "same-key"})
	if status != 201 {
		t.Fatalf("first: %d %v", status, first)
	}
	status, second, header := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: body, key: "same-key"})
	if status != 201 || second["org_id"] != first["org_id"] {
		t.Fatalf("replay: %d %v vs %v", status, second, first)
	}
	if header.Get("Idempotent-Replay") != "true" {
		t.Fatal("the replay was not marked")
	}
	status, out, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "Different", "slug": "other-org"}, key: "same-key"})
	if status != 409 || out["error"] != "idempotency_payload_mismatch" {
		t.Fatalf("mismatch: %d %v", status, out)
	}
	status, out, _ = owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "Keyless", "slug": "keyless-org"}})
	if status != 400 || out["error"] != "idempotency_key_required" {
		t.Fatalf("missing key: %d %v", status, out)
	}
	// A failed mutation releases the key so the client can correct and retry.
	status, out, _ = owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "", "slug": "invalid-org"}, key: "retry-key"})
	if status != 400 {
		t.Fatalf("expected a validation failure: %d %v", status, out)
	}
	status, out, _ = owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "Fixed", "slug": "fixed-org"}, key: "retry-key"})
	if status != 201 {
		t.Fatalf("the key stayed locked after a failure: %d %v", status, out)
	}
	// The same key belongs to one principal only.
	other := h.signIn(t, "github", "idem2", "idem2@example.test", "J")
	status, out, _ = other.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "Theirs", "slug": "theirs-org"}, key: "same-key"})
	if status != 201 {
		t.Fatalf("another principal's key collided: %d %v", status, out)
	}
}

func TestDeviceFlowEndToEnd(t *testing.T) {
	h := newHarness(t)
	cli := h.newClient() // the CLI has no session
	status, start, _ := cli.call(t, call{method: http.MethodPost, path: "/api/v1/auth/device"})
	if status != 200 {
		t.Fatalf("device start: %d %v", status, start)
	}
	deviceCode := start["device_code"].(string)
	userCode := start["user_code"].(string)
	if start["interval"].(float64) != 5 || start["expires_in"].(float64) != 600 {
		t.Fatalf("device parameters %v", start)
	}
	if !strings.Contains(start["verification_uri"].(string), userCode) {
		t.Fatalf("verification_uri %v", start["verification_uri"])
	}

	poll := func() (int, map[string]any) {
		status, body, _ := cli.call(t, call{method: http.MethodPost,
			path: "/api/v1/auth/device/token", body: map[string]any{"device_code": deviceCode}})
		return status, body
	}
	status, body := poll()
	if status != 400 || body["error"] != "authorization_pending" {
		t.Fatalf("first poll: %d %v", status, body)
	}
	status, body = poll()
	if status != 400 || body["error"] != "slow_down" {
		t.Fatalf("second poll should be told to slow down: %d %v", status, body)
	}

	person := h.signIn(t, "google", "dev-flow", "cli@example.test", "CLI")
	status, body, _ = person.call(t, call{method: http.MethodPost,
		path: "/api/v1/auth/device/approve", body: map[string]any{"user_code": userCode}})
	if status != 200 || body["state"] != "approved" {
		t.Fatalf("approve: %d %v", status, body)
	}

	status, token := poll()
	if status != 200 {
		t.Fatalf("after approval: %d %v", status, token)
	}
	secret := token["token"].(string)
	if !strings.HasPrefix(secret, identity.TokenPrefix) {
		t.Fatalf("token %q", secret)
	}
	if token["user"].(map[string]any)["id"] != person.userID(t) {
		t.Fatalf("token belongs to %v", token["user"])
	}
	// One approval yields exactly one secret.
	status, body = poll()
	if status != 400 || body["error"] != "expired_token" {
		t.Fatalf("the device code was reusable: %d %v", status, body)
	}

	// The personal token acts for the person, without a session or CSRF.
	bearer := h.newClient()
	bearer.token = secret
	status, me, _ := bearer.call(t, call{method: http.MethodGet, path: "/api/v1/me"})
	if status != 200 || me["user"].(map[string]any)["id"] != person.userID(t) {
		t.Fatalf("personal token /me: %d %v", status, me)
	}
	if me["csrf_token"] != "" {
		t.Fatal("a bearer principal was given a csrf token")
	}
	status, out, _ := bearer.call(t, call{method: http.MethodPost, path: "/api/v1/orgs",
		body: map[string]any{"name": "From CLI", "slug": "from-cli"}, key: "cli-org"})
	if status != 201 {
		t.Fatalf("personal token mutation: %d %v", status, out)
	}
}

func TestDeviceFlowDenial(t *testing.T) {
	h := newHarness(t)
	cli := h.newClient()
	_, start, _ := cli.call(t, call{method: http.MethodPost, path: "/api/v1/auth/device"})
	person := h.signIn(t, "google", "deny", "deny@example.test", "D")
	status, body, _ := person.call(t, call{method: http.MethodPost, path: "/api/v1/auth/device/deny",
		body: map[string]any{"user_code": start["user_code"]}})
	if status != 200 || body["state"] != "denied" {
		t.Fatalf("deny: %d %v", status, body)
	}
	status, body, _ = cli.call(t, call{method: http.MethodPost, path: "/api/v1/auth/device/token",
		body: map[string]any{"device_code": start["device_code"]}})
	if status != 400 || body["error"] != "access_denied" {
		t.Fatalf("after denial: %d %v", status, body)
	}
	status, body, _ = cli.call(t, call{method: http.MethodPost, path: "/api/v1/auth/device/token",
		body: map[string]any{"device_code": "gf_not_a_code"}})
	if status != 400 || body["error"] != "expired_token" {
		t.Fatalf("unknown device code: %d %v", status, body)
	}
	// Approving needs a session.
	if status, _, _ = cli.call(t, call{method: http.MethodPost, path: "/api/v1/auth/device/approve",
		body: map[string]any{"user_code": start["user_code"]}}); status != 401 {
		t.Fatalf("an anonymous caller approved a device code: %d", status)
	}
}

func TestInstallationTokens(t *testing.T) {
	h := newHarness(t)
	owner := h.signIn(t, "google", "inst", "inst@example.test", "I")
	owner.createOrg(t, "tokens-org", "Tokens")

	status, created, _ := owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/tokens-org/installations", key: "i1",
		body: map[string]any{"name": "Claude Code", "repo_id": "monorepo",
			"scopes": []string{"use", "search"}, "harness": "claude"}})
	if status != http.StatusCreated {
		t.Fatalf("create: %d %v", status, created)
	}
	secret := created["token"].(string)
	if !strings.HasPrefix(secret, identity.TokenPrefix) {
		t.Fatalf("token %q", secret)
	}
	scopes := created["scopes"].([]any)
	if len(scopes) != 2 || scopes[0] != "search" || scopes[1] != "use" {
		t.Fatalf("scopes %v", scopes)
	}
	// Creating an installation registers its repository for the organisation.
	repos, e := h.svc.Repos(t.Context(), created["org_id"].(string))
	if e != nil {
		t.Fatal(e)
	}
	if len(repos) != 1 || repos[0] != "monorepo" {
		t.Fatalf("repos %v", repos)
	}

	status, list, _ := owner.call(t, call{method: http.MethodGet,
		path: "/api/v1/orgs/tokens-org/installations"})
	if status != 200 {
		t.Fatalf("list: %d %v", status, list)
	}
	if strings.Contains(mustJSON(t, list), secret) {
		t.Fatal("the list returned the secret")
	}
	items := list["items"].([]any)
	if len(items) != 1 {
		t.Fatalf("items %v", items)
	}
	item := items[0].(map[string]any)
	if item["harness"] != "claude" || item["installation_id"] != created["installation_id"] {
		t.Fatalf("item %v", item)
	}

	status, ci, _ := owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/tokens-org/installations", key: "i2",
		body: map[string]any{"name": "CI", "kind": "ci"}})
	if status != 201 || ci["scopes"].([]any)[0] != "validate" {
		t.Fatalf("ci token: %d %v", status, ci)
	}
	status, bad, _ := owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/tokens-org/installations", key: "i3",
		body: map[string]any{"name": "Bad", "scopes": []string{"admin"}}})
	if status != 400 || bad["error"] != "invalid_scopes" {
		t.Fatalf("an unknown scope was accepted: %d %v", status, bad)
	}
	status, bad, _ = owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/tokens-org/installations", key: "i4",
		body: map[string]any{"name": "Bad CI", "kind": "ci", "scopes": []string{"search"}}})
	if status != 400 {
		t.Fatalf("a CI token took a delivery scope: %d %v", status, bad)
	}

	status, revoked, _ := owner.call(t, call{method: http.MethodDelete,
		path: "/api/v1/orgs/tokens-org/installations/" + created["installation_id"].(string),
		key:  "r1"})
	if status != 204 || len(revoked) != 0 {
		t.Fatalf("revoke: %d %v", status, revoked)
	}
	bearer := h.newClient()
	bearer.token = secret
	if status, body, _ := bearer.call(t, call{method: http.MethodGet, path: "/api/v1/me"}); status != 401 {
		t.Fatalf("a revoked token still authenticated: %d %v", status, body)
	}
}

// An installation token is not a person: it never reaches the management API.
func TestInstallationTokenCannotAdminister(t *testing.T) {
	h := newHarness(t)
	owner := h.signIn(t, "google", "adm", "adm@example.test", "A")
	owner.createOrg(t, "guard-org", "Guard")
	_, created, _ := owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/guard-org/installations", key: "g1",
		body: map[string]any{"name": "Adapter", "scopes": []string{"search"}}})
	bearer := h.newClient()
	bearer.token = created["token"].(string)
	for _, x := range []call{
		{method: http.MethodGet, path: "/api/v1/me"},
		{method: http.MethodGet, path: "/api/v1/orgs"},
		{method: http.MethodGet, path: "/api/v1/orgs/guard-org/members"},
		{method: http.MethodPost, path: "/api/v1/orgs/guard-org/installations", key: "g2",
			body: map[string]any{"name": "Another", "scopes": []string{"search"}}},
	} {
		status, body, _ := bearer.call(t, x)
		if status != 403 {
			t.Fatalf("%s %s: %d %v", x.method, x.path, status, body)
		}
	}
}

func TestAuditRecordsEveryMutation(t *testing.T) {
	h := newHarness(t)
	owner := h.signIn(t, "google", "aud", "aud@example.test", "A")
	owner.createOrg(t, "audited", "Audited")
	owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/audited/invitations",
		body: map[string]any{"email": "someone@example.test"}, key: "a1"})
	owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/audited/installations",
		body: map[string]any{"name": "A", "scopes": []string{"search"}}, key: "a2"})

	status, body, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/audited/audit"})
	if status != 200 {
		t.Fatalf("audit: %d %v", status, body)
	}
	actions := map[string]bool{}
	for _, raw := range body["items"].([]any) {
		entry := raw.(map[string]any)
		actions[entry["action"].(string)] = true
		if entry["request_id"] == "" {
			t.Fatal("an audit entry has no request id")
		}
	}
	for _, want := range []string{"org.create", "invitation.create", "installation.create"} {
		if !actions[want] {
			t.Errorf("no audit entry for %s: %v", want, actions)
		}
	}
	// The audit log records the invitation, never the invited address.
	if strings.Contains(mustJSON(t, body), "someone@example.test") {
		t.Fatal("the audit log carries an e-mail address")
	}
}

// TestAuditIsMemberScoped covers Contract 1.3.0's GET {org_base}/audit: an
// owner still reads every row, a member reads only the rows whose actor is
// their own principal id, and that filter composes with cursor paging.
func TestAuditIsMemberScoped(t *testing.T) {
	h := newHarness(t)
	owner := h.signIn(t, "google", "scope-own", "scope-owner@example.test", "Owner")
	orgID := owner.createOrg(t, "scoped", "Scoped")

	status, invitation, _ := owner.call(t, call{method: http.MethodPost,
		path: "/api/v1/orgs/scoped/invitations",
		body: map[string]any{"email": "scope-member@example.test", "role": "member"}, key: "inv-scoped"})
	if status != http.StatusCreated {
		t.Fatalf("invite: %d %v", status, invitation)
	}
	acceptPath := mustURL(t, invitation["accept_url"].(string)).Path

	member := h.signIn(t, "github", "scope-mem", "scope-member@example.test", "Member")
	if status, body, _ := member.call(t, call{method: http.MethodPost, path: acceptPath, key: "accept-scoped"}); status != 200 {
		t.Fatalf("accept: %d %v", status, body)
	}
	// invitation.accept above is audited under the member's own actor id; this
	// installation.create is audited under the owner's — the org now has rows
	// by two actors.
	if status, body, _ := owner.call(t, call{method: http.MethodPost, path: "/api/v1/orgs/scoped/installations",
		body: map[string]any{"name": "A", "scopes": []string{"search"}}, key: "install-scoped"}); status != http.StatusCreated {
		t.Fatalf("installation: %d %v", status, body)
	}

	ownerID := "user:" + owner.userID(t)
	memberID := "user:" + member.userID(t)

	// The owner reads rows by both actors.
	status, body, _ := owner.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/scoped/audit"})
	if status != 200 {
		t.Fatalf("owner audit: %d %v", status, body)
	}
	actors := map[string]bool{}
	for _, raw := range body["items"].([]any) {
		actors[raw.(map[string]any)["actor"].(string)] = true
	}
	if !actors[ownerID] || !actors[memberID] {
		t.Fatalf("the owner should see rows from both actors, saw: %v", actors)
	}

	// The member reads only their own rows.
	status, body, _ = member.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/scoped/audit"})
	if status != 200 {
		t.Fatalf("member audit: %d %v", status, body)
	}
	items, _ := body["items"].([]any)
	if len(items) == 0 {
		t.Fatal("the member's own invitation.accept row is missing")
	}
	for _, raw := range items {
		entry := raw.(map[string]any)
		if entry["actor"].(string) != memberID {
			t.Fatalf("a member saw another actor's row: %v", entry)
		}
	}

	// Seed extra rows directly in gfm.audit, interleaving actors, so the
	// cursor parameter has to combine with the actor filter rather than just
	// pass through an empty next_cursor.
	ctx := context.Background()
	insert := `INSERT INTO gfm.audit(org_id,actor,action,entity,request_id)
 VALUES($1::uuid,$2,$3,$4,'seed') RETURNING audit_id`
	var memberSeeded []int64
	for i := 0; i < 3; i++ {
		var id int64
		if e := h.pool.QueryRow(ctx, insert, orgID, memberID, "seed.member", "seed:m").Scan(&id); e != nil {
			t.Fatal(e)
		}
		memberSeeded = append(memberSeeded, id)
		if e := h.pool.QueryRow(ctx, insert, orgID, ownerID, "seed.owner", "seed:o").Scan(&id); e != nil {
			t.Fatal(e)
		}
	}

	// Without a cursor the member sees their invitation.accept row plus all
	// three seeded rows — four rows total, never an owner row.
	status, body, _ = member.call(t, call{method: http.MethodGet, path: "/api/v1/orgs/scoped/audit"})
	if status != 200 {
		t.Fatalf("member audit: %d %v", status, body)
	}
	items, _ = body["items"].([]any)
	if len(items) != 4 {
		t.Fatalf("member audit has %d rows, want 4 (1 accept + 3 seeded): %v", len(items), items)
	}
	for _, raw := range items {
		if raw.(map[string]any)["actor"].(string) != memberID {
			t.Fatalf("saw another actor's row: %v", raw)
		}
	}

	// A cursor set to the oldest seeded member row excludes it and the two
	// newer seeded rows, and the owner rows interleaved between them, leaving
	// only the member's earlier invitation.accept row — the actor filter and
	// the cursor filter must both apply to the same page.
	status, body, _ = member.call(t, call{method: http.MethodGet,
		path: "/api/v1/orgs/scoped/audit?cursor=" + strconv.FormatInt(memberSeeded[0], 10)})
	if status != 200 {
		t.Fatalf("member audit with cursor: %d %v", status, body)
	}
	items, _ = body["items"].([]any)
	if len(items) != 1 {
		t.Fatalf("cursor before the seeded rows should leave exactly the accept row, got %d: %v", len(items), items)
	}
	entry := items[0].(map[string]any)
	if entry["actor"].(string) != memberID || entry["action"].(string) != "invitation.accept" {
		t.Fatalf("cursor page returned the wrong row: %v", entry)
	}

	// The same cursor for the owner still returns rows by both actors, never
	// filtered to one.
	status, body, _ = owner.call(t, call{method: http.MethodGet,
		path: "/api/v1/orgs/scoped/audit?cursor=" + strconv.FormatInt(memberSeeded[0], 10)})
	if status != 200 {
		t.Fatalf("owner audit with cursor: %d %v", status, body)
	}
	items, _ = body["items"].([]any)
	ownerActors := map[string]bool{}
	for _, raw := range items {
		ownerActors[raw.(map[string]any)["actor"].(string)] = true
	}
	if !ownerActors[ownerID] || !ownerActors[memberID] {
		t.Fatalf("the owner's cursor page should still show both actors: %v", ownerActors)
	}
}

func TestProvidersAndLoginRedirect(t *testing.T) {
	h := newHarness(t)
	c := h.newClient()
	status, body, _ := c.call(t, call{method: http.MethodGet, path: "/api/v1/auth/providers"})
	if status != 200 || body["mode"] != "dev" {
		t.Fatalf("providers: %d %v", status, body)
	}
	if len(body["providers"].([]any)) != 2 {
		t.Fatalf("providers %v", body["providers"])
	}
	resp, e := c.http.Get(h.server.URL + "/api/v1/auth/login/google?return_to=/organization")
	if e != nil {
		t.Fatal(e)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusFound {
		t.Fatalf("login: %d", resp.StatusCode)
	}
	if !strings.HasPrefix(resp.Header.Get("Location"), "/api/v1/auth/dev?state=") {
		t.Fatalf("dev login went to %q", resp.Header.Get("Location"))
	}
	// An absolute return_to is replaced by the root rather than followed.
	form := url.Values{"provider": {"google"}, "subject": {"redir"},
		"email": {"r@example.test"}, "return_to": {"https://evil.example/"}}
	resp = c.devPost(t, form, http.StatusFound)
	if resp.Header.Get("Location") != "/" {
		t.Fatalf("open redirect: %q", resp.Header.Get("Location"))
	}
	// The form itself is served only in development mode.
	page, e := c.http.Get(h.server.URL + "/api/v1/auth/dev")
	if e != nil {
		t.Fatal(e)
	}
	defer page.Body.Close()
	raw, _ := io.ReadAll(page.Body)
	if page.StatusCode != 200 || !strings.Contains(string(raw), `name="subject"`) {
		t.Fatalf("dev form: %d %s", page.StatusCode, raw)
	}
}

func TestWorkOSDeploymentExchangesTheCode(t *testing.T) {
	var authenticated struct {
		ClientID string `json:"client_id"`
		Secret   string `json:"client_secret"`
		Grant    string `json:"grant_type"`
		Code     string `json:"code"`
	}
	provider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/user_management/authenticate" {
			w.WriteHeader(404)
			return
		}
		_ = json.NewDecoder(r.Body).Decode(&authenticated)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"user":{"id":"workos-user-1","email":"kay@example.test",
"first_name":"Kay","last_name":"Ng"}}`))
	}))
	defer provider.Close()

	h := newHarnessWith(t, identity.Config{Mode: identity.ModeWorkOS,
		PublicURL: "https://guidefold.example", InsecureCookies: true,
		WorkOSAPIKey: "sk_test_key", WorkOSClientID: "client_123", WorkOSBase: provider.URL})
	c := h.newClient()
	resp, e := c.http.Get(h.server.URL + "/api/v1/auth/login/github?return_to=/organization")
	if e != nil {
		t.Fatal(e)
	}
	resp.Body.Close()
	location := mustURL(t, resp.Header.Get("Location"))
	if !strings.HasPrefix(resp.Header.Get("Location"), provider.URL+"/user_management/authorize") {
		t.Fatalf("authorize URL %q", resp.Header.Get("Location"))
	}
	q := location.Query()
	if q.Get("provider") != "GitHubOAuth" || q.Get("client_id") != "client_123" ||
		q.Get("redirect_uri") != "https://guidefold.example/api/v1/auth/callback" {
		t.Fatalf("authorize parameters %v", q)
	}
	if q.Get("scope") != "" {
		t.Fatalf("the authorize URL requested scopes: %v", q)
	}
	state := q.Get("state")

	callback, e := c.http.Get(h.server.URL + "/api/v1/auth/callback?code=code-1&state=" + url.QueryEscape(state))
	if e != nil {
		t.Fatal(e)
	}
	callback.Body.Close()
	if callback.StatusCode != http.StatusFound || callback.Header.Get("Location") != "/organization" {
		t.Fatalf("callback: %d %q", callback.StatusCode, callback.Header.Get("Location"))
	}
	if authenticated.Code != "code-1" || authenticated.ClientID != "client_123" ||
		authenticated.Secret != "sk_test_key" || authenticated.Grant != "authorization_code" {
		t.Fatalf("exchange %+v", authenticated)
	}
	body := c.refresh(t)
	if body["user"].(map[string]any)["email"] != "kay@example.test" ||
		body["user"].(map[string]any)["name"] != "Kay Ng" {
		t.Fatalf("user %v", body["user"])
	}
	// The state is single use, so a replayed callback cannot mint a session.
	replay, e := c.http.Get(h.server.URL + "/api/v1/auth/callback?code=code-1&state=" + url.QueryEscape(state))
	if e != nil {
		t.Fatal(e)
	}
	replay.Body.Close()
	if replay.StatusCode != 400 {
		t.Fatalf("state replay: %d", replay.StatusCode)
	}
	// The development form does not exist in a WorkOS deployment.
	if status, _, _ := c.call(t, call{method: http.MethodGet, path: "/api/v1/auth/dev"}); status != 404 {
		t.Fatalf("dev form in workos mode: %d", status)
	}
}

// G6 — login CSRF. The state row proves that someone started a login, not that
// this browser did. An attacker who starts one and hands the victim the
// resulting callback URL would otherwise sign the victim into the attacker's
// account. A callback that arrives without the browser's state cookie is
// refused, and the state is not consumed by the attempt.
func TestCallbackRefusesAStateFromAnotherBrowser(t *testing.T) {
	provider := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"user":{"id":"workos-user-9","email":"mallory@example.test",
"first_name":"Mal","last_name":"Ory"}}`))
	}))
	defer provider.Close()
	h := newHarnessWith(t, identity.Config{Mode: identity.ModeWorkOS,
		PublicURL: "https://guidefold.example", InsecureCookies: true,
		WorkOSAPIKey: "sk_test_key", WorkOSClientID: "client_123", WorkOSBase: provider.URL})

	attacker := h.newClient()
	resp, e := attacker.http.Get(h.server.URL + "/api/v1/auth/login/github")
	if e != nil {
		t.Fatal(e)
	}
	resp.Body.Close()
	state := mustURL(t, resp.Header.Get("Location")).Query().Get("state")
	if state == "" {
		t.Fatal("the login produced no state")
	}
	if !strings.Contains(resp.Header.Get("Set-Cookie"), identity.AuthStateCookie) {
		t.Fatalf("the login set no state cookie: %q", resp.Header.Get("Set-Cookie"))
	}

	// The victim's browser never started this login, so it carries no cookie.
	victim := h.newClient()
	forged, e := victim.http.Get(h.server.URL + "/api/v1/auth/callback?code=code-9&state=" +
		url.QueryEscape(state))
	if e != nil {
		t.Fatal(e)
	}
	forged.Body.Close()
	if forged.StatusCode != http.StatusBadRequest {
		t.Fatalf("a callback from another browser was accepted: %d %q",
			forged.StatusCode, forged.Header.Get("Location"))
	}
	for _, cookie := range forged.Cookies() {
		if cookie.Name == identity.SessionCookie && cookie.Value != "" {
			t.Fatal("the refused callback still started a session")
		}
	}
	// The state was not consumed, so the browser that started the login can
	// still finish it.
	completed, e := attacker.http.Get(h.server.URL + "/api/v1/auth/callback?code=code-9&state=" +
		url.QueryEscape(state))
	if e != nil {
		t.Fatal(e)
	}
	completed.Body.Close()
	if completed.StatusCode != http.StatusSeeOther && completed.StatusCode != http.StatusFound {
		t.Fatalf("the originating browser could not finish its own login: %d", completed.StatusCode)
	}
}

func TestWorkOSRequiresCredentials(t *testing.T) {
	_, pool := testdb.Start(t)
	if _, e := identity.New(pool, identity.Config{Mode: identity.ModeWorkOS}); e == nil {
		t.Fatal("a WorkOS deployment started without an API key")
	}
	if _, e := identity.New(pool, identity.Config{Mode: "something-else"}); e == nil {
		t.Fatal("an unknown auth mode was accepted")
	}
	if _, e := identity.New(pool, identity.Config{}); e == nil {
		t.Fatal("a service started without a named auth mode")
	}
}

// TestAuthModeFailsClosed is the S1 regression: an environment that does not
// name GUIDEFOLD_AUTH must not resolve to the development provider. It needs no
// database, so it also runs where PostgreSQL is unavailable.
func TestAuthModeFailsClosed(t *testing.T) {
	t.Setenv("GUIDEFOLD_AUTH", "")
	cfg, e := identity.ConfigFromEnv()
	if e == nil {
		t.Fatalf("an empty environment yielded mode %q instead of an error", cfg.Mode)
	}
	if cfg.Mode == identity.ModeDev {
		t.Fatalf("an empty environment defaulted to the development provider")
	}
	t.Setenv("GUIDEFOLD_AUTH", "Dev")
	if _, e := identity.ConfigFromEnv(); e == nil {
		t.Fatal("an unknown auth mode was accepted from the environment")
	}
	t.Setenv("GUIDEFOLD_AUTH", identity.ModeWorkOS)
	cfg, e = identity.ConfigFromEnv()
	if e != nil || cfg.Mode != identity.ModeWorkOS {
		t.Fatalf("workos mode: %v %q", e, cfg.Mode)
	}
	t.Setenv("GUIDEFOLD_AUTH", identity.ModeDev)
	cfg, e = identity.ConfigFromEnv()
	if e != nil || cfg.Mode != identity.ModeDev {
		t.Fatalf("dev mode: %v %q", e, cfg.Mode)
	}
}

// TestDevRoutesAreNotMountedOutsideDevMode proves the /auth/dev pair is absent
// from the routing table itself, not merely refused by its handler.
func TestDevRoutesAreNotMountedOutsideDevMode(t *testing.T) {
	_, pool := testdb.Start(t)
	svc, e := identity.New(pool, identity.Config{Mode: identity.ModeWorkOS,
		WorkOSAPIKey: "sk_test_key", WorkOSClientID: "client_123"})
	if e != nil {
		t.Fatal(e)
	}
	router := mgmt.New(mgmt.Options{Pool: pool, Resolve: svc.Resolve})
	svc.Register(router)
	for _, method := range []string{http.MethodGet, http.MethodPost} {
		rec := httptest.NewRecorder()
		router.ServeHTTP(rec, httptest.NewRequest(method, "/api/v1/auth/dev", nil))
		if rec.Code != http.StatusNotFound {
			t.Fatalf("%s /api/v1/auth/dev in workos mode: %d", method, rec.Code)
		}
	}
}
