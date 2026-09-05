package main

import (
	"os"
	"testing"
)

func TestTelemetryValidationMatchesSQLiteReference(t *testing.T) {
	raw, e := os.ReadFile("testdata/telemetry.json")
	if e != nil {
		t.Fatal(e)
	}
	value, e := strictJSON(raw)
	if e != nil {
		t.Fatal(e)
	}
	for i, v := range arr(value) {
		row := obj(v)
		if got := validateEvent(row["event"]); got != str(row["reason"]) {
			t.Fatalf("case %d: got %q expected %q", i, got, row["reason"])
		}
	}
}
