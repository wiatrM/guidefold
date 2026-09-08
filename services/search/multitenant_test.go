package main

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/identity"
	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/schema"
	"github.com/wiatrM/guidefold/services/search/internal/testdb"
	"github.com/wiatrM/guidefold/services/search/internal/usage"
)

func TestMain(m *testing.M) { testdb.Main(m) }

const fixturePolicySHA = "0000000000000000000000000000000000000000000000000000000000000001"

// tenantFixture is one organisation's published snapshot. The two tenants in
// these tests publish the *same* repo_id and the *same* URNs, so any answer
// that mixes them is visible in the card names and bodies.
type tenantFixture struct {
	OrgID     string
	RepoID    string
	Snapshot  string
	Marker    string
	Revisions map[string]string
	Token     string
}

func fixtureNodes(t *testing.T) M {
	t.Helper()
	raw, e := os.ReadFile("testdata/policy.json")
	if e != nil {
		t.Fatal(e)
	}
	v, e := strictJSON(raw)
	if e != nil {
		t.Fatal(e)
	}
	return obj(obj(v)["nodes"])
}

// publishFixture writes one snapshot directly. The publisher itself is covered
// by its own tests; what matters here is that two tenants hold rows with the
// same identifiers so the request path has to keep them apart.
func publishFixture(t *testing.T, pool *pgxpool.Pool, tenant, repo, marker string) *tenantFixture {
	t.Helper()
	ctx := context.Background()
	nodes := fixtureNodes(t)
	cards := M{
		"u:01": M{"urn": "u:01", "node": "alpha", "name": marker + "-retry-1",
			"description": marker + " retry kafka", "digest": "retry database",
			"triggers": []any{"postgres retry"}, "negative_triggers": []any{},
			"requires": []any{}, "refines": []any{}, "status": "active", "replaced_by": nil},
		"u:02": M{"urn": "u:02", "node": "alpha", "name": marker + "-retry-2",
			"description": marker + " retry kafka", "digest": "retry database",
			"triggers": []any{"postgres retry"}, "negative_triggers": []any{},
			"requires": []any{}, "refines": []any{}, "status": "active", "replaced_by": nil},
	}
	snapshot := "repository:" + hash([]byte(tenant+"\x00"+repo))
	fixture := &tenantFixture{OrgID: tenant, RepoID: repo, Snapshot: snapshot,
		Marker: marker, Revisions: map[string]string{}}
	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `INSERT INTO gf.snapshots(tenant,repo,snapshot_id,revision,cli_sha,nodes,weights)
 VALUES($1,$2,$3,$4,$5,$6,$7)`, tenant, repo, snapshot, "rev-"+marker, fixturePolicySHA,
		string(canonical(nodes)), "{}"); e != nil {
		t.Fatal(e)
	}
	order := keys(cards)
	for _, u := range order {
		card := obj(cards[u])
		metadata := M{}
		for k, v := range card {
			metadata[k] = v
		}
		revision := hash(pythonJSON(card, false))
		fixture.Revisions[u] = revision
		body := "body-" + marker + "-" + u
		search := strings.Join([]string{str(card["name"]), str(card["description"]), body}, "\n")
		if _, e = tx.Exec(ctx, `INSERT INTO gf.skills
 (tenant,repo,snapshot_id,urn,skill_revision,node,status,metadata,body,search_text)
 VALUES($1,$2,$3,$4,$5,$6,'active',$7,$8,$9)`, tenant, repo, snapshot, u, revision,
			str(card["node"]), json.RawMessage(canonical(metadata)), []byte(body), search); e != nil {
			t.Fatal(e)
		}
	}
	if _, e = tx.Exec(ctx, `INSERT INTO gf.router_indexes(tenant,repo,snapshot_id,index_sha,n_docs,n_terms)
 VALUES($1,$2,$3,$4,$5,1)`, tenant, repo, snapshot, "index-"+marker, len(order)); e != nil {
		t.Fatal(e)
	}
	packed := make([]byte, 12*len(order))
	for i := range order {
		binary.LittleEndian.PutUint32(packed[i*12:], uint32(i))
		binary.LittleEndian.PutUint64(packed[i*12+4:], uint64(4096-i))
	}
	if _, e = tx.Exec(ctx, `INSERT INTO gf.router_terms(tenant,repo,snapshot_id,term,postings)
 VALUES($1,$2,$3,'retry',$4)`, tenant, repo, snapshot, packed); e != nil {
		t.Fatal(e)
	}
	if _, e = tx.Exec(ctx, `INSERT INTO gf.heads(tenant,repo,snapshot_id) VALUES($1,$2,$3)`,
		tenant, repo, snapshot); e != nil {
		t.Fatal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
	return fixture
}

func exec(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) {
	t.Helper()
	ctx := context.Background()
	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, sql, args...); e != nil {
		t.Fatal(e)
	}
	if e = tx.Commit(ctx); e != nil {
		t.Fatal(e)
	}
}

func makeOrg(t *testing.T, pool *pgxpool.Pool, slug string) string {
	t.Helper()
	id := identity.NewID()
	exec(t, pool, `INSERT INTO gfm.orgs(org_id,slug,name) VALUES($1::uuid,$2,$3)`, id, slug, slug)
	return id
}

func makeToken(t *testing.T, pool *pgxpool.Pool, kind, orgID, repoID, userID string, scopes []string) string {
	t.Helper()
	secret := "gf_" + hash([]byte(kind+orgID+repoID+userID+identity.NewID()))
	exec(t, pool, `INSERT INTO gfm.tokens(token_id,token_sha256,kind,user_id,org_id,repo_id,scopes,name)
 VALUES($1::uuid,$2,$3,$4::uuid,$5::uuid,$6,$7,'test')`,
		identity.NewID(), hash([]byte(secret)), kind, nilIfEmpty(userID), nilIfEmpty(orgID),
		nilIfEmpty(repoID), scopes)
	return secret
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

type deliveryHarness struct {
	app    *App
	server *httptest.Server
	pool   *pgxpool.Pool
	svc    *identity.Service
}

func newDeliveryHarness(t *testing.T) *deliveryHarness {
	t.Helper()
	_, pool := testdb.Start(t)
	validator, e := newValidator("../../tools/serve_spike/contracts/harness-service-v1.1.schema.json")
	if e != nil {
		t.Fatal(e)
	}
	svc, e := identity.New(pool, identity.Config{Mode: identity.ModeDev,
		PublicURL: "http://127.0.0.1", InsecureCookies: true})
	if e != nil {
		t.Fatal(e)
	}
	router := mgmt.New(mgmt.Options{Pool: pool, Resolve: svc.Resolve})
	svc.Register(router)
	usage.New(pool).Register(router)
	store := &Store{Pool: pool, Tenant: "operator-tenant", Repo: "meridian",
		PolicySHA: fixturePolicySHA, LexicalEngine: "router", catalogs: newCatalogCache(catalogCacheSize)}
	app := &App{Store: store, Validator: validator, Token: strings.Repeat("o", 40),
		Identity: svc, Management: router,
		Slots: make(chan struct{}, 64), EventSlots: make(chan struct{}, 16)}
	server := httptest.NewServer(app)
	t.Cleanup(server.Close)
	return &deliveryHarness{app: app, server: server, pool: pool, svc: svc}
}

func (h *deliveryHarness) post(t *testing.T, path, token, body string, headers map[string]string) (int, M) {
	t.Helper()
	req, e := http.NewRequest(http.MethodPost, h.server.URL+path, strings.NewReader(body))
	if e != nil {
		t.Fatal(e)
	}
	req.Header.Set("Content-Type", "application/json")
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, e := http.DefaultClient.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	var out M
	_ = json.NewDecoder(resp.Body).Decode(&out)
	return resp.StatusCode, out
}

// twoTenants publishes the same repository twice, under two organisations.
func twoTenants(t *testing.T, h *deliveryHarness) (*tenantFixture, *tenantFixture) {
	t.Helper()
	a := makeOrg(t, h.pool, "org-a")
	b := makeOrg(t, h.pool, "org-b")
	exec(t, h.pool, `INSERT INTO gfm.repos(org_id,repo_id) VALUES($1::uuid,'meridian')`, a)
	exec(t, h.pool, `INSERT INTO gfm.repos(org_id,repo_id) VALUES($1::uuid,'meridian')`, b)
	fa := publishFixture(t, h.pool, a, "meridian", "alpha")
	fb := publishFixture(t, h.pool, b, "meridian", "bravo")
	fa.Token = makeToken(t, h.pool, mgmt.SourceInstallation, a, "meridian", "", []string{"search", "use", "events"})
	fb.Token = makeToken(t, h.pool, mgmt.SourceInstallation, b, "meridian", "", []string{"search", "use", "events"})
	return fa, fb
}

func TestSearchAndUseNeverCrossOrganisations(t *testing.T) {
	h := newDeliveryHarness(t)
	a, b := twoTenants(t, h)
	// Warm both catalogs first: a shared cache is exactly where a leak would hide.
	for _, f := range []*tenantFixture{a, b} {
		status, body := h.post(t, "/v1/search", f.Token, `{"query":"retry","node":"alpha"}`, nil)
		if status != 200 {
			t.Fatalf("%s warm-up: %d %v", f.Marker, status, body)
		}
	}
	if n := h.app.Store.catalogs.len(); n != 2 {
		t.Fatalf("catalog cache holds %d entries, expected one per tenant", n)
	}
	var wg sync.WaitGroup
	for i := 0; i < 24; i++ {
		f := a
		other := b
		if i%2 == 1 {
			f, other = b, a
		}
		wg.Add(1)
		go func(f, other *tenantFixture) {
			defer wg.Done()
			status, body := h.post(t, "/v1/search", f.Token, `{"query":"retry","node":"alpha"}`, nil)
			if status != 200 {
				t.Errorf("search %s: %d %v", f.Marker, status, body)
				return
			}
			if str(body["snapshot"]) != f.Snapshot {
				t.Errorf("search %s returned snapshot %v", f.Marker, body["snapshot"])
			}
			cards := arr(body["cards"])
			if len(cards) == 0 {
				t.Errorf("search %s returned no cards", f.Marker)
			}
			for _, raw := range cards {
				card := obj(raw)
				name := str(card["name"])
				if !strings.HasPrefix(name, f.Marker) {
					t.Errorf("search %s returned card %q", f.Marker, name)
				}
				if strings.Contains(name, other.Marker) {
					t.Errorf("search %s leaked %s card %q", f.Marker, other.Marker, name)
				}
				if got := str(card["revision"]); got != f.Revisions[str(card["skill_id"])] {
					t.Errorf("search %s revision %s", f.Marker, got)
				}
			}
			use := fmt.Sprintf(`{"skill_id":"u:01","revision":%q}`, f.Revisions["u:01"])
			status, body = h.post(t, "/v1/use", f.Token, use, nil)
			if status != 200 {
				t.Errorf("use %s: %d %v", f.Marker, status, body)
				return
			}
			if got := str(body["body"]); got != "body-"+f.Marker+"-u:01" {
				t.Errorf("use %s returned body %q", f.Marker, got)
			}
		}(f, other)
	}
	wg.Wait()
	// The other tenant's revision must not open the door either.
	status, body := h.post(t, "/v1/use", a.Token,
		fmt.Sprintf(`{"skill_id":"u:01","revision":%q}`, b.Revisions["u:01"]), nil)
	if status != 409 || str(body["error"]) != "revision_mismatch" {
		t.Fatalf("cross-tenant revision accepted: %d %v", status, body)
	}
}

func TestTelemetryCountersStayWithTheirTenant(t *testing.T) {
	h := newDeliveryHarness(t)
	a, b := twoTenants(t, h)
	event := func(id string) string {
		return fmt.Sprintf(`{"events":[{"event_id":%q,"event_type":"card_injected","schema_version":"1.0",
"environment":"dev","occurred_at":"2026-09-06T00:00:00Z","sequence":1,"producer":"test",
"adapter_version":"1.0.0","exposure_id":"x1","skill_id":"u:01","revision":"r","position":1,
"surface":"context","delivery_evidence":"rendered","search_id":"s1"}]}`, id)
	}
	for _, x := range []struct {
		f  *tenantFixture
		id string
	}{{a, "e-alpha"}, {b, "e-bravo"}} {
		status, body := h.post(t, "/v1/events:batch", x.f.Token, event(x.id), nil)
		if status != 200 {
			t.Fatalf("%s: %d %v", x.f.Marker, status, body)
		}
		if len(arr(body["accepted"])) != 1 {
			t.Fatalf("%s not accepted: %v", x.f.Marker, body)
		}
	}
	for _, x := range []struct{ org, id string }{{a.OrgID, "e-alpha"}, {b.OrgID, "e-bravo"}} {
		var count int
		if e := h.pool.QueryRow(context.Background(),
			`SELECT count(*) FROM gf.events WHERE tenant_id=$1 AND event_id=$2`,
			x.org, []byte(x.id)).Scan(&count); e != nil {
			t.Fatal(e)
		}
		if count != 1 {
			t.Fatalf("event %s not stored under its own tenant", x.id)
		}
	}
	var crossed int
	if e := h.pool.QueryRow(context.Background(),
		`SELECT count(*) FROM gf.events WHERE tenant_id=$1 AND event_id=$2`,
		a.OrgID, []byte("e-bravo")).Scan(&crossed); e != nil {
		t.Fatal(e)
	}
	if crossed != 0 {
		t.Fatal("telemetry landed under the wrong tenant")
	}
}

func TestRevokedTokenIsRejectedOnTheNextRequest(t *testing.T) {
	h := newDeliveryHarness(t)
	a, _ := twoTenants(t, h)
	if status, _ := h.post(t, "/v1/search", a.Token, `{"query":"retry","node":"alpha"}`, nil); status != 200 {
		t.Fatalf("baseline %d", status)
	}
	exec(t, h.pool, `UPDATE gfm.tokens SET revoked_at=now() WHERE token_sha256=$1`, hash([]byte(a.Token)))
	status, body := h.post(t, "/v1/search", a.Token, `{"query":"retry","node":"alpha"}`, nil)
	if status != 401 || str(body["error"]) != "unauthorized" {
		t.Fatalf("revocation not immediate: %d %v", status, body)
	}
}

func TestInstallationTokenIsBoundToItsRepository(t *testing.T) {
	h := newDeliveryHarness(t)
	a, _ := twoTenants(t, h)
	exec(t, h.pool, `INSERT INTO gfm.repos(org_id,repo_id) VALUES($1::uuid,'other')`, a.OrgID)
	bound := makeToken(t, h.pool, mgmt.SourceInstallation, a.OrgID, "meridian", "", []string{"search", "use"})
	body := `{"schema_version":"1.1","query":"retry","workspace":{"repo_id":"other","cwd":"services/alpha"}}`
	status, out := h.post(t, "/v1/search", bound, body, nil)
	if status != 403 || str(out["error"]) != "repository_not_permitted" {
		t.Fatalf("a token bound to meridian searched another repository: %d %v", status, out)
	}
	status, out = h.post(t, "/v1/search", bound, `{"query":"retry","node":"alpha"}`,
		map[string]string{repoHeader: "other"})
	if status != 403 {
		t.Fatalf("the header bypassed the binding: %d %v", status, out)
	}
}

func TestScopesGateTheDeliveryEndpoints(t *testing.T) {
	h := newDeliveryHarness(t)
	a, _ := twoTenants(t, h)
	searchOnly := makeToken(t, h.pool, mgmt.SourceInstallation, a.OrgID, "meridian", "", []string{"search"})
	if status, _ := h.post(t, "/v1/search", searchOnly, `{"query":"retry","node":"alpha"}`, nil); status != 200 {
		t.Fatalf("search scope rejected")
	}
	status, body := h.post(t, "/v1/use", searchOnly,
		fmt.Sprintf(`{"skill_id":"u:01","revision":%q}`, a.Revisions["u:01"]), nil)
	if status != 403 || str(body["error"]) != "insufficient_token_scope" {
		t.Fatalf("use without the use scope: %d %v", status, body)
	}
	status, body = h.post(t, "/v1/events:batch", searchOnly, `{"events":[]}`, nil)
	if status != 403 || str(body["error"]) != "insufficient_token_scope" {
		t.Fatalf("telemetry without the events scope: %d %v", status, body)
	}
}

// A signed-in member of one organisation cannot reach another, even when the
// repository identifier in the request matches.
func TestSessionCannotReachAnotherOrganisation(t *testing.T) {
	h := newDeliveryHarness(t)
	a, b := twoTenants(t, h)
	jar := newJar(t)
	client := &http.Client{Jar: jar, CheckRedirect: func(*http.Request, []*http.Request) error {
		return http.ErrUseLastResponse
	}}
	form := strings.NewReader("provider=google&subject=member-a&email=a@example.test&name=A")
	req, e := http.NewRequest(http.MethodPost, h.server.URL+"/api/v1/auth/dev", form)
	if e != nil {
		t.Fatal(e)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, e := client.Do(req)
	if e != nil {
		t.Fatal(e)
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusFound {
		t.Fatalf("dev sign-in: %d", resp.StatusCode)
	}
	var userID string
	if e = h.pool.QueryRow(context.Background(),
		`SELECT user_id::text FROM gfm.identities WHERE provider='google' AND subject='member-a'`).
		Scan(&userID); e != nil {
		t.Fatal(e)
	}
	exec(t, h.pool, `INSERT INTO gfm.memberships(org_id,user_id,role) VALUES($1::uuid,$2::uuid,'member')`,
		a.OrgID, userID)

	search := func(org string) (int, M) {
		body := `{"schema_version":"1.1","query":"retry","workspace":{"repo_id":"meridian","cwd":"services/alpha"}}`
		req, e := http.NewRequest(http.MethodPost, h.server.URL+"/v1/search", strings.NewReader(body))
		if e != nil {
			t.Fatal(e)
		}
		req.Header.Set("Content-Type", "application/json")
		if org != "" {
			req.Header.Set(orgHeader, org)
		}
		resp, e := client.Do(req)
		if e != nil {
			t.Fatal(e)
		}
		defer resp.Body.Close()
		var out M
		_ = json.NewDecoder(resp.Body).Decode(&out)
		return resp.StatusCode, out
	}
	status, out := search(a.OrgID)
	if status != 200 {
		t.Fatalf("own organisation refused: %d %v", status, out)
	}
	for _, card := range arr(out["cards"]) {
		if !strings.HasPrefix(str(obj(card)["name"]), a.Marker) {
			t.Fatalf("session read another tenant's cards: %v", out["cards"])
		}
	}
	status, out = search(b.OrgID)
	if status != 403 || str(out["error"]) != "organization_not_permitted" {
		t.Fatalf("session reached organisation B: %d %v", status, out)
	}
	status, out = search("org-b")
	if status != 403 {
		t.Fatalf("the slug reached organisation B: %d %v", status, out)
	}
	// A member of exactly one organisation does not have to name it.
	if status, out = search(""); status != 200 {
		t.Fatalf("single-membership default failed: %d %v", status, out)
	}
}

func TestOperatorTokenKeepsItsConfiguredIdentity(t *testing.T) {
	h := newDeliveryHarness(t)
	fixture := publishFixture(t, h.pool, "operator-tenant", "meridian", "opr")
	status, body := h.post(t, "/v1/search", h.app.Token, `{"query":"retry","node":"alpha"}`, nil)
	if status != 200 {
		t.Fatalf("operator search: %d %v", status, body)
	}
	if str(body["snapshot"]) != fixture.Snapshot {
		t.Fatalf("operator read %v", body["snapshot"])
	}
	// No management row exists for the operator tenant; that must not matter.
	var repos int
	if e := h.pool.QueryRow(context.Background(), `SELECT count(*) FROM gfm.repos`).Scan(&repos); e != nil {
		t.Fatal(e)
	}
	if repos != 0 {
		t.Fatalf("the operator path created management rows")
	}
}

func TestCatalogCacheIsBoundedAndKeyedBySnapshot(t *testing.T) {
	cache := newCatalogCache(2)
	first := &Catalog{ID: "s1"}
	if got := cache.put(catalogKey("a", "r", "s1"), first); got != first {
		t.Fatal("put returned a different catalog")
	}
	again := cache.put(catalogKey("a", "r", "s1"), &Catalog{ID: "s1"})
	if again != first {
		t.Fatal("a concurrent load replaced the resident catalog")
	}
	cache.put(catalogKey("b", "r", "s1"), &Catalog{ID: "s1"})
	cache.put(catalogKey("c", "r", "s1"), &Catalog{ID: "s1"})
	if cache.len() != 2 {
		t.Fatalf("cache grew to %d", cache.len())
	}
	if cache.get(catalogKey("a", "r", "s1")) != nil {
		t.Fatal("the least recently used entry survived eviction")
	}
	if cache.get(catalogKey("a", "r", "s2")) != nil {
		t.Fatal("a different snapshot matched the same key")
	}
}

func newJar(t *testing.T) http.CookieJar {
	t.Helper()
	jar, e := cookiejar.New(nil)
	if e != nil {
		t.Fatal(e)
	}
	return jar
}

// On the plain PostgreSQL profile the router engine serves normally and
// readiness reports the missing extension as a state, not an error.
func TestReadinessReportsAnAbsentPgSearch(t *testing.T) {
	h := newDeliveryHarness(t)
	caps, e := schema.Detect(context.Background(), h.pool)
	if e != nil {
		t.Fatal(e)
	}
	h.app.Store.Caps = caps
	h.app.Store.Version = caps.PgSearch
	fixture := publishFixture(t, h.pool, "operator-tenant", "meridian", "ready")
	resp, e := http.Get(h.server.URL + "/health/ready")
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	var body M
	if e = json.NewDecoder(resp.Body).Decode(&body); e != nil {
		t.Fatal(e)
	}
	if resp.StatusCode != 200 || body["ready"] != true {
		t.Fatalf("ready: %d %v", resp.StatusCode, body)
	}
	if caps.HasPgSearch() {
		t.Skip("this cluster has pg_search")
	}
	if body["pg_search_version"] != schema.PgSearchAbsent {
		t.Fatalf("pg_search_version %v, want %q", body["pg_search_version"], schema.PgSearchAbsent)
	}
	if body["backend"] != "router_bm25f_v1" || str(body["snapshot"]) != fixture.Snapshot {
		t.Fatalf("readiness payload %v", body)
	}
}

// A tenant with nothing published yet (fresh GitHub import, nothing reviewed
// or published) must still report ready: the management API (identity,
// import, knowledge, review, usage) never reads the retrieval catalog. Only
// the retrieval surface is unconfigured, and that is a state, not an error —
// otherwise the Kubernetes readiness probe would keep the pod out of Service
// rotation forever, even though every mgmt/import/review route works.
func TestReadinessWithoutAnyPublishedSnapshot(t *testing.T) {
	h := newDeliveryHarness(t)
	resp, e := http.Get(h.server.URL + "/health/ready")
	if e != nil {
		t.Fatal(e)
	}
	defer resp.Body.Close()
	var body M
	if e = json.NewDecoder(resp.Body).Decode(&body); e != nil {
		t.Fatal(e)
	}
	if resp.StatusCode != 200 || body["ready"] != true {
		t.Fatalf("ready: %d %v", resp.StatusCode, body)
	}
	if body["retrieval"] != "not_configured" {
		t.Fatalf("retrieval: %v, want not_configured", body["retrieval"])
	}
	if _, present := body["snapshot"]; present {
		t.Fatalf("no snapshot exists; the payload must not claim one: %v", body)
	}
}
