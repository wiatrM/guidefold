#!/usr/bin/env bash
# PreToolUse Edit|Write: in ui/src, colour values live only in ui/src/tokens/tokens.css (docs/ui/pipeline/08-components.md).
source "$(dirname "$0")/_lib.sh"
f="$(repo_rel "$(hook_field tool_input.file_path)")"
case "$f" in ui/src/*) ;; *) exit 0 ;; esac
case "$f" in ui/src/tokens/tokens.css|*.test.tsx|*.test.ts|*/test/*|*.json) exit 0 ;; esac
content="$(hook_field tool_input.new_string)"; [ -z "$content" ] && content="$(hook_field tool_input.content)"
if printf '%s' "$content" | grep -Eq '#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?\b'; then
  deny "Hex colour outside ui/src/tokens/tokens.css in $f. Use a token (var(--...)); add a new token with a written reason (docs/ui/pipeline/08-components.md, ADR-0032)."
fi
exit 0
