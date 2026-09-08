#!/usr/bin/env bash
# PostToolUse Edit|Write: banned vocabulary from docs/ui/UX.md §6 in product strings, pipeline docs and README.
source "$(dirname "$0")/_lib.sh"
f="$(repo_rel "$(hook_field tool_input.file_path)")"
case "$f" in
  docs/ui/UX.md|docs/ui/PIPELINE-PROMPT.md|ui/node_modules/*) exit 0 ;;   # these quote the banned list as a rule
  ui/*|docs/ui/*|prototypes/pipeline-*|README.md|docs/PRODUCT-FOCUS.md|skills/guidefold/SKILL.md) ;;
  *) exit 0 ;;
esac
root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
hits="$(grep -n -i -E '\b(seamless(ly)?|streamlin(e|ed|ing)|empower(s|ed|ing)?|unlock(s|ed|ing)?|effortless(ly)?|supercharge[sd]?|delve|leverag(e|es|ing)|elevate[sd]?)\b|studies show|badania pokazuj' "$root/$f" 2>/dev/null | grep -v -i 'banned\|nie używaj\|zakazan\|slop' | head -8)"
if [ -n "$hits" ]; then
  printf 'Banned vocabulary (docs/ui/UX.md §6) in %s:\n%s\nRewrite: say the one thing that is true.\n' "$f" "$hits" >&2
  exit 2
fi
exit 0
