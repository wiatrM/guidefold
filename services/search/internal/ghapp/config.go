package ghapp

import (
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"os"
	"strings"
)

// DefaultBaseURL is GitHub's production API host. Overridable per Config so a
// test can point a Client at an httptest server without touching the process
// environment.
const DefaultBaseURL = "https://api.github.com"

// Config is everything a Client needs, already resolved out of the
// environment. It is a separate type from Client (rather than fields New
// reads itself) so a caller can validate or log "is the App configured" —
// without the private key — before committing to build a Client.
type Config struct {
	AppID      string
	PrivateKey *rsa.PrivateKey
	BaseURL    string
}

// ConfigFromEnv reads GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY_FILE (the
// *_FILE convention this service uses for every secret) plus the optional
// GITHUB_API_BASE_URL override, through an env func rather than os.Getenv
// directly — so a test supplies values without mutating process-wide
// environment variables that other parallel tests also read.
func ConfigFromEnv(env func(string) string) (Config, error) {
	appID := strings.TrimSpace(env("GITHUB_APP_ID"))
	keyPath := strings.TrimSpace(env("GITHUB_APP_PRIVATE_KEY_FILE"))
	if appID == "" || keyPath == "" {
		return Config{}, ErrNotConfigured
	}
	raw, err := os.ReadFile(keyPath)
	if err != nil {
		// The path came from configuration and is safe to name; the file's
		// contents never are, so they do not appear here even on failure.
		return Config{}, fmt.Errorf("ghapp: GITHUB_APP_PRIVATE_KEY_FILE is unreadable: %w", err)
	}
	key, err := parsePrivateKey(raw)
	if err != nil {
		return Config{}, err
	}
	base := strings.TrimSuffix(strings.TrimSpace(env("GITHUB_API_BASE_URL")), "/")
	if base == "" {
		base = DefaultBaseURL
	}
	return Config{AppID: appID, PrivateKey: key, BaseURL: base}, nil
}

// parsePrivateKey accepts both the PKCS#1 ("BEGIN RSA PRIVATE KEY") and
// PKCS#8 ("BEGIN PRIVATE KEY") PEM encodings, because GitHub hands the App
// owner a PKCS#1 key on generation but some key managers re-encode it as
// PKCS#8 — rejecting the second form would make key rotation depend on which
// tool re-saved the file.
func parsePrivateKey(pemBytes []byte) (*rsa.PrivateKey, error) {
	block, _ := pem.Decode(pemBytes)
	if block == nil {
		return nil, fmt.Errorf("ghapp: GITHUB_APP_PRIVATE_KEY_FILE is not PEM-encoded")
	}
	if key, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		return key, nil
	}
	parsed, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("ghapp: GITHUB_APP_PRIVATE_KEY_FILE does not hold a parseable private key: %w", err)
	}
	key, ok := parsed.(*rsa.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("ghapp: GITHUB_APP_PRIVATE_KEY_FILE does not hold an RSA key")
	}
	return key, nil
}
