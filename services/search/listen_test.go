package main

import "testing"

// `serve` and `healthcheck` read one variable, so a deployment that moves the
// port cannot end up with a health check pointing at the old one (tech-lead
// decision 16).
func TestListenAddressAndReadyURL(t *testing.T) {
	if got := listenAddress(); got != ":8080" {
		t.Fatalf("the default listen address is %q, want :8080", got)
	}
	t.Setenv("GUIDEFOLD_LISTEN", "127.0.0.1:9001")
	if got := listenAddress(); got != "127.0.0.1:9001" {
		t.Fatalf("GUIDEFOLD_LISTEN was ignored: %q", got)
	}
	for addr, want := range map[string]string{
		// A wildcard bind is not an address a client can connect to; the
		// container probes itself on loopback.
		":8080":           "http://127.0.0.1:8080/health/ready",
		"0.0.0.0:8080":    "http://127.0.0.1:8080/health/ready",
		"[::]:8080":       "http://127.0.0.1:8080/health/ready",
		"127.0.0.1:9001":  "http://127.0.0.1:9001/health/ready",
		"api.internal:80": "http://api.internal:80/health/ready",
	} {
		if got := readyURL(addr); got != want {
			t.Errorf("readyURL(%q) = %q, want %q", addr, got, want)
		}
	}
}
