package main

import (
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"os"
	"reflect"
	"strings"
	"testing"
)

func fixture(t *testing.T) (M, *Catalog) {
	t.Helper()
	raw, e := os.ReadFile("testdata/policy.json")
	if e != nil {
		t.Fatal(e)
	}
	v, e := strictJSON(raw)
	if e != nil {
		t.Fatal(e)
	}
	f := obj(v)
	cards := map[string]M{}
	for u, c := range obj(f["cards"]) {
		cards[u] = obj(c)
	}
	c := &Catalog{ID: "fixture", Repo: "repo", Revision: "abc", Nodes: obj(f["nodes"]), Cards: cards, Revisions: map[string]string{}}
	if e = c.prepare(); e != nil {
		t.Fatal(e)
	}
	return f, c
}
func TestPolicyMatchesSharedRouter(t *testing.T) {
	f, c := fixture(t)
	if hash(canonical(obj(f["cards"]))) != str(f["canonical_sha256"]) {
		t.Fatal("canonical snapshot digest differs")
	}
	if c.ScopeSHA != str(f["scope_map_sha256"]) {
		t.Fatal("scope digest differs")
	}
	if hash(pythonJSON(c.Cards["u:01"], false)) != str(f["card_revision"]) {
		t.Fatal("card revision differs")
	}
	for i, v := range arr(f["cases"]) {
		t.Run(fmt.Sprint(i), func(t *testing.T) {
			x := obj(v)
			c.Weights = obj(x["weights"])
			allowed, drops := c.allowed(str(x["node"]), str(x["query"]))
			if !reflect.DeepEqual(keys(allowed), stringList(x["allowed"])) || drops != int(number(x["drops"])) {
				t.Fatalf("policy mismatch: %v %d", keys(allowed), drops)
			}
			candidates := []Candidate{}
			for _, v := range arr(x["candidates"]) {
				row := obj(v)
				candidates = append(candidates, Candidate{URN: str(row["urn"]), BM25Rank: int(number(row["bm25_rank"])), DenseRank: int(number(row["dense_rank"]))})
			}
			scored := c.score(candidates, str(x["node"]))
			want := arr(x["scored"])
			if len(scored) != len(want) {
				t.Fatal("score count")
			}
			for i, row := range scored {
				w := obj(want[i])
				if row.URN != str(w["urn"]) || row.Score != number(w["score"]) {
					t.Fatalf("score mismatch at %d: got %+v want %v", i, row, w)
				}
			}
			selected := c.selectCards(scored, int(number(x["k"])), allowed)
			if !reflect.DeepEqual(selected, stringList(x["selected"])) {
				t.Fatalf("selection got %v want %v", selected, x["selected"])
			}
		})
	}
}
func TestContextResolution(t *testing.T) {
	_, c := fixture(t)
	cases := []struct {
		path, want string
		status     int
	}{{".", "_root", 0}, {"services/alpha", "alpha", 0}, {"services/alpha/child/x.go", "alpha.child", 0}, {"services/beta/main.go", "beta", 0}, {"unknown/path", "", 422}}
	for _, x := range cases {
		got, e := c.mapPath(x.path)
		if x.status == 0 && (e != nil || got != x.want) {
			t.Fatalf("%s: %s %v", x.path, got, e)
		}
		if x.status != 0 && e == nil {
			t.Fatal("unmapped accepted")
		}
	}
	p := M{"workspace": M{"repo_id": "repo", "cwd": "services/alpha", "target_paths": []any{M{"path": "services/beta/x.go", "source": "edited"}, M{"path": "services/alpha/x.go", "source": "inferred"}}}}
	scopes, _, e := c.resolve(p)
	if e != nil || !reflect.DeepEqual(scopes, []string{"beta"}) {
		t.Fatal(scopes, e)
	}
	obj(p["workspace"])["revision"] = "wrong"
	if _, _, e = c.resolve(p); e == nil {
		t.Fatal("stale revision accepted")
	}
}
func TestStrictJSON(t *testing.T) {
	bad := []string{`{"query":"a","query":"b"}`, `{"workspace":{"cwd":"a","cwd":"b"}}`, `{"q":"\ud800"}`, `{"q":"\udc00"}`, `{"q":"\ud800\u0041"}`, `{} {}`, `{"x":` + strings.Repeat("[", 65) + `0` + strings.Repeat("]", 65) + `}`}
	for _, raw := range bad {
		if _, e := strictJSON([]byte(raw)); e == nil {
			t.Errorf("accepted %s", raw)
		}
	}
	for _, raw := range []string{`{"q":"\ud83d\ude00"}`, `{"q":"\\ud800"}`, `{"q":"quote\" café 😀"}`, `{"n":1,"b":false,"a":[null]}`} {
		if _, e := strictJSON([]byte(raw)); e != nil {
			t.Errorf("rejected %s: %v", raw, e)
		}
	}
}
func TestPublishedSchemaValidationAndHTTP(t *testing.T) {
	v, e := newValidator("../../tools/serve_spike/contracts/harness-service-v1.1.schema.json")
	if e != nil {
		t.Fatal(e)
	}
	valid := []string{`{"query":"retry"}`, `{"schema_version":"1.1","query":"retry","workspace":{"repo_id":"repo","cwd":"services/alpha"}}`, `{"schema_version":"1.1","query":"retry","budget":{"max_cards":0}}`}
	for _, raw := range valid {
		p, e := strictJSON([]byte(raw))
		if e != nil {
			t.Fatal(e)
		}
		if e = v.validate(obj(p), "search"); e != nil {
			t.Fatalf("valid rejected: %s: %v", raw, e)
		}
	}
	invalid := []string{`{"query":" "}`, `{"query":"retry","unknown":true}`, `{"query":"retry","deadline_ms":1.0}`, `{"query":"retry","deadline_ms":true}`, `{"schema_version":"2.0","query":"retry"}`, `{"schema_version":"1.1","query":"retry","workspace":{"repo_id":"repo","cwd":"../private"}}`, `{"schema_version":"1.1","query":"retry","workspace":{"repo_id":"repo","cwd":"C:\\private"}}`, `{"schema_version":"1.1","query":"retry","workspace":{"repo_id":"repo","cwd":"/private"}}`, `{"schema_version":"1.1","query":"retry","workspace":{"repo_id":"repo","cwd":"services//alpha"}}`, `{"schema_version":"1.1","query":"retry","budget":{"max_cards":5}}`, `{"schema_version":"1.1","query":"retry","capabilities":["\n"]}`}
	app := &App{Validator: v, Token: strings.Repeat("t", 40), Slots: make(chan struct{}, 8)}
	for _, raw := range invalid {
		p, e := strictJSON([]byte(raw))
		if e != nil {
			t.Fatal(e)
		}
		if e = v.validate(obj(p), "search"); e == nil {
			t.Errorf("invalid accepted: %s", raw)
		}
		req := httptest.NewRequest("POST", "/v1/search", strings.NewReader(raw))
		req.Header.Set("Authorization", "Bearer "+app.Token)
		w := httptest.NewRecorder()
		app.ServeHTTP(w, req)
		if w.Code != 400 {
			t.Errorf("HTTP %d: %s", w.Code, raw)
		}
	}
	t.Run("auth", func(t *testing.T) {
		w := httptest.NewRecorder()
		app.ServeHTTP(w, httptest.NewRequest("POST", "/v1/search", strings.NewReader(valid[0])))
		if w.Code != 401 {
			t.Fatal(w.Code)
		}
	})
	t.Run("body-limit", func(t *testing.T) {
		req := httptest.NewRequest("POST", "/v1/search", strings.NewReader(strings.Repeat("x", 16385)))
		req.Header.Set("Authorization", "Bearer "+app.Token)
		w := httptest.NewRecorder()
		app.ServeHTTP(w, req)
		if w.Code != 413 {
			t.Fatal(w.Code)
		}
	})
	t.Run("concurrent-schema", func(t *testing.T) {
		for i := 0; i < 20; i++ {
			t.Run(fmt.Sprint(i), func(t *testing.T) {
				t.Parallel()
				p, _ := strictJSON([]byte(valid[1]))
				if e := v.validate(obj(p), "search"); e != nil {
					t.Fatal(e)
				}
			})
		}
	})
}
func TestNumbersAndUnicodeCanonical(t *testing.T) {
	raw := `{"z":"é 😀\u2028 <>&","n":9007199254740993,"a":[true,null]}`
	v, e := strictJSON([]byte(raw))
	if e != nil {
		t.Fatal(e)
	}
	actual := canonical(v)
	var want any
	d := json.NewDecoder(strings.NewReader(string(actual)))
	d.UseNumber()
	if e = d.Decode(&want); e != nil {
		t.Fatal(e)
	}
	if !reflect.DeepEqual(v, want) {
		t.Fatalf("roundtrip %s", actual)
	}
	if !strings.Contains(string(actual), "9007199254740993") || strings.Contains(string(actual), `\u003c`) {
		t.Fatal(string(actual))
	}
}
