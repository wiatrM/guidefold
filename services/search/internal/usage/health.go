package usage

import (
	"context"
	"encoding/json"
	"regexp"
	"sort"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// uuidText is what an organisation identifier looks like. The legacy operator
// profile has a configured tenant that is not an organisation at all, and it
// must not create a row here.
var uuidText = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)

// batchHealth is what one accepted batch says about one adapter.
type batchHealth struct {
	harness      string
	version      string
	capabilities []string
	produced     int64
	acknowledged int64
	dropped      int64
	lag          int
	hasLag       bool
}

// RecordAdapterHealth updates the gfm.adapter_health projection from one
// accepted batch of events (API-CONTRACT §7).
//
// Three things about it are deliberate.
//
// The tenant is the verified principal's organisation and nothing else. The
// events carry no tenant and cannot be relabelled by one: a client whose account
// changed between spooling and flushing uploads under the identity it proves
// now, and the ledger's own rule that a spool keeps its origin partition is what
// stops the old events being attributed to the new organisation
// (SEARCH-USE-TELEMETRY §4).
//
// Only accepted events count. A retried batch re-sends the same event_ids, the
// ledger answers `duplicate`, and this function skips them — otherwise a client
// with a flaky connection would appear to have produced twice the traffic.
//
// A failure here is a lost diagnostic, never a lost observation: the events are
// already committed to gf.events, and the caller logs rather than failing the
// batch.
func RecordAdapterHealth(ctx context.Context, pool *pgxpool.Pool, orgID, installationID string,
	batch []any, result map[string]any) error {
	if pool == nil || !uuidText.MatchString(orgID) {
		return nil
	}
	accepted := acceptedIDs(result)
	if len(accepted) == 0 {
		return nil
	}
	now := time.Now().UTC()
	adapters := map[string]*batchHealth{}
	for _, raw := range batch {
		event, _ := raw.(map[string]any)
		if event == nil {
			continue
		}
		id, _ := event["event_id"].(string)
		if !accepted[id] {
			continue
		}
		harness, _ := event["producer"].(string)
		if harness == "" {
			continue
		}
		a := adapters[harness]
		if a == nil {
			a = &batchHealth{harness: harness}
			adapters[harness] = a
		}
		if v, ok := event["adapter_version"].(string); ok && v != "" {
			a.version = v
		}
		if occurred, ok := event["occurred_at"].(string); ok {
			if t, ok := parseEventTime(occurred); ok {
				lag := int(now.Sub(t).Seconds())
				if lag < 0 {
					// A client clock ahead of the server is not negative lag.
					lag = 0
				}
				if !a.hasLag || lag > a.lag {
					a.lag, a.hasLag = lag, true
				}
			}
		}
		if kind, _ := event["event_type"].(string); kind == "telemetry_health" {
			a.produced += counter(event["produced"])
			a.acknowledged += counter(event["acknowledged"])
			a.dropped += counter(event["dropped"])
			if flags := capabilityFlags(event["capability_flags"]); flags != nil {
				a.capabilities = flags
			}
		}
	}
	if len(adapters) == 0 {
		return nil
	}
	names := make([]string, 0, len(adapters))
	for name := range adapters {
		names = append(names, name)
	}
	sort.Strings(names)

	tx, e := pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return e
	}
	defer tx.Rollback(ctx)
	for _, name := range names {
		a := adapters[name]
		var capabilities any
		if a.capabilities != nil {
			encoded, _ := json.Marshal(a.capabilities)
			capabilities = string(encoded)
		}
		var lag any
		if a.hasLag {
			lag = a.lag
		}
		if _, e := tx.Exec(ctx, adapterHealthSQL, orgID, a.harness, nullable(installationID),
			nullable(a.version), capabilities, now, a.produced, a.acknowledged, a.dropped,
			lag); e != nil {
			return e
		}
	}
	return tx.Commit(ctx)
}

// adapterHealthSQL upserts one adapter's row. The counters accumulate because
// they are totals the client reports; the lag replaces, because it is a
// condition and a recovered adapter must stop looking stale.
const adapterHealthSQL = `INSERT INTO gfm.adapter_health
 (org_id,harness,installation_id,adapter_version,capabilities,last_seen_at,
  produced,acknowledged,dropped,oldest_lag_s,updated_at)
 SELECT $1::uuid,$2,$3::uuid,$4,$5::jsonb,$6,$7,$8,$9,$10,now()
 WHERE EXISTS(SELECT 1 FROM gfm.orgs WHERE org_id=$1::uuid)
 ON CONFLICT (org_id,harness) DO UPDATE SET
  installation_id=COALESCE(EXCLUDED.installation_id,gfm.adapter_health.installation_id),
  adapter_version=COALESCE(EXCLUDED.adapter_version,gfm.adapter_health.adapter_version),
  capabilities=COALESCE(EXCLUDED.capabilities,gfm.adapter_health.capabilities),
  last_seen_at=GREATEST(EXCLUDED.last_seen_at,gfm.adapter_health.last_seen_at),
  produced=gfm.adapter_health.produced+EXCLUDED.produced,
  acknowledged=gfm.adapter_health.acknowledged+EXCLUDED.acknowledged,
  dropped=gfm.adapter_health.dropped+EXCLUDED.dropped,
  oldest_lag_s=COALESCE(EXCLUDED.oldest_lag_s,gfm.adapter_health.oldest_lag_s),
  updated_at=now()`

func acceptedIDs(result map[string]any) map[string]bool {
	ids := map[string]bool{}
	list, _ := result["accepted"].([]any)
	for _, v := range list {
		if id, ok := v.(string); ok {
			ids[id] = true
		}
	}
	return ids
}

// counter reads one non-negative count. The delivery endpoint decodes request
// bodies with json.Number (it has to: an event identifier must survive intact),
// so the same value arrives as a json.Number here and as a float64 when it is
// read back out of the ledger. Both are the same number.
func counter(v any) int64 {
	switch n := v.(type) {
	case json.Number:
		parsed, e := n.Int64()
		if e != nil || parsed < 0 {
			return 0
		}
		return parsed
	case float64:
		if n < 0 {
			return 0
		}
		return int64(n)
	case int:
		if n < 0 {
			return 0
		}
		return int64(n)
	case int64:
		if n < 0 {
			return 0
		}
		return n
	}
	return 0
}

// capabilityFlags accepts the two shapes an adapter sends: a list of names and
// a map of name to boolean. Anything else is unknown, which is nil — an empty
// list would claim the adapter reported that it can do nothing.
func capabilityFlags(v any) []string {
	switch flags := v.(type) {
	case []any:
		out := []string{}
		for _, item := range flags {
			if name, ok := item.(string); ok && name != "" {
				out = append(out, name)
			}
		}
		sort.Strings(out)
		return out
	case map[string]any:
		out := []string{}
		for name, value := range flags {
			if on, ok := value.(bool); ok && !on {
				continue
			}
			out = append(out, name)
		}
		sort.Strings(out)
		return out
	}
	return nil
}
