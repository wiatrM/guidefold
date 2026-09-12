package secrets_test

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/secrets"
)

func key(t *testing.T) []byte {
	t.Helper()
	b := make([]byte, 32)
	if _, e := rand.Read(b); e != nil {
		t.Fatal(e)
	}
	return b
}

func ring(t *testing.T) *secrets.Keyring {
	t.Helper()
	kr, e := secrets.NewKeyring("k1", map[string][]byte{"k1": key(t)})
	if e != nil {
		t.Fatal(e)
	}
	return kr
}

func TestSealAndOpenRoundTrip(t *testing.T) {
	kr := ring(t)
	const plain = "sk-or-v1-abcdef0123456789"
	id, nonce, ct, e := kr.Seal("org-a", secrets.ProviderOpenRouter, plain)
	if e != nil {
		t.Fatal(e)
	}
	if id != "k1" {
		t.Fatalf("sealed under %q, want the active key", id)
	}
	if strings.Contains(string(ct), "abcdef") {
		t.Fatal("the ciphertext contains the plaintext")
	}
	got, e := kr.Open("org-a", secrets.ProviderOpenRouter, id, nonce, ct)
	if e != nil {
		t.Fatal(e)
	}
	if got != plain {
		t.Fatalf("opened %q, want %q", got, plain)
	}
}

// The reason the organisation is authenticated into the ciphertext: a row lifted
// from one tenant's table into another's must fail to open rather than decrypt
// into someone else's run (ADR-0045 §2).
func TestOpenRefusesAnotherOrganisation(t *testing.T) {
	kr := ring(t)
	id, nonce, ct, e := kr.Seal("org-a", secrets.ProviderOpenRouter, "sk-or-v1-secret")
	if e != nil {
		t.Fatal(e)
	}
	if _, e := kr.Open("org-b", secrets.ProviderOpenRouter, id, nonce, ct); e == nil {
		t.Fatal("a ciphertext sealed for org-a opened for org-b")
	}
	if _, e := kr.Open("org-a", secrets.ProviderAnthropic, id, nonce, ct); e == nil {
		t.Fatal("a ciphertext sealed for openrouter opened as anthropic")
	}
}

func TestRetiredKeyStillOpensItsRows(t *testing.T) {
	old, new := key(t), key(t)
	first, e := secrets.NewKeyring("k1", map[string][]byte{"k1": old})
	if e != nil {
		t.Fatal(e)
	}
	id, nonce, ct, e := first.Seal("org-a", secrets.ProviderOpenAI, "sk-old-credential")
	if e != nil {
		t.Fatal(e)
	}
	rotated, e := secrets.NewKeyring("k2", map[string][]byte{"k1": old, "k2": new})
	if e != nil {
		t.Fatal(e)
	}
	if rotated.ActiveKeyID() != "k2" {
		t.Fatalf("active key is %q, want k2", rotated.ActiveKeyID())
	}
	got, e := rotated.Open("org-a", secrets.ProviderOpenAI, id, nonce, ct)
	if e != nil {
		t.Fatalf("a row sealed under the retired key no longer opens: %v", e)
	}
	if got != "sk-old-credential" {
		t.Fatalf("opened %q", got)
	}
}

func TestNilKeyringSealsNothing(t *testing.T) {
	var kr *secrets.Keyring
	if _, _, _, e := kr.Seal("org-a", secrets.ProviderOpenRouter, "sk-anything"); !errors.Is(e, secrets.ErrNoKeyring) {
		t.Fatalf("sealing without a keyring returned %v, want ErrNoKeyring", e)
	}
}

func TestLoadKeyringRejectsAShortKey(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "keys.json")
	body, _ := json.Marshal(map[string]any{
		"active": "k1",
		"keys":   map[string]string{"k1": base64.StdEncoding.EncodeToString([]byte("too-short"))},
	})
	if e := os.WriteFile(path, body, 0o600); e != nil {
		t.Fatal(e)
	}
	if _, e := secrets.LoadKeyring(func(string) string { return path }); e == nil {
		t.Fatal("a 9-byte master key was accepted")
	}
}

func TestLoadKeyringAbsentIsNotAnError(t *testing.T) {
	kr, e := secrets.LoadKeyring(func(string) string { return "" })
	if e != nil || kr != nil {
		t.Fatalf("no key file gave (%v, %v), want (nil, nil)", kr, e)
	}
}

func TestLast4IsAllThatEverLeaves(t *testing.T) {
	if got := secrets.Last4("sk-or-v1-0123456789abcdef"); got != "cdef" {
		t.Fatalf("Last4 = %q", got)
	}
	if got := secrets.Last4("abc"); got != "abc" {
		t.Fatalf("Last4 of a short string = %q", got)
	}
}

// A provider that is merely unreachable must not be reported as an invalid key:
// the owner would go looking for a problem in their own account.
func TestVerifierSeparatesRejectedFromUnreachable(t *testing.T) {
	for _, tc := range []struct {
		name     string
		status   int
		rejected bool
		ok       bool
	}{
		{"accepted", http.StatusOK, false, true},
		{"rejected", http.StatusUnauthorized, true, false},
		{"forbidden", http.StatusForbidden, true, false},
		{"provider down", http.StatusInternalServerError, false, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Header.Get("Authorization") != "Bearer sk-test-key" {
					t.Errorf("key not presented as a bearer token: %q", r.Header.Get("Authorization"))
				}
				w.WriteHeader(tc.status)
			}))
			defer srv.Close()
			v := secrets.NewHTTPVerifier()
			v.Endpoint = func(string) (string, string, func(*http.Request)) {
				return http.MethodGet, srv.URL, func(r *http.Request) {
					r.Header.Set("Authorization", "Bearer "+r.Header.Get("X-Key"))
					r.Header.Del("X-Key")
				}
			}
			e := v.Verify(context.Background(), secrets.ProviderOpenRouter, "sk-test-key")
			switch {
			case tc.ok && e != nil:
				t.Fatalf("an accepted key reported %v", e)
			case tc.rejected && !errors.Is(e, secrets.ErrRejected):
				t.Fatalf("a rejected key reported %v, want ErrRejected", e)
			case !tc.ok && !tc.rejected && (e == nil || errors.Is(e, secrets.ErrRejected)):
				t.Fatalf("an unreachable provider reported %v, want a plain error", e)
			}
		})
	}
}
