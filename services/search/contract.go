package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/dlclark/regexp2"
	"github.com/santhosh-tekuri/jsonschema/v6"
)

type M = map[string]any

func obj(v any) M      { m, _ := v.(map[string]any); return m }
func str(v any) string { s, _ := v.(string); return s }
func arr(v any) []any  { a, _ := v.([]any); return a }
func text(m M, k, def string) string {
	if v, ok := m[k]; ok {
		return str(v)
	}
	return def
}
func number(v any) int64 {
	switch n := v.(type) {
	case json.Number:
		i, _ := n.Int64()
		return i
	case float64:
		return int64(n)
	case int64:
		return n
	case int:
		return int64(n)
	}
	return 0
}
func integer(m M, k string, def int64) int64 {
	if v, ok := m[k]; ok {
		return number(v)
	}
	return def
}
func stringList(v any) []string {
	out := []string{}
	for _, x := range arr(v) {
		out = append(out, str(x))
	}
	return out
}
func keys[V any](m map[string]V) []string {
	a := make([]string, 0, len(m))
	for k := range m {
		a = append(a, k)
	}
	sort.Strings(a)
	return a
}
func hash(b []byte) string { s := sha256.Sum256(b); return hex.EncodeToString(s[:]) }
func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}
func secret(path string) (string, error) {
	b, e := os.ReadFile(path)
	if e != nil {
		return "", e
	}
	s := strings.TrimSpace(string(b))
	if len(s) < 32 {
		return "", fmt.Errorf("secret_too_short")
	}
	return s, nil
}

type APIError struct {
	Status int
	Code   string
}

func (e *APIError) Error() string        { return e.Code }
func fail(status int, code string) error { return &APIError{status, code} }

// Python snapshot canonical JSON: sorted keys, UTF-8 (also U+2028/U+2029), no HTML escaping.
// Request JSON uses the normal encoder. Only this digest format needs custom quoting.
func canonical(v any) []byte              { return canonicalJSON(v, false, false) }
func pythonJSON(v any, ascii bool) []byte { return canonicalJSON(v, true, ascii) }
func canonicalJSON(v any, spaced, ascii bool) []byte {
	var b bytes.Buffer
	var write func(any)
	quote := func(s string) {
		b.WriteByte('"')
		for _, r := range s {
			switch r {
			case '"', '\\':
				b.WriteByte('\\')
				b.WriteRune(r)
			case '\b':
				b.WriteString(`\b`)
			case '\f':
				b.WriteString(`\f`)
			case '\n':
				b.WriteString(`\n`)
			case '\r':
				b.WriteString(`\r`)
			case '\t':
				b.WriteString(`\t`)
			default:
				if r < 32 {
					fmt.Fprintf(&b, `\u%04x`, r)
				} else if ascii && r > 127 {
					if r <= 65535 {
						fmt.Fprintf(&b, `\u%04x`, r)
					} else {
						x := r - 65536
						fmt.Fprintf(&b, `\u%04x\u%04x`, 0xd800+(x>>10), 0xdc00+(x&1023))
					}
				} else {
					b.WriteRune(r)
				}
			}
		}
		b.WriteByte('"')
	}
	write = func(v any) {
		switch x := v.(type) {
		case map[string]any:
			b.WriteByte('{')
			for i, k := range keys(x) {
				if i > 0 {
					b.WriteByte(',')
					if spaced {
						b.WriteByte(' ')
					}
				}
				quote(k)
				b.WriteByte(':')
				if spaced {
					b.WriteByte(' ')
				}
				write(x[k])
			}
			b.WriteByte('}')
		case []any:
			b.WriteByte('[')
			for i, a := range x {
				if i > 0 {
					b.WriteByte(',')
					if spaced {
						b.WriteByte(' ')
					}
				}
				write(a)
			}
			b.WriteByte(']')
		case string:
			quote(x)
		case json.Number:
			b.WriteString(string(x))
		default:
			j, e := json.Marshal(x)
			if e != nil {
				panic(e)
			}
			b.Write(j)
		}
	}
	write(v)
	return b.Bytes()
}

// encoding/json replaces invalid Unicode. Reject it before decoding, including lone escapes.
func strictJSON(data []byte) (any, error) {
	if !utf8.Valid(data) {
		return nil, fmt.Errorf("invalid_utf8")
	}
	in := false
	for i := 0; i < len(data); i++ {
		if data[i] == '"' {
			in = !in
			continue
		}
		if !in || data[i] != '\\' {
			continue
		}
		i++
		if i >= len(data) {
			break
		}
		if data[i] != 'u' {
			continue
		}
		if i+4 >= len(data) {
			return nil, fmt.Errorf("invalid_escape")
		}
		n, e := strconv.ParseUint(string(data[i+1:i+5]), 16, 16)
		if e != nil {
			return nil, e
		}
		i += 4
		if n >= 0xd800 && n <= 0xdbff {
			if i+6 >= len(data) || data[i+1] != '\\' || data[i+2] != 'u' {
				return nil, fmt.Errorf("lone_surrogate")
			}
			lo, e := strconv.ParseUint(string(data[i+3:i+7]), 16, 16)
			if e != nil || lo < 0xdc00 || lo > 0xdfff {
				return nil, fmt.Errorf("lone_surrogate")
			}
			i += 6
		} else if n >= 0xdc00 && n <= 0xdfff {
			return nil, fmt.Errorf("lone_surrogate")
		}
	}
	d := json.NewDecoder(bytes.NewReader(data))
	d.UseNumber()
	var parse func(int) (any, error)
	parse = func(depth int) (any, error) {
		if depth > 64 {
			return nil, fmt.Errorf("json_too_deep")
		}
		t, e := d.Token()
		if e != nil {
			return nil, e
		}
		switch t {
		case json.Delim('{'):
			m := M{}
			for d.More() {
				k, e := d.Token()
				if e != nil {
					return nil, e
				}
				s, ok := k.(string)
				if !ok {
					return nil, fmt.Errorf("invalid_key")
				}
				if _, ok = m[s]; ok {
					return nil, fmt.Errorf("duplicate_key")
				}
				v, e := parse(depth + 1)
				if e != nil {
					return nil, e
				}
				m[s] = v
			}
			_, e = d.Token()
			return m, e
		case json.Delim('['):
			a := []any{}
			for d.More() {
				v, e := parse(depth + 1)
				if e != nil {
					return nil, e
				}
				a = append(a, v)
			}
			_, e = d.Token()
			return a, e
		default:
			if _, ok := t.(json.Delim); ok {
				return nil, fmt.Errorf("invalid_json")
			}
			return t, nil
		}
	}
	v, e := parse(0)
	if e != nil {
		return nil, e
	}
	if _, e = d.Token(); e != io.EOF {
		return nil, fmt.Errorf("trailing_json")
	}
	return v, nil
}

type schemaRegexp struct{ *regexp2.Regexp }

func (r schemaRegexp) MatchString(s string) bool {
	v, e := r.Regexp.MatchString(s)
	return e == nil && v
}

type Validator struct{ search, use *jsonschema.Schema }

func newValidator(path string) (*Validator, error) {
	data, e := os.ReadFile(path)
	if e != nil {
		return nil, e
	}
	schema, e := jsonschema.UnmarshalJSON(bytes.NewReader(data))
	if e != nil {
		return nil, e
	}
	c := jsonschema.NewCompiler()
	c.UseRegexpEngine(func(s string) (jsonschema.Regexp, error) {
		r, e := regexp2.Compile(s, regexp2.ECMAScript)
		if e != nil {
			return nil, e
		}
		r.MatchTimeout = 50 * time.Millisecond
		return schemaRegexp{r}, nil
	})
	const uri = "urn:guidefold:harness-service:1.1"
	if e = c.AddResource(uri, schema); e != nil {
		return nil, e
	}
	a, e := c.Compile(uri + "#/$defs/search_request")
	if e != nil {
		return nil, e
	}
	b, e := c.Compile(uri + "#/$defs/use_request")
	return &Validator{a, b}, e
}
func (v *Validator) validate(p M, endpoint string) error {
	if p == nil {
		return fail(400, "invalid_payload")
	}
	contextual := false
	base := map[string]bool{"query": true, "node": true, "profile": true, "deadline_ms": true}
	if endpoint == "use" {
		base = map[string]bool{"skill_id": true, "revision": true, "search_id": true, "deadline_ms": true}
	}
	for k := range p {
		if !base[k] {
			contextual = true
		}
	}
	if contextual && str(p["schema_version"]) != "1.1" {
		return fail(400, "unsupported_schema_version")
	}
	cp := M{}
	for k, x := range p {
		cp[k] = x
	}
	cp["schema_version"] = "1.1"
	sch := v.search
	if endpoint == "use" {
		sch = v.use
	}
	if e := sch.Validate(cp); e != nil {
		return fail(400, "invalid_request_schema")
	}
	for _, m := range []M{p, obj(p["budget"])} {
		for _, k := range []string{"deadline_ms", "max_cards", "max_bytes", "remaining_skill_tokens"} {
			if n, ok := m[k]; ok {
				if x, ok := n.(json.Number); !ok || strings.ContainsAny(x.String(), ".eE") {
					return fail(400, "invalid_integer")
				}
			}
		}
	}
	var validStrings func(any) bool
	validStrings = func(x any) bool {
		switch a := x.(type) {
		case string:
			if strings.TrimSpace(a) == "" {
				return false
			}
			for _, r := range a {
				if r < 32 {
					return false
				}
			}
		case M:
			for _, s := range a {
				if !validStrings(s) {
					return false
				}
			}
		case []any:
			for _, s := range a {
				if !validStrings(s) {
					return false
				}
			}
		}
		return true
	}
	for k, x := range p {
		if !base[k] && !validStrings(x) {
			return fail(400, "invalid_context_value")
		}
	}
	if endpoint == "search" && strings.TrimSpace(str(p["query"])) == "" {
		return fail(400, "invalid_query")
	}
	return nil
}
