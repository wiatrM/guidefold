package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"strings"
	"testing"
)

// G4 — the delivery surface is dispatched by comparing r.URL.Path, so no route
// registration exists for the contract checker to read and it reported these
// endpoints as "not registered yet". They are declared instead by
// `// contract-route:` annotations, which tools/contract/check_api_contract.py
// parses. This test is what keeps the annotation honest: every annotated route
// must actually be dispatched, and every delivery path the dispatch compares
// must be annotated.
var annotationRE = regexp.MustCompile(`//\s*contract-route:\s*(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)`)

func annotations(t *testing.T) [][2]string {
	t.Helper()
	src, e := os.ReadFile("main.go")
	if e != nil {
		t.Fatal(e)
	}
	var out [][2]string
	for _, m := range annotationRE.FindAllStringSubmatch(string(src), -1) {
		out = append(out, [2]string{m[1], m[2]})
	}
	if len(out) == 0 {
		t.Fatal("main.go declares no delivery routes; the contract checker is blind again")
	}
	return out
}

func TestAnnotatedDeliveryRoutesAreDispatched(t *testing.T) {
	a := admissionApp(t)
	for _, route := range annotations(t) {
		method, path := route[0], route[1]
		// Placeholders stand for identifiers; any value exercises the dispatch.
		concrete := regexp.MustCompile(`\{[^}]+\}`).ReplaceAllString(path, "x")
		w := httptest.NewRecorder()
		a.ServeHTTP(w, httptest.NewRequest(method, concrete, strings.NewReader("{}")))
		if w.Code == http.StatusNotFound && strings.Contains(w.Body.String(), `"not_found"`) {
			t.Fatalf("%s %s is declared to the contract checker but the dispatch answers 404",
				method, concrete)
		}
	}
}

func TestEveryDeliveryPathInTheDispatchIsAnnotated(t *testing.T) {
	src, e := os.ReadFile("main.go")
	if e != nil {
		t.Fatal(e)
	}
	declared := map[string]bool{}
	for _, route := range annotations(t) {
		declared[route[1]] = true
	}
	// Path literals the dispatch compares against, and the prefixes it matches.
	compared := regexp.MustCompile(`r\.URL\.Path(?:\s*==\s*|,\s*)"(/[^"]*)"`)
	for _, m := range compared.FindAllStringSubmatch(string(src), -1) {
		path := m[1]
		if !strings.HasPrefix(path, "/v1/") && !strings.HasPrefix(path, "/health") && path != "/metrics" {
			continue
		}
		found := declared[path]
		for d := range declared {
			if strings.HasPrefix(d, path) {
				found = true
			}
		}
		if !found {
			t.Fatalf("the dispatch answers %q with no `// contract-route:` annotation, "+
				"so tools/contract/check_api_contract.py cannot see it", path)
		}
	}
}
