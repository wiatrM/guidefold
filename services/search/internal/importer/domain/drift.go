package domain

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
)

// Owner-queue reasons this module raises (API-CONTRACT §5.5).
const (
	ReasonSourceChanged = "source_changed"
	ReasonSourceRemoved = "source_removed"
)

// Publication statuses a skill can hold (API-CONTRACT §5.3, §6).
const (
	StatusDraft       = "draft"
	StatusPublished   = "published"
	StatusNeedsReview = "needs_review"
	StatusArchived    = "archived"
)

// RevisionID is the immutable identifier of one skill revision: the digest of
// the skill's identity and its exact bytes. Deriving it rather than minting a
// random id is what makes a restarted parse job write the same row again
// instead of a second one (U1.5).
func RevisionID(skillID, contentSHA256 string) string {
	sum := sha256.Sum256([]byte(skillID + "@" + contentSHA256))
	return hex.EncodeToString(sum[:])
}

// SkillState is what the catalog already holds about one skill of a repository.
type SkillState struct {
	SkillID           string
	Path              string
	ContentSHA256     string
	PublicationStatus string
	SourceStatus      string
	CurrentRevisionID string
}

// ParsedSkill is one skill this import carried.
type ParsedSkill struct {
	SkillID       string
	Path          string
	ContentSHA256 string
	RevisionID    string
}

// DriftAction is one consequence of comparing an import against the catalog.
// It never deletes: a removed source archives its skill and keeps every
// revision, because the decision belongs to the owner (U9).
type DriftAction struct {
	SkillID string
	Reason  string
	// RevisionID identifies the revision the queue item is about: the new one
	// for a changed source, the last known one for a removed source.
	RevisionID string
	// PublicationStatus is the status to write, or "" to leave it alone.
	PublicationStatus string
	// SourceStatus is "removed" when the file is gone, "" otherwise.
	SourceStatus string
	Evidence     map[string]any
}

// Drift compares the catalog with one parsed import.
//
//   - an unchanged hash means nothing happened;
//   - a changed hash under a *published* skill needs a human look, so the skill
//     becomes needs_review and the owner gets one queue item;
//   - a file missing from a *complete* manifest archives its skill;
//   - a partial scan never removes anything, because absence from a partial
//     scan is not evidence of deletion (U1.5, U9).
//
// Re-running the same manifest produces no actions at all: every hash matches
// and nothing is missing.
func Drift(existing []SkillState, parsed []ParsedSkill, complete bool, importID string) []DriftAction {
	seen := make(map[string]ParsedSkill, len(parsed))
	for _, p := range parsed {
		seen[p.SkillID] = p
	}
	actions := []DriftAction{}
	for _, was := range existing {
		now, present := seen[was.SkillID]
		switch {
		case present && now.ContentSHA256 == was.ContentSHA256:
			// Unchanged source: no observation to report.
		case present:
			if was.PublicationStatus != StatusPublished {
				continue
			}
			actions = append(actions, DriftAction{
				SkillID: was.SkillID, Reason: ReasonSourceChanged,
				RevisionID: now.RevisionID, PublicationStatus: StatusNeedsReview,
				Evidence: map[string]any{"import_id": importID, "path": now.Path,
					"previous_content_sha256": was.ContentSHA256,
					"content_sha256":          now.ContentSHA256},
			})
		case !complete:
			// A partial scan cannot infer a deletion.
		case was.PublicationStatus == StatusArchived:
			// Already archived by an earlier complete import.
		default:
			actions = append(actions, DriftAction{
				SkillID: was.SkillID, Reason: ReasonSourceRemoved,
				RevisionID: was.CurrentRevisionID, PublicationStatus: StatusArchived,
				SourceStatus: "removed",
				Evidence: map[string]any{"import_id": importID, "path": was.Path,
					"content_sha256": was.ContentSHA256},
			})
		}
	}
	sort.Slice(actions, func(i, j int) bool {
		if actions[i].SkillID != actions[j].SkillID {
			return actions[i].SkillID < actions[j].SkillID
		}
		return actions[i].Reason < actions[j].Reason
	})
	return actions
}
