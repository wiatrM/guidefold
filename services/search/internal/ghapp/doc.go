// Package ghapp is the only adapter in this service that speaks to
// api.github.com. It signs the Guidefold GitHub App's own JWT (RS256, stdlib
// crypto only — no dependency this module does not already have), exchanges
// it for a short-lived installation token, and offers two kinds of
// operation on top of it: read and write.
//
// The read half — ListSkillFiles and ReadFile — is unchanged by ADR-0036's
// 2026-09-12 amendment and stays exactly what it was: AGENTS.md at a
// repository's root and **/.agents/skills/**/SKILL.md anywhere under it,
// nothing cloned, nothing from the repository ever executed.
//
// The write half exists because that amendment makes the App behave like a
// coverage bot (ADR-0036 points 1, 1a): it comments on the pull request that
// triggered it, and it proposes skill files through a branch and pull
// request of Guidefold's own. It is deliberately narrow — three operations,
// against two things only:
//
//   - UpsertStickyComment writes to the pull request's own conversation, one
//     comment per PR, rewritten rather than multiplied on every push.
//   - CreateBranchCommit and OpenPullRequest write to a branch and pull
//     request Guidefold creates, never to the customer's PR branch, and
//     CreateBranchCommit refuses, with ErrPathNotAllowed, any file outside
//     AGENTS.md or a .agents/skills directory — this App proposes skill
//     files and nothing else (ADR-0036 point 1a), and that rule is enforced
//     here, in the one place a caller cannot route around it, rather than
//     trusted to every caller's own judgment.
//
// CreateBranchCommit builds its commit through the git data API — resolve a
// base commit, create a blob per file, create a tree with base_tree set,
// create the commit, create or fast-forward the branch ref — rather than the
// /work clone ADR-0036 point 2 describes for ascend.run. That is a
// deliberate deviation, not an oversight: the API route needs neither git in
// the worker image nor a working directory on disk, and unlike a clone it
// has no filesystem state in which something from the customer's repository
// could end up executed by accident.
//
// The installation token never leaves this package as a plain value handed
// back to a caller: every exported operation takes an installation id and
// does its own token exchange internally. The token is cached in memory,
// refreshed five minutes before GitHub's own expiry, and set only as the
// Authorization header of the requests this package makes on a caller's
// behalf — never logged, never put in an error string, never a field of a
// struct that gets marshalled.
package ghapp
