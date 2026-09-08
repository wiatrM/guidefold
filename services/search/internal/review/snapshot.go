package review

import (
	"context"
	"encoding/json"
)

// snapshotNodes reads a published snapshot's graph back out of the immutable
// catalog.
//
// Reactivation validates the graph the snapshot actually holds, not the one the
// management tables hold now: rolling back to yesterday's snapshot must not be
// blocked, or allowed, by a change made since (ADR-0028).
func snapshotNodes(ctx context.Context, tx pgxTx, orgID, repoID, snapshotID string) ([]Node, map[string]bool, error) {
	rows, e := tx.Query(ctx, `SELECT urn,node,metadata::text FROM gf.skills
 WHERE tenant=$1 AND repo=$2 AND snapshot_id=$3 ORDER BY urn`, orgID, repoID, snapshotID)
	if e != nil {
		return nil, nil, e
	}
	defer rows.Close()
	nodes := []Node{}
	known := map[string]bool{}
	for rows.Next() {
		var urn, node, metadata string
		if e = rows.Scan(&urn, &node, &metadata); e != nil {
			return nil, nil, e
		}
		var card map[string]any
		_ = json.Unmarshal([]byte(metadata), &card)
		nodes = append(nodes, Node{SkillID: urn, Scope: node,
			Requires: stringList(card["requires"]), Refines: stringList(card["refines"])})
		known[urn] = true
	}
	return nodes, known, rows.Err()
}

func stringList(v any) []string {
	switch value := v.(type) {
	case []any:
		out := make([]string, 0, len(value))
		for _, item := range value {
			if s, ok := item.(string); ok && s != "" {
				out = append(out, s)
			}
		}
		return out
	case []string:
		return value
	case string:
		if value == "" {
			return nil
		}
		return []string{value}
	}
	return nil
}
