package testdb

import (
	"strings"
	"testing"
)

// TestMissingDatabaseIsFatalWhenRequired is the S2 regression. Every test that
// proves the three gates calls Start; when the binaries are absent the package
// used to skip unconditionally, so `go test ./...` could exit 0 having measured
// none of them. With GUIDEFOLD_REQUIRE_PG=1 -- which CI sets -- the absence is
// an error instead.
func TestMissingDatabaseIsFatalWhenRequired(t *testing.T) {
	skip, err := missing("/nowhere/bin", false)
	if err != nil || !strings.Contains(skip, "/nowhere/bin") {
		t.Fatalf("without the flag the absence must be a skip: %q %v", skip, err)
	}
	skip, err = missing("/nowhere/bin", true)
	if err == nil {
		t.Fatal("with GUIDEFOLD_REQUIRE_PG=1 the absence must fail the run")
	}
	if skip != "" {
		t.Fatalf("a required run must not also skip: %q", skip)
	}
	if !strings.Contains(err.Error(), "GUIDEFOLD_REQUIRE_PG=1") {
		t.Fatalf("the error must name the flag that made it fatal: %v", err)
	}
}

func TestRequiredReadsTheEnvironment(t *testing.T) {
	t.Setenv("GUIDEFOLD_REQUIRE_PG", "")
	if Required() {
		t.Fatal("unset must not require the database")
	}
	t.Setenv("GUIDEFOLD_REQUIRE_PG", "1")
	if !Required() {
		t.Fatal("GUIDEFOLD_REQUIRE_PG=1 must require the database")
	}
}
