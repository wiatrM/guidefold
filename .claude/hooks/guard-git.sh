#!/usr/bin/env bash
# PreToolUse Bash: git safety. Deny force push / --no-verify / commits on main; ask before history-destroying commands.
source "$(dirname "$0")/_lib.sh"
cmd="$(hook_field tool_input.command)"
[ -z "$cmd" ] && exit 0
case "$cmd" in *git*) ;; *) exit 0 ;; esac
# Only git invocations in command position count (start of line or after && ; |), not text inside heredocs/strings.
G='(^|&&|;|\|)[[:space:]]*(cd[[:space:]]+[^&;|]+&&[[:space:]]*)?git[[:space:]]+'
gitcmd() { printf '%s\n' "$cmd" | grep -Eq "${G}$1"; }
if gitcmd 'push\b[^&;|]*([[:space:]]--force([[:space:]]|$)|[[:space:]]-f([[:space:]]|$)|--force-with-lease)'; then
  deny "Force push is not used in this repo (git-workflow skill). Open a new PR or rebase locally without rewriting the remote."
fi
if gitcmd '(commit|push)\b[^&;|]*--no-verify'; then
  deny "--no-verify skips the checks the PR template requires. Fix the hook failure instead."
fi
if gitcmd 'commit\b'; then
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
    deny "Committing on $branch is not allowed: create a branch/worktree first (git-workflow skill, superpowers:using-git-worktrees). Also confirm the user asked for a commit."
  fi
fi
if gitcmd '(reset[[:space:]]+--hard|clean[[:space:]]+-[a-zA-Z]*f|checkout[[:space:]]+--[[:space:]]+\.|restore[[:space:]]+\.|branch[[:space:]]+-D)'; then
  ask "This git command discards work. Confirm with the user (uncommitted pivot docs and ui/ live in this tree)."
fi
exit 0
