#!/usr/bin/env bash
# PreToolUse Edit|Write|MultiEdit: deny edits to frozen references, warn on fixture skills.
source "$(dirname "$0")/_lib.sh"
f="$(repo_rel "$(hook_field tool_input.file_path)")"
[ -z "$f" ] && exit 0
case "$f" in
  prototypes/industrial-surveyor/*) deny "Frozen visual reference (docs/ui/UI.md §5.5, ui/README.md). Change ui/ or the pipeline docs instead." ;;
  prototypes/pipeline-hifi/*)       deny "Frozen hi-fi baseline (ui/README.md). Further UI work happens in ui/." ;;
  skills/guidefold/hooks/*.json)    note "Distributable hook template: consumers copy this file. Keep it harness-generic; do not add Guidefold-internal paths." ;;
  examples/monorepo/.agents/skills/*) note "Meridian fixture skill. Do not edit it to change project instructions (docs/DOCUMENTATION-RULES.md); fixture edits need a test that depends on them." ;;
  skills/guidefold/SKILL.md)        note "Distributable bootstrap skill for consumer repos. No internal Guidefold plans or repo-local paths (docs/DOCUMENTATION-RULES.md, Instrukcje projektu)." ;;
esac
exit 0
