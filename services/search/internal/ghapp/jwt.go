package ghapp

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"time"
)

// jwtBackdate covers clock skew between this process and GitHub's: a JWT
// whose iat is in GitHub's future by even a second is rejected outright, and
// a few seconds of drift between two different machines is normal.
const jwtBackdate = 60 * time.Second

// jwtLifetime is GitHub's own hard ceiling on an App JWT's exp - iat.
const jwtLifetime = 10 * time.Minute

// appJWT signs the App's own authentication token. This is deliberately not
// a library call: the whole signing operation is header, claims, dot,
// signature — four stdlib primitives (crypto/rsa, crypto/sha256,
// encoding/base64, encoding/json) — and adding a JWT dependency for four
// lines would be a new module dependency this package is not allowed to add.
func (c *Client) appJWT() (string, error) {
	now := c.now()
	header, err := json.Marshal(map[string]string{"alg": "RS256", "typ": "JWT"})
	if err != nil {
		return "", err
	}
	claims, err := json.Marshal(map[string]any{
		"iat": now.Add(-jwtBackdate).Unix(),
		"exp": now.Add(jwtLifetime).Unix(),
		"iss": c.appID,
	})
	if err != nil {
		return "", err
	}
	signingInput := base64URLEncode(header) + "." + base64URLEncode(claims)
	hashed := sha256.Sum256([]byte(signingInput))
	signature, err := rsa.SignPKCS1v15(rand.Reader, c.privateKey, crypto.SHA256, hashed[:])
	if err != nil {
		return "", fmt.Errorf("ghapp: signing the App JWT failed: %w", err)
	}
	return signingInput + "." + base64URLEncode(signature), nil
}

func base64URLEncode(b []byte) string {
	return base64.RawURLEncoding.EncodeToString(b)
}
