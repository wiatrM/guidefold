package review

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"github.com/wiatrM/guidefold/services/search/internal/mgmt"
)

// Export is where the product stops and git starts.
//
// An export is a patch and a set of files, nothing else. It does not commit,
// open a pull request or touch a repository, and it never marks anything
// published: the proposal moves to `awaiting_git`, and it is a *later import*
// carrying the same bytes that makes it `published`. Anything else would let
// the UI claim a change is live while the repository still disagrees
// (error-handling-and-states, "Eksport nie jest publikacją").

// exportRequest is the body of POST …/proposals/{id}/export.
type exportRequest struct {
	IdempotencyKey string `json:"idempotency_key"`
}

// handleExport turns an approved candidate into a patch against the revision it
// was approved from.
func (s *Service) handleExport(c *mgmt.Context) error {
	rc, e := s.authorizeReviewer(c)
	if e != nil {
		return e
	}
	id := c.Param("proposal_id")
	if !parseUUID(id) {
		return notFound("proposal_not_found", "No such proposal in this repository.")
	}
	var req exportRequest
	if len(c.Body) > 0 {
		if e := c.Decode(&req); e != nil {
			return e
		}
	}
	tx, txErr := s.tx(c.Ctx())
	if txErr != nil {
		return mgmt.Internal(txErr)
	}
	defer tx.Rollback(c.Ctx())
	p, err := lockProposal(c.Ctx(), tx, rc.Org.ID, rc.RepoID, id)
	if isNoRows(err) {
		return notFound("proposal_not_found", "No such proposal in this repository.")
	}
	if err != nil {
		return mgmt.Internal(err)
	}
	if p.State != StateApprovedForExport && p.State != StateAwaitingGit {
		return mgmt.Conflict("proposal_state_invalid",
			"Only an approved proposal can be exported; this one is "+p.State+".")
	}
	body, blobErr := s.blobs.Get(c.Ctx(), rc.Org.ID, p.CandidateBlobSHA256)
	if blobErr != nil {
		return mgmt.Conflict("proposal_state_invalid",
			"The approved candidate's bytes are no longer stored.")
	}
	before := ""
	if p.TargetSkillID != "" {
		var blobSHA string
		e := tx.QueryRow(c.Ctx(), `SELECT COALESCE(r.blob_sha256,'') FROM gfm.skill_revisions r
 WHERE r.org_id=$1::uuid AND r.revision_id=$2`, rc.Org.ID, p.ExpectedRevision).Scan(&blobSHA)
		if e == nil && blobSHA != "" {
			if raw, e := s.blobs.Get(c.Ctx(), rc.Org.ID, blobSHA); e == nil {
				before = string(raw)
			}
		} else if e != nil && !isNoRows(e) {
			return mgmt.Internal(e)
		}
	}
	commit, e2 := s.loadImportCommit(c.Ctx(), rc.Org.ID, p.ImportID)
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	patch := UnifiedPatch(p.CandidatePath, before, string(body))
	files := []map[string]any{{"path": p.CandidatePath, "sha256": digest(string(body)),
		"content": string(body)}}
	filesDigest := digest(p.CandidatePath + "\x00" + digest(string(body)))

	exportID := newID()
	var stored string
	insertErr := tx.QueryRow(c.Ctx(), `INSERT INTO gfm.exports
 (org_id,export_id,proposal_id,base_commit,files,patch,files_digest,created_by)
 VALUES($1::uuid,$2::uuid,$3::uuid,$4,$5::jsonb,$6,$7,$8::uuid)
 ON CONFLICT (org_id,proposal_id,files_digest) DO NOTHING
 RETURNING export_id::text`,
		rc.Org.ID, exportID, id, nullable(commit), string(mustJSON(files)), patch, filesDigest,
		nullable(c.Principal.UserID)).Scan(&stored)
	if isNoRows(insertErr) {
		// The same approved bytes were already exported. The patch is a function
		// of the files, so the existing export is the answer.
		if e := tx.QueryRow(c.Ctx(), `SELECT export_id::text FROM gfm.exports
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid AND files_digest=$3`,
			rc.Org.ID, id, filesDigest).Scan(&stored); e != nil {
			return mgmt.Internal(e)
		}
	} else if insertErr != nil {
		return mgmt.Internal(insertErr)
	}
	if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.proposals SET state='awaiting_git',updated_at=now()
 WHERE org_id=$1::uuid AND proposal_id=$2::uuid AND state='approved_for_export'`,
		rc.Org.ID, id); e != nil {
		return mgmt.Internal(e)
	}
	if p.TargetSkillID != "" {
		if _, e := tx.Exec(c.Ctx(), `UPDATE gfm.skills SET publication_status='awaiting_git',
 updated_at=now() WHERE org_id=$1::uuid AND skill_id=$2 AND publication_status IN ('draft','approved_for_export')`,
			rc.Org.ID, p.TargetSkillID); e != nil {
			return mgmt.Internal(e)
		}
	}
	if e := c.Audit(c.Ctx(), tx, rc.Org.ID, "proposal.export", "proposal:"+id, filesDigest); e != nil {
		return mgmt.Internal(e)
	}
	if e := tx.Commit(c.Ctx()); e != nil {
		return mgmt.Internal(e)
	}
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"export_id": stored, "proposal_id": id, "state": StateAwaitingGit,
		"base_commit": nullable(commit), "files": files, "patch": patch})
}

func (s *Service) handleGetExport(c *mgmt.Context) error {
	rc, e := s.authorize(c, mgmt.RoleAny)
	if e != nil {
		return e
	}
	id := c.Param("export_id")
	if !parseUUID(id) {
		return notFound("export_not_found", "No such export in this repository.")
	}
	var proposalID, patch, filesRaw, state string
	var commit *string
	e2 := s.pool.QueryRow(c.Ctx(), `SELECT e.proposal_id::text,e.base_commit,e.files::text,e.patch,
 p.state FROM gfm.exports e JOIN gfm.proposals p
   ON p.org_id=e.org_id AND p.proposal_id=e.proposal_id
 WHERE e.org_id=$1::uuid AND p.repo_id=$2 AND e.export_id=$3::uuid`,
		rc.Org.ID, rc.RepoID, id).Scan(&proposalID, &commit, &filesRaw, &patch, &state)
	if isNoRows(e2) {
		return notFound("export_not_found", "No such export in this repository.")
	}
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	var files any
	_ = json.Unmarshal([]byte(filesRaw), &files)
	return c.JSON(http.StatusOK, map[string]any{
		"schema_version": mgmt.SchemaVersion, "org_id": rc.Org.ID, "repo_id": rc.RepoID,
		"export_id": id, "proposal_id": proposalID, "state": state, "base_commit": commit,
		"files": files, "patch": patch})
}

// handleExportPatch answers the patch as a diff, so it can be piped straight
// into `git apply`.
func (s *Service) handleExportPatch(c *mgmt.Context) error {
	rc, e := s.authorize(c, mgmt.RoleAny)
	if e != nil {
		return e
	}
	id := c.Param("export_id")
	if !parseUUID(id) {
		return notFound("export_not_found", "No such export in this repository.")
	}
	var patch string
	e2 := s.pool.QueryRow(c.Ctx(), `SELECT e.patch FROM gfm.exports e JOIN gfm.proposals p
   ON p.org_id=e.org_id AND p.proposal_id=e.proposal_id
 WHERE e.org_id=$1::uuid AND p.repo_id=$2 AND e.export_id=$3::uuid`,
		rc.Org.ID, rc.RepoID, id).Scan(&patch)
	if isNoRows(e2) {
		return notFound("export_not_found", "No such export in this repository.")
	}
	if e2 != nil {
		return mgmt.Internal(e2)
	}
	c.W.Header().Set("Content-Type", "text/x-diff; charset=utf-8")
	c.W.Header().Set("X-Content-SHA256", digest(patch))
	c.W.WriteHeader(http.StatusOK)
	_, _ = c.W.Write([]byte(patch))
	return nil
}

// UnifiedPatch renders a git-applicable diff that replaces `before` with
// `after` at `path`.
//
// It is one whole-file hunk rather than a minimal diff on purpose. A minimal
// diff is nicer to read and *harder to trust*: it applies against neighbouring
// text it never checked. A whole-file hunk applies only when the working tree
// holds exactly the revision the proposal was approved against, which is the
// same guarantee `expected_revision` gives on the API side.
func UnifiedPatch(path, before, after string) string {
	var b strings.Builder
	b.WriteString("diff --git a/" + path + " b/" + path + "\n")
	oldLines, oldNewline := splitLines(before)
	newLines, newNewline := splitLines(after)
	switch {
	case before == "":
		b.WriteString("new file mode 100644\n--- /dev/null\n+++ b/" + path + "\n")
		fmt.Fprintf(&b, "@@ -0,0 +1,%d @@\n", len(newLines))
	case after == "":
		b.WriteString("deleted file mode 100644\n--- a/" + path + "\n+++ /dev/null\n")
		fmt.Fprintf(&b, "@@ -1,%d +0,0 @@\n", len(oldLines))
	default:
		b.WriteString("--- a/" + path + "\n+++ b/" + path + "\n")
		fmt.Fprintf(&b, "@@ -1,%d +1,%d @@\n", len(oldLines), len(newLines))
	}
	for i, l := range oldLines {
		b.WriteString("-" + l + "\n")
		if i == len(oldLines)-1 && !oldNewline {
			b.WriteString("\\ No newline at end of file\n")
		}
	}
	for i, l := range newLines {
		b.WriteString("+" + l + "\n")
		if i == len(newLines)-1 && !newNewline {
			b.WriteString("\\ No newline at end of file\n")
		}
	}
	return b.String()
}

// splitLines returns the file's lines and whether it ended with a newline. The
// distinction matters: a patch that silently adds a trailing newline does not
// apply to the file it claims to describe.
func splitLines(text string) ([]string, bool) {
	if text == "" {
		return nil, true
	}
	trailing := strings.HasSuffix(text, "\n")
	if trailing {
		text = text[:len(text)-1]
	}
	return strings.Split(text, "\n"), trailing
}
