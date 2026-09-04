"""B0 (original CLI, scope-only ranking) vs Router 0.1 on the 220-case golden set.

B0 is the literal CLI from commit 984d08c, extracted from git, run as a subprocess at each
case's cwd. No reimplementation, so the comparison cannot flatter the new code by accident.
"""
import importlib.util, json, pathlib, re, subprocess, sys, yaml

ROOT = pathlib.Path("/home/mike/projects/guidefold")
B0_COMMIT = "984d08c"   # the original scope-only CLI, before the Router split
FIX = ROOT / "examples" / "monorepo"
URN_RE = re.compile(r"^- (urn:skill:\S+)$", re.M)

spec = importlib.util.spec_from_file_location("m", ROOT / "tools" / "eval" / "metrics.py")
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)

# Extract B0 straight from git rather than reimplementing it, so the comparison cannot
# accidentally flatter the new code.
import tempfile
b0_src = subprocess.run(["git", "show", f"{B0_COMMIT}:skills/guidefold/scripts/guidefold"],
                        cwd=ROOT, capture_output=True, text=True).stdout
assert b0_src, f"could not extract the B0 CLI from {B0_COMMIT}"
b0_path = pathlib.Path(tempfile.mkdtemp()) / "guidefold_B0.py"
b0_path.write_text(b0_src)

cases = []
for f in sorted((ROOT / "tests" / "golden").glob("*.yaml")):
    d = yaml.safe_load(f.read_text())
    for c in d["cases"]:
        c.setdefault("category", d["category"]); cases.append(c)
print(f"{len(cases)} golden cases", file=sys.stderr)

results = []
for i, c in enumerate(cases):
    cwd = FIX / c["cwd"] if c["cwd"] != "." else FIX
    out = subprocess.run([sys.executable, str(b0_path), "find", c["query"], "--limit", "8"],
                         cwd=cwd, capture_output=True, text=True)
    results.append((URN_RE.findall(out.stdout), c))
    if i % 40 == 0: print(f"  {i}/{len(cases)}", file=sys.stderr)

overall = M.evaluate(results); per = M.by_category(results)
print(M.format_table(overall, per))
print("\nB0 is the scope-only ranking this router replaces; see docs/reports/golden/README.md", file=sys.stderr)
