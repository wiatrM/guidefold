package model

import (
	"bufio"
	"io"
	"strings"
)

// sseEvent is one Server-Sent-Events message: an optional named type plus
// the joined body of its "data:" lines. All three providers speak SSE for a
// streamed completion; only the JSON each data line carries differs, which
// is exactly the boundary this port is built around.
type sseEvent struct {
	Event string
	Data  string
}

// maxSSELineBytes bounds one line this scanner will hold in memory. A
// provider's own delta lines are small; this is defence against a
// misbehaving proxy or test double answering with an unbounded line, not a
// real provider response shape (the same reasoning internal/ghapp's
// maxWriteResponseBytes documents for its own ceiling).
const maxSSELineBytes = 1 << 20

// scanSSE reads body as an SSE stream and calls onEvent for each message,
// in arrival order, stopping early when onEvent returns true. It returns
// once the stream ends, flushing a final message that was not terminated
// by a blank line — a provider closing the connection right after its last
// data line is normal, not truncation.
func scanSSE(body io.Reader, onEvent func(sseEvent) (stop bool)) error {
	scanner := bufio.NewScanner(body)
	scanner.Buffer(make([]byte, 0, 64*1024), maxSSELineBytes)
	var ev sseEvent
	var data []string
	flush := func() bool {
		if len(data) == 0 && ev.Event == "" {
			return false
		}
		ev.Data = strings.Join(data, "\n")
		stop := onEvent(ev)
		ev, data = sseEvent{}, nil
		return stop
	}
	for scanner.Scan() {
		line := scanner.Text()
		switch {
		case line == "":
			if flush() {
				return nil
			}
		case strings.HasPrefix(line, "data:"):
			data = append(data, strings.TrimPrefix(strings.TrimPrefix(line, "data:"), " "))
		case strings.HasPrefix(line, "event:"):
			ev.Event = strings.TrimSpace(strings.TrimPrefix(line, "event:"))
		default:
			// "id:", "retry:" and ":"-comment lines carry nothing this port
			// reads; a field it does not recognise must not abort the
			// stream, or a provider that added one would break every call.
		}
	}
	flush()
	return scanner.Err()
}
