// Package testdb runs one throwaway PostgreSQL cluster per test process.
//
// It uses the plain PostgreSQL binaries from GUIDEFOLD_PG_BIN (default
// ~/.cache/guidefold/toolchain/pg18/bin), so tests exercise the same "plain
// PostgreSQL profile" the migration has to tolerate: no pg_search, no pgvector.
// The cluster is initdb'd under ~/.cache/guidefold/pg/test-<pid>, listens on a
// free loopback port with fsync off, and is stopped and deleted by Main.
//
//	func TestMain(m *testing.M) { testdb.Main(m) }
//	dsn, pool := testdb.Start(t)
package testdb

import (
	"context"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"sync/atomic"
	"syscall"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/wiatrM/guidefold/services/search/internal/schema"
)

// TestAppPassword is the guidefold_api password the test migration installs.
// The role is never used by tests (they connect as the bootstrap superuser);
// the value only has to satisfy the migration's own length rule.
const TestAppPassword = "guidefold-test-app-password-0123456789"

const templateDB = "guidefold_template"

type cluster struct {
	dir  string
	port int
	proc *exec.Cmd
}

var (
	boot     sync.Once
	shared   *cluster
	bootErr  error
	bootSkip string
	created  atomic.Int64
	makeMu   sync.Mutex
)

// BinDir is the directory holding initdb/postgres.
func BinDir() string {
	if v := os.Getenv("GUIDEFOLD_PG_BIN"); v != "" {
		return v
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".cache", "guidefold", "toolchain", "pg18", "bin")
}

// Required reports whether a missing database must fail the run instead of
// skipping it. CI sets GUIDEFOLD_REQUIRE_PG=1 so a green pipeline cannot be
// produced by a suite that never ran.
func Required() bool { return os.Getenv("GUIDEFOLD_REQUIRE_PG") == "1" }

// missing reports the absence of the PostgreSQL binaries as either a skip or a
// hard failure. A skip means "not measured here", not a pass, so where the
// suite is meant to be evidence -- CI -- the absence has to stop the run: every
// test that proves the three gates needs the database.
func missing(bin string, required bool) (string, error) {
	absence := fmt.Sprintf("PostgreSQL binaries not found in %s (set GUIDEFOLD_PG_BIN); "+
		"install them with tools/dev/pg.py or skip database tests", bin)
	if required {
		return "", fmt.Errorf("GUIDEFOLD_REQUIRE_PG=1 but %s", absence)
	}
	return absence, nil
}

// Main runs the package tests and then stops the cluster. It calls os.Exit.
func Main(m *testing.M) {
	code := m.Run()
	Shutdown()
	os.Exit(code)
}

// Shutdown stops the cluster and removes its data directory. Safe to call twice.
func Shutdown() {
	makeMu.Lock()
	defer makeMu.Unlock()
	c := shared
	shared = nil
	if c == nil {
		return
	}
	if c.proc != nil && c.proc.Process != nil {
		// SIGINT is PostgreSQL's "fast" shutdown: roll back, flush, exit.
		_ = c.proc.Process.Signal(syscall.SIGINT)
		done := make(chan struct{})
		go func() { _, _ = c.proc.Process.Wait(); close(done) }()
		select {
		case <-done:
		case <-time.After(15 * time.Second):
			_ = c.proc.Process.Kill()
		}
	}
	_ = os.RemoveAll(c.dir)
}

// Start returns a DSN and pool for a fresh, fully migrated database. The
// database is dropped when the test finishes. The first call boots the cluster.
func Start(t *testing.T) (string, *pgxpool.Pool) {
	t.Helper()
	boot.Do(bootstrap)
	if bootSkip != "" {
		t.Skip(bootSkip)
	}
	if bootErr != nil {
		t.Fatalf("testdb: %v", bootErr)
	}
	name := fmt.Sprintf("gft_%d", created.Add(1))
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	makeMu.Lock()
	admin, e := connect(ctx, shared.port, "postgres")
	if e == nil {
		_, e = admin.Exec(ctx, `CREATE DATABASE `+quoteIdent(name)+` TEMPLATE `+quoteIdent(templateDB))
		admin.Close()
	}
	port := shared.port
	makeMu.Unlock()
	if e != nil {
		t.Fatalf("testdb: create database: %v", e)
	}
	pool, e := connect(ctx, port, name)
	if e != nil {
		t.Fatalf("testdb: connect: %v", e)
	}
	t.Cleanup(func() {
		pool.Close()
		drop, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		makeMu.Lock()
		defer makeMu.Unlock()
		if shared == nil {
			return
		}
		if admin, e := connect(drop, port, "postgres"); e == nil {
			_, _ = admin.Exec(drop, `DROP DATABASE IF EXISTS `+quoteIdent(name)+` WITH (FORCE)`)
			admin.Close()
		}
	})
	return dsn(port, name), pool
}

func bootstrap() {
	bin := BinDir()
	for _, tool := range []string{"initdb", "postgres"} {
		if _, e := os.Stat(filepath.Join(bin, tool)); e != nil {
			bootSkip, bootErr = missing(bin, Required())
			return
		}
	}
	home, e := os.UserHomeDir()
	if e != nil {
		bootErr = e
		return
	}
	dir := filepath.Join(home, ".cache", "guidefold", "pg", fmt.Sprintf("test-%d", os.Getpid()))
	if e = os.RemoveAll(dir); e != nil {
		bootErr = e
		return
	}
	if e = os.MkdirAll(filepath.Dir(dir), 0o700); e != nil {
		bootErr = e
		return
	}
	out, e := exec.Command(filepath.Join(bin, "initdb"),
		"-D", dir, "-U", "postgres", "-A", "trust",
		"--encoding=UTF8", "--locale=C", "--no-sync").CombinedOutput()
	if e != nil {
		bootErr = fmt.Errorf("initdb: %v: %s", e, out)
		return
	}
	port, e := freePort()
	if e != nil {
		bootErr = e
		return
	}
	conf := fmt.Sprintf(`
listen_addresses = '127.0.0.1'
port = %d
unix_socket_directories = ''
fsync = off
synchronous_commit = off
full_page_writes = off
autovacuum = off
max_connections = 200
shared_buffers = 32MB
log_min_messages = warning
`, port)
	f, e := os.OpenFile(filepath.Join(dir, "postgresql.conf"), os.O_APPEND|os.O_WRONLY, 0o600)
	if e != nil {
		bootErr = e
		return
	}
	_, e = f.WriteString(conf)
	f.Close()
	if e != nil {
		bootErr = e
		return
	}
	proc := exec.Command(filepath.Join(bin, "postgres"), "-D", dir)
	proc.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if e = proc.Start(); e != nil {
		bootErr = fmt.Errorf("postgres: %w", e)
		return
	}
	shared = &cluster{dir: dir, port: port, proc: proc}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	if e = waitReady(ctx, port); e != nil {
		bootErr = e
		Shutdown()
		return
	}
	if e = migrateTemplate(ctx, port); e != nil {
		bootErr = e
		Shutdown()
		return
	}
}

// migrateTemplate builds the migrated template once. Every test database is a
// file-level copy of it, so a test pays for CREATE DATABASE, not for the DDL.
func migrateTemplate(ctx context.Context, port int) error {
	admin, e := connect(ctx, port, "postgres")
	if e != nil {
		return e
	}
	_, e = admin.Exec(ctx, `CREATE DATABASE `+quoteIdent(templateDB))
	admin.Close()
	if e != nil {
		return fmt.Errorf("create template: %w", e)
	}
	pool, e := connect(ctx, port, templateDB)
	if e != nil {
		return e
	}
	e = schema.Migrate(ctx, pool, TestAppPassword)
	pool.Close()
	if e != nil {
		return fmt.Errorf("migrate template: %w", e)
	}
	return nil
}

func waitReady(ctx context.Context, port int) error {
	deadline := time.Now().Add(45 * time.Second)
	var last error
	for time.Now().Before(deadline) {
		probe, cancel := context.WithTimeout(ctx, 2*time.Second)
		pool, e := connect(probe, port, "postgres")
		if e == nil {
			e = pool.Ping(probe)
			pool.Close()
		}
		cancel()
		if e == nil {
			return nil
		}
		last = e
		time.Sleep(150 * time.Millisecond)
	}
	return fmt.Errorf("postgres did not become ready: %w", last)
}

func connect(ctx context.Context, port int, db string) (*pgxpool.Pool, error) {
	cfg, e := pgxpool.ParseConfig(dsn(port, db))
	if e != nil {
		return nil, e
	}
	cfg.MaxConns = 16
	cfg.MinConns = 0
	cfg.ConnConfig.ConnectTimeout = 5 * time.Second
	cfg.ConnConfig.RuntimeParams["application_name"] = "guidefold-test"
	return pgxpool.NewWithConfig(ctx, cfg)
}

func dsn(port int, db string) string {
	return fmt.Sprintf("postgres://postgres@127.0.0.1:%d/%s?sslmode=disable", port, db)
}

func freePort() (int, error) {
	l, e := net.Listen("tcp", "127.0.0.1:0")
	if e != nil {
		return 0, e
	}
	defer l.Close()
	return l.Addr().(*net.TCPAddr).Port, nil
}

// Database names here are generated, never user input; the quoting keeps the
// statement safe if that ever changes.
func quoteIdent(s string) string {
	out := make([]byte, 0, len(s)+2)
	out = append(out, '"')
	for i := 0; i < len(s); i++ {
		if s[i] == '"' {
			out = append(out, '"')
		}
		out = append(out, s[i])
	}
	return string(append(out, '"'))
}
