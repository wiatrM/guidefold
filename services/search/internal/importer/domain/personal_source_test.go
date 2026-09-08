package domain_test

import (
	"strings"
	"testing"

	"github.com/wiatrM/guidefold/services/search/internal/importer/domain"
)

// `files[].source` and the `_personal/` boundary (API-CONTRACT §5.6).
//
// The decoder rejects unknown fields, so this is not a formality: without the
// field, a manifest from `guidefold extract --personal` would be refused as
// invalid JSON, and with the field but without the checks below, a repository
// file could claim to be somebody's personal skill or the other way round.

func personalManifest(t *testing.T, file string) []byte {
	t.Helper()
	return []byte(`{"format":"guidefold-import-manifest-v1","org":"acme","repo":"monorepo",
 "commit":null,"complete":true,"dirty":false,"publish":false,"cli_version":"0.1.0",
 "scan_profile":"default","root":".","excluded":[],"aliases":[],"suggestions":[],
 "limits":{"max_files":100000,"max_bytes":104857600},"files":[` + file + `]}`)
}

const digest = "0000000000000000000000000000000000000000000000000000000000000000"

func TestAPersonalFileIsAcceptedAndKeepsItsSource(t *testing.T) {
	raw := personalManifest(t, `{"path":"_personal/claude/helper/SKILL.md","sha256":"`+digest+
		`","size":10,"kind":"skill","mode":"100644","source":{"kind":"personal","harness":"claude"}}`)
	m, e := domain.ParseManifest(raw)
	if e != nil {
		t.Fatalf("a manifest carrying files[].source must decode: %v", e)
	}
	if e := m.Validate("monorepo"); e != nil {
		t.Fatalf("validate: %v", e)
	}
	if m.Files[0].Source == nil || m.Files[0].Source.Harness != "claude" {
		t.Fatalf("the source was dropped: %+v", m.Files[0].Source)
	}
	if m.Publishes() {
		t.Error("a personal import must not ask for publication")
	}
}

func TestARepositoryFileStillNeedsNoSource(t *testing.T) {
	raw := personalManifest(t, `{"path":"README.md","sha256":"`+digest+
		`","size":10,"kind":"document","mode":"100644"}`)
	m, e := domain.ParseManifest(raw)
	if e != nil {
		t.Fatal(e)
	}
	if e := m.Validate("monorepo"); e != nil {
		t.Fatalf("validate: %v", e)
	}
	if m.Files[0].Source != nil {
		t.Error("a repository file must carry no source")
	}
}

func TestThePersonalBoundaryIsCheckedInBothDirections(t *testing.T) {
	cases := map[string]string{
		"a personal path with no source": `{"path":"_personal/claude/x/SKILL.md","sha256":"` +
			digest + `","size":1,"kind":"skill","mode":"100644"}`,
		"a repository path claiming a harness": `{"path":"docs/x.md","sha256":"` + digest +
			`","size":1,"kind":"document","mode":"100644","source":{"kind":"personal","harness":"claude"}}`,
		"a harness that does not match the path": `{"path":"_personal/codex/x/SKILL.md","sha256":"` +
			digest + `","size":1,"kind":"skill","mode":"100644","source":{"kind":"personal","harness":"claude"}}`,
		"an unknown harness": `{"path":"_personal/gemini/x/SKILL.md","sha256":"` + digest +
			`","size":1,"kind":"skill","mode":"100644","source":{"kind":"personal","harness":"gemini"}}`,
		"an unknown source kind": `{"path":"_personal/claude/x/SKILL.md","sha256":"` + digest +
			`","size":1,"kind":"skill","mode":"100644","source":{"kind":"vendored","harness":"claude"}}`,
	}
	for name, file := range cases {
		t.Run(name, func(t *testing.T) {
			m, e := domain.ParseManifest(personalManifest(t, file))
			if e != nil {
				return // refused at decode time is also a refusal
			}
			if e := m.Validate("monorepo"); e == nil {
				t.Fatal("this manifest must be refused")
			} else if !strings.Contains(e.Error(), "invalid_request") {
				t.Fatalf("unexpected code: %v", e)
			}
		})
	}
}
