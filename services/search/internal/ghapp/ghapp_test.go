package ghapp_test

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/wiatrM/guidefold/services/search/internal/ghapp"
)

// Shared across the file: everything is exercised against an httptest server
// standing in for api.github.com (no network, no database), through the
// package's two exported operations — ListSkillFiles and ReadFile — so the
// tests exercise the same path a real caller does, token exchange included.

var (
	testKeyOnce sync.Once
	testKeyPEM  []byte
	testKey     *rsa.PrivateKey
)

// testAppKey generates one RSA key for the whole test binary (key generation
// is the slow part of these tests) and writes it to a fresh temp file per
// caller, matching the GITHUB_APP_PRIVATE_KEY_FILE contract of one file per
// deployment.
func testAppKey(t *testing.T) (string, *rsa.PrivateKey) {
	t.Helper()
	testKeyOnce.Do(func() {
		key, err := rsa.GenerateKey(rand.Reader, 2048)
		if err != nil {
			t.Fatal(err)
		}
		testKey = key
		testKeyPEM = pem.EncodeToMemory(&pem.Block{
			Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key),
		})
	})
	dir := t.TempDir()
	path := filepath.Join(dir, "app.pem")
	if err := os.WriteFile(path, testKeyPEM, 0o600); err != nil {
		t.Fatal(err)
	}
	return path, testKey
}

func testEnv(t *testing.T, baseURL string, extra map[string]string) func(string) string {
	t.Helper()
	keyPath, _ := testAppKey(t)
	env := map[string]string{
		"GITHUB_APP_ID":               "12345",
		"GITHUB_APP_PRIVATE_KEY_FILE": keyPath,
		"GITHUB_API_BASE_URL":         baseURL,
	}
	for k, v := range extra {
		env[k] = v
	}
	return func(name string) string { return env[name] }
}

func newTestClient(t *testing.T, baseURL string) *ghapp.Client {
	t.Helper()
	client, err := ghapp.NewFromEnv(testEnv(t, baseURL, nil))
	if err != nil {
		t.Fatalf("NewFromEnv: %v", err)
	}
	return client
}

// clock is a settable time source a test hands to Client.SetClock, so token
// expiry can be crossed without an hour of wall-clock time passing.
type clock struct {
	mu  sync.Mutex
	now time.Time
}

func newClock(start time.Time) *clock { return &clock{now: start} }
func (c *clock) Now() time.Time       { c.mu.Lock(); defer c.mu.Unlock(); return c.now }
func (c *clock) Advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now = c.now.Add(d)
}
