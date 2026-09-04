// Package audit is the shared structured audit-event logger for Meridian services.
// Every read or change of labelled data emits exactly one Event through Logger.Emit.
package audit

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"sync"
	"time"

	authsdk "meridian.example/libs/auth-sdk"
	"meridian.example/libs/classification"
)

// SchemaVersion is bumped only when a field is added; fields are never removed.
const SchemaVersion = 3

// Outcome is the result of the audited operation.
type Outcome string

const (
	Allowed Outcome = "allowed"
	Denied  Outcome = "denied"
	Failed  Outcome = "failed"
)

// Event is one audit record. JSON names are the wire schema and are append-only.
type Event struct {
	SchemaVersion  int                  `json:"schema_version"`
	Time           time.Time            `json:"time"`
	Service        string               `json:"service"`
	Actor          string               `json:"actor"`
	SessionID      string               `json:"session_id"`
	Action         string               `json:"action"`
	Resource       string               `json:"resource"`
	Classification classification.Label `json:"classification"`
	Outcome        Outcome              `json:"outcome"`
	CorrelationID  string               `json:"correlation_id"`
	Details        map[string]string    `json:"details,omitempty"`
	PrevHash       string               `json:"prev_hash"`
	Hash           string               `json:"hash"`
}

// Config wires a Logger to its service identity and its append-only sink.
type Config struct {
	Service string
	Sink    io.Writer // production: streaming sink; tests and air-gapped buffering: file sink
}

// Logger emits hash-chained events. Construct one per process.
type Logger struct {
	cfg  Config
	mu   sync.Mutex
	prev string
}

func NewLogger(cfg Config) (*Logger, error) {
	if cfg.Service == "" || cfg.Sink == nil {
		return nil, errors.New("audit: Service and Sink are required")
	}
	return &Logger{cfg: cfg}, nil
}

// Emit fills actor and session from the auth-sdk principal in ctx, chains the hash and writes
// synchronously. A sink error is returned so the caller blocks the operation.
func (l *Logger) Emit(ctx context.Context, ev Event) error {
	p := authsdk.PrincipalFrom(ctx)
	if p == nil {
		return errors.New("audit: no principal in context")
	}
	if ev.Action == "" || ev.Resource == "" || ev.Outcome == "" {
		return fmt.Errorf("audit: action, resource and outcome are mandatory (action=%q)", ev.Action)
	}
	ev.SchemaVersion, ev.Service = SchemaVersion, l.cfg.Service
	ev.Actor, ev.SessionID = p.Subject, p.SessionID
	ev.Time = time.Now().UTC()

	l.mu.Lock()
	defer l.mu.Unlock()
	ev.PrevHash = l.prev
	body, _ := json.Marshal(ev)
	sum := sha256.Sum256(body)
	ev.Hash = hex.EncodeToString(sum[:])
	line, _ := json.Marshal(ev)
	if _, err := l.cfg.Sink.Write(append(line, '\n')); err != nil {
		return fmt.Errorf("audit: sink write failed, operation must not proceed: %w", err)
	}
	l.prev = ev.Hash
	return nil
}
