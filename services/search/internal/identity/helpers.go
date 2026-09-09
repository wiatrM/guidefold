package identity

import "github.com/jackc/pgx/v5/pgconn"

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func isUniqueViolation(err error) bool {
	pgErr, ok := err.(*pgconn.PgError)
	return ok && pgErr.Code == "23505"
}
