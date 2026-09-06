package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestModelFileDigestDetectsReplacement(t *testing.T) {
	path := filepath.Join(t.TempDir(), "tokenizer.json")
	if err := os.WriteFile(path, []byte("original"), 0600); err != nil {
		t.Fatal(err)
	}
	original, err := fileDigest(path)
	if err != nil || original != hash([]byte("original")) {
		t.Fatal(original, err)
	}
	if err = os.WriteFile(path, []byte("changed"), 0600); err != nil {
		t.Fatal(err)
	}
	changed, err := fileDigest(path)
	if err != nil || changed == original {
		t.Fatal("replacement not detected", err)
	}
}
func TestModelVerifierFailsWithoutMatchingManifest(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "guidefold-encoder.json"), []byte(`{"format":"guidefold-encoder-v1"}`), 0600); err != nil {
		t.Fatal(err)
	}
	if err := verifyModelDirectory(dir, "wrong"); err == nil {
		t.Fatal("unverified model was accepted")
	}
}
