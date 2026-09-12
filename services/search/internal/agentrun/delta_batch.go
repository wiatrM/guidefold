package agentrun

import (
	"strings"
	"time"
)

// deltaBatchInterval and deltaBatchBytes are the "~500 ms or ~2 KB" ADR-0046
// §4 names for how often a streamed model.delta becomes a durable event —
// the exact thresholds are this package's own reading of "~", not a number
// the contract pins down further.
const (
	deltaBatchInterval = 500 * time.Millisecond
	deltaBatchBytes    = 2048
)

// deltaBatcher buffers text deltas from one model.Client.Stream call and
// calls flush whenever the buffer would exceed deltaBatchBytes or
// deltaBatchInterval has passed since the last flush — never on every
// individual delta, so a chatty model cannot turn one repository into
// thousands of event rows (ADR-0046 §4).
type deltaBatcher struct {
	flush     func(text string) error
	buf       strings.Builder
	lastFlush time.Time
	now       func() time.Time
	// err is the first error a flush produced. Stream's own callback
	// signature (func(string), no error return) cannot report a failure
	// directly, so it is captured here and checked by the caller after the
	// streamed call returns.
	err error
}

func newDeltaBatcher(flush func(text string) error) *deltaBatcher {
	return &deltaBatcher{flush: flush, now: time.Now, lastFlush: time.Now()}
}

// onDelta is passed to model.Client.Stream as the DeltaFunc.
func (b *deltaBatcher) onDelta(text string) {
	if b.err != nil || text == "" {
		return
	}
	b.buf.WriteString(text)
	if b.buf.Len() >= deltaBatchBytes || b.now().Sub(b.lastFlush) >= deltaBatchInterval {
		b.flushNow()
	}
}

func (b *deltaBatcher) flushNow() {
	if b.buf.Len() == 0 {
		b.lastFlush = b.now()
		return
	}
	text := b.buf.String()
	b.buf.Reset()
	b.lastFlush = b.now()
	if e := b.flush(text); e != nil && b.err == nil {
		b.err = e
	}
}

// done flushes whatever is left in the buffer and returns the first error a
// flush produced, if any — called once Stream itself has returned.
func (b *deltaBatcher) done() error {
	b.flushNow()
	return b.err
}
