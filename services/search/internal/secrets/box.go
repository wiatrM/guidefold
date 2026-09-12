// Package secrets owns the one credential this product stores in a form it can
// read back: the model key an organisation supplies so the Live Agent can call
// the provider with nobody present (ADR-0045).
//
// Everything else in gfm keeps a sha256 the server can check but never
// reproduce. That is the right shape for a credential someone presents, and the
// wrong shape for one the service has to present on their behalf. So this key is
// sealed, not hashed, and the rules that follow from that live here rather than
// in a handler: the organisation is authenticated into the ciphertext, the
// plaintext leaves in exactly one direction, and a deployment with no master key
// stores nothing rather than storing a key in the clear.
package secrets

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sort"
	"strings"
)

// ErrNoKeyring is returned when the deployment has no master key. Callers turn
// it into `secret_encryption_unavailable`; nothing falls back to plaintext.
var ErrNoKeyring = errors.New("secrets: no master key configured")

// Keyring holds the deployment's master keys by id, with one marked active.
// Several keys exist at once so a retired key can still open the rows that were
// sealed under it, until a re-seal pass has moved them across. Rotation that
// dropped the old key would make those rows unreadable, which is data loss
// dressed up as security.
type Keyring struct {
	active string
	keys   map[string][]byte
}

type keyringFile struct {
	Active string            `json:"active"`
	Keys   map[string]string `json:"keys"`
}

// LoadKeyring reads the JSON key file named by GUIDEFOLD_SECRET_KEY_FILE.
// A missing variable is not an error: it means this deployment has no keyring,
// and every caller degrades to a named, honest failure.
func LoadKeyring(env func(string) string) (*Keyring, error) {
	path := strings.TrimSpace(env("GUIDEFOLD_SECRET_KEY_FILE"))
	if path == "" {
		return nil, nil
	}
	raw, e := os.ReadFile(path)
	if e != nil {
		return nil, fmt.Errorf("secrets: reading %s: %w", path, e)
	}
	var f keyringFile
	if e := json.Unmarshal(raw, &f); e != nil {
		return nil, fmt.Errorf("secrets: %s is not a JSON keyring: %w", path, e)
	}
	if strings.TrimSpace(f.Active) == "" {
		return nil, fmt.Errorf("secrets: %s names no active key", path)
	}
	kr := &Keyring{active: f.Active, keys: map[string][]byte{}}
	for id, encoded := range f.Keys {
		key, e := base64.StdEncoding.DecodeString(strings.TrimSpace(encoded))
		if e != nil {
			return nil, fmt.Errorf("secrets: key %q in %s is not base64: %w", id, path, e)
		}
		if len(key) != 32 {
			return nil, fmt.Errorf("secrets: key %q in %s is %d bytes, want 32", id, path, len(key))
		}
		kr.keys[id] = key
	}
	if _, ok := kr.keys[kr.active]; !ok {
		return nil, fmt.Errorf("secrets: %s marks %q active but does not contain it", path, kr.active)
	}
	return kr, nil
}

// NewKeyring builds a keyring in memory. Tests use it; the service reads a file.
func NewKeyring(active string, keys map[string][]byte) (*Keyring, error) {
	if _, ok := keys[active]; !ok {
		return nil, fmt.Errorf("secrets: active key %q is not in the keyring", active)
	}
	for id, key := range keys {
		if len(key) != 32 {
			return nil, fmt.Errorf("secrets: key %q is %d bytes, want 32", id, len(key))
		}
	}
	return &Keyring{active: active, keys: keys}, nil
}

// ActiveKeyID names the key new ciphertexts are sealed under.
func (k *Keyring) ActiveKeyID() string {
	if k == nil {
		return ""
	}
	return k.active
}

// KeyIDs lists every key the ring can open, for diagnostics.
func (k *Keyring) KeyIDs() []string {
	if k == nil {
		return nil
	}
	out := make([]string, 0, len(k.keys))
	for id := range k.keys {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}

// aad binds a ciphertext to the row it belongs to. Without it, a row copied
// from one organisation to another would decrypt, and one tenant's run would
// spend another tenant's money. With it, the copy fails to open.
func aad(orgID, provider, keyID string) []byte {
	return []byte(orgID + "\x00" + provider + "\x00" + keyID)
}

func (k *Keyring) gcm(keyID string) (cipher.AEAD, error) {
	if k == nil {
		return nil, ErrNoKeyring
	}
	key, ok := k.keys[keyID]
	if !ok {
		return nil, fmt.Errorf("secrets: no key %q in the keyring", keyID)
	}
	block, e := aes.NewCipher(key)
	if e != nil {
		return nil, e
	}
	return cipher.NewGCM(block)
}

// Seal encrypts one plaintext for one organisation and provider under the
// active key. It returns the key id, the nonce and the ciphertext, which is
// everything a row needs to be opened later.
func (k *Keyring) Seal(orgID, provider, plaintext string) (keyID string, nonce, ciphertext []byte, err error) {
	if k == nil {
		return "", nil, nil, ErrNoKeyring
	}
	keyID = k.active
	aead, e := k.gcm(keyID)
	if e != nil {
		return "", nil, nil, e
	}
	nonce = make([]byte, aead.NonceSize())
	if _, e := rand.Read(nonce); e != nil {
		return "", nil, nil, e
	}
	ciphertext = aead.Seal(nil, nonce, []byte(plaintext), aad(orgID, provider, keyID))
	return keyID, nonce, ciphertext, nil
}

// Open decrypts a row. It fails, rather than returning something usable, when
// the organisation, the provider or the key id does not match what was sealed.
func (k *Keyring) Open(orgID, provider, keyID string, nonce, ciphertext []byte) (string, error) {
	aead, e := k.gcm(keyID)
	if e != nil {
		return "", e
	}
	if len(nonce) != aead.NonceSize() {
		return "", errors.New("secrets: stored nonce has the wrong length")
	}
	plain, e := aead.Open(nil, nonce, ciphertext, aad(orgID, provider, keyID))
	if e != nil {
		return "", fmt.Errorf("secrets: cannot open the stored credential: %w", e)
	}
	return string(plain), nil
}

// Last4 is the only part of a key that is ever shown, logged or audited. A key
// shorter than that is refused before it reaches here.
func Last4(key string) string {
	r := []rune(key)
	if len(r) <= 4 {
		return string(r)
	}
	return string(r[len(r)-4:])
}
