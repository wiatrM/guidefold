// Package mgmt is the HTTP layer of the management API: one router mounted on
// /api/, the JSON error envelope, request identifiers, the CSRF double submit,
// the idempotency replay and organisation authorization.
//
// It knows the gfm tables for orgs, memberships, audit and idempotency, and
// nothing else about the product. Feature packages register their routes with
// Handle and read the resolved principal and organisation from the Context, so
// no feature package has to repeat the authorization rules.
package mgmt

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// DefaultBodyLimit bounds a management request body. Blob uploads get their own,
// larger limit on their own route.
const DefaultBodyLimit = 1 << 20

// Handler serves one route. Returning an error renders the envelope.
type Handler func(c *Context) error

// Resolver turns a request into a principal. It returns (nil, nil) when the
// request carries no credentials at all.
type Resolver func(ctx context.Context, r *http.Request) (*Principal, error)

// Options configures the router.
type Options struct {
	Pool      *pgxpool.Pool
	Resolve   Resolver
	BodyLimit int64
	OpenAPI   []byte // served at GET /api/v1/openapi.yaml when present
	Logger    *slog.Logger
	Now       func() time.Time
}

type route struct {
	handler Handler
	flags   routeFlags
}

type routeFlags struct {
	public     bool
	noCSRF     bool
	idempotent bool
	live       bool
	stream     bool
	bodyLimit  int64
}

// RouteOption adjusts one route's middleware.
type RouteOption func(*routeFlags)

// Public allows unauthenticated requests (login, callback, device start).
func Public() RouteOption { return func(f *routeFlags) { f.public = true } }

// NoCSRF skips the double-submit check. Only for routes that establish a
// session rather than act with one.
func NoCSRF() RouteOption { return func(f *routeFlags) { f.noCSRF = true } }

// Idempotent requires an Idempotency-Key (header or body field) and replays the
// stored response for a repeat of the same key and payload.
func Idempotent() RouteOption { return func(f *routeFlags) { f.idempotent = true } }

// IdempotentLive requires and claims an Idempotency-Key exactly like
// Idempotent, so a duplicate that arrives while the first is still running is
// told so rather than doing the work twice — but it re-runs the handler on a
// repeat instead of replaying the stored body.
//
// It exists for mutations whose response is a *live view* of server state. The
// import creation answers with the blobs it is still missing; replaying the
// first answer would tell a resumed sync to upload files the server already
// holds, which is precisely the case the key was supposed to make safe. The
// no-duplicate-work guarantee for those routes comes from the resource itself
// (one import per manifest digest), not from a remembered response.
func IdempotentLive() RouteOption {
	return func(f *routeFlags) { f.idempotent = true; f.live = true }
}

// Stream leaves the request body unread and raises its ceiling for one route.
// The handler reads Context.R.Body itself, so a blob upload is hashed as it
// arrives instead of being buffered twice. Context.Body stays empty, which is
// why a streaming route can never be Idempotent: the replay key is a digest of
// the body the router did not read.
func Stream(limit int64) RouteOption {
	return func(f *routeFlags) { f.stream = true; f.bodyLimit = limit }
}

// Router is an http.Handler for everything under /api/.
type Router struct {
	mux    *http.ServeMux
	opts   Options
	limit  int64
	log    *slog.Logger
	now    func() time.Time
	routes map[string]bool
}

// New builds a router. It always answers under /api/, including for unknown
// paths, so a client never sees a bare Go 404 page.
func New(o Options) *Router {
	limit := o.BodyLimit
	if limit <= 0 {
		limit = DefaultBodyLimit
	}
	log := o.Logger
	if log == nil {
		log = slog.Default()
	}
	now := o.Now
	if now == nil {
		now = time.Now
	}
	rt := &Router{mux: http.NewServeMux(), opts: o, limit: limit, log: log, now: now,
		routes: map[string]bool{}}
	rt.mux.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) {
		c := rt.newContext(w, r)
		rt.render(c, NotFound("not_found", "No such endpoint."))
	})
	if len(o.OpenAPI) > 0 {
		rt.Handle(http.MethodGet, "/api/v1/openapi.yaml", func(c *Context) error {
			c.W.Header().Set("Content-Type", "application/yaml")
			c.W.WriteHeader(http.StatusOK)
			_, _ = c.W.Write(o.OpenAPI)
			return nil
		}, Public())
	}
	return rt
}

// Handle registers a route. Patterns use Go's ServeMux wildcards, so
// "/api/v1/orgs/{org}/members/{user_id}" exposes Param("org") and
// Param("user_id").
func (rt *Router) Handle(method, pattern string, h Handler, opts ...RouteOption) {
	flags := routeFlags{}
	for _, o := range opts {
		o(&flags)
	}
	if flags.stream && flags.idempotent {
		panic("mgmt: a streaming route cannot be idempotent (" + method + " " + pattern + ")")
	}
	r := route{handler: h, flags: flags}
	key := method + " " + pattern
	if rt.routes[key] {
		panic("mgmt: duplicate route " + key)
	}
	rt.routes[key] = true
	rt.mux.HandleFunc(key, func(w http.ResponseWriter, req *http.Request) {
		rt.serve(w, req, r)
	})
}

// Pool exposes the database to feature packages that register routes.
func (rt *Router) Pool() *pgxpool.Pool { return rt.opts.Pool }

// Now is the router's clock; tests can move it.
func (rt *Router) Now() time.Time { return rt.now() }

func (rt *Router) ServeHTTP(w http.ResponseWriter, r *http.Request) { rt.mux.ServeHTTP(w, r) }

func (rt *Router) newContext(w http.ResponseWriter, r *http.Request) *Context {
	id := requestID(r.Header.Get("X-Request-Id"))
	w.Header().Set("X-Request-Id", id)
	w.Header().Set("Cache-Control", "no-store")
	return &Context{W: w, R: r, RequestID: id, router: rt}
}

func (rt *Router) serve(w http.ResponseWriter, r *http.Request, ro route) {
	start := rt.now()
	c := rt.newContext(w, r)
	recorder := &recorder{ResponseWriter: w}
	c.W = recorder
	e := rt.dispatch(c, ro)
	if e != nil {
		rt.render(c, e)
	}
	// Allowlist logging: no bodies, no query strings, no cookies, no e-mails.
	rt.log.Info("management_request", "method", r.Method, "path", r.URL.Path,
		"status", recorder.status, "duration_ms", float64(rt.now().Sub(start).Microseconds())/1000,
		"request_id", c.RequestID, "source", source(c.Principal), "org_id", c.orgID)
}

func (rt *Router) dispatch(c *Context, ro route) error {
	if ro.flags.stream {
		limit := ro.flags.bodyLimit
		if limit <= 0 {
			limit = rt.limit
		}
		c.Body = nil
		if c.R.Body != nil {
			c.R.Body = http.MaxBytesReader(nil, c.R.Body, limit)
		}
	} else if e := c.readBody(rt.limit); e != nil {
		return e
	}
	if rt.opts.Resolve != nil {
		p, e := rt.opts.Resolve(c.R.Context(), c.R)
		if e != nil {
			return e
		}
		c.Principal = p
	}
	if !ro.flags.public && c.Principal == nil {
		return Unauthenticated("Sign in to continue.")
	}
	if e := c.checkCSRF(ro.flags); e != nil {
		return e
	}
	if ro.flags.idempotent {
		return rt.replayable(c, ro.handler, ro.flags.live)
	}
	return ro.handler(c)
}

func (rt *Router) render(c *Context, e error) {
	api := asError(e)
	details := api.Details
	if api.Status >= 500 {
		if cause, ok := details["cause"]; ok {
			rt.log.Error("management_failure", "request_id", c.RequestID, "error", cause)
		}
		details = nil
	}
	body := map[string]any{"error": api.Code, "message": api.Message, "request_id": c.RequestID}
	if len(details) > 0 {
		body["details"] = details
	}
	encoded, err := json.Marshal(body)
	if err != nil {
		encoded = []byte(`{"error":"internal_error","message":"serialization failed"}`)
	}
	c.W.Header().Set("Content-Type", "application/json")
	c.W.WriteHeader(api.Status)
	_, _ = c.W.Write(encoded)
}

func source(p *Principal) string {
	if p == nil {
		return "anonymous"
	}
	return p.Source
}

// recorder captures status and body so the idempotency middleware can store a
// response and replay it later.
type recorder struct {
	http.ResponseWriter
	status  int
	body    bytes.Buffer
	capture bool
	wrote   bool
}

func (r *recorder) WriteHeader(status int) {
	if r.wrote {
		return
	}
	r.wrote = true
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}
func (r *recorder) Write(b []byte) (int, error) {
	if !r.wrote {
		r.WriteHeader(http.StatusOK)
	}
	if r.capture {
		r.body.Write(b)
	}
	return r.ResponseWriter.Write(b)
}

// NewID returns a random RFC 4122 version 4 identifier. Feature packages use it
// for the identifiers they mint inside a request — a judgment, an item — so
// there is one generator behind the management API rather than one per module.
func NewID() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	s := hex.EncodeToString(b[:])
	return s[:8] + "-" + s[8:12] + "-" + s[12:16] + "-" + s[16:20] + "-" + s[20:]
}

// requestID reuses a caller-supplied identifier when it is safe to echo, and
// otherwise mints one. Anything else would put attacker text in every log line.
func requestID(incoming string) string {
	if n := len(incoming); n >= 8 && n <= 64 {
		ok := true
		for i := 0; i < n; i++ {
			ch := incoming[i]
			if !(ch >= 'a' && ch <= 'z' || ch >= 'A' && ch <= 'Z' || ch >= '0' && ch <= '9' ||
				ch == '-' || ch == '_') {
				ok = false
				break
			}
		}
		if ok {
			return incoming
		}
	}
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b[:])
}

func (c *Context) checkCSRF(flags routeFlags) error {
	if flags.noCSRF || c.R.Method == http.MethodGet || c.R.Method == http.MethodHead {
		return nil
	}
	if c.Principal == nil || c.Principal.Source != SourceSession {
		return nil // bearer tokens are not sent automatically by a browser
	}
	sent := c.R.Header.Get("X-CSRF-Token")
	if sent == "" || subtle.ConstantTimeCompare([]byte(sent), []byte(c.Principal.CSRF)) != 1 {
		return Fail(http.StatusForbidden, "csrf_token_mismatch",
			"Send the csrf_token from /api/v1/me in the X-CSRF-Token header.")
	}
	return nil
}

func (c *Context) readBody(limit int64) error {
	if c.R.Body == nil {
		c.Body = []byte{}
		return nil
	}
	c.R.Body = http.MaxBytesReader(nil, c.R.Body, limit)
	body, e := io.ReadAll(c.R.Body)
	if e != nil {
		var over *http.MaxBytesError
		if ok := asMaxBytes(e, &over); ok {
			return Fail(http.StatusRequestEntityTooLarge, "body_too_large",
				"The request body exceeds the limit for this endpoint.")
		}
		return Invalid("invalid_body", "The request body could not be read.")
	}
	c.Body = body
	c.R.Body = io.NopCloser(bytes.NewReader(body))
	return nil
}

// TooLarge reports whether a read from Context.R.Body stopped at the ceiling a
// Stream route set. Handlers that read the body themselves need it to answer
// 413 rather than 500.
func TooLarge(e error) bool {
	var over *http.MaxBytesError
	return asMaxBytes(e, &over)
}

func asMaxBytes(e error, target **http.MaxBytesError) bool {
	for e != nil {
		if v, ok := e.(*http.MaxBytesError); ok {
			*target = v
			return true
		}
		u, ok := e.(interface{ Unwrap() error })
		if !ok {
			return false
		}
		e = u.Unwrap()
	}
	return false
}

// Relative reports whether a return_to value is a safe same-origin path.
func Relative(path string) bool {
	return strings.HasPrefix(path, "/") && !strings.HasPrefix(path, "//") &&
		!strings.Contains(path, "\\") && !strings.ContainsAny(path, "\r\n")
}

// Routes lists the registered routes as "METHOD /pattern", sorted. The OpenAPI
// test uses it to check that the document and the server describe the same
// surface.
func (rt *Router) Routes() []string {
	out := make([]string, 0, len(rt.routes))
	for key := range rt.routes {
		out = append(out, key)
	}
	sort.Strings(out)
	return out
}
