#!/usr/bin/env bash
# PostToolUse Edit|Write: after touching the distributable CLI, verify it still compiles and imports only stdlib + yaml.
source "$(dirname "$0")/_lib.sh"
f="$(repo_rel "$(hook_field tool_input.file_path)")"
[ "$f" = "skills/guidefold/scripts/guidefold" ] || exit 0
root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
out="$(python3 - "$root/$f" <<'PY' 2>&1
import ast, sys
path = sys.argv[1]
src = open(path, encoding="utf-8").read()
try:
    tree = ast.parse(src, path)
except SyntaxError as e:
    print(f"SyntaxError: {e}"); sys.exit(1)
allowed = set(sys.stdlib_module_names) | {"yaml"}
bad = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for a in node.names: bad.add(a.name.split(".")[0]) if a.name.split(".")[0] not in allowed else None
    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        m = node.module.split(".")[0]
        if m not in allowed: bad.add(m)
if bad:
    print("Non-stdlib imports (CLAUDE.md: stdlib + PyYAML only): " + ", ".join(sorted(bad))); sys.exit(1)
PY
)"
if [ -n "$out" ]; then
  echo "skills/guidefold/scripts/guidefold: $out" >&2
  exit 2
fi
exit 0
