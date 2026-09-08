package schema

// Telemetry projection and the two ledger indexes the usage module reads
// (API-CONTRACT §7). They are in their own file because they straddle the two
// schemas: the projection is a management table, the indexes belong to the
// append-only catalog ledger, and both exist for one reader.
//
// gfm.adapter_health is a projection, not a source of truth. The API writes it
// while ingesting a batch on /v1/events:batch, from the events themselves, so
// "which adapters are reporting, how stale are they, how much did they drop" is
// answerable without scanning the whole ledger. Losing the table loses a
// diagnostic, never an observation: the events stay in gf.events.
//
// gf.events.payload is bytea on purpose — the ledger preserves the reference's
// exact UTF-8 bytes, including NUL, which PostgreSQL's jsonb type refuses. A
// plain `payload->>'skill_id'` therefore does not exist here, and casting the
// payload to jsonb inside an index expression would make one such event
// unstorable. gf.event_field decodes defensively and answers NULL for a payload
// it cannot parse, so the index can never reject a row the ledger accepted.
const usageSQL = `
CREATE TABLE IF NOT EXISTS gfm.adapter_health (
 org_id uuid NOT NULL REFERENCES gfm.orgs(org_id) ON DELETE CASCADE,
 harness text NOT NULL,
 installation_id uuid,
 adapter_version text,
 capabilities jsonb,
 last_seen_at timestamptz,
 produced bigint NOT NULL DEFAULT 0,
 acknowledged bigint NOT NULL DEFAULT 0,
 dropped bigint NOT NULL DEFAULT 0,
 oldest_lag_s integer,
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(org_id,harness)
);

CREATE OR REPLACE FUNCTION gf.event_field(payload bytea, field text) RETURNS text
 LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE STRICT AS $fn$
BEGIN
 RETURN (convert_from(payload,'UTF8')::jsonb)->>field;
EXCEPTION WHEN others THEN
 RETURN NULL;
END
$fn$;

CREATE INDEX IF NOT EXISTS events_tenant_type_occurred
 ON gf.events(tenant_id,event_type,occurred_at);
CREATE INDEX IF NOT EXISTS events_skill
 ON gf.events(tenant_id,gf.event_field(payload,'skill_id'));
INSERT INTO gf.schema_version VALUES (11) ON CONFLICT DO NOTHING;
`
