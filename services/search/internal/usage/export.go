package usage

import (
	"encoding/csv"
	"net/http"
	"reflect"
	"strconv"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
	"github.com/wiatrM/guidefold/services/search/internal/usage/domain"
)

// exportRow is one line of the export.
//
// The field order is the contract (API-CONTRACT §5.5): the CSV header and the
// JSON keys are both generated from this struct by reflection, so the two can
// never drift apart and reordering a column here is visibly a breaking change
// rather than an accident.
//
// What is not here matters as much as what is: no prompt, no query, no file
// path, no skill body, no person. An export reproduces the counts, not the work
// (PRODUCT-PIVOT §9 AC4).
type exportRow struct {
	SkillID           string  `json:"skill_id"`
	Revision          *string `json:"revision"`
	Scope             *string `json:"scope"`
	Owner             *string `json:"owner"`
	Harness           *string `json:"harness"`
	WindowFrom        string  `json:"window_from"`
	WindowTo          string  `json:"window_to"`
	Exposures         int     `json:"exposures"`
	LoadsVerified     int     `json:"loads_verified"`
	ContextLoaded     int     `json:"context_loaded"`
	ContextUnknown    int     `json:"context_unknown"`
	UseReported       int     `json:"use_reported"`
	UseObserved       int     `json:"use_observed"`
	Helped            *int    `json:"helped"`
	Hindered          *int    `json:"hindered"`
	Mixed             *int    `json:"mixed"`
	NotApplicable     *int    `json:"not_applicable"`
	Unknown           *int    `json:"unknown"`
	FeedbackN         *int    `json:"feedback_n"`
	HelpedNumerator   *int    `json:"helped_numerator"`
	HelpedDenominator *int    `json:"helped_denominator"`
	SmallSample       *bool   `json:"small_sample"`
	ZeroLoads         bool    `json:"zero_loads"`
	// The two later names of the same revision, appended at the end because the
	// column order before them is pinned (API-CONTRACT §5.5).
	CardRevision  *string `json:"card_revision"`
	ContentSHA256 *string `json:"content_sha256"`
	// Contract 1.1.4, appended after the two above for the same reason.
	ExposuresExpanded int `json:"exposures_expanded"`
	LoadsUnlinked     int `json:"loads_unlinked"`
}

// exportHeader is the pinned column order, read once from the struct tags.
var exportHeader = func() []string {
	t := reflect.TypeOf(exportRow{})
	out := make([]string, 0, t.NumField())
	for i := 0; i < t.NumField(); i++ {
		out = append(out, strings.Split(t.Field(i).Tag.Get("json"), ",")[0])
	}
	return out
}()

// exportValues renders one row as CSV cells. A nil pointer becomes an empty
// cell, never a zero: "nobody judged this revision" and "everybody said it did
// not help" are different facts and must not print the same.
func exportValues(row exportRow) []string {
	v := reflect.ValueOf(row)
	out := make([]string, 0, v.NumField())
	for i := 0; i < v.NumField(); i++ {
		out = append(out, cell(v.Field(i)))
	}
	return out
}

func cell(v reflect.Value) string {
	if v.Kind() == reflect.Ptr {
		if v.IsNil() {
			return ""
		}
		v = v.Elem()
	}
	switch v.Kind() {
	case reflect.String:
		return v.String()
	case reflect.Int:
		return strconv.Itoa(int(v.Int()))
	case reflect.Bool:
		return strconv.FormatBool(v.Bool())
	}
	return ""
}

func exportRows(report domain.Report) []exportRow {
	window := windowOf(report.Window)
	rows := make([]exportRow, 0, len(report.Skills))
	for _, s := range report.Skills {
		row := exportRow{SkillID: s.SkillID, Revision: s.Revision,
			CardRevision: s.CardRevision, ContentSHA256: s.ContentSHA256,
			Scope: s.Scope, Owner: s.Owner, Harness: s.Harness,
			WindowFrom: window.From, WindowTo: window.To,
			Exposures: s.Exposures, LoadsVerified: s.LoadsVerified,
			ContextLoaded: s.ContextLoaded, ContextUnknown: s.ContextUnknown,
			UseReported: s.UseReported, UseObserved: s.UseObserved, ZeroLoads: s.ZeroLoads,
			ExposuresExpanded: s.ExposuresExpanded, LoadsUnlinked: s.LoadsUnlinked}
		if s.Feedback != nil {
			f := *s.Feedback
			row.Helped, row.Hindered, row.Mixed = &f.Helped, &f.Hindered, &f.Mixed
			row.NotApplicable, row.Unknown, row.FeedbackN = &f.NotApplicable, &f.Unknown, &f.N
		}
		if s.HelpedRatio != nil {
			r := *s.HelpedRatio
			row.HelpedNumerator, row.HelpedDenominator = &r.Numerator, &r.Denominator
			row.SmallSample = &r.SmallSample
		}
		rows = append(rows, row)
	}
	return rows
}

// exportDocument is the `format=json` shape pinned by the tech lead's decision
// 12: one object with the window and the coverage beside the rows, so a
// consumer cannot read the numbers without reading what they do not cover.
type exportDocument struct {
	SchemaVersion string           `json:"schema_version"`
	Window        windowDTO        `json:"window"`
	Coverage      *domain.Coverage `json:"coverage"`
	Rows          []exportRow      `json:"rows"`
}

// handleExport writes the same rows as CSV or JSON.
func (s *Service) handleExport(c *mgmt.Context) error {
	org, repo, e := c.AuthorizeRepo("org", "repo", mgmt.RoleAny)
	if e != nil {
		return e
	}
	format := c.Query("format")
	if format == "" {
		format = "csv"
	}
	if format != "csv" && format != "json" {
		return mgmt.Invalid("invalid_request", "format must be csv or json.")
	}
	v, e := s.build(c.Ctx(), c, org.ID, repo.ID)
	if e != nil {
		return e
	}
	rows := exportRows(v.report)
	if format == "json" {
		coverage := v.report.Coverage
		return c.JSON(http.StatusOK, exportDocument{SchemaVersion: mgmt.SchemaVersion,
			Window: windowOf(v.report.Window), Coverage: &coverage, Rows: rows})
	}
	c.W.Header().Set("Content-Type", "text/csv; charset=utf-8")
	c.W.Header().Set("Content-Disposition", `attachment; filename="usage.csv"`)
	c.W.WriteHeader(http.StatusOK)
	w := csv.NewWriter(c.W)
	if err := w.Write(exportHeader); err != nil {
		return nil
	}
	for _, row := range rows {
		if err := w.Write(exportValues(row)); err != nil {
			return nil
		}
	}
	w.Flush()
	return nil
}
