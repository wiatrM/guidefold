package mgmt

import (
	"encoding/base64"
	"strings"
)

// Cursors are opaque to the client and keyset-based on the server: they carry
// the sort key of the last row of a page, never an offset. An offset would skip
// or repeat rows when the underlying table changes between pages, which for a
// catalog that an import is actively rewriting is not a corner case.

// EncodeCursor packs the sort key of the last row into one opaque token.
func EncodeCursor(parts ...string) string {
	return base64.RawURLEncoding.EncodeToString([]byte(strings.Join(parts, "\x1f")))
}

// DecodeCursor unpacks a cursor into exactly n parts. A cursor that does not
// decode, or that carries the wrong number of parts, is a client error rather
// than a silent first page: paging that quietly restarts loses rows.
func DecodeCursor(cursor string, n int) ([]string, error) {
	raw, e := base64.RawURLEncoding.DecodeString(cursor)
	if e != nil {
		return nil, Invalid("invalid_cursor", "cursor must be the next_cursor of a previous page.")
	}
	parts := strings.Split(string(raw), "\x1f")
	if len(parts) != n {
		return nil, Invalid("invalid_cursor", "cursor must be the next_cursor of a previous page.")
	}
	return parts, nil
}
