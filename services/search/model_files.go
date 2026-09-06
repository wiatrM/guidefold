package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

func fileDigest(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	h := sha256.New()
	if _, err = io.Copy(h, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
func verifyModelDirectory(dir, expected string) error {
	raw, err := os.ReadFile(filepath.Join(dir, "guidefold-encoder.json"))
	if err != nil {
		return err
	}
	value, err := strictJSON(raw)
	if err != nil {
		return err
	}
	manifest := obj(value)
	if !validEncoderManifest(manifest) || hash(canonical(manifest)) != expected {
		return fmt.Errorf("model_manifest_mismatch")
	}
	names := []string{"config.json", "tokenizer.json", "tokenizer_config.json", "config_sentence_transformers.json", "sentence_bert_config.json", "modules.json", "1_Pooling/config.json"}
	allowed := map[string]bool{"guidefold-encoder.json": true, "model.safetensors": true, "README.md": true, "guidefold-adapter.json": true}
	for _, name := range names {
		allowed[name] = true
	}
	if err = filepath.WalkDir(dir, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() {
			return nil
		}
		relative, err := filepath.Rel(dir, path)
		if err != nil {
			return err
		}
		if entry.Type()&os.ModeSymlink != 0 || !allowed[filepath.ToSlash(relative)] {
			return fmt.Errorf("unexpected_model_file: %s", relative)
		}
		return nil
	}); err != nil {
		return err
	}
	files := obj(manifest["files_sha256"])
	if len(files) != len(names) {
		return fmt.Errorf("model_file_manifest_mismatch")
	}
	for _, name := range append(names, "model.safetensors") {
		want := str(files[name])
		if name == "model.safetensors" {
			want = str(manifest["weights_sha256"])
		}
		got, err := fileDigest(filepath.Join(dir, name))
		if err != nil {
			return err
		}
		if got != want {
			return fmt.Errorf("model_file_checksum_mismatch: %s", name)
		}
	}
	return printOperatorResult(M{"encoder_id": expected, "files_verified": len(names) + 1}, nil)
}
