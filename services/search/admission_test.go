package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type countedBody struct {
	io.Reader
	reads int
}

func (b *countedBody) Read(p []byte) (int, error) { b.reads++; return b.Reader.Read(p) }
func (b *countedBody) Close() error               { return nil }

func admissionApp(t *testing.T) *App {
	t.Helper()
	v, err := newValidator("../../tools/serve_spike/contracts/harness-service-v1.1.schema.json")
	if err != nil {
		t.Fatal(err)
	}
	return &App{Validator: v, Store: &Store{LexicalEngine: "router"}, Token: "test-token", Slots: make(chan struct{}, 1), EventSlots: make(chan struct{}, 1)}
}
func admissionRequest(a *App, path string, body io.Reader) *http.Request {
	r := httptest.NewRequest("POST", path, body)
	r.Header.Set("Authorization", "Bearer "+a.Token)
	return r
}
func TestOverloadRejectsBeforeReadingBody(t *testing.T) {
	for _, x := range []struct{ path, body, code string }{
		{"/v1/search", `{"query":"retry"}`, "overloaded"},
		{"/v1/use", `{"skill_id":"u","revision":"r"}`, "overloaded"},
		{"/v1/events:batch", `{"events":[]}`, "telemetry_overloaded"},
	} {
		t.Run(x.path, func(t *testing.T) {
			a := admissionApp(t)
			a.Slots <- struct{}{}
			a.EventSlots <- struct{}{}
			body := &countedBody{Reader: strings.NewReader(x.body)}
			r := admissionRequest(a, x.path, body)
			r.Body = body
			w := httptest.NewRecorder()
			a.ServeHTTP(w, r)
			if w.Code != 429 || body.reads != 0 {
				t.Fatalf("status=%d body_reads=%d", w.Code, body.reads)
			}
			if w.Header().Get("Retry-After") != "1" || !strings.Contains(w.Body.String(), x.code) {
				t.Fatal(w.Header(), w.Body.String())
			}
			if len(a.Slots) != 1 || len(a.EventSlots) != 1 {
				t.Fatal("changed occupied slots")
			}
		})
	}
}

type heldBody struct{ started, release chan struct{} }

func (b *heldBody) Read(p []byte) (int, error) {
	close(b.started)
	<-b.release
	return 0, io.ErrUnexpectedEOF
}
func (b *heldBody) Close() error { return nil }
func TestBodyReadOccupiesAndReleasesSlot(t *testing.T) {
	for _, path := range []string{"/v1/search", "/v1/events:batch"} {
		t.Run(path, func(t *testing.T) {
			a := admissionApp(t)
			body := &heldBody{started: make(chan struct{}), release: make(chan struct{})}
			r := admissionRequest(a, path, nil)
			r.Body = body
			w := httptest.NewRecorder()
			done := make(chan struct{})
			go func() { defer close(done); a.ServeHTTP(w, r) }()
			defer func() {
				close(body.release)
				<-done
				if w.Code != 400 || len(a.Slots) != 0 || len(a.EventSlots) != 0 {
					t.Errorf("cancelled read: status=%d slots=%d/%d", w.Code, len(a.Slots), len(a.EventSlots))
				}
			}()
			select {
			case <-body.started:
			case <-time.After(time.Second):
				t.Fatal("body read did not begin")
			}
			slots := a.Slots
			other := a.EventSlots
			if path == "/v1/events:batch" {
				slots, other = other, slots
			}
			if len(slots) != 1 || len(other) != 0 {
				t.Errorf("read not counted in endpoint admission")
			}
		})
	}
}
func TestAdmissionErrorPathsDoNotLeakSlots(t *testing.T) {
	a := admissionApp(t)
	for _, x := range []struct {
		path, body string
		status     int
	}{
		{"/v1/search", "{", 400},
		{"/v1/search", `{"query":""}`, 400},
		{"/v1/search", strings.Repeat("x", 16385), 413},
		{"/v1/events:batch", "{", 400},
		{"/v1/events:batch", `{}`, 400},
		{"/v1/events:batch", strings.Repeat("x", 2*1024*1024+1), 413},
	} {
		w := httptest.NewRecorder()
		a.ServeHTTP(w, admissionRequest(a, x.path, strings.NewReader(x.body)))
		if w.Code != x.status || len(a.Slots) != 0 || len(a.EventSlots) != 0 {
			t.Fatalf("%s: status=%d slots=%d/%d", x.path, w.Code, len(a.Slots), len(a.EventSlots))
		}
	}
}
func TestAdmissionPoolsAndAuthenticationAreIndependent(t *testing.T) {
	a := admissionApp(t)
	a.Slots <- struct{}{}
	w := httptest.NewRecorder()
	a.ServeHTTP(w, admissionRequest(a, "/v1/events:batch", strings.NewReader("{")))
	if w.Code != 400 {
		t.Fatal("search exhaustion blocked telemetry", w.Code)
	}
	<-a.Slots
	a.EventSlots <- struct{}{}
	w = httptest.NewRecorder()
	a.ServeHTTP(w, admissionRequest(a, "/v1/search", strings.NewReader("{")))
	if w.Code != 400 {
		t.Fatal("telemetry exhaustion blocked search", w.Code)
	}
	a.Slots <- struct{}{}
	body := &countedBody{Reader: strings.NewReader("{")}
	r := admissionRequest(a, "/v1/search", body)
	r.Body = body
	r.Header.Set("Authorization", "invalid")
	w = httptest.NewRecorder()
	a.ServeHTTP(w, r)
	if w.Code != 401 || body.reads != 0 {
		t.Fatal("unauthenticated request used resources")
	}
}
