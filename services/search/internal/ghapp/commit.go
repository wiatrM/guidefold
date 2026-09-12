package ghapp

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strings"
)

// CreateBranchCommit builds one commit against Guidefold's own branch,
// entirely through the git data API: resolve baseRef to a commit, create a
// blob per file, create a tree with base_tree set to the base commit's own
// tree (so every file this call did not touch survives unchanged), create
// the commit, then create or fast-forward refs/heads/<newBranch>.
//
// This is deliberately not the clone-into-/work path ADR-0036 point 2
// describes for ascend.run: the git data API needs no git binary in the
// worker image and no working directory on disk, and because nothing from
// the customer's repository is ever materialized onto a filesystem here,
// there is no path by which building this commit could execute anything the
// repository contains.
//
// Every path in files must be AGENTS.md or sit under a directory named
// .agents/skills; this App proposes skill files and nothing else (ADR-0036
// point 1a). That is checked before any request leaves this package, so a
// caller's mistake never becomes a partially-built commit on GitHub.
func (c *Client) CreateBranchCommit(ctx context.Context, installationID int64, fullName, baseRef, newBranch, message string, files map[string][]byte) (string, error) {
	paths := make([]string, 0, len(files))
	for path := range files {
		if !writePathAllowed(path) {
			return "", fmt.Errorf("%w: %s", ErrPathNotAllowed, path)
		}
		paths = append(paths, path)
	}
	sort.Strings(paths) // deterministic tree entry order across runs

	token, err := c.installationToken(ctx, installationID)
	if err != nil {
		return "", err
	}
	baseCommitSHA, baseTreeSHA, err := c.resolveCommit(ctx, token, fullName, baseRef)
	if err != nil {
		return "", err
	}
	entries := make([]map[string]any, 0, len(paths))
	for _, path := range paths {
		blobSHA, err := c.createBlob(ctx, token, fullName, files[path])
		if err != nil {
			return "", err
		}
		entries = append(entries, map[string]any{
			"path": path, "mode": "100644", "type": "blob", "sha": blobSHA,
		})
	}
	newTreeSHA, err := c.createTree(ctx, token, fullName, baseTreeSHA, entries)
	if err != nil {
		return "", err
	}
	commitSHA, err := c.createCommit(ctx, token, fullName, message, newTreeSHA, []string{baseCommitSHA})
	if err != nil {
		return "", err
	}
	if err := c.createOrFastForwardRef(ctx, token, fullName, newBranch, commitSHA); err != nil {
		return "", err
	}
	return commitSHA, nil
}

// writePathAllowed is the enforcement point for "this App proposes skill
// files and nothing else": true for AGENTS.md at the root, or any path that
// sits inside a directory literally named .agents/skills, wherever in the
// repository that directory occurs.
func writePathAllowed(path string) bool {
	if path == "AGENTS.md" {
		return true
	}
	segments := strings.Split(path, "/")
	for i := 0; i+1 < len(segments); i++ {
		if segments[i] == ".agents" && segments[i+1] == "skills" && len(segments) > i+2 {
			return true
		}
	}
	return false
}

// resolveCommit turns baseRef (a branch name, tag or SHA) into the commit
// SHA and tree SHA the new tree is built on top of, through the ordinary
// commits API rather than the lower-level git refs+commits pair — it
// accepts any ref form in one call.
func (c *Client) resolveCommit(ctx context.Context, token, fullName, ref string) (commitSHA, treeSHA string, err error) {
	rawURL, err := c.apiURL("/repos/"+fullName+"/commits/"+ref, nil)
	if err != nil {
		return "", "", fmt.Errorf("ghapp: %w", err)
	}
	var body struct {
		SHA    string `json:"sha"`
		Commit struct {
			Tree struct {
				SHA string `json:"sha"`
			} `json:"tree"`
		} `json:"commit"`
	}
	if err := c.getJSON(ctx, token, rawURL, &body); err != nil {
		return "", "", err
	}
	if body.SHA == "" || body.Commit.Tree.SHA == "" {
		return "", "", fmt.Errorf("ghapp: %s did not resolve to a commit with a tree", ref)
	}
	return body.SHA, body.Commit.Tree.SHA, nil
}

func (c *Client) createBlob(ctx context.Context, token, fullName string, content []byte) (string, error) {
	rawURL, err := c.apiURL("/repos/"+fullName+"/git/blobs", nil)
	if err != nil {
		return "", fmt.Errorf("ghapp: %w", err)
	}
	payload := map[string]string{
		"content": base64.StdEncoding.EncodeToString(content), "encoding": "base64",
	}
	result, err := c.doWrite(ctx, token, http.MethodPost, rawURL, payload)
	if err != nil {
		return "", err
	}
	if result.status != http.StatusCreated {
		return "", classifyWriteError(result.status, result.body)
	}
	return shaFromBody(result.body, "blob")
}

func (c *Client) createTree(ctx context.Context, token, fullName, baseTreeSHA string, entries []map[string]any) (string, error) {
	rawURL, err := c.apiURL("/repos/"+fullName+"/git/trees", nil)
	if err != nil {
		return "", fmt.Errorf("ghapp: %w", err)
	}
	// base_tree is what makes this a change to the tree rather than a
	// replacement of it: every file the base commit already had, that this
	// call did not name, is carried into the new tree unchanged.
	payload := map[string]any{"base_tree": baseTreeSHA, "tree": entries}
	result, err := c.doWrite(ctx, token, http.MethodPost, rawURL, payload)
	if err != nil {
		return "", err
	}
	if result.status != http.StatusCreated {
		return "", classifyWriteError(result.status, result.body)
	}
	return shaFromBody(result.body, "tree")
}

func (c *Client) createCommit(ctx context.Context, token, fullName, message, treeSHA string, parents []string) (string, error) {
	rawURL, err := c.apiURL("/repos/"+fullName+"/git/commits", nil)
	if err != nil {
		return "", fmt.Errorf("ghapp: %w", err)
	}
	payload := map[string]any{"message": message, "tree": treeSHA, "parents": parents}
	result, err := c.doWrite(ctx, token, http.MethodPost, rawURL, payload)
	if err != nil {
		return "", err
	}
	if result.status != http.StatusCreated {
		return "", classifyWriteError(result.status, result.body)
	}
	return shaFromBody(result.body, "commit")
}

// createOrFastForwardRef creates refs/heads/<branch> when it does not exist
// yet, or moves it forward to sha when it does. It never forces the update:
// this is Guidefold's own branch, but "our own" still means the update
// fails loudly rather than discarding a commit that is there for a reason
// this package does not know.
func (c *Client) createOrFastForwardRef(ctx context.Context, token, fullName, branch, sha string) error {
	rawURL, err := c.apiURL("/repos/"+fullName+"/git/refs", nil)
	if err != nil {
		return fmt.Errorf("ghapp: %w", err)
	}
	payload := map[string]any{"ref": "refs/heads/" + branch, "sha": sha}
	result, err := c.doWrite(ctx, token, http.MethodPost, rawURL, payload)
	if err != nil {
		return err
	}
	if result.status == http.StatusCreated {
		return nil
	}
	if result.status != http.StatusUnprocessableEntity {
		return classifyWriteError(result.status, result.body)
	}
	// 422 here is GitHub's "Reference already exists" — expected on every
	// push after the branch's first commit, not a failure.
	updateURL, err := c.apiURL("/repos/"+fullName+"/git/refs/heads/"+branch, nil)
	if err != nil {
		return fmt.Errorf("ghapp: %w", err)
	}
	result, err = c.doWrite(ctx, token, http.MethodPatch, updateURL, map[string]any{"sha": sha, "force": false})
	if err != nil {
		return err
	}
	if result.status != http.StatusOK {
		return classifyWriteError(result.status, result.body)
	}
	return nil
}

func shaFromBody(body []byte, kind string) (string, error) {
	var out struct {
		SHA string `json:"sha"`
	}
	if err := json.Unmarshal(body, &out); err != nil {
		return "", fmt.Errorf("ghapp: %s response is unreadable: %w", kind, err)
	}
	if out.SHA == "" {
		return "", fmt.Errorf("ghapp: %s response carried no sha", kind)
	}
	return out.SHA, nil
}
