#!/usr/bin/env bash
# Shared helpers for Guidefold hooks. Input: hook JSON on stdin (Claude Code hook contract).
# Every hook reads stdin once into $HOOK_JSON and uses python3 for parsing (no jq dependency).
HOOK_JSON="$(cat)"
hook_field() { # hook_field <dotted.path>  -> prints value or empty
  printf '%s' "$HOOK_JSON" | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
for k in sys.argv[1].split("."):
    d=d.get(k,{}) if isinstance(d,dict) else {}
if isinstance(d,(dict,list)) or d is None: print("")
else: print(d)' "$1"
}
deny() { # deny <reason>  (PreToolUse): block the tool call, reason shown to Claude
  python3 -c 'import json,sys;print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":sys.argv[1]}}))' "$1"
  exit 0
}
ask() { # ask <reason>  (PreToolUse): escalate to the user
  python3 -c 'import json,sys;print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":sys.argv[1]}}))' "$1"
  exit 0
}
note() { # note <text>  (PreToolUse): allow, but add context for Claude
  python3 -c 'import json,sys;print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","additionalContext":sys.argv[1]}}))' "$1"
  exit 0
}
repo_rel() { # repo_rel <abs-or-rel path> -> path relative to repo root
  local root; root="$(git -C "${CLAUDE_PROJECT_DIR:-.}" rev-parse --show-toplevel 2>/dev/null || pwd)"
  python3 -c 'import os,sys;p=sys.argv[1];r=sys.argv[2];print(os.path.relpath(p,r) if os.path.isabs(p) else p)' "$1" "$root"
}
