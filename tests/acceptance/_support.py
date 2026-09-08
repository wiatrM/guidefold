"""Plumbing for the acceptance suite: a real stack on free ports, a real CLI, a real report.

Nothing here fakes a product behaviour. The HTTP client is the one a browser would drive
(cookie jar + CSRF double submit), the CLI is the shipped single-file script run as a
subprocess with its own ``HOME`` and ``GUIDEFOLD_CREDENTIALS``, and the database client is a
minimal PostgreSQL v3 simple-query client used only to *observe* (and, for the one synthetic
scale row, to seed) — never to substitute for a product path.

Loaded by ``tests/acceptance/conftest.py`` via ``importlib`` so it does not depend on
``sys.path`` order (``pytest.ini`` puts ``tests/`` on the path, not ``tests/acceptance/``).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


stack = _load("gf_acc_stack", REPO_ROOT / "tools" / "dev" / "stack.py")
pg = stack.pg

ApiSession = stack.ApiSession
SeedError = stack.SeedError

# ---------------------------------------------------------------------------------------
# Minimal PostgreSQL client (observation only)
# ---------------------------------------------------------------------------------------


class PgError(RuntimeError):
    pass


def pg_query(port: int, sql: str, dbname: str = "guidefold", user: str = "postgres") -> list:
    """Run one simple query and return its rows as lists of ``str | None``.

    ``tools/dev/pg.py`` ships no ``psql`` and the toolchain has none, so this speaks the v3
    wire protocol directly (trust auth, single simple query, text format). It is deliberately
    tiny: the acceptance suite reads through the API wherever the API can answer, and drops to
    SQL only where the product has no read path (job fencing rows, the synthetic scale seed)."""
    s = socket.create_connection(("127.0.0.1", port), timeout=30)
    s.settimeout(120)
    try:
        params = b"user\x00" + user.encode() + b"\x00database\x00" + dbname.encode() + b"\x00\x00"
        s.sendall(struct.pack("!I", len(params) + 8) + struct.pack("!I", 196608) + params)
        buf, rows, error, sent, done = b"", [], None, False, False
        while not done:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            while len(buf) >= 5:
                kind, length = buf[0:1], struct.unpack("!I", buf[1:5])[0]
                if len(buf) < length + 1:
                    break
                body, buf = buf[5:length + 1], buf[length + 1:]
                if kind == b"E":
                    error = " ".join(f[1:].decode("utf-8", "replace")
                                     for f in body.split(b"\x00") if f[:1] == b"M")
                elif kind == b"D":
                    n = struct.unpack("!H", body[0:2])[0]
                    off, row = 2, []
                    for _ in range(n):
                        size = struct.unpack("!i", body[off:off + 4])[0]
                        off += 4
                        if size < 0:
                            row.append(None)
                        else:
                            row.append(body[off:off + size].decode("utf-8", "replace"))
                            off += size
                    rows.append(row)
                elif kind == b"Z":
                    if not sent:
                        s.sendall(b"Q" + struct.pack("!I", len(sql) + 5) + sql.encode() + b"\x00")
                        sent = True
                    else:
                        done = True
                        break
        s.sendall(b"X" + struct.pack("!I", 4))
    finally:
        s.close()
    if error:
        raise PgError(f"{error}\nSQL: {sql[:400]}")
    return rows


def pg_scalar(port: int, sql: str, **kw):
    rows = pg_query(port, sql, **kw)
    return rows[0][0] if rows and rows[0] else None


# ---------------------------------------------------------------------------------------
# Stack
# ---------------------------------------------------------------------------------------


@dataclass
class Stack:
    """One running API + worker + PostgreSQL, on ports nothing else is using."""
    name: str
    pg_port: int
    api_port: int
    paths: Any
    secret_paths: dict
    generator: str
    # The CLI revision `serve` and `worker` hashed at startup (GUIDEFOLD_POLICY_SOURCE).
    # `build_tree.py` hashes the same file when it builds a snapshot, so an edit to the CLI
    # mid-run makes every publication fail with `snapshot_policy_mismatch` -- an environment
    # problem that reads exactly like a product bug unless it is named.
    cli_sha256: str = ""

    @property
    def api(self) -> str:
        return f"http://127.0.0.1:{self.api_port}"

    def env_for(self, **overrides) -> dict:
        kwargs = dict(pg_port=self.pg_port, api_port=self.api_port,
                      secret_paths=self.secret_paths, contract=self.paths.contract,
                      policy_source=self.paths.policy_source, generator=self.generator,
                      repo_root=self.paths.repo_root)
        kwargs.update(overrides)
        return kwargs

    def sql(self, statement: str) -> list:
        return pg_query(self.pg_port, statement)

    def assert_cli_unchanged(self) -> None:
        current = sha256_bytes(self.paths.policy_source.read_bytes())
        if self.cli_sha256 and current != self.cli_sha256:
            raise AssertionError(
                "skills/guidefold/scripts/guidefold changed while the stack was running: the "
                f"processes hashed {self.cli_sha256[:12]}…, the file is now {current[:12]}…. "
                "Every publication will fail with snapshot_policy_mismatch until the stack is "
                "restarted. This is an environment problem, not a product defect.")

    def api_log(self) -> str:
        return stack.tail_lines(self.paths.api_log, 200)

    def worker_log(self) -> str:
        return stack.tail_lines(self.paths.worker_log, 200)

    def restart_worker(self, *, generator: Optional[str] = None) -> int:
        stack.stop_pid(self.paths.worker_pid, "worker", needle="guidefold-search")
        env = self.env_for(**({"generator": generator} if generator else {}))
        return stack.spawn([str(self.paths.binary), "worker"],
                           stack.full_env(stack.worker_env(**env)),
                           self.paths.worker_log, self.paths.worker_pid, self.paths.repo_root)

    def stop_worker(self) -> None:
        stack.stop_pid(self.paths.worker_pid, "worker", needle="guidefold-search")


def start_stack(*, name: str, generator: str = "deterministic",
                subdir: str = "acceptance") -> Stack:
    """Build the binary, wipe and start PostgreSQL, migrate, then run serve + worker."""
    paths = stack.paths_for(REPO_ROOT, subdir=subdir)
    pg_port = stack.free_port()
    api_port = stack.free_port()

    build = stack.build_binary(paths)
    if build.returncode != 0:
        raise RuntimeError(f"go build failed:\n{build.stdout}\n{build.stderr}")

    pg.reset(name, pg_port)  # a pristine cluster: acceptance must not inherit yesterday's rows
    secret_paths = stack.ensure_secrets(paths.secrets_dir)

    migrated = stack.run_migrate(paths, pg_port, secret_paths)
    if migrated.returncode != 0:
        raise RuntimeError(f"migrate failed:\n{stack.tail_lines(paths.migrate_log, 60)}")

    s = Stack(name=name, pg_port=pg_port, api_port=api_port, paths=paths,
              secret_paths=secret_paths, generator=generator,
              cli_sha256=sha256_bytes(paths.policy_source.read_bytes()))
    stack.stop_pid(paths.api_pid, "api", needle="guidefold-search")
    stack.spawn([str(paths.binary), "serve"], stack.full_env(stack.serve_env(**s.env_for())),
                paths.api_log, paths.api_pid, paths.repo_root)
    if not stack.wait_for_live(f"{s.api}/health/live", timeout=60.0):
        raise RuntimeError(f"api never became live:\n{stack.tail_lines(paths.api_log, 60)}")
    s.restart_worker()
    return s


def stop_stack(s: Stack) -> None:
    stack.stop_pid(s.paths.worker_pid, "worker", needle="guidefold-search")
    stack.stop_pid(s.paths.api_pid, "api", needle="guidefold-search")
    pg.stop(s.name)


# ---------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------


@dataclass
class Cli:
    """The shipped single-file script, run as a subprocess with an isolated identity.

    ``HOME``, ``XDG_CONFIG_HOME`` and ``GUIDEFOLD_CREDENTIALS`` all point inside ``home`` so a
    run can never read or write the developer's own ``~/.config/guidefold/credentials.json``."""
    home: Path
    api: str
    org: Optional[str] = None
    repo: Optional[str] = None
    token: Optional[str] = None
    extra: dict = field(default_factory=dict)

    @property
    def script(self) -> Path:
        return REPO_ROOT / "skills" / "guidefold" / "scripts" / "guidefold"

    @property
    def credentials(self) -> Path:
        return self.home / "credentials.json"

    def env(self, **overrides) -> dict:
        self.home.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        for key in list(env):
            if key.startswith("GUIDEFOLD_"):
                env.pop(key)
        env.update({
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "GUIDEFOLD_CREDENTIALS": str(self.credentials),
            "GUIDEFOLD_API": self.api,
        })
        if self.org:
            env["GUIDEFOLD_ORG"] = self.org
        if self.repo:
            env["GUIDEFOLD_REPO_ID"] = self.repo
        if self.token:
            env["GUIDEFOLD_TOKEN"] = self.token
        env.update(self.extra)
        env.update({k: v for k, v in overrides.items() if v is not None})
        for k, v in overrides.items():
            if v is None:
                env.pop(k, None)
        return env

    def run(self, args: list, *, cwd: Path, timeout: float = 900.0,
            check: bool = True, **env_overrides) -> subprocess.CompletedProcess:
        result = subprocess.run([sys.executable, str(self.script), *args], cwd=str(cwd),
                                env=self.env(**env_overrides), capture_output=True,
                                text=True, timeout=timeout)
        if check and result.returncode != 0:
            raise AssertionError(
                f"guidefold {' '.join(args)} exited {result.returncode}\n"
                f"--- stdout\n{result.stdout}\n--- stderr\n{result.stderr}")
        return result

    def json(self, args: list, *, cwd: Path, **kw) -> dict:
        result = self.run(args, cwd=cwd, **kw)
        return stack.last_json_object(result.stdout)

    def popen(self, args: list, *, cwd: Path, **env_overrides) -> subprocess.Popen:
        """`-u` matters: `login` prints the user code and then blocks polling, so a
        block-buffered pipe would hide the code until the process exits."""
        return subprocess.Popen([sys.executable, "-u", str(self.script), *args], cwd=str(cwd),
                                env=self.env(PYTHONUNBUFFERED="1", **env_overrides),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)


USER_CODE_RE = re.compile(r"enter code\s+(\S+)")


def cli_device_login(cli: Cli, session: ApiSession, *, cwd: Path, timeout: float = 120.0) -> str:
    """Drive `guidefold login` end to end: start it, read the user code it prints, approve that
    code with the browser session, and wait for it to store the credentials.

    This is the product path U5 AC2 describes — the CLI never sees a client secret and the
    approval happens in an authenticated session, not in the CLI."""
    proc = cli.popen(["login"], cwd=cwd)
    user_code, lines = None, []
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            lines.append(line)
            match = USER_CODE_RE.search(line)
            if match:
                user_code = match.group(1)
                break
        if not user_code:
            proc.kill()
            raise SeedError(f"guidefold login printed no user code:\n{''.join(lines)}")
        session.expect("POST", "/api/v1/auth/device/approve", body={"user_code": user_code})
        rest = proc.communicate(timeout=max(5.0, deadline - time.monotonic()))[0] or ""
        lines.append(rest)
    finally:
        if proc.poll() is None:
            proc.kill()
    if proc.returncode != 0:
        raise SeedError(f"guidefold login exited {proc.returncode}:\n{''.join(lines)}")
    return "".join(lines)


# ---------------------------------------------------------------------------------------
# Git trees
# ---------------------------------------------------------------------------------------


def git(tree: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ,
               GIT_AUTHOR_NAME="guidefold acceptance", GIT_AUTHOR_EMAIL="acc@example.test",
               GIT_COMMITTER_NAME="guidefold acceptance", GIT_COMMITTER_EMAIL="acc@example.test")
    result = subprocess.run(["git", *args], cwd=str(tree), env=env, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {result.returncode}\n{result.stdout}{result.stderr}")
    return result


def make_git_tree(dest: Path, source: Optional[Path] = None) -> str:
    """A fresh git work tree holding a copy of ``source`` (default: the Meridian fixture)."""
    source = source or (REPO_ROOT / "examples" / "monorepo")
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".git", ".guidefold"))
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "acceptance baseline")
    return git(dest, "rev-parse", "HEAD").stdout.strip()


def commit_all(tree: Path, message: str) -> str:
    git(tree, "add", "-A")
    git(tree, "commit", "-q", "-m", message)
    return git(tree, "rev-parse", "HEAD").stdout.strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------------------
# Editing a SKILL.md without breaking it
# ---------------------------------------------------------------------------------------


def edit_frontmatter(path: Path, mutate) -> dict:
    """Round-trip a SKILL.md's YAML frontmatter through ``mutate(dict) -> dict``.

    String surgery on frontmatter is how a test accidentally measures `invalid_card` instead
    of the rule it meant to check: appending a second `metadata:` key, or splicing a block
    into an existing one, produces YAML the CLI rejects outright. Parsing and re-emitting
    keeps the file valid, so a failure afterwards is the product's, not the test's."""
    import yaml

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise AssertionError(f"{path} has no frontmatter to edit")
    end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    front = yaml.safe_load("".join(lines[1:end])) or {}
    front = mutate(front)
    rendered = yaml.safe_dump(front, sort_keys=False, allow_unicode=True, width=10_000)
    path.write_text("---\n" + rendered + "---\n" + "".join(lines[end + 1:]), encoding="utf-8")
    return front


def set_metadata(path: Path, **entries) -> dict:
    """Merge keys into a SKILL.md's ``metadata:`` block, creating it if absent."""

    def mutate(front):
        metadata = dict(front.get("metadata") or {})
        metadata.update(entries)
        front["metadata"] = metadata
        return front

    return edit_frontmatter(path, mutate)


def authored_skills(tree: Path) -> list:
    """Every SKILL.md in ``tree`` that the catalog is supposed to hold.

    A card carrying ``metadata.generated: true`` -- the committed `hierarchy-index` is one --
    is deliberately left out of a snapshot and listed under `generated_skipped` instead
    (tools/worker/build_tree.py, ADR-0012: nothing generated is committed). Counting files on
    disk and expecting that number back from `/skills` therefore fails for a correct product,
    so the expectation is computed the same way the builder computes it."""
    import yaml

    out = []
    for path in sorted(tree.rglob("SKILL.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        front = {}
        if lines and lines[0].strip() == "---":
            end = next((i for i, line in enumerate(lines[1:], start=1)
                        if line.strip() == "---"), None)
            if end is not None:
                try:
                    front = yaml.safe_load("".join(lines[1:end])) or {}
                except yaml.YAMLError:
                    front = {}
        metadata = front.get("metadata") or {}
        if str(metadata.get("generated", "")).lower() == "true":
            continue
        out.append(str(path.relative_to(tree)))
    return out


def break_frontmatter(path: Path) -> None:
    """Make a SKILL.md genuinely unparsable.

    An unterminated `---` is not enough: the CLI's `frontmatter()` returns `{}` for it and the
    file is simply not a skill. Invalid YAML *inside* a terminated block is what raises, which
    is what "one broken file fails on its own" needs."""
    path.write_text("---\nname: broken-on-purpose\n"
                    "description: \"[meridian] deliberately invalid frontmatter\"\n"
                    "metadata: [1, 2\n---\n\n# Broken\n\nbody\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------
# Documents the deterministic recipe can actually extract from
# ---------------------------------------------------------------------------------------

RUNBOOK_TEMPLATE = """# {title}

## Purpose

{purpose}

## When to use

Use when {when}.

## When not to use

Do not use for {not_when}.

## Steps

1. Announce the change in the {channel} channel and record the ticket id.
2. Generate the new key pair with `guidefold-keys new --scope {scope}`.
3. Publish the new public key to the shared trust store and wait for propagation.
4. Switch {component} to sign with the new key and keep the old key for verification.
5. Remove the old key after two full retention windows have passed.

## Verification

Check that {component} reports the new key id in its readiness probe and that no request
is rejected with `unknown_key` for a full hour.
"""


def write_runbook(tree: Path, name: str, *, title: str, purpose: str, when: str,
                  not_when: str, channel: str, scope: str, component: str) -> Path:
    """A markdown document with the headings `det-1` recognises: purpose, when to use, when
    not to use, an ordered `Steps` list and a verification section.

    The Meridian fixture's own README files are prose, so the deterministic recipe abstains on
    every one of them with `no_procedure_found` -- which is correct behaviour, and which means a
    test that wants a candidate has to supply a document that actually holds a procedure."""
    path = tree / "docs" / "runbooks" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(RUNBOOK_TEMPLATE.format(title=title, purpose=purpose, when=when,
                                             not_when=not_when, channel=channel, scope=scope,
                                             component=component), encoding="utf-8")
    return path


def add_runbooks(tree: Path) -> list:
    """Two runbooks that share three literal steps -- enough for extraction, and the shared
    element consolidation is supposed to notice."""
    return [
        write_runbook(tree, "rotate-turnstile-signing-keys",
                      title="Rotate Turnstile signing keys",
                      purpose="Turnstile signs session tokens with a rotating key pair.",
                      when="a signing key reaches its rotation date or is suspected leaked",
                      not_when="rotating database credentials or TLS certificates",
                      channel="#atlas-identity", scope="atlas.identity",
                      component="turnstile"),
        write_runbook(tree, "rotate-relay-signing-keys",
                      title="Rotate Relay signing keys",
                      purpose="Relay signs webhook payloads with a rotating key pair.",
                      when="a webhook signing key reaches its rotation date",
                      not_when="rotating the ingress TLS certificate",
                      channel="#relay-platform", scope="relay",
                      component="relay"),
    ]


# ---------------------------------------------------------------------------------------
# Waiting
# ---------------------------------------------------------------------------------------


def wait_until(predicate: Callable[[], Any], *, timeout: float = 120.0, interval: float = 0.4,
               what: str = "condition"):
    """Poll ``predicate`` until it returns something truthy; return that value."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"timed out after {timeout:.0f}s waiting for {what}; last value: {last!r}")


def percentile(values: list, q: float) -> float:
    """Nearest-rank percentile of a non-empty sample."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("empty sample")
    rank = max(1, int(round(q / 100.0 * len(ordered))))
    return ordered[min(rank, len(ordered)) - 1]


# ---------------------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------------------

PASS, FAIL, NOT_MEASURED = "pass", "fail", "not_measured_here"


@dataclass
class Report:
    """One row per acceptance criterion, written to `.guidefold/checks/` at session teardown.

    A row is a claim with its receipt: what was executed, against which data, and what came
    back. ``not_measured_here`` is a first-class result (eval-evidence-rules: a skip is "not
    measured", never a pass), and its ``limitation`` says who or what is missing."""
    rows: list = field(default_factory=list)
    environment: dict = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def record(self, acc_id: str, *, prd_ac: str, scenario: str, command_or_endpoint: str,
               data_origin: str, result: str, evidence: Optional[dict] = None,
               limitation: str = "") -> dict:
        assert result in (PASS, FAIL, NOT_MEASURED), result
        row = {"acc_id": acc_id, "prd_ac": prd_ac, "scenario": scenario,
               "command_or_endpoint": command_or_endpoint, "data_origin": data_origin,
               "result": result, "evidence": evidence or {}, "limitation": limitation,
               "recorded_at": datetime.now(timezone.utc).isoformat()}
        self.rows.append(row)
        return row

    def counts(self) -> dict:
        out = {PASS: 0, FAIL: 0, NOT_MEASURED: 0}
        for row in self.rows:
            out[row["result"]] += 1
        return out

    def as_dict(self) -> dict:
        return {"format": "guidefold-acceptance-report-v1",
                "started_at": self.started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "environment": self.environment,
                "counts": self.counts(),
                "rows": sorted(self.rows, key=lambda r: (r["acc_id"], r["recorded_at"]))}

    def write(self, directory: Path) -> tuple:
        directory.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        json_path = directory / f"acceptance-{day}.json"
        md_path = directory / f"acceptance-{day}.md"
        data = self.as_dict()
        json_path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        md_path.write_text(self.as_markdown(data), encoding="utf-8")
        return json_path, md_path

    def as_markdown(self, data: dict) -> str:
        counts = data["counts"]
        lines = [
            "# Acceptance run — Guidefold pivot MVP",
            "",
            f"Status: measurement record, run {data['started_at']} → {data['finished_at']} (UTC).",
            "Cel: jeden wiersz na kryterium akceptacji z komendą, pochodzeniem danych i wynikiem.",
            "Zakres zastępowania: brak — to raport z przebiegu, nie dokument kanoniczny.",
            "",
            f"**{counts[PASS]} pass · {counts[FAIL]} fail · {counts[NOT_MEASURED]} not_measured_here**",
            "",
            "`not_measured_here` means exactly that: the criterion needs a human, a real vendor or a",
            "network this run does not have. It is never a pass and never a failure.",
            "",
            "## Environment",
            "",
        ]
        for key in sorted(data["environment"]):
            lines.append(f"- `{key}`: {data['environment'][key]}")
        lines += ["", "## Rows", "",
                  "| ACC | PRD AC | Result | Scenario | Command / endpoint | Data origin | Limitation |",
                  "|---|---|---|---|---|---|---|"]
        for row in data["rows"]:
            lines.append("| {acc_id} | {prd_ac} | **{result}** | {scenario} | `{cmd}` | {origin} | {lim} |".format(
                acc_id=row["acc_id"], prd_ac=row["prd_ac"], result=row["result"],
                scenario=_cell(row["scenario"]), cmd=_cell(row["command_or_endpoint"]),
                origin=_cell(row["data_origin"]), lim=_cell(row["limitation"]) or "—"))
        lines += ["", "## Evidence", ""]
        for row in data["rows"]:
            if not row["evidence"]:
                continue
            lines.append(f"### {row['acc_id']}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(row["evidence"], indent=2, sort_keys=True))
            lines.append("```")
            lines.append("")
        return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")
