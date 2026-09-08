#!/usr/bin/env python3
"""Drift checker between docs/API-CONTRACT.md, the management OpenAPI file and the Go service.

The contract document is the source of truth (docs/API-CONTRACT.md §1). This script only
detects the *one* direction that is always a defect: code or schema that exists without a
contract entry. The reverse (a contracted endpoint, column or error code that is not
implemented yet) is reported as INFO, because the contract is written before the code.

Three comparisons:

  1. Endpoints   doc endpoint tables  <->  OpenAPI `paths:`  <->  Go route registrations.
  2. Database    doc `#### gfm.<table>` sections  <->  `CREATE TABLE` / `ALTER TABLE ... ADD
                 COLUMN` statements found in Go migration strings.
  3. Error codes doc "Kody błędów" table  <->  string literals in Go `fail(...)` and error
                 envelopes.

Doc format the parser expects (tolerant about spacing and alignment, strict about content):

  * Path alias: a line of the form ``- `{repo_base}` = `/api/v1/orgs/{org}/repos/{repo}` ``
    declares a prefix that endpoint rows may use; the parser expands it before comparing.
  * Endpoint row: a Markdown table row whose first cell is exactly one HTTP method
    (GET/POST/PUT/PATCH/DELETE, optionally in backticks) and whose second cell is a path
    starting with `/` or with a declared alias. One method per row - never `GET/POST`.
  * Table definition, compact form (used by §7): a Markdown table row whose first cell is
    `gf.<name>` or `gfm.<name>` in backticks and whose second cell lists the columns,
    comma separated, each starting with the column name (`org_id uuid NN, kind text NN`).
  * Table definition, detailed form: a heading (any level) whose text is `gf.<name>` or
    `gfm.<name>`, followed by a Markdown table whose first column holds column names.
  * Error codes: every Markdown table row under a heading containing `Kody błędów` whose
    first cell is a backticked snake_case identifier.

Usage:
    python3 tools/contract/check_api_contract.py [--allow-missing-openapi] [--dump] [--root DIR]

Exit code 0 = no drift, 1 = drift (or a doc that cannot be parsed).
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

# --------------------------------------------------------------------------------------
# Configuration. Everything a future router style change touches lives in this block.
# --------------------------------------------------------------------------------------

DOC_REL = "docs/API-CONTRACT.md"
OPENAPI_REL = "services/search/openapi/management-v1.yaml"
GO_GLOB_REL = "services/search/**/*.go"
CLI_REL = "skills/guidefold/scripts/guidefold"

# The CLI is the fourth side of the contract: every network command goes through
# `_service_request(api, "METHOD", path)`. The paths are f-strings built from a small
# set of prefix helpers, so the checker expands those and then compares the shape.
CLI_CALL_RE = re.compile(
    r'_service_request\(\s*[^,]+,\s*"(GET|POST|PUT|PATCH|DELETE)"\s*,\s*f?"([^"]*)"'
)
# Prefix helpers the CLI interpolates, mapped to the aliases §1 of the document declares.
CLI_PREFIXES = {
    "{base}": "{repo_base}",
    "{_repo_base(svc)}": "{repo_base}",
    "{repo_base}": "{repo_base}",
    "{_org_base(svc)}": "{org_base}",
    "{org_base}": "{org_base}",
}

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

# How a route registration looks in Go. Each entry is (regex, method_group, path_group);
# a method group of 0 means "the pattern does not name a method" and only the path is
# compared. Add a pattern here - and say so in docs/API-CONTRACT.md §1 - when the router
# changes style. The three supported shapes today:
#
#   mux.HandleFunc("GET /api/v1/orgs", h)          Go 1.22 method patterns
#   mux.HandleFunc("/api/v1/orgs", h)              method-less registration
#   rt.Handle(http.MethodGet, "/api/v1/orgs", h)   mgmt.Router.Handle (the router in use)
#   route("GET", "/api/v1/orgs", h)                helper taking method and path separately
#   r.Get("/api/v1/orgs", h)                       helper named after the method
#
# The delivery endpoints (`/v1/*`, `/health/*`, `/metrics`) are not registered on a
# router at all: App.ServeHTTP in main.go dispatches by comparing `r.URL.Path`, so no
# registration pattern can see them, and the checker used to report them as "contract
# has it, Go does not register it yet" -- factually wrong, and blind to exactly the
# surface an installation token reaches. Each such dispatch site carries
#
#   // contract-route: POST /v1/search
#
# immediately above it. The annotation is the declaration the checker reads; it is
# verified against the running handler by TestDeliveryRoutesAreAnnotated in main_test.go,
# so it cannot drift from the dispatch without a red test.
ROUTE_PATTERNS = [
    (re.compile(r'//\s*contract-route:\s*(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)'), 1, 2),
    (re.compile(r'HandleFunc\(\s*"(?:(GET|POST|PUT|PATCH|DELETE)\s+)?(/[^"\s]*)"'), 1, 2),
    (
        re.compile(
            r'\bHandle\(\s*http\.Method(Get|Post|Put|Patch|Delete)\s*,\s*"(/[^"]*)"'
        ),
        1,
        2,
    ),
    (
        re.compile(
            r'\b(?:route|Route|handle|Handle|register|Register|method|Method)\(\s*'
            r'"(GET|POST|PUT|PATCH|DELETE)"\s*,\s*"(/[^"]*)"'
        ),
        1,
        2,
    ),
    (re.compile(r'\.(Get|Post|Put|Patch|Delete)\(\s*"(/[^"]*)"'), 1, 2),
]

# Error-code literals in Go: fail(status, "code"), the raw envelope, and the named
# variables the existing handler uses for codes it picks at runtime (overloadCode).
ERROR_PATTERNS = [
    re.compile(r'\bfail\(\s*\d+\s*,\s*"([a-z][a-z0-9_]*)"'),
    re.compile(r'"error"\s*:\s*"([a-z][a-z0-9_]*)"'),
    re.compile(r'\bfailf?\(\s*(?:w|ctx)[^,]*,\s*\d+\s*,\s*"([a-z][a-z0-9_]*)"'),
    re.compile(r'\b(?:code|errCode|errorCode|overloadCode)\s*:?=\s*[^\n]*?"([a-z][a-z0-9_]*)"'),
    # internal/mgmt error constructors: Fail/Invalid/NotFound/Conflict/Unprocessable.
    re.compile(
        r'\b(?:Fail|Invalid|NotFound|Conflict|Unprocessable)\('
        r'(?:\s*http\.Status\w+\s*,)?\s*"([a-z][a-z0-9_]*)"'
    ),
    # RFC 8628 device-flow errors built by internal/identity.deviceError.
    re.compile(r'\b(?:deviceError|apiError|newError)\(\s*"([a-z][a-z0-9_]*)"'),
]

# Go error literals that are not wire error codes.
ERROR_IGNORE = {"serialization_failed"}

# Registrations that are not endpoints. Add a path only with a comment saying why.
ROUTE_IGNORE: set[str] = {
    "/api/",  # mgmt.Router catch-all that renders the JSON 404 envelope for unknown paths
}

# Tables the checker knows about but that carry no contract obligation.
TABLE_IGNORE: set[str] = set()

SQL_CONSTRAINT_WORDS = {
    "PRIMARY",
    "UNIQUE",
    "FOREIGN",
    "CHECK",
    "CONSTRAINT",
    "EXCLUDE",
    "LIKE",
    "INHERITS",
}


# --------------------------------------------------------------------------------------
# Markdown helpers
# --------------------------------------------------------------------------------------


CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


def _cells(line: str) -> list[str] | None:
    """Split one Markdown table row into cells, or return None if it is not a row.

    A `\\|` inside a cell (used for enum domains such as `CHECK(owner\\|member)`) is
    content, not a column separator.
    """
    s = line.strip()
    if not s.startswith("|"):
        return None
    if set(s) <= set("|-: "):  # separator row
        return None
    parts = CELL_SPLIT_RE.split(s)
    if len(parts) < 3:
        return None
    return [p.strip() for p in parts[1:-1]]


def _bare(cell: str) -> str:
    """Strip backticks, bold markers and link syntax from a table cell."""
    s = cell.strip()
    s = re.sub(r"\*\*", "", s)
    s = re.sub(r"^\[(.*?)\]\(.*\)$", r"\1", s)
    return s.strip().strip("`").strip()


# --------------------------------------------------------------------------------------
# Document parsing
# --------------------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
TABLE_HEADING_RE = re.compile(r"^`?(gf|gfm)\.([a-z_][a-z0-9_]*)`?$")
IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


ALIAS_RE = re.compile(r"^\s*[-*]?\s*`(\{[a-z_]+\})`\s*=\s*`(/[^`]+)`")


class Doc:
    def __init__(self) -> None:
        self.endpoints: set[tuple[str, str]] = set()
        self.tables: dict[str, set[str]] = {}
        self.error_codes: set[str] = set()
        self.contract_version: str | None = None
        self.headings: list[str] = []
        self.aliases: dict[str, str] = {}


def _expand(path: str, aliases: dict[str, str]) -> str:
    for _ in range(4):
        for name, value in aliases.items():
            if path.startswith(name):
                path = value + path[len(name):]
        if path.startswith("/"):
            break
    return path


def parse_doc(path: str) -> Doc:
    doc = Doc()
    lines = open(path, encoding="utf-8").read().splitlines()
    raw_endpoints: list[tuple[str, str]] = []
    pending_table: str | None = None  # "gfm.jobs" while we are inside its column table
    in_error_section = False

    for line in lines:
        a = ALIAS_RE.match(line)
        if a:
            doc.aliases[a.group(1)] = a.group(2)
            continue

        h = HEADING_RE.match(line)
        if h:
            heading = h.group(2)
            doc.headings.append(heading)
            in_error_section = "Kody błędów" in heading
            m = TABLE_HEADING_RE.match(_bare(heading))
            pending_table = f"{m.group(1)}.{m.group(2)}" if m else None
            continue

        cells = _cells(line)
        if cells is None:
            if line.strip() and pending_table and doc.tables.get(pending_table):
                pending_table = None
            continue

        first = _bare(cells[0])

        # 1. endpoints
        if len(cells) >= 2 and first in METHODS:
            path_cell = _bare(cells[1])
            if path_cell.startswith("/") or path_cell.startswith("{"):
                raw_endpoints.append((first, path_cell))

        # 2. database columns, compact form: | `gfm.jobs` | org_id uuid NN, ... | ... |
        m = TABLE_HEADING_RE.match(first)
        if m and len(cells) >= 2:
            name = f"{m.group(1)}.{m.group(2)}"
            cols = doc.tables.setdefault(name, set())
            for item in cells[1].split(","):
                token = _bare(item).split(" ")[0].strip("`")
                if IDENT_RE.match(token):
                    cols.add(token)

        # 3. database columns, detailed form: heading + first column of the table
        if pending_table and IDENT_RE.match(first) and first not in {"kolumna", "column"}:
            doc.tables.setdefault(pending_table, set()).add(first)

        # 4. error codes: every backticked snake_case token in the first cell, so one
        # row may document a family (`invalid_state`, `expired_state`).
        if in_error_section and cells[0].strip().startswith("`"):
            for token in re.findall(r"`([a-z][a-z0-9_]*)`", cells[0]):
                doc.error_codes.add(token)

    for method, p in raw_endpoints:
        doc.endpoints.add((method, _expand(p, doc.aliases)))

    m = re.search(r"contract_version[`\s:*]*[=:]?\s*`?(\d+\.\d+\.\d+)`?", "\n".join(lines))
    if m:
        doc.contract_version = m.group(1)
    return doc


# --------------------------------------------------------------------------------------
# Go parsing
# --------------------------------------------------------------------------------------


def go_sources(root: str) -> list[str]:
    return sorted(
        p
        for p in glob.glob(os.path.join(root, GO_GLOB_REL), recursive=True)
        if not p.endswith("_test.go")
    )


def parse_go_routes(files: list[str]) -> set[tuple[str | None, str]]:
    out: set[tuple[str | None, str]] = set()
    for f in files:
        src = open(f, encoding="utf-8", errors="replace").read()
        for regex, mg, pg in ROUTE_PATTERNS:
            for m in regex.finditer(src):
                method = m.group(mg) if mg else None
                if method:
                    method = method.upper()
                path = m.group(pg)
                if path in ROUTE_IGNORE:
                    continue
                out.add((method, path))
    return out


def _shape(path: str) -> str:
    """Reduce a path to its shape: every `{...}` segment becomes one placeholder.

    `/api/v1/orgs/{svc['org']}/repos` and `/api/v1/orgs/{org}/repos` are the same
    endpoint; only the segment structure is comparable across the two languages.
    """
    return re.sub(r"\{[^}]*\}", "{}", path)


def parse_cli_paths(path: str, aliases: dict[str, str]) -> tuple[set[tuple[str, str]], int]:
    """Extract (method, path) from the CLI's `_service_request` call sites.

    Also reports how many call sites the regex could not read, so a path built from
    a variable is a visible gap rather than a silent one.
    """
    out: set[tuple[str, str]] = set()
    if not os.path.exists(path):
        return out, 0
    src = open(path, encoding="utf-8", errors="replace").read()
    # One occurrence is the definition itself, not a call.
    sites = len(re.findall(r"_service_request\(", src)) - len(re.findall(r"def _service_request\(", src))
    unreadable = sites - len(CLI_CALL_RE.findall(src))
    for m in CLI_CALL_RE.finditer(src):
        method, raw = m.group(1).upper(), m.group(2)
        for helper, alias in CLI_PREFIXES.items():
            if raw.startswith(helper):
                raw = aliases.get(alias, alias) + raw[len(helper) :]
                break
        if not raw.startswith("/"):
            # A path assembled from a variable the checker cannot follow. Those
            # exist (`proposals list` builds a query string), and reporting them
            # as drift would be wrong; they are listed as a note instead.
            out.add((method, raw))
            continue
        out.add((method, raw))
    return out, unreadable


def _split_top_level(body: str) -> list[str]:
    items, depth, buf = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        items.append("".join(buf))
    return items


def parse_go_tables(files: list[str]) -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    create = re.compile(r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+([A-Za-z0-9_.]+)\s*\(")
    alter = re.compile(
        r"ALTER\s+TABLE\s+([A-Za-z0-9_.]+)\s+ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+([A-Za-z0-9_]+)"
    )
    for f in files:
        src = open(f, encoding="utf-8", errors="replace").read()
        for m in create.finditer(src):
            name = m.group(1).lower()
            if name in TABLE_IGNORE:
                continue
            depth, j = 1, m.end()
            while j < len(src) and depth:
                if src[j] == "(":
                    depth += 1
                elif src[j] == ")":
                    depth -= 1
                j += 1
            body = src[m.end() : j - 1]
            cols = tables.setdefault(name, set())
            for item in _split_top_level(body):
                item = re.sub(r"--[^\n]*", " ", item).strip()
                if not item:
                    continue
                word = item.split()[0].strip('"')
                if word.upper() in SQL_CONSTRAINT_WORDS:
                    continue
                if IDENT_RE.match(word):
                    cols.add(word)
        for m in alter.finditer(src):
            name = m.group(1).lower()
            if name in TABLE_IGNORE:
                continue
            tables.setdefault(name, set()).add(m.group(2))
    return tables


def parse_go_errors(files: list[str]) -> set[str]:
    out: set[str] = set()
    for f in files:
        src = open(f, encoding="utf-8", errors="replace").read()
        for regex in ERROR_PATTERNS:
            for m in regex.finditer(src):
                code = m.group(1)
                if code not in ERROR_IGNORE:
                    out.add(code)
    return out


# --------------------------------------------------------------------------------------
# OpenAPI parsing
# --------------------------------------------------------------------------------------


def parse_openapi(path: str) -> set[tuple[str, str]]:
    try:
        import yaml
    except ImportError:  # pragma: no cover - environment problem, not drift
        raise SystemExit("PyYAML is required to read " + path)
    spec = yaml.safe_load(open(path, encoding="utf-8")) or {}
    out: set[tuple[str, str]] = set()
    for p, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in item:
            if method.upper() in METHODS:
                out.add((method.upper(), p))
    return out


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------


class Report:
    def __init__(self, quiet: bool = False) -> None:
        self.drift: list[str] = []
        self.info: list[str] = []
        self.quiet = quiet

    def fail(self, msg: str) -> None:
        self.drift.append(msg)

    def note(self, msg: str) -> None:
        self.info.append(msg)

    def emit(self) -> int:
        for line in [] if self.quiet else self.info:
            print("INFO  " + line)
        for line in self.drift:
            print("DRIFT " + line)
        if self.drift:
            print(f"\n{len(self.drift)} drift finding(s); docs/API-CONTRACT.md is the source of truth.")
            return 1
        print(f"\nOK: no contract drift ({len(self.info)} informational note(s)).")
        return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ap.add_argument("--allow-missing-openapi", action="store_true",
                    help="do not fail while services/search/openapi/management-v1.yaml does not exist yet")
    ap.add_argument("--dump", action="store_true", help="print what was extracted from each side and exit 0")
    ap.add_argument("--quiet", action="store_true", help="print only drift, not the informational not-implemented-yet list")
    args = ap.parse_args(argv)

    root = args.root
    doc_path = os.path.join(root, DOC_REL)
    openapi_path = os.path.join(root, OPENAPI_REL)

    if not os.path.exists(doc_path) and not args.dump:
        print(f"DRIFT missing contract document: {DOC_REL}")
        return 1

    doc = parse_doc(doc_path) if os.path.exists(doc_path) else Doc()
    files = go_sources(root)
    go_routes = parse_go_routes(files)
    go_tables = parse_go_tables(files)
    go_errors = parse_go_errors(files)

    if args.dump:
        print("# doc endpoints"), [print(f"  {m} {p}") for m, p in sorted(doc.endpoints)]
        print("# doc tables")
        for t in sorted(doc.tables):
            print(f"  {t}: {' '.join(sorted(doc.tables[t]))}")
        print("# doc error codes:", " ".join(sorted(doc.error_codes)))
        print("# go routes"), [print(f"  {m or '*'} {p}") for m, p in sorted(go_routes, key=lambda x: (x[1], x[0] or ""))]
        print("# go tables")
        for t in sorted(go_tables):
            print(f"  {t}: {' '.join(sorted(go_tables[t]))}")
        print("# go error codes:", " ".join(sorted(go_errors)))
        return 0

    r = Report(quiet=args.quiet)

    # -- structure -----------------------------------------------------------------
    if not doc.contract_version:
        r.fail("docs/API-CONTRACT.md does not state a contract_version (x.y.z)")
    if not doc.endpoints:
        r.fail("docs/API-CONTRACT.md has no parseable endpoint rows (method | path)")
    if not doc.error_codes:
        r.fail("docs/API-CONTRACT.md has no parseable error-code table under a 'Kody błędów' heading")
    if not doc.tables:
        r.fail("docs/API-CONTRACT.md has no parseable `gf.`/`gfm.` table sections")

    doc_paths = {p for _, p in doc.endpoints}

    # -- endpoints vs OpenAPI ------------------------------------------------------
    if os.path.exists(openapi_path):
        spec = parse_openapi(openapi_path)
        for method, path in sorted(spec - doc.endpoints):
            r.fail(f"OpenAPI has {method} {path}, the contract document does not")
        for method, path in sorted(doc.endpoints - spec):
            r.note(f"contract has {method} {path}, OpenAPI does not (not published yet)")
    elif args.allow_missing_openapi:
        r.note(f"{OPENAPI_REL} does not exist yet; endpoint/OpenAPI comparison skipped")
    else:
        r.fail(f"{OPENAPI_REL} is missing (pass --allow-missing-openapi while it is not written)")

    # -- endpoints vs Go routes ----------------------------------------------------
    if not go_routes:
        r.note("no route registration matched ROUTE_PATTERNS in services/search/**/*.go; "
               "Go route comparison skipped (add a pattern when the router is written)")
    else:
        for method, path in sorted(go_routes, key=lambda x: (x[1], x[0] or "")):
            if method is None:
                if path not in doc_paths:
                    r.fail(f"Go registers {path}, the contract document does not")
            elif (method, path) not in doc.endpoints:
                r.fail(f"Go registers {method} {path}, the contract document does not")
        registered = {p for _, p in go_routes}
        for method, path in sorted(doc.endpoints):
            if path not in registered:
                r.note(f"contract has {method} {path}, Go does not register it yet")

    # -- endpoints vs CLI network commands -----------------------------------------
    cli_paths, cli_unreadable = parse_cli_paths(os.path.join(root, CLI_REL), doc.aliases)
    if cli_unreadable > 0:
        r.note(f"{cli_unreadable} `_service_request` call site(s) in {CLI_REL} build the path "
               "from a variable and were not compared")
    if not cli_paths:
        r.note(f"no `_service_request` call site was found in {CLI_REL}; CLI comparison skipped")
    else:
        doc_shapes = {(m, _shape(p)) for m, p in doc.endpoints}
        for method, path in sorted(cli_paths):
            if not path.startswith("/"):
                r.note(f"the CLI calls {method} {path}, whose prefix the checker cannot expand")
                continue
            if (method, _shape(path)) not in doc_shapes:
                r.fail(f"the CLI calls {method} {path}, the contract document does not")

    # -- database ------------------------------------------------------------------
    for table in sorted(go_tables):
        if table not in doc.tables:
            r.fail(f"Go migrations create {table}, the contract document does not describe it")
            continue
        for column in sorted(go_tables[table] - doc.tables[table]):
            r.fail(f"{table}.{column} exists in Go migrations, not in the contract document")
        for column in sorted(doc.tables[table] - go_tables[table]):
            r.note(f"{table}.{column} is contracted, not created by Go migrations yet")
    for table in sorted(set(doc.tables) - set(go_tables)):
        r.note(f"{table} is contracted, not created by Go migrations yet")

    # -- error codes ---------------------------------------------------------------
    for code in sorted(go_errors - doc.error_codes):
        r.fail(f"Go returns error code `{code}`, the contract document does not list it")
    for code in sorted(doc.error_codes - go_errors):
        r.note(f"contract lists error code `{code}`, no Go literal uses it yet")

    return r.emit()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
