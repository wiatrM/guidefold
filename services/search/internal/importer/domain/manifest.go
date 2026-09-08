// Package domain holds the import rules that do not depend on HTTP, SQL, a
// blob store or a Python builder: what a scan manifest may contain, how its
// digest is computed, which files belong to a skill package, and what a source
// change means for a skill that is already published.
//
// Nothing here imports net/http or database/sql. The application layer in the
// parent package turns these decisions into requests, rows and jobs.
package domain

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
)

// Format is the only manifest format this contract accepts (API-CONTRACT §5.6).
const Format = "guidefold-import-manifest-v1"

// Limits the server applies whatever the client declared (API-CONTRACT §3).
const (
	MaxBlobBytes  = 8 << 20   // 8 MiB per blob
	MaxTotalBytes = 100 << 20 // 100 MiB per import
	MaxFiles      = 100000
	MaxPathBytes  = 1024
)

// Kinds a manifest file may declare.
const (
	KindSkill    = "skill"
	KindDocument = "document"
	KindConfig   = "config"
	KindResource = "resource"
)

// File is one entry of the manifest's file list.
type File struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Size   int64  `json:"size"`
	Kind   string `json:"kind"`
	Mode   string `json:"mode"`
	// Source names content that did not come from the repository tree. It is
	// absent for every repository file, and present only for the personal skill
	// directories `guidefold extract --personal` was explicitly asked to include
	// (API-CONTRACT §5.6). Keeping it a separate field rather than inferring it
	// from the path means the server never has to guess whether `_personal/...`
	// is somebody's home directory or a directory in the repository.
	Source *FileSource `json:"source"`
}

// Excluded is one path the scan deliberately left out, with its reason. The
// server stores it for the operator's benefit and never asks for its bytes.
type Excluded struct {
	Path   string `json:"path"`
	Reason string `json:"reason"`
}

// Alias maps a path a previous import knew to the path this one carries, so a
// renamed skill keeps its identity instead of looking like a delete plus an add
// (U1.5).
type Alias struct {
	From string `json:"from"`
	To   string `json:"to"`
}

// Suggestion is advisory scope/owner guidance for a skill file that
// guidefold.yaml does not cover on its own (API-CONTRACT §5.6, U1 AC2). It is
// stored with the manifest and never acted on: an uncertain hierarchy stays
// visible instead of quietly becoming policy.
type Suggestion struct {
	Path           string   `json:"path"`
	SuggestedScope *string  `json:"suggested_scope"`
	SuggestedOwner *string  `json:"suggested_owner"`
	Reasons        []string `json:"reasons"`
	Candidates     []string `json:"candidates"`
}

// Limits are the client's own declared ceilings. They are diagnostics: the
// server applies its own.
type Limits struct {
	MaxFiles json.Number `json:"max_files"`
	MaxBytes json.Number `json:"max_bytes"`
}

// Manifest is the deterministic description of one scanned tree.
type Manifest struct {
	Format      string       `json:"format"`
	Org         string       `json:"org"`
	Repo        string       `json:"repo"`
	Commit      *string      `json:"commit"`
	Complete    bool         `json:"complete"`
	Dirty       bool         `json:"dirty"`
	Publish     *bool        `json:"publish"`
	CLIVersion  string       `json:"cli_version"`
	ScanProfile string       `json:"scan_profile"`
	Root        string       `json:"root"`
	Files       []File       `json:"files"`
	Excluded    []Excluded   `json:"excluded"`
	Aliases     []Alias      `json:"aliases"`
	Suggestions []Suggestion `json:"suggestions"`
	Limits      Limits       `json:"limits"`
}

// Publishes reports whether finalizing this import should also queue a
// publication. The field is optional and defaults to true (API-CONTRACT §6).
func (m *Manifest) Publishes() bool { return m.Publish == nil || *m.Publish }

// CommitOrEmpty is the scanned commit, or "" for a scan without git.
func (m *Manifest) CommitOrEmpty() string {
	if m.Commit == nil {
		return ""
	}
	return *m.Commit
}

// FileSource is where a non-repository file came from.
type FileSource struct {
	Kind    string `json:"kind"`
	Harness string `json:"harness"`
}

// SourceKindPersonal is the only non-repository source there is.
const SourceKindPersonal = "personal"

// personalHarnesses is the closed list of tools whose personal skill directory
// the CLI knows how to read.
var personalHarnesses = map[string]bool{"claude": true, "codex": true, "copilot": true}

// PersonalPrefix is the path prefix a personal file must carry. It cannot
// collide with a repository path, because a repository directory named
// `_personal` would have to declare a harness it does not have.
const PersonalPrefix = "_personal/"

// validSource checks one file's origin, and the agreement between its origin and
// its path. Either both say "personal" or neither does: a repository file that
// claims a harness, and a `_personal/` path with no source, are both attempts to
// move content across the boundary the flag exists to guard.
func validSource(f File) error {
	inPersonalTree := strings.HasPrefix(f.Path, PersonalPrefix)
	if f.Source == nil {
		if inPersonalTree {
			return fault("invalid_request",
				"%q is under %s but declares no source; personal content must say so.",
				f.Path, PersonalPrefix)
		}
		return nil
	}
	if f.Source.Kind != SourceKindPersonal {
		return fault("invalid_request", "%q declares the unknown source kind %q.",
			f.Path, f.Source.Kind)
	}
	if !personalHarnesses[f.Source.Harness] {
		return fault("invalid_request", "%q declares the unknown harness %q.",
			f.Path, f.Source.Harness)
	}
	if !strings.HasPrefix(f.Path, PersonalPrefix+f.Source.Harness+"/") {
		return fault("invalid_request",
			"%q declares a personal source but does not sit under %s%s/.",
			f.Path, PersonalPrefix, f.Source.Harness)
	}
	return nil
}

// Fault is a rejected manifest: a stable code from the contract's closed list
// plus a sentence naming the offending value.
type Fault struct {
	Code    string
	Message string
}

func (f *Fault) Error() string { return f.Code + ": " + f.Message }

func fault(code, format string, args ...any) *Fault {
	return &Fault{Code: code, Message: fmt.Sprintf(format, args...)}
}

// ParseManifest decodes one manifest, rejecting unknown fields so a typo in a
// client is an error rather than a silently dropped instruction.
func ParseManifest(raw []byte) (*Manifest, error) {
	if len(raw) == 0 {
		return nil, fault("invalid_request", "manifest is required.")
	}
	d := json.NewDecoder(strings.NewReader(string(raw)))
	d.DisallowUnknownFields()
	var m Manifest
	if e := d.Decode(&m); e != nil {
		return nil, fault("invalid_json", "the manifest is not valid JSON for this contract: %s", e.Error())
	}
	return &m, nil
}

// Validate applies the contract's own limits and shape rules. The format check
// comes first, because a different format means every other rule is guesswork.
func (m *Manifest) Validate(repoID string) error {
	if m.Format != Format {
		return fault("unsupported_manifest_format",
			"this server reads %s manifests; the scan declared %q.", Format, m.Format)
	}
	if m.Repo != "" && m.Repo != repoID {
		return fault("invalid_request",
			"the manifest was scanned for repository %q but was sent to %q.", m.Repo, repoID)
	}
	if c := m.CommitOrEmpty(); c != "" && !isHex40(c) {
		return fault("invalid_request", "commit must be 40 hex characters or null.")
	}
	if len(m.Files) > MaxFiles {
		return fault("limit_exceeded", "the scan holds %d files; the limit is %d.", len(m.Files), MaxFiles)
	}
	var total int64
	seen := make(map[string]bool, len(m.Files))
	for _, f := range m.Files {
		if e := validPath(f.Path); e != nil {
			return e
		}
		if seen[f.Path] {
			return fault("invalid_request", "the manifest lists %q twice.", f.Path)
		}
		seen[f.Path] = true
		if !IsSHA256(f.SHA256) {
			return fault("invalid_request", "%q has a sha256 that is not 64 lower-case hex characters.", f.Path)
		}
		if f.Size < 0 {
			return fault("invalid_request", "%q declares a negative size.", f.Path)
		}
		if f.Size > MaxBlobBytes {
			return fault("limit_exceeded", "%q is %d bytes; the per-blob limit is %d.",
				f.Path, f.Size, MaxBlobBytes)
		}
		if e := validSource(f); e != nil {
			return e
		}
		switch f.Kind {
		case KindSkill, KindDocument, KindConfig, KindResource:
		default:
			return fault("invalid_request", "%q declares the unknown kind %q.", f.Path, f.Kind)
		}
		total += f.Size
		if total > MaxTotalBytes {
			return fault("limit_exceeded", "the scan holds more than %d bytes.", MaxTotalBytes)
		}
	}
	for _, a := range m.Aliases {
		if e := validPath(a.From); e != nil {
			return e
		}
		if e := validPath(a.To); e != nil {
			return e
		}
	}
	return nil
}

// TotalBytes is the declared size of every file in the manifest.
func (m *Manifest) TotalBytes() int64 {
	var total int64
	for _, f := range m.Files {
		total += f.Size
	}
	return total
}

// Digests returns the distinct blob hashes the manifest refers to, sorted, so
// the "which of these do you already hold" question has one stable form.
func (m *Manifest) Digests() []string {
	set := make(map[string]bool, len(m.Files))
	for _, f := range m.Files {
		set[f.SHA256] = true
	}
	out := make([]string, 0, len(set))
	for sha := range set {
		out = append(out, sha)
	}
	sort.Strings(out)
	return out
}

// Wants reports whether the manifest asks for one blob. A hash that is not
// listed is refused on upload, so content the scan excluded on purpose can
// never reach the store (U1.3).
func (m *Manifest) Wants(sha string) bool {
	for _, f := range m.Files {
		if f.SHA256 == sha {
			return true
		}
	}
	return false
}

// AliasTargets maps a new path to the old path it replaces.
func (m *Manifest) AliasTargets() map[string]string {
	out := make(map[string]string, len(m.Aliases))
	for _, a := range m.Aliases {
		if a.From != "" && a.To != "" {
			out[a.To] = a.From
		}
	}
	return out
}

func validPath(p string) error {
	switch {
	case p == "":
		return fault("invalid_request", "the manifest holds an empty path.")
	case len(p) > MaxPathBytes:
		return fault("invalid_request", "a manifest path is longer than %d bytes.", MaxPathBytes)
	case strings.HasPrefix(p, "/"), strings.Contains(p, `\`):
		return fault("invalid_request", "%q is not a repository-relative path.", p)
	case strings.ContainsRune(p, 0):
		return fault("invalid_request", "a manifest path holds a NUL byte.")
	}
	for _, seg := range strings.Split(p, "/") {
		if seg == "" || seg == "." || seg == ".." {
			return fault("invalid_request", "%q is not a normalised path.", p)
		}
	}
	return nil
}

// IsSHA256 reports whether s is 64 lower-case hex characters.
func IsSHA256(s string) bool {
	if len(s) != 64 {
		return false
	}
	for i := 0; i < 64; i++ {
		c := s[i]
		if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f') {
			return false
		}
	}
	return true
}

func isHex40(s string) bool {
	if len(s) != 40 {
		return false
	}
	for i := 0; i < 40; i++ {
		c := s[i]
		if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f' || c >= 'A' && c <= 'F') {
			return false
		}
	}
	return true
}

// ManifestDigest is sha256 of the canonical JSON encoding of the manifest
// (API-CONTRACT §5.6). It is computed from the bytes the client sent, not from
// the decoded struct, so a field this server does not model still counts.
func ManifestDigest(raw []byte) (string, error) {
	canonical, e := CanonicalJSON(raw)
	if e != nil {
		return "", e
	}
	sum := sha256.Sum256(canonical)
	return hex.EncodeToString(sum[:]), nil
}

// CanonicalJSON re-encodes a JSON document byte-for-byte the way the CLI's
// `_canonical_json` does: keys sorted by code point, no whitespace, numbers
// verbatim, non-ASCII left as UTF-8. The two implementations have to agree,
// because the CLI's idempotency key and the server's manifest_digest are the
// same value computed on two machines.
func CanonicalJSON(raw []byte) ([]byte, error) {
	d := json.NewDecoder(strings.NewReader(string(raw)))
	d.UseNumber()
	var value any
	if e := d.Decode(&value); e != nil {
		return nil, fault("invalid_json", "the manifest is not valid JSON.")
	}
	var out strings.Builder
	if e := writeCanonical(&out, value); e != nil {
		return nil, e
	}
	return []byte(out.String()), nil
}

func writeCanonical(out *strings.Builder, value any) error {
	switch v := value.(type) {
	case nil:
		out.WriteString("null")
	case bool:
		if v {
			out.WriteString("true")
		} else {
			out.WriteString("false")
		}
	case json.Number:
		out.WriteString(v.String())
	case string:
		writeCanonicalString(out, v)
	case []any:
		out.WriteByte('[')
		for i, item := range v {
			if i > 0 {
				out.WriteByte(',')
			}
			if e := writeCanonical(out, item); e != nil {
				return e
			}
		}
		out.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(v))
		for k := range v {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		out.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				out.WriteByte(',')
			}
			writeCanonicalString(out, k)
			out.WriteByte(':')
			if e := writeCanonical(out, v[k]); e != nil {
				return e
			}
		}
		out.WriteByte('}')
	default:
		return fault("invalid_json", "the manifest holds a value this server cannot encode.")
	}
	return nil
}

// writeCanonicalString matches Python's json encoder with ensure_ascii=False:
// the six short escapes, \u00xx for the remaining control characters, and every
// other rune written as UTF-8. Go's own encoder differs (it escapes <, > and &
// by default and spells backspace and form feed with \u escapes), which is
// why this is hand-rolled rather than delegated to encoding/json.
func writeCanonicalString(out *strings.Builder, s string) {
	out.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			out.WriteString(`\"`)
		case '\\':
			out.WriteString(`\\`)
		case '\b':
			out.WriteString(`\b`)
		case '\f':
			out.WriteString(`\f`)
		case '\n':
			out.WriteString(`\n`)
		case '\r':
			out.WriteString(`\r`)
		case '\t':
			out.WriteString(`\t`)
		default:
			if r < 0x20 {
				const hexDigits = "0123456789abcdef"
				out.WriteString(`\u00`)
				out.WriteByte(hexDigits[(r>>4)&0xf])
				out.WriteByte(hexDigits[r&0xf])
				continue
			}
			out.WriteRune(r)
		}
	}
	out.WriteByte('"')
}
