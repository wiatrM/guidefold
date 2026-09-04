// Package db provides the shared Postgres connection pool used by every Meridian service.
package db

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// maxConns is the per-replica pool ceiling. Services may lower it through Config.MaxConns but
// must not exceed it without platform-engineering review (see the postgres-production skill).
const maxConns int32 = 20

// Config is the subset of pool settings a service is allowed to tune.
type Config struct {
	URL             string
	MaxConns        int32         // 0 means maxConns; values above maxConns are clamped
	MinConns        int32
	MaxConnLifetime time.Duration // 0 means 30m
	AppName         string        // reported as pg_stat_activity.application_name
}

// NewPool builds a pgxpool.Pool with Meridian defaults applied.
func NewPool(ctx context.Context, cfg Config) (*pgxpool.Pool, error) {
	pc, err := pgxpool.ParseConfig(cfg.URL)
	if err != nil {
		return nil, fmt.Errorf("db: parse config: %w", err)
	}
	pc.MaxConns = maxConns
	if cfg.MaxConns > 0 && cfg.MaxConns < maxConns {
		pc.MaxConns = cfg.MaxConns
	}
	pc.MinConns = cfg.MinConns
	pc.MaxConnLifetime = 30 * time.Minute
	if cfg.MaxConnLifetime > 0 {
		pc.MaxConnLifetime = cfg.MaxConnLifetime
	}
	pc.ConnConfig.RuntimeParams["application_name"] = cfg.AppName
	pc.ConnConfig.RuntimeParams["statement_timeout"] = "30s"
	return pgxpool.NewWithConfig(ctx, pc)
}
