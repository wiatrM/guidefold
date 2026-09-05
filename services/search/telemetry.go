package main

import (
	"context"
	_ "embed"
	"encoding/json"
	"fmt"
	"github.com/jackc/pgx/v5"
	"os"
	"strings"
	"time"
)

//go:embed telemetry-schema.json
var telemetrySchemaJSON []byte

var telemetrySchema = func() M {
	v, e := strictJSON(telemetrySchemaJSON)
	if e != nil {
		panic(e)
	}
	return obj(v)
}()

const telemetryMigration = `
CREATE TABLE IF NOT EXISTS gf.events (
 tenant_id text NOT NULL, event_id bytea NOT NULL,
 event_type text NOT NULL, schema_version text NOT NULL,
 occurred_at text NOT NULL, received_at text NOT NULL,
 search_id text, load_id text, payload bytea NOT NULL,
 PRIMARY KEY(tenant_id,event_id)
);
CREATE INDEX IF NOT EXISTS events_tenant_type ON gf.events(tenant_id,event_type);
CREATE INDEX IF NOT EXISTS events_occurred ON gf.events(occurred_at);
CREATE INDEX IF NOT EXISTS events_search ON gf.events(tenant_id,search_id);
CREATE INDEX IF NOT EXISTS events_load ON gf.events(tenant_id,load_id);
INSERT INTO gf.schema_version VALUES (7) ON CONFLICT DO NOTHING;
`

// ID/payload bytes preserve the reference's exact UTF-8 strings (including NUL)
// without PostgreSQL JSONB/text restrictions. HTTP still uses ordinary JSON IDs.
func requiredEventFields(e M, required, nullable []string) string {
	for _, k := range required {
		v, exists := e[k]
		empty, isString := v.(string)
		if !exists || v == nil || (isString && empty == "") {
			return "missing_required_field:" + k
		}
	}
	for _, k := range nullable {
		if _, exists := e[k]; !exists {
			return "missing_required_field:" + k
		}
	}
	return ""
}
func eventMember(key string, value any) bool {
	s, ok := value.(string)
	if !ok {
		return false
	}
	for _, v := range stringList(telemetrySchema[key]) {
		if s == v {
			return true
		}
	}
	return false
}
func validEventTime(value any) bool {
	s, ok := value.(string)
	if !ok {
		return false
	}
	// Canonical UTC plus ISO offset/fraction forms emitted by the adapters.
	for _, layout := range []string{time.RFC3339Nano, "2006-01-02 15:04:05.999999999Z07:00", "2006-01-02T15:04:05.999999999Z0700", "20060102T150405.999999999Z07:00"} {
		if _, e := time.Parse(layout, s); e == nil {
			return true
		}
	}
	return false
}
func validateEvent(value any) string {
	e := obj(value)
	if e == nil {
		return "event_not_an_object"
	}
	if id, ok := e["event_id"].(string); !ok || id == "" {
		return "missing_required_field:event_id"
	}
	if reason := requiredEventFields(e, stringList(telemetrySchema["envelope_required"]), nil); reason != "" {
		return reason
	}
	if !eventMember("schema_versions", e["schema_version"]) {
		return "unsupported_schema_version"
	}
	if !eventMember("event_types", e["event_type"]) {
		return "unknown_event_type"
	}
	if !eventMember("environments", e["environment"]) {
		return "invalid_environment"
	}
	if !validEventTime(e["occurred_at"]) {
		return "invalid_occurred_at"
	}
	fields := obj(obj(telemetrySchema["required_fields"])[str(e["event_type"])])
	if reason := requiredEventFields(e, stringList(fields["required"]), stringList(fields["nullable"])); reason != "" {
		return reason
	}
	if str(e["event_type"]) == "skill_feedback" && !eventMember("verdicts", e["verdict"]) {
		return "invalid_verdict"
	}
	return ""
}
func eventLink(v any) any {
	s, ok := v.(string)
	if !ok || strings.ContainsRune(s, 0) {
		return nil
	}
	return s
}

const eventInsertSQL = `INSERT INTO gf.events(tenant_id,event_id,event_type,schema_version,occurred_at,received_at,search_id,load_id,payload) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT(tenant_id,event_id) DO NOTHING`

func (s *Store) ingestEvents(ctx context.Context, batch []any) (M, error) {
	if s.Tenant == "" {
		return nil, fmt.Errorf("verified_tenant_required")
	}
	accepted, duplicate, rejected := []any{}, []any{}, []any{}
	received := time.Now().UTC().Format("2006-01-02T15:04:05Z")
	tx, e := s.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return nil, e
	}
	defer tx.Rollback(ctx)
	queries := &pgx.Batch{}
	validIDs := []any{}
	for _, value := range batch {
		event := obj(value)
		var id any
		if event != nil {
			id = event["event_id"]
		}
		if reason := validateEvent(value); reason != "" {
			rejected = append(rejected, M{"event_id": id, "reason": reason, "retryable": false})
			continue
		}
		queries.Queue("guidefold_event_insert_v1", s.Tenant, []byte(str(id)), str(event["event_type"]), str(event["schema_version"]), str(event["occurred_at"]), received, eventLink(event["search_id"]), eventLink(event["load_id"]), canonical(event))
		validIDs = append(validIDs, id)
	}
	if len(validIDs) != 0 {
		// Prepare is idempotent per pooled connection; reuse the same plan for
		// every row without changing the pool's other query modes.
		if _, e = tx.Prepare(ctx, "guidefold_event_insert_v1", eventInsertSQL); e != nil {
			return nil, e
		}
	}
	// Send the ordered INSERTs in one protocol batch. Read every command result
	// before commit so duplicates within this batch retain their first-wins ACK,
	// and any storage error still rolls back all accepted rows.
	results := tx.SendBatch(ctx, queries)
	defer results.Close()
	for _, id := range validIDs {
		tag, err := results.Exec()
		if err != nil {
			return nil, err
		}
		if tag.RowsAffected() == 1 {
			accepted = append(accepted, id)
		} else {
			duplicate = append(duplicate, id)
		}
	}
	if e = results.Close(); e != nil {
		return nil, e
	}
	if e = tx.Commit(ctx); e != nil {
		return nil, e
	}
	return M{"accepted": accepted, "duplicate": duplicate, "rejected": rejected}, nil
}
func (s *Store) exportEvents(ctx context.Context) (M, error) {
	rows, e := s.Pool.Query(ctx, `SELECT payload FROM gf.events WHERE tenant_id=$1 ORDER BY occurred_at,event_id`, s.Tenant)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	events := []any{}
	for rows.Next() {
		var raw []byte
		if e = rows.Scan(&raw); e != nil {
			return nil, e
		}
		value, err := strictJSON(raw)
		if err != nil {
			return nil, err
		}
		events = append(events, value)
	}
	return M{"tenant_id": s.Tenant, "events": events}, rows.Err()
}
func (s *Store) eventTenants(ctx context.Context) ([]string, error) {
	rows, e := s.Pool.Query(ctx, `SELECT DISTINCT tenant_id FROM gf.events ORDER BY tenant_id`)
	if e != nil {
		return nil, e
	}
	defer rows.Close()
	tenants := []string{}
	for rows.Next() {
		var v string
		if e = rows.Scan(&v); e != nil {
			return nil, e
		}
		tenants = append(tenants, v)
	}
	return tenants, rows.Err()
}
func (s *Store) retainEvents(ctx context.Context, days int, now time.Time) (int64, error) {
	if days < 0 {
		return 0, fmt.Errorf("invalid_retention_days")
	}
	cutoff := now.UTC().AddDate(0, 0, -days).Format("2006-01-02T15:04:05Z")
	// Preserve the reference ledger's occurred_at text cutoff semantics.
	tx, e := s.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return 0, e
	}
	defer tx.Rollback(ctx)
	tag, e := tx.Exec(ctx, `DELETE FROM gf.events WHERE occurred_at < $1`, cutoff)
	if e != nil {
		return 0, e
	}
	if _, e = tx.Exec(ctx, `DELETE FROM gf.search_shadow WHERE created_at < $1::timestamptz`, cutoff); e != nil {
		return 0, e
	}
	if e = tx.Commit(ctx); e != nil {
		return 0, e
	}
	return tag.RowsAffected(), nil
}
func printOperatorResult(value any, e error) error {
	if e != nil {
		return e
	}
	return json.NewEncoder(os.Stdout).Encode(value)
}
