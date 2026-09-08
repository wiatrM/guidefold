package mgmt

import (
	"fmt"
	"net/http"
)

// SchemaVersion labels every management payload.
const SchemaVersion = "mgmt-1"

// Error is the only error shape the management API emits. It renders as
// {"error","message","request_id","details"}.
type Error struct {
	Status  int
	Code    string
	Message string
	Details map[string]any
}

func (e *Error) Error() string { return e.Code }

// Fail builds an Error.
func Fail(status int, code, message string) *Error {
	return &Error{Status: status, Code: code, Message: message}
}

// WithDetails attaches machine-readable context (a conflicting revision, the
// missing blobs). Never put secrets or e-mail addresses here.
func (e *Error) WithDetails(details map[string]any) *Error {
	e.Details = details
	return e
}

// Invalid is a 400.
func Invalid(code, message string) *Error { return Fail(http.StatusBadRequest, code, message) }

// Unauthenticated is a 401.
func Unauthenticated(message string) *Error {
	return Fail(http.StatusUnauthorized, "unauthenticated", message)
}

// Forbidden is the single 403 body used for a non-member and for an
// organisation that does not exist. The two must be indistinguishable.
func Forbidden() *Error {
	return Fail(http.StatusForbidden, "forbidden", "You do not have access to this organization.")
}

// NotFound is a 404 and is only ever used inside the caller's own organisation.
func NotFound(code, message string) *Error { return Fail(http.StatusNotFound, code, message) }

// Conflict is a 409.
func Conflict(code, message string) *Error { return Fail(http.StatusConflict, code, message) }

// Unprocessable is a 422, used for graph and validation errors.
func Unprocessable(code, message string) *Error {
	return Fail(http.StatusUnprocessableEntity, code, message)
}

// Internal wraps an unexpected failure. The cause is logged, not returned.
func Internal(cause error) *Error {
	return &Error{Status: http.StatusInternalServerError, Code: "internal_error",
		Message: "The request could not be completed.", Details: map[string]any{"cause": cause.Error()}}
}

func asError(e error) *Error {
	if e == nil {
		return nil
	}
	if api, ok := e.(*Error); ok {
		return api
	}
	return Internal(fmt.Errorf("%w", e))
}
