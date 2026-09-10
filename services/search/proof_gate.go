package main

import (
	"bytes"
	"context"
	"regexp"
	"sort"
	"strings"
)

// Proof-gated delivery is an opt-in safety boundary for USE 1.2. Retrieval
// remains free to suggest a card, but a card enters the harness only when the
// immutable snapshot can show where each mandatory claim came from. The gate
// deliberately consumes structured metadata; it never asks a model to decide
// whether a citation is real.

const sourceProofSchema = "source-proof-v1"

const (
	maxProofScopes    = 8
	maxProofClaims    = 64
	maxProofRefs      = 16
	maxProofChildRefs = 16
	maxProofPath      = 1024
)

var proofSHA256 = regexp.MustCompile(`^[0-9a-f]{64}$`)

// cardRevision is the immutable revision used by the delivery path. Source
// proof is deliberately excluded: proof.snapshot and proof.revision are
// publisher-bound fields, so including them would create a self-referential
// hash that no snapshot could ever satisfy.
func cardRevision(card M) string {
	identity := M{}
	for key, value := range card {
		if key != "proof" {
			identity[key] = value
		}
	}
	return hash(pythonJSON(identity, false))
}

// bindProofPlaceholders makes generated, review-ready proofs usable after the
// immutable snapshot is published. It only fills explicit placeholders; a
// non-empty value supplied by an importer or reviewer is left untouched and
// will be checked by proofGate. In particular, it never upgrades verified.
func bindProofPlaceholders(card M, snapshot string) {
	proof := obj(card["proof"])
	if proof == nil {
		return
	}
	if value := str(proof["snapshot"]); value == "" || value == "pending" {
		proof["snapshot"] = snapshot
	}
	if value := str(proof["revision"]); value == "" || value == "pending" {
		proof["revision"] = cardRevision(card)
	}
	if value := str(proof["body_sha256"]); value == "" || value == "pending" {
		proof["body_sha256"] = hash([]byte(str(card["_body"])))
	}
}

func bindAllProofPlaceholders(cards M, snapshot string) {
	for _, urn := range keys(cards) {
		bindProofPlaceholders(obj(cards[urn]), snapshot)
	}
}

func sortedProofStrings(values []string) []string {
	seen := map[string]bool{}
	for _, value := range values {
		if value != "" {
			seen[value] = true
		}
	}
	out := make([]string, 0, len(seen))
	for value := range seen {
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

func proofMissing(requirement, reason string) []M {
	return []M{{"requirement": requirement, "reason": reason}}
}

func proofString(m M, key string) (string, bool) {
	v, ok := m[key]
	if !ok {
		return "", false
	}
	s, ok := v.(string)
	return s, ok && strings.TrimSpace(s) != ""
}

func proofScopes(v any) ([]string, bool) {
	items, ok := v.([]any)
	if !ok {
		return nil, false
	}
	values := make([]string, 0, len(items))
	if len(items) == 0 || len(items) > maxProofScopes {
		return nil, false
	}
	for _, item := range items {
		s, ok := item.(string)
		if !ok || strings.TrimSpace(s) == "" || len(s) > 128 {
			return nil, false
		}
		values = append(values, s)
	}
	return sortedProofStrings(values), true
}

func proofScopeCovers(proofScopes, requested []string) bool {
	set := map[string]bool{}
	for _, scope := range proofScopes {
		set[scope] = true
	}
	if set["*"] {
		return true
	}
	for _, scope := range requested {
		if !set[scope] {
			return false
		}
	}
	return true
}

func proofInteger(v any) (int64, bool) {
	switch n := v.(type) {
	case int:
		return int64(n), true
	case int64:
		return n, true
	case jsonNumber:
		i, err := n.Int64()
		return i, err == nil
	}
	return 0, false
}

// jsonNumber is the small interface implemented by encoding/json.Number. It
// keeps this file independent from JSON decoding details while still rejecting
// floating point and boolean line addresses.
type jsonNumber interface {
	Int64() (int64, error)
}

func proofRef(ref M) (M, bool) {
	path, pathOK := proofString(ref, "path")
	sha, shaOK := proofString(ref, "sha256")
	from, fromOK := proofInteger(ref["line_from"])
	to, toOK := proofInteger(ref["line_to"])
	if !pathOK || !shaOK || !sha256Proof(sha) || !fromOK || !toOK || from < 1 || to < from || len(path) > maxProofPath {
		return nil, false
	}
	// A relative source path is part of the provenance contract. Do not let a
	// proof turn into a path traversal or an opaque absolute location.
	if strings.HasPrefix(path, "/") || strings.Contains(path, `\`) || strings.ContainsRune(path, 0) {
		return nil, false
	}
	for _, segment := range strings.Split(path, "/") {
		if segment == "" || segment == "." || segment == ".." {
			return nil, false
		}
	}
	return M{"path": path, "sha256": sha, "line_from": from, "line_to": to}, true
}

func sha256Proof(value string) bool { return proofSHA256.MatchString(value) }

// proofClaimRef is the wire-level pointer used by an abstract card to cite a
// claim in a lower card.  The pointer is deliberately content addressed: a
// model may suggest the child identity, but it cannot mint the child digest or
// commitment that the published snapshot will accept.
type proofClaimRef struct {
	skillID, revision, claimID, claimDigest, commitment string
}

func proofClaimRefFrom(raw M) (proofClaimRef, bool) {
	ref := proofClaimRef{
		skillID:     str(raw["skill_id"]),
		revision:    str(raw["revision"]),
		claimID:     str(raw["claim_id"]),
		claimDigest: str(raw["claim_digest"]),
		commitment:  str(raw["commitment"]),
	}
	if ref.skillID == "" || len(ref.skillID) > 512 || ref.revision == "" || len(ref.revision) > 512 ||
		ref.claimID == "" || len(ref.claimID) > 128 || !sha256Proof(ref.claimDigest) || !sha256Proof(ref.commitment) {
		return proofClaimRef{}, false
	}
	return ref, true
}

func proofClaimRefs(claim M) ([]proofClaimRef, bool) {
	raw, present := claim["claim_refs"]
	if !present {
		return nil, true
	}
	items, ok := raw.([]any)
	if !ok || len(items) > maxProofChildRefs {
		return nil, false
	}
	refs := make([]proofClaimRef, 0, len(items))
	for _, item := range items {
		ref, valid := proofClaimRefFrom(obj(item))
		if !valid {
			return nil, false
		}
		refs = append(refs, ref)
	}
	return refs, true
}

func proofClaimDigest(claim M) (string, bool) {
	id, idOK := proofString(claim, "id")
	status, statusOK := proofString(claim, "status")
	if !idOK || !statusOK || !proofClaimStatus(status) {
		return "", false
	}
	canonical := M{"id": id, "status": status, "source_refs": []M{}, "claim_refs": []M{}}
	if text, present := claim["text"]; present {
		if _, ok := text.(string); !ok {
			return "", false
		}
		canonical["text"] = text
	}
	if rawRefs, present := claim["source_refs"]; present {
		items, ok := rawRefs.([]any)
		if !ok || len(items) > maxProofRefs {
			return "", false
		}
		refs := []M{}
		for _, rawRef := range items {
			ref, valid := proofRef(obj(rawRef))
			if !valid {
				return "", false
			}
			refs = append(refs, ref)
		}
		canonical["source_refs"] = refs
	}
	childRefs, ok := proofClaimRefs(claim)
	if !ok {
		return "", false
	}
	refs := []M{}
	for _, ref := range childRefs {
		refs = append(refs, M{"skill_id": ref.skillID, "revision": ref.revision, "claim_id": ref.claimID,
			"claim_digest": ref.claimDigest, "commitment": ref.commitment})
	}
	canonical["claim_refs"] = refs
	return hash(pythonJSON(canonical, false)), true
}

func proofCommitment(proof M) (string, bool) {
	claims, ok := proof["claims"].([]any)
	if !ok || len(claims) == 0 || len(claims) > maxProofClaims {
		return "", false
	}
	rows := []M{}
	for _, raw := range claims {
		claim := obj(raw)
		digest, valid := proofClaimDigest(claim)
		if !valid {
			return "", false
		}
		id, _ := proofString(claim, "id")
		rows = append(rows, M{"id": id, "digest": digest})
	}
	sort.SliceStable(rows, func(i, j int) bool { return str(rows[i]["id"]) < str(rows[j]["id"]) })
	return hash(pythonJSON(rows, false)), true
}

func proofNodeDescendant(parent, child string) bool {
	if parent == "_root" {
		return child != "_root" && child != ""
	}
	return child != "" && child != parent && strings.HasPrefix(child, parent+".")
}

// proofProvenance returns a bounded, deterministic view of the card's proof.
// It intentionally does not echo source text or arbitrary metadata. Even an
// invalid proof can be shown to an owner as a useful diagnostic, while the
// gate itself only accepts the fully validated form.
func proofProvenance(c *Catalog, id, body string, scopes []string) M {
	result := M{
		"schema":      sourceProofSchema,
		"snapshot":    c.ID,
		"skill_id":    id,
		"revision":    c.Revisions[id],
		"body_sha256": hash([]byte(body)),
		"scopes":      sortedProofStrings(scopes),
		"claims":      []M{},
	}
	proof := obj(c.Cards[id]["proof"])
	if proof == nil {
		return result
	}
	claims, ok := proof["claims"].([]any)
	if !ok {
		return result
	}
	for claimIndex, raw := range claims {
		if claimIndex >= maxProofClaims {
			break
		}
		claim := obj(raw)
		if claim == nil {
			continue
		}
		claimID, idOK := proofString(claim, "id")
		status, statusOK := proofString(claim, "status")
		if !idOK || len(claimID) > 128 || !statusOK || !proofClaimStatus(status) {
			continue
		}
		refs := []M{}
		if rawRefs, refsOK := claim["source_refs"].([]any); refsOK {
			for refIndex, rawRef := range rawRefs {
				if refIndex >= maxProofRefs {
					break
				}
				if ref, valid := proofRef(obj(rawRef)); valid {
					refs = append(refs, ref)
				}
			}
		}
		childRefs, _ := proofClaimRefs(claim)
		childPointers := []M{}
		for _, ref := range childRefs {
			childPointers = append(childPointers, M{
				"skill_id": ref.skillID, "revision": ref.revision, "claim_id": ref.claimID,
				"claim_digest": ref.claimDigest, "commitment": ref.commitment,
			})
		}
		result["claims"] = append(result["claims"].([]M), M{
			"id":          claimID,
			"status":      status,
			"source_refs": refs,
			"claim_refs":  childPointers,
		})
	}
	claimsOut := result["claims"].([]M)
	sort.SliceStable(claimsOut, func(i, j int) bool { return str(claimsOut[i]["id"]) < str(claimsOut[j]["id"]) })
	result["claims"] = claimsOut
	return result
}

func proofClaimHasSupport(claim M) bool {
	if raw, present := claim["source_refs"]; present {
		refs, ok := raw.([]any)
		if !ok {
			return false
		}
		if len(refs) > 0 {
			return true
		}
	}
	if raw, present := claim["claim_refs"]; present {
		refs, ok := raw.([]any)
		if !ok {
			return false
		}
		if len(refs) > 0 {
			return true
		}
	}
	return false
}

// verifyProofHierarchy checks recursive proof edges before any source bytes
// are exposed.  It is intentionally independent of ranking and of model
// confidence: an abstract card can cite a lower card only when that card's
// proof, claim digest and commitment all belong to this immutable catalog.
// The recursive walk is bounded by the number of published cards and has a
// cycle guard, so malformed generated graphs fail closed instead of looping.
func verifyProofHierarchy(c *Catalog, id, body string) string {
	return verifyProofHierarchyWithLoader(c, id, body, nil)
}

// verifyProofHierarchyWithLoader is the production variant used by the HTTP
// delivery path.  Catalogs intentionally keep only card metadata in memory;
// when a recursive edge points at another card, the loader fetches that
// card's body by its immutable snapshot and revision before checking its
// proof hash.  Unit callers with in-memory cards continue to use the wrapper
// above and need no database.
func verifyProofHierarchyWithLoader(c *Catalog, id, body string, load func(skillID, revision string) (string, error)) string {
	stack := map[string]bool{}
	var walk func(parentID, parentNode string, ref proofClaimRef) string
	walk = func(parentID, parentNode string, ref proofClaimRef) string {
		key := parentID + "\x00" + ref.skillID + "\x00" + ref.claimID
		if stack[key] {
			return "proof_recursive_invalid"
		}
		stack[key] = true
		defer delete(stack, key)
		child, ok := c.Cards[ref.skillID]
		if !ok || str(child["status"]) != "active" {
			return "proof_recursive_invalid"
		}
		if c.Revisions[ref.skillID] != ref.revision {
			return "proof_recursive_invalid"
		}
		childNode := str(child["node"])
		// A repository may place abstract and leaf cards in the same scope. In
		// that case the published `refines` edge is the authority relation;
		// scoped descendants remain valid when no explicit edge is available.
		linked := c.RefinesParent[ref.skillID] == parentID
		if !linked && !proofNodeDescendant(parentNode, childNode) {
			return "proof_recursive_invalid"
		}
		childBody, bodyOK := child["_body"].(string)
		if !bodyOK && load != nil {
			var err error
			childBody, err = load(ref.skillID, ref.revision)
			bodyOK = err == nil
		}
		if !bodyOK {
			return "proof_recursive_invalid"
		}
		proof := obj(child["proof"])
		if proof == nil || proof["schema"] != sourceProofSchema || proof["verified"] != true ||
			str(proof["skill_id"]) != ref.skillID || str(proof["snapshot"]) != c.ID ||
			str(proof["revision"]) != ref.revision || str(proof["body_sha256"]) != hash([]byte(childBody)) {
			return "proof_recursive_invalid"
		}
		covered, coveredOK := proofScopes(proof["scopes"])
		if !coveredOK || !proofScopeCovers(covered, []string{childNode}) {
			return "proof_recursive_invalid"
		}
		commitment, commitmentOK := proofCommitment(proof)
		if !commitmentOK || commitment != ref.commitment {
			return "proof_recursive_invalid"
		}
		claims, claimsOK := proof["claims"].([]any)
		if !claimsOK {
			return "proof_recursive_invalid"
		}
		var selected M
		for _, raw := range claims {
			claim := obj(raw)
			if str(claim["id"]) == ref.claimID {
				selected = claim
				break
			}
		}
		if selected == nil || str(selected["status"]) != "supported" || !proofClaimHasSupport(selected) {
			return "proof_recursive_invalid"
		}
		digest, digestOK := proofClaimDigest(selected)
		if !digestOK || digest != ref.claimDigest {
			return "proof_recursive_invalid"
		}
		childRefs, refsOK := proofClaimRefs(selected)
		if !refsOK {
			return "proof_recursive_invalid"
		}
		for _, nested := range childRefs {
			if reason := walk(ref.skillID, childNode, nested); reason != "" {
				return reason
			}
		}
		return ""
	}
	card := c.Cards[id]
	if card == nil {
		return "proof_recursive_invalid"
	}
	proof := obj(card["proof"])
	if proof == nil {
		return "proof_recursive_invalid"
	}
	claims, ok := proof["claims"].([]any)
	if !ok {
		return "proof_recursive_invalid"
	}
	parentNode := str(card["node"])
	for _, raw := range claims {
		claim := obj(raw)
		refs, refsOK := proofClaimRefs(claim)
		if !refsOK {
			return "proof_recursive_invalid"
		}
		for _, ref := range refs {
			if reason := walk(id, parentNode, ref); reason != "" {
				return reason
			}
		}
	}
	return ""
}

func proofClaimStatus(status string) bool {
	switch status {
	case "supported", "partial", "uncertain", "unsupported":
		return true
	default:
		return false
	}
}

// proofSourceRef is the small, typed projection used by the byte-level
// verification pass. The wire proof remains an untyped metadata object so the
// publisher can preserve its forward-compatible shape; this pass runs only
// after proofGate has accepted the structural form.
type proofSourceRef struct {
	path             string
	sha              string
	lineFrom, lineTo int64
}

type proofSourceEntry struct {
	cardID string
	body   string
	ref    proofSourceRef
}

// proofSourceEntries expands direct and recursive claim references while
// retaining the card whose package manifest or SKILL.md must satisfy the
// pointer.  The proof hierarchy was already structurally checked; this walk
// only gathers the bounded byte checks and repeats the cycle guard defensively.
func proofSourceEntries(c *Catalog, id, body string) []proofSourceEntry {
	return proofSourceEntriesWithLoader(c, id, body, nil)
}

func proofSourceEntriesWithLoader(c *Catalog, id, body string, load func(skillID, revision string) (string, error)) []proofSourceEntry {
	entries := []proofSourceEntry{}
	seen := map[string]bool{}
	var walk func(cardID, cardBody string, claim M)
	walk = func(cardID, cardBody string, claim M) {
		key := cardID + "\x00" + str(claim["id"])
		if seen[key] {
			return
		}
		seen[key] = true
		if rawRefs, ok := claim["source_refs"].([]any); ok {
			for _, rawRef := range rawRefs {
				if ref, valid := proofRef(obj(rawRef)); valid {
					from, _ := proofInteger(ref["line_from"])
					to, _ := proofInteger(ref["line_to"])
					entries = append(entries, proofSourceEntry{cardID: cardID, body: cardBody, ref: proofSourceRef{
						path: str(ref["path"]), sha: str(ref["sha256"]), lineFrom: from, lineTo: to,
					}})
				}
			}
		}
		for _, childRef := range mustProofClaimRefs(claim) {
			child := c.Cards[childRef.skillID]
			if child == nil {
				continue
			}
			childProof := obj(child["proof"])
			childClaims := arr(childProof["claims"])
			for _, rawChild := range childClaims {
				childClaim := obj(rawChild)
				if str(childClaim["id"]) == childRef.claimID {
					childBody, bodyOK := child["_body"].(string)
					if !bodyOK && load != nil {
						var err error
						childBody, err = load(childRef.skillID, childRef.revision)
						bodyOK = err == nil
					}
					if bodyOK {
						walk(childRef.skillID, childBody, childClaim)
					}
					break
				}
			}
		}
	}
	card := c.Cards[id]
	if card == nil {
		return nil
	}
	for _, rawClaim := range arr(obj(card["proof"])["claims"]) {
		walk(id, body, obj(rawClaim))
	}
	return entries
}

func mustProofClaimRefs(claim M) []proofClaimRef {
	refs, ok := proofClaimRefs(claim)
	if !ok {
		return nil
	}
	return refs
}

func sourceLineCount(data []byte) int64 {
	// A trailing newline terminates the last line; retaining the conventional
	// `newline count + 1` form is intentionally permissive for files with an
	// empty final line and never permits line zero or a negative range.
	return int64(bytes.Count(data, []byte{'\n'}) + 1)
}

// repositorySourceBytes resolves a source reference that is outside the
// selected card's package. Abstract cards generated by `guidefold ascend` cite
// the child SKILL.md files that support a synthesized claim; those files are
// published as skills of the same immutable snapshot, rather than copied into
// the parent package. Ordinary repository documents use the same snapshot's
// import record. Both lookups are tenant- and repository-scoped and return the
// content-addressed blob only after the path has been bound to that snapshot.
// A path/hash mismatch is kept distinct from a missing blob so the caller can
// surface drift as a specific, fail-closed ASK reason.
func (s *Store) repositorySourceBytes(ctx context.Context, c *Catalog, ref proofSourceRef) ([]byte, string) {
	if !isUUID(c.Tenant) {
		return nil, "proof_source_unavailable"
	}
	var actualSHA, blobSHA string
	err := s.Pool.QueryRow(ctx, `SELECT r.content_sha256,r.blob_sha256
 FROM gfm.skills source
 JOIN gfm.skill_revisions r
   ON r.org_id=source.org_id AND r.skill_id=source.skill_id
  AND r.revision_id=source.published_revision_id
 WHERE source.org_id=$1::uuid AND source.repo_id=$2 AND source.path=$3
   AND source.published_snapshot_id=$4 AND source.source_status='active'
 LIMIT 1`, c.Tenant, c.Repo, ref.path, c.ID).Scan(&actualSHA, &blobSHA)
	if err == nil {
		if actualSHA != ref.sha {
			return nil, "proof_source_hash_mismatch"
		}
		data, e := s.blobBytes(ctx, c.Tenant, blobSHA)
		if e != nil {
			return nil, "proof_source_unavailable"
		}
		return data, ""
	}

	// Non-skill files are recorded as documents with the import that built the
	// serving snapshot. Joining that publication prevents a document from an
	// older import at the same path from satisfying a current proof.
	err = s.Pool.QueryRow(ctx, `SELECT d.sha256
 FROM gfm.documents d
 JOIN gfm.publications p
   ON p.org_id=d.org_id AND p.repo_id=d.repo_id AND p.import_id=d.import_id
 WHERE d.org_id=$1::uuid AND d.repo_id=$2 AND d.path=$3
   AND p.snapshot_id=$4
 ORDER BY d.created_at DESC
 LIMIT 1`, c.Tenant, c.Repo, ref.path, c.ID).Scan(&actualSHA)
	if err != nil {
		return nil, "proof_source_unavailable"
	}
	if actualSHA != ref.sha {
		return nil, "proof_source_hash_mismatch"
	}
	data, err := s.blobBytes(ctx, c.Tenant, ref.sha)
	if err != nil {
		return nil, "proof_source_unavailable"
	}
	return data, ""
}

// verifyProofSourceBytes checks the bytes named by every accepted source ref.
// The proof's SHA is a content address, so the source can be fetched without
// trusting a path supplied by a client. Legacy operator snapshots have no
// organisation blob store; their own SKILL.md body remains verifiable, while
// any external source ref safely abstains rather than pretending it was read.
func (s *Store) verifyProofSourceBytes(ctx context.Context, c *Catalog, id, body string) (int, string) {
	return s.verifyProofSourceBytesWithLoader(ctx, c, id, body, nil)
}

func (s *Store) verifyProofSourceBytesWithLoader(ctx context.Context, c *Catalog, id, body string, load func(skillID, revision string) (string, error)) (int, string) {
	entries := proofSourceEntriesWithLoader(c, id, body, load)
	if len(entries) == 0 {
		return 0, "proof_source_ref_invalid"
	}
	cache := map[string][]byte{}
	verified := 0
	manifests := map[string]map[string]string{}
	for _, entry := range entries {
		ref := entry.ref
		data, cached := cache[ref.sha]
		if !cached {
			if ref.path == "SKILL.md" {
				data = []byte(entry.body)
			} else {
				if !isUUID(c.Tenant) {
					return verified, "proof_source_unavailable"
				}
				resourceDigests, presentManifest := manifests[entry.cardID]
				if !presentManifest {
					rows, _, err := s.resourcesFor(ctx, c.Tenant, c.Repo, c.ID, entry.cardID)
					if err != nil {
						return verified, "proof_source_unavailable"
					}
					resourceDigests = map[string]string{}
					for _, row := range rows {
						resourceDigests[row.Path] = row.SHA256
					}
					manifests[entry.cardID] = resourceDigests
				}
				manifestSHA, present := resourceDigests[ref.path]
				if present {
					if manifestSHA != ref.sha {
						return verified, "proof_source_hash_mismatch"
					}
					var err error
					data, err = s.blobBytes(ctx, c.Tenant, ref.sha)
					if err != nil {
						return verified, "proof_source_unavailable"
					}
				} else {
					var sourceReason string
					data, sourceReason = s.repositorySourceBytes(ctx, c, ref)
					if sourceReason != "" {
						return verified, sourceReason
					}
				}
			}
			cache[ref.sha] = data
		}
		if hash(data) != ref.sha {
			return verified, "proof_source_hash_mismatch"
		}
		if ref.lineFrom < 1 || ref.lineTo < ref.lineFrom || ref.lineTo > sourceLineCount(data) {
			return verified, "proof_source_line_range"
		}
		verified++
	}
	return verified, ""
}

func proofGate(c *Catalog, id, body string, scopes []string, closureStatus string) M {
	return proofGateWithLoader(c, id, body, scopes, closureStatus, nil)
}

func proofGateWithLoader(c *Catalog, id, body string, scopes []string, closureStatus string, load func(skillID, revision string) (string, error)) M {
	provenance := proofProvenance(c, id, body, scopes)
	decision := func(action, reason string, missing []M) M {
		return M{"action": action, "reason": reason, "missing": missing, "provenance": provenance}
	}
	rawProof, present := c.Cards[id]["proof"]
	if !present || rawProof == nil {
		return decision("ASK", "proof_missing", proofMissing("source_proof", "the published card has no source-proof-v1 record"))
	}
	proof := obj(rawProof)
	if proof == nil {
		return decision("ASK", "proof_schema_invalid", proofMissing("source_proof", "proof must be a structured source-proof-v1 object"))
	}
	if str(proof["schema"]) != sourceProofSchema || proof["verified"] != true {
		return decision("ASK", "proof_schema_invalid", proofMissing("source_proof", "proof schema or importer verification flag is invalid"))
	}
	proofID, idOK := proofString(proof, "skill_id")
	proofRevision, revisionOK := proofString(proof, "revision")
	proofSnapshot, snapshotOK := proofString(proof, "snapshot")
	bodySHA, bodySHAOK := proofString(proof, "body_sha256")
	if !idOK || proofID != id {
		return decision("ASK", "proof_identity_mismatch", proofMissing("skill_identity", "proof skill_id does not match the requested card"))
	}
	if !snapshotOK || proofSnapshot != c.ID {
		return decision("ASK", "proof_snapshot_mismatch", proofMissing("snapshot", "proof was issued for another immutable snapshot"))
	}
	if !revisionOK || proofRevision != c.Revisions[id] {
		return decision("ASK", "proof_revision_mismatch", proofMissing("revision", "proof revision does not match the published card"))
	}
	if !bodySHAOK || !sha256Proof(bodySHA) || bodySHA != hash([]byte(body)) {
		return decision("ASK", "proof_body_hash_mismatch", proofMissing("body_integrity", "proof body_sha256 does not match the bytes being delivered"))
	}
	covered, coveredOK := proofScopes(proof["scopes"])
	if !coveredOK || !proofScopeCovers(covered, scopes) {
		return decision("ASK", "proof_scope_incomplete", proofMissing("scope", "proof does not cover every resolved workspace scope"))
	}
	if conflicts, present := proof["conflicts"]; present {
		list, ok := conflicts.([]any)
		if !ok {
			return decision("ASK", "proof_schema_invalid", proofMissing("conflicts", "proof conflicts must be an array"))
		}
		if len(list) > 32 {
			return decision("ASK", "proof_schema_invalid", proofMissing("conflicts", "proof contains too many conflict records"))
		}
		if len(list) > 0 {
			return decision("ASK", "proof_conflict", proofMissing("conflict_free", "the proof contains an unresolved conflict"))
		}
	}
	claims, claimsOK := proof["claims"].([]any)
	if !claimsOK || len(claims) == 0 {
		return decision("ASK", "proof_claim_incomplete", proofMissing("mandatory_claims", "proof has no mandatory supported claims"))
	}
	if len(claims) > maxProofClaims {
		return decision("ASK", "proof_schema_invalid", proofMissing("mandatory_claims", "proof contains too many claim records"))
	}
	for _, raw := range claims {
		claim := obj(raw)
		if claim == nil {
			return decision("ASK", "proof_claim_incomplete", proofMissing("mandatory_claims", "every claim must be supported"))
		}
		claimID := str(claim["id"])
		if len(claimID) == 0 || len(claimID) > 128 || str(claim["status"]) != "supported" {
			return decision("ASK", "proof_claim_incomplete", proofMissing("mandatory_claims", "every claim must be supported"))
		}
		rawRefs, refsOK := claim["source_refs"].([]any)
		if !refsOK && claim["source_refs"] != nil {
			return decision("ASK", "proof_source_ref_invalid", proofMissing("source_reference", "source_refs must be an array"))
		}
		if refsOK {
			if len(rawRefs) > maxProofRefs {
				return decision("ASK", "proof_schema_invalid", proofMissing("source_reference", "a claim contains too many source references"))
			}
			for _, rawRef := range rawRefs {
				if _, valid := proofRef(obj(rawRef)); !valid {
					return decision("ASK", "proof_source_ref_invalid", proofMissing("source_reference", "a claim contains an invalid path, digest or line range"))
				}
			}
		}
		childRefs, childRefsOK := proofClaimRefs(claim)
		if !childRefsOK {
			return decision("ASK", "proof_recursive_invalid", proofMissing("recursive_claims", "a claim contains an invalid child-card reference"))
		}
		if !proofClaimHasSupport(claim) {
			return decision("ASK", "proof_claim_incomplete", proofMissing("mandatory_claims", "every supported claim needs source lines or a recursive child claim"))
		}
		if len(childRefs) > maxProofChildRefs {
			return decision("ASK", "proof_schema_invalid", proofMissing("recursive_claims", "a claim contains too many child-card references"))
		}
	}
	if reason := verifyProofHierarchyWithLoader(c, id, body, load); reason != "" {
		return decision("ASK", reason, proofMissing("recursive_claims", "a child claim, commitment or proof path is not valid in this snapshot"))
	}
	if closureStatus != "complete" {
		return decision("ASK", "closure_incomplete", proofMissing("closure", "the current dependency closure is not complete"))
	}
	return decision("LOAD", "source_proof_complete", []M{})
}
