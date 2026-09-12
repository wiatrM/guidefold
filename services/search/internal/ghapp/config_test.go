package ghapp_test

import (
	"errors"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
)

// No app id and no key file at all: this is the ordinary "the deployment has
// not connected the GitHub App yet" state ADR-0036 point 5 / ADR-0046
// consequences name — it must be a value a caller can match, not a generic
// error a caller has to string-match.
func TestMissingAppKeyGivesErrNotConfigured(t *testing.T) {
	empty := func(string) string { return "" }
	if _, err := ghapp.ConfigFromEnv(empty); !errors.Is(err, ghapp.ErrNotConfigured) {
		t.Fatalf("ConfigFromEnv with nothing set = %v, want ErrNotConfigured", err)
	}
	if _, err := ghapp.NewFromEnv(empty); !errors.Is(err, ghapp.ErrNotConfigured) {
		t.Fatalf("NewFromEnv with nothing set = %v, want ErrNotConfigured", err)
	}
}

// An App id with no key file is the same "not configured" state, not a
// different error: half a configuration is not a working one.
func TestAppIDWithoutKeyFileGivesErrNotConfigured(t *testing.T) {
	env := func(name string) string {
		if name == "GITHUB_APP_ID" {
			return "12345"
		}
		return ""
	}
	if _, err := ghapp.ConfigFromEnv(env); !errors.Is(err, ghapp.ErrNotConfigured) {
		t.Fatalf("ConfigFromEnv with only an App id = %v, want ErrNotConfigured", err)
	}
}

// A configured App builds a Client that defaults to GitHub's real host, and
// a GITHUB_API_BASE_URL override replaces it.
func TestConfigFromEnvUsesBaseURLOverride(t *testing.T) {
	keyPath, _ := testAppKey(t)
	env := func(name string) string {
		switch name {
		case "GITHUB_APP_ID":
			return "12345"
		case "GITHUB_APP_PRIVATE_KEY_FILE":
			return keyPath
		case "GITHUB_API_BASE_URL":
			return "https://fake.example.test/"
		}
		return ""
	}
	cfg, err := ghapp.ConfigFromEnv(env)
	if err != nil {
		t.Fatalf("ConfigFromEnv: %v", err)
	}
	if cfg.BaseURL != "https://fake.example.test" {
		t.Fatalf("BaseURL = %q, want the override with its trailing slash trimmed", cfg.BaseURL)
	}
	if cfg.AppID != "12345" || cfg.PrivateKey == nil {
		t.Fatalf("Config did not carry the App id or the parsed key: %+v", cfg)
	}
	if _, err := ghapp.New(cfg); err != nil {
		t.Fatalf("New: %v", err)
	}
}

func TestConfigFromEnvDefaultsBaseURL(t *testing.T) {
	keyPath, _ := testAppKey(t)
	env := func(name string) string {
		switch name {
		case "GITHUB_APP_ID":
			return "12345"
		case "GITHUB_APP_PRIVATE_KEY_FILE":
			return keyPath
		}
		return ""
	}
	cfg, err := ghapp.ConfigFromEnv(env)
	if err != nil {
		t.Fatalf("ConfigFromEnv: %v", err)
	}
	if cfg.BaseURL != ghapp.DefaultBaseURL {
		t.Fatalf("BaseURL = %q, want %q", cfg.BaseURL, ghapp.DefaultBaseURL)
	}
}
