package mgmt

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/http"

	"github.com/jackc/pgx/v5"
)

const nilOrg = "00000000-0000-0000-0000-000000000000"

func newReader(b []byte) io.Reader { return bytes.NewReader(b) }

// replayable makes a mutation safe to repeat.
//
// The key is claimed before the handler runs, so a repeat that arrives while
// the first is still working is told so rather than doing the work twice. The
// same key with a different payload is a client bug and is rejected; the same
// key with the same payload returns the first response byte for byte.
func (rt *Router) replayable(c *Context, h Handler, live bool) error {
	key := c.idempotencyKey()
	if key == "" {
		return Invalid("idempotency_key_required",
			"Send an Idempotency-Key header or an idempotency_key field.")
	}
	if len(key) > 200 {
		return Invalid("idempotency_key_invalid", "The idempotency key is too long.")
	}
	orgID := c.ResolveOrgID(c.Ctx(), c.Param("org"))
	if orgID == "" {
		orgID = nilOrg
	}
	principal := c.Principal.ID()
	sum := sha256.Sum256(append([]byte(c.R.Method+" "+c.R.URL.Path+"\n"), c.Body...))
	digest := hex.EncodeToString(sum[:])

	claimed, stored, e := rt.claim(c.Ctx(), orgID, principal, key, digest)
	if e != nil {
		return e
	}
	if !claimed {
		if stored.payload != digest {
			return Conflict("idempotency_payload_mismatch",
				"This idempotency key was already used with a different request body.")
		}
		if stored.status == 0 {
			return Conflict("idempotency_in_progress",
				"A request with this idempotency key is still running.")
		}
		if live {
			// The stored answer was true when it was written and is not true
			// now. Run the handler again: the resource itself refuses to
			// duplicate the work.
			c.W.Header().Set("Idempotent-Replay", "false")
			return h(c)
		}
		c.W.Header().Set("Idempotent-Replay", "true")
		if len(stored.body) > 0 {
			c.W.Header().Set("Content-Type", "application/json")
		}
		c.W.WriteHeader(stored.status)
		_, _ = c.W.Write(stored.body)
		return nil
	}
	rec, _ := c.W.(*recorder)
	if rec != nil {
		rec.capture = true
	}
	err := h(c)
	if err != nil {
		// A failed mutation must not be replayed as a success, and must not
		// hold the key hostage: release it so the client can retry.
		rt.release(context.WithoutCancel(c.Ctx()), orgID, principal, key)
		return err
	}
	if rec != nil {
		status := rec.status
		if status == 0 {
			status = http.StatusOK
		}
		rt.store(context.WithoutCancel(c.Ctx()), orgID, principal, key, status, rec.body.Bytes())
	}
	return nil
}

func (c *Context) idempotencyKey() string {
	if v := c.R.Header.Get("Idempotency-Key"); v != "" {
		return v
	}
	var body struct {
		Key string `json:"idempotency_key"`
	}
	if len(c.Body) > 0 && json.Unmarshal(c.Body, &body) == nil {
		return body.Key
	}
	return ""
}

type storedResponse struct {
	payload string
	status  int
	body    []byte
}

func (rt *Router) claim(ctx context.Context, orgID, principal, key, digest string) (bool, storedResponse, error) {
	var stored storedResponse
	tx, e := rt.opts.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return false, stored, Internal(e)
	}
	defer tx.Rollback(ctx)
	tag, e := tx.Exec(ctx, `INSERT INTO gfm.idempotency(org_id,principal_id,key,payload_sha256)
 VALUES($1::uuid,$2,$3,$4) ON CONFLICT DO NOTHING`, orgID, principal, key, digest)
	if e != nil {
		return false, stored, Internal(e)
	}
	if tag.RowsAffected() == 1 {
		if e = tx.Commit(ctx); e != nil {
			return false, stored, Internal(e)
		}
		return true, stored, nil
	}
	e = tx.QueryRow(ctx, `SELECT payload_sha256,status,body FROM gfm.idempotency
 WHERE org_id=$1::uuid AND principal_id=$2 AND key=$3`, orgID, principal, key).
		Scan(&stored.payload, &stored.status, &stored.body)
	if errors.Is(e, pgx.ErrNoRows) {
		// The other request released the key between the insert and the read.
		return false, storedResponse{payload: digest}, Conflict("idempotency_in_progress",
			"A request with this idempotency key is still running.")
	}
	if e != nil {
		return false, stored, Internal(e)
	}
	return false, stored, nil
}

func (rt *Router) store(ctx context.Context, orgID, principal, key string, status int, body []byte) {
	tx, e := rt.opts.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `UPDATE gfm.idempotency SET status=$4,body=$5
 WHERE org_id=$1::uuid AND principal_id=$2 AND key=$3`, orgID, principal, key, status, body); e == nil {
		_ = tx.Commit(ctx)
	}
}

func (rt *Router) release(ctx context.Context, orgID, principal, key string) {
	tx, e := rt.opts.Pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadWrite})
	if e != nil {
		return
	}
	defer tx.Rollback(ctx)
	if _, e = tx.Exec(ctx, `DELETE FROM gfm.idempotency
 WHERE org_id=$1::uuid AND principal_id=$2 AND key=$3 AND status=0`, orgID, principal, key); e == nil {
		_ = tx.Commit(ctx)
	}
}
