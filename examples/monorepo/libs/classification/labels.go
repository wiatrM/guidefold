// Package classification defines the data-classification labels used across Meridian and the
// propagation rule for derived data. A Label describes the handling level of a dataset or record;
// it is not an access-control decision (that is the auth-sdk policy check).
package classification

import (
	"errors"
	"fmt"
)

// Label is the closed set of classification levels, ordered from least to most restrictive.
type Label int

const (
	UNCLASSIFIED Label = iota
	OFFICIAL
	RESTRICTED
	CONFIDENTIAL
)

var names = [...]string{"UNCLASSIFIED", "OFFICIAL", "RESTRICTED", "CONFIDENTIAL"}

// ErrUnlabelled is returned when data carries no label; callers must never default to UNCLASSIFIED.
var ErrUnlabelled = errors.New("classification: data carries no label")

func (l Label) String() string {
	if l < UNCLASSIFIED || l > CONFIDENTIAL {
		return fmt.Sprintf("Label(%d)", int(l))
	}
	return names[l]
}

// Parse converts the canonical upper-case name into a Label.
func Parse(s string) (Label, error) {
	for i, n := range names {
		if n == s {
			return Label(i), nil
		}
	}
	return 0, fmt.Errorf("classification: unknown label %q", s)
}

// AtMost reports whether l is no more restrictive than other.
func (l Label) AtMost(other Label) bool { return l <= other }

// Dominates reports whether l is at least as restrictive as other.
func (l Label) Dominates(other Label) bool { return l >= other }

// Propagate returns the label of data derived from the given inputs: the highest input label.
// It errors on an empty input set so that unlabelled derivations are impossible.
func Propagate(inputs ...Label) (Label, error) {
	if len(inputs) == 0 {
		return 0, ErrUnlabelled
	}
	out := inputs[0]
	for _, in := range inputs[1:] {
		if in.Dominates(out) {
			out = in
		}
	}
	return out, nil
}
