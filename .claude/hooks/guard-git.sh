#!/usr/bin/env bash
# PreToolUse Bash: git safety. Deny force push / --no-verify / commits on main; ask before history-destroying commands.
source "$(dirname "$0")/_lib.sh"
cmd="$(hook_field tool_input.command)"
[ -z "$cmd" ] && exit 0
case "$cmd" in *git*) ;; *) exit 0 ;; esac
# Only git invocations in command position count (start of line or after && ; |), not text inside heredocs/strings.
G='(^|&&|;|\|)[[:space:]]*(cd[[:space:]]+[^&;|]+&&[[:space:]]*)?git[[:space:]]+'
gitcmd() { printf '%s\n' "$cmd" | grep -Eq "${G}$1"; }
# The directory the commit actually runs in, or empty. It is the last directory
# changed into before the commit, which is not always the step right before it:
# `cd <dir> && git add -A && git commit` is the ordinary shape.
commit_dir() {
  printf '%s\n' "$cmd" \
    | sed -E 's/git[[:space:]]+commit.*$//' \
    | grep -oE '(^|&&|;|\|)[[:space:]]*cd[[:space:]]+[^&;|[:space:]]+' \
    | tail -n1 \
    | sed -E 's/.*cd[[:space:]]+//'
}
if gitcmd 'push\b[^&;|]*([[:space:]]--force([[:space:]]|$)|[[:space:]]-f([[:space:]]|$)|--force-with-lease)'; then
  deny "Force push is not used in this repo (git-workflow skill). Open a new PR or rebase locally without rewriting the remote."
fi
if gitcmd '(commit|push)\b[^&;|]*--no-verify'; then
  deny "--no-verify skips the checks the PR template requires. Fix the hook failure instead."
fi
if gitcmd 'commit\b'; then
  # Read the branch of the tree the commit actually runs in, not the session's.
  # Several worktrees of this repo are checked out at once, so the session
  # directory is routinely on a different branch from the one being committed to.
  # Reading HEAD here refused commits on feature branches whenever the session
  # directory happened to sit on main, and would equally have allowed the reverse.
  target="$(commit_dir)"
  branch="$(git -C "${target:-.}" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
    deny "Committing on $branch is not allowed: create a branch/worktree first (git-workflow skill, superpowers:using-git-worktrees). Also confirm the user asked for a commit."
  fi
fi
if gitcmd '(reset[[:space:]]+--hard|clean[[:space:]]+-[a-zA-Z]*f|checkout[[:space:]]+--[[:space:]]+\.|restore[[:space:]]+\.|branch[[:space:]]+-D)'; then
  ask "This git command discards work. Confirm with the user (uncommitted pivot docs and ui/ live in this tree)."
fi
exit 0
