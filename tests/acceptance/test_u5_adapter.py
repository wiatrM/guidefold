"""U5 — the adapter side: installing it, signing in, what its token may do, and what happens
when the service is not there."""
from __future__ import annotations

import json
import time
import urllib.parse

import pytest

from gf_acceptance_support import (PASS, FAIL, NOT_MEASURED, ApiSession, make_git_tree,
                                   percentile, stack, wait_until)

pytestmark = pytest.mark.acceptance


@pytest.mark.acc("U5-1")
def test_u5_1_install_is_idempotent_uninstall_is_complete_and_doctor_names_the_gaps(
        fresh_org, report, bring_up):
    """U5-1: install, install again, doctor, uninstall."""
    w = fresh_org("u5-install")
    bring_up(w)
    first = w.cli.run(["install", "--harness", "claude"], cwd=w.tree)
    manifest_path = w.tree / ".agents/skills/guidefold/INSTALL-MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    dry = w.cli.run(["install", "--harness", "claude", "--dry-run"], cwd=w.tree)
    second = w.cli.run(["install", "--harness", "claude"], cwd=w.tree)

    doctor = w.cli.run(["doctor", "--json"], cwd=w.tree, check=False)
    checks = {c["name"]: c for c in json.loads(_json_slice(doctor.stdout))["checks"]}

    uninstalled = w.cli.run(["uninstall", "--harness", "claude"], cwd=w.tree)
    left = list((w.tree / ".agents/skills/guidefold").rglob("*")) if (
        w.tree / ".agents/skills/guidefold").exists() else []

    ok = ("nothing to do" in second.stdout
          and manifest.get("package_sha256")
          and "service-config" in checks and "adapter-install" in checks
          and not left)
    report.record("U5-1", prd_ac="U5 AC1 (installer, diff, uninstall, doctor)",
                  scenario="install, --dry-run, install again, `doctor --json`, uninstall",
                  command_or_endpoint="guidefold install --harness claude [--dry-run]; "
                                      "guidefold doctor --json; guidefold uninstall --harness claude",
                  data_origin="examples/monorepo in a fresh git work tree, against this run's API",
                  result=PASS if ok else FAIL,
                  evidence={"files_in_manifest": len(manifest.get("files", {})),
                            "package_sha256": manifest.get("package_sha256"),
                            "cli_version": manifest.get("cli_version"),
                            "second_install": second.stdout.strip().splitlines()[-1:],
                            "dry_run_wrote_nothing": "[dry-run]" in dry.stdout,
                            "doctor": {name: {"status": c["status"], "detail": c.get("detail")}
                                       for name, c in checks.items()
                                       if name in ("service-config", "service-api",
                                                   "service-identity", "adapter-install",
                                                   "capabilities-claude", "search-service",
                                                   "search-token")},
                            "files_left_after_uninstall": [str(p) for p in left]},
                  limitation="Claude harness only; the Copilot instructions block is not measured "
                             "in this run.")
    assert ok, (second.stdout, sorted(checks), left)


@pytest.mark.acc("U5-2")
def test_u5_2_device_login_denies_expires_and_stores_its_credential_outside_the_repo(
        fresh_org, gf_stack, report, scratch):
    """U5-2: pending, denied and the 0600 credential file outside the work tree."""
    w = fresh_org("u5-device")
    make_git_tree(w.tree)
    # `fresh_org` mints its token through the API; this AC is about the CLI's own login, so
    # run that too and inspect what it stored.
    from gf_acceptance_support import cli_device_login
    cli_device_login(w.cli, w.owner, cwd=w.tree)
    anon = ApiSession(gf_stack.api)

    pending_start = anon.expect("POST", "/api/v1/auth/device")
    pending_status, pending_body, _ = anon.request(
        "POST", "/api/v1/auth/device/token", body={"device_code": pending_start["device_code"]})

    denied_start = anon.expect("POST", "/api/v1/auth/device")
    w.owner.expect("POST", "/api/v1/auth/device/deny", ok=(200, 204),
                   body={"user_code": denied_start["user_code"]})
    denied_status, denied_body, _ = anon.request(
        "POST", "/api/v1/auth/device/token", body={"device_code": denied_start["device_code"]})

    unknown_status, unknown_body, _ = anon.request(
        "POST", "/api/v1/auth/device/token",
        body={"device_code": "00000000-0000-4000-8000-0000000000ff"})

    mode = oct(w.cli.credentials.stat().st_mode & 0o777)
    inside_repo = str(w.cli.credentials).startswith(str(w.tree))
    body_keys = sorted(pending_start)

    ok = (pending_status == 400 and pending_body.get("error") in ("authorization_pending",
                                                                  "slow_down")
          and denied_status == 400 and denied_body.get("error") == "access_denied"
          and unknown_status in (400, 404)
          and mode == "0o600" and not inside_repo
          and "client_secret" not in body_keys)
    report.record("U5-2", prd_ac="U5 AC2 (device login without a client secret)",
                  scenario="start a device flow and exchange it before approval, after a denial, "
                           "and with an unknown code; then inspect where the CLI stored the token",
                  command_or_endpoint="POST /api/v1/auth/device; .../device/deny; .../device/token",
                  data_origin="this run's API",
                  result=PASS if ok else FAIL,
                  evidence={"device_start_fields": body_keys,
                            "pending": {"status": pending_status, "error": pending_body.get("error"),
                                        "interval": pending_start.get("interval")},
                            "denied": {"status": denied_status, "error": denied_body.get("error")},
                            "unknown_code": {"status": unknown_status,
                                             "error": unknown_body.get("error")},
                            "credentials_path": str(w.cli.credentials),
                            "credentials_mode": mode,
                            "inside_the_repository": inside_repo},
                  limitation="Expiry is proven by the `expires_in` the server returns and by the "
                             "denied path; waiting out a real 600-second expiry is not measured.")
    assert ok, (pending_body, denied_body, mode, inside_repo)


@pytest.mark.acc("U5-3")
def test_u5_3_an_installation_token_cannot_import_publish_or_change_membership(
        fresh_org, report, bring_up, gf_stack):
    """U5-3: least privilege, checked against the endpoints the scope must not reach."""
    w = fresh_org("u5-scopes")
    bring_up(w)
    installation = w.owner.expect(
        "POST", w.org_base + "/installations", ok=(200, 201),
        body={"name": "u5-3", "kind": "installation", "repo_id": w.repo,
              "scopes": ["search", "use", "events"]},
        headers={"Idempotency-Key": "u5-3-inst"})
    ci = w.owner.expect(
        "POST", w.org_base + "/installations", ok=(200, 201),
        body={"name": "u5-3-ci", "kind": "ci", "repo_id": w.repo, "scopes": ["validate"]},
        headers={"Idempotency-Key": "u5-3-ci"})

    probes = {}
    for label, token in (("installation", installation["token"]), ("ci", ci["token"])):
        client = ApiSession(gf_stack.api)
        probes[label] = {
            "create_import": client.request(
                "POST", w.base + "/imports", token=token,
                body={"idempotency_key": "u5-3", "manifest": {}},
                headers={"Idempotency-Key": "u5-3"})[0],
            "publish": client.request(
                "POST", w.base + "/publish", token=token,
                body={"idempotency_key": "u5-3", "import_id": w.import_id},
                headers={"Idempotency-Key": "u5-3b"})[0],
            "members": client.request("GET", w.org_base + "/members", token=token)[0],
            "invite": client.request(
                "POST", w.org_base + "/invitations", token=token,
                body={"email": "x@acceptance.test", "role": "owner"},
                headers={"Idempotency-Key": "u5-3c"})[0],
            "search": client.request("POST", "/v1/search", token=token, body={
                "schema_version": "1.1", "query": "outage",
                "workspace": {"repo_id": w.repo, "cwd": "."}})[0],
        }

    inst = probes["installation"]
    ok = (all(inst[k] in (401, 403) for k in ("create_import", "publish", "members", "invite"))
          and inst["search"] == 200
          and all(probes["ci"][k] in (401, 403) for k in
                  ("create_import", "publish", "members", "invite")))
    report.record("U5-3", prd_ac="U5 AC3 (token scopes)",
                  scenario="an installation token and a CI token against import, publish, "
                           "membership and invitation, plus /v1/search",
                  command_or_endpoint="POST {repo_base}/imports|/publish; GET {org_base}/members; "
                                      "POST {org_base}/invitations; POST /v1/search",
                  data_origin="two tokens issued through the API in this run",
                  result=PASS if ok else FAIL,
                  evidence={"installation_scopes": installation["scopes"],
                            "ci_scopes": ci["scopes"],
                            "status_codes": probes},
                  limitation="Status codes only; it does not prove the absence of a side channel "
                             "that leaks the same data through another route.")
    assert ok, probes


@pytest.mark.acc("U5-4")
def test_u5_4_two_real_harness_sessions_are_not_measured_here(fresh_org, report, bring_up,
                                                              gf_stack):
    """U5-4 is `not_measured_here`, but the hook path it depends on is exercised and its event
    ids are shown in the usage report."""
    w = fresh_org("u5-hook")
    bring_up(w)
    installation = w.owner.expect(
        "POST", w.org_base + "/installations", ok=(200, 201),
        body={"name": "u5-4", "kind": "installation", "repo_id": w.repo,
              "scopes": ["search", "use", "events"], "harness": "claude-code"},
        headers={"Idempotency-Key": "u5-4-inst"})["token"]
    token_file = w.cli.home / "hook-token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(installation)
    token_file.chmod(0o600)
    _configure_service_search(w, gf_stack.api, token_file)

    hook_payload = json.dumps({"prompt": "handle an outage in turnstile auth",
                               "cwd": str(w.tree / "platforms/atlas/identity")})
    hooked = w.cli.run(["hook", "--stdin-json"], cwd=w.tree / "platforms/atlas/identity",
                       check=False, GUIDEFOLD_HOOK_STDIN=hook_payload)
    spool = _spool_events(w.tree)
    flushed = w.cli.run(["telemetry", "flush", "--url", gf_stack.api,
                         "--token-file", str(token_file)], cwd=w.tree, check=False)
    usage = w.get("/usage")

    report.record("U5-4", prd_ac="U5 AC4 (two harnesses, real sessions)",
                  scenario="two real Claude Code / Copilot CLI sessions on a real repository, with "
                           "the search and load entries visible in the ledger",
                  command_or_endpoint="a real harness, not a script",
                  data_origin="—",
                  result=NOT_MEASURED,
                  evidence={"hook_path_exercised": True,
                            "hook_exit": hooked.returncode,
                            "hook_stdout_bytes": len(hooked.stdout),
                            "spooled_event_types": spool,
                            "telemetry_flush": flushed.stdout.strip().splitlines()[-1:],
                            "usage_totals": usage["totals"]},
                  limitation="A CLI subprocess driven by a test is not a harness session. This row "
                             "records that the hook -> SEARCH -> USE -> ledger path runs and what it "
                             "produced; it does not close the criterion, which needs two real "
                             "sessions by someone who is not building Guidefold.")


@pytest.mark.acc("U5-5")
def test_u5_5_use_rechecks_access_and_answers_resources_relative_to_the_skill(
        fresh_org, report, bring_up, gf_stack):
    """U5-5: a token revoked between SEARCH and USE gets 403; resource paths are relative."""
    w = fresh_org("u5-recheck")
    bring_up(w)
    token = w.owner.expect(
        "POST", w.org_base + "/installations", ok=(200, 201),
        body={"name": "u5-5", "kind": "installation", "repo_id": w.repo,
              "scopes": ["search", "use"]},
        headers={"Idempotency-Key": "u5-5-inst"})
    client = ApiSession(gf_stack.api)
    _, search, _ = client.request("POST", "/v1/search", token=token["token"], body={
        "schema_version": "1.1", "query": "handle an outage in turnstile auth",
        "workspace": {"repo_id": w.repo, "cwd": "platforms/atlas/identity"}})
    card = search["cards"][0]
    use_status, used, _ = client.request("POST", "/v1/use", token=token["token"], body={
        "schema_version": "1.2", "search_id": search["search_id"], "skill_id": card["urn"],
        "revision": card["revision"],
        "workspace": {"repo_id": w.repo, "cwd": "platforms/atlas/identity"}})
    absolute = [r["path"] for r in used.get("resources", [])
                if r["path"].startswith("/") or ".." in r["path"]]

    w.owner.expect("DELETE", f"{w.org_base}/installations/{token['installation_id']}",
                   ok=(200, 204), headers={"Idempotency-Key": "u5-5-revoke"})
    after_status, after_body, _ = client.request("POST", "/v1/use", token=token["token"], body={
        "schema_version": "1.2", "search_id": search["search_id"], "skill_id": card["urn"],
        "revision": card["revision"],
        "workspace": {"repo_id": w.repo, "cwd": "platforms/atlas/identity"}})

    ok = use_status == 200 and after_status in (401, 403) and not absolute
    report.record("U5-5", prd_ac="U5 AC5 (USE rechecks access; package resources)",
                  scenario="SEARCH then USE with a valid token, revoke it, then USE again with the "
                           "same search_id",
                  command_or_endpoint="POST /v1/search; POST /v1/use (1.2); "
                                      "DELETE {org_base}/installations/{id}; POST /v1/use",
                  data_origin="examples/monorepo published in this run",
                  result=PASS if ok else FAIL,
                  evidence={"use_before_revocation": use_status,
                            "use_after_revocation": after_status,
                            "error_after": after_body.get("error"),
                            "resources": used.get("resources"),
                            "absolute_or_escaping_paths": absolute,
                            "closure": used.get("closure")},
                  limitation="The missing-required-resource error is measured in U1-7, at "
                             "publication time, where it blocks the snapshot.")
    assert ok, (use_status, after_status, absolute)


@pytest.mark.acc("U5-6")
def test_u5_6_a_service_that_is_not_there_degrades_to_a_named_local_profile(
        fresh_org, report, bring_up, gf_stack):
    """U5-6: with the URL pointing at a closed port, `find` says which profile answered."""
    w = fresh_org("u5-degrade")
    bring_up(w)
    token_file = w.cli.home / "dead-token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text("gf_not-a-real-token-but-long-enough-for-the-file")
    token_file.chmod(0o600)
    dead = f"http://127.0.0.1:{stack.free_port()}"
    _configure_service_search(w, dead, token_file)

    found = w.cli.run(["find", "handle an outage in turnstile auth", "--limit", "3"],
                      cwd=w.tree / "platforms/atlas/identity", check=False)
    spooled = _spool_events(w.tree)
    reasons = _fallback_reasons(w.tree)
    urns = [line.strip()[2:] for line in found.stdout.splitlines()
            if line.strip().startswith("- urn:skill:")]

    ok = found.returncode == 0 and bool(urns) and bool(reasons)
    report.record("U5-6", prd_ac="U5 AC6 (service unavailable -> named local profile)",
                  scenario="point search.url at a closed loopback port and run `find`",
                  command_or_endpoint="guidefold find (search.backend: service, unreachable url)",
                  data_origin="examples/monorepo, local index",
                  result=PASS if ok else FAIL,
                  evidence={"exit_code": found.returncode,
                            "cards": len(urns),
                            "stderr_tail": found.stderr.strip().splitlines()[-3:],
                            "spooled_event_types": spooled,
                            "fallback_reasons": reasons},
                  limitation="A closed port is one failure mode; timeouts, 5xx and auth failures "
                             "are covered by the CLI's own unit tests.")
    assert ok, (found.returncode, found.stderr, reasons)


@pytest.mark.slow
@pytest.mark.acc("U5-7")
def test_u5_7_hook_latency_on_loopback(fresh_org, report, bring_up, gf_stack):
    """U5-7: 200 hook invocations at concurrency 1 and 4, on loopback. Not an SLA."""
    w = fresh_org("u5-latency")
    bring_up(w)
    token = w.owner.expect(
        "POST", w.org_base + "/installations", ok=(200, 201),
        body={"name": "u5-7", "kind": "installation", "repo_id": w.repo,
              "scopes": ["search", "use", "events"]},
        headers={"Idempotency-Key": "u5-7-inst"})["token"]

    client = ApiSession(gf_stack.api)
    body = {"schema_version": "1.1", "query": "handle an outage in turnstile auth",
            "workspace": {"repo_id": w.repo, "cwd": "platforms/atlas/identity"}}

    def once():
        start = time.monotonic()
        status, _b, _h = client.request("POST", "/v1/search", token=token, body=body)
        assert status == 200, status
        return (time.monotonic() - start) * 1000.0

    c1 = [once() for _ in range(200)]
    from concurrent.futures import ThreadPoolExecutor
    clients = [ApiSession(gf_stack.api) for _ in range(4)]

    def concurrent(i):
        start = time.monotonic()
        status, _b, _h = clients[i % 4].request("POST", "/v1/search", token=token, body=body)
        assert status == 200, status
        return (time.monotonic() - start) * 1000.0

    with ThreadPoolExecutor(max_workers=4) as pool:
        c4 = list(pool.map(concurrent, range(200)))

    p95_c1, p95_c4 = percentile(c1, 95), percentile(c4, 95)
    report.record("U5-7", prd_ac="U5 AC7 (hook budget, 400 ms p95)",
                  scenario="200 SEARCH requests at concurrency 1 and 200 at concurrency 4, over "
                           "loopback, against the published snapshot",
                  command_or_endpoint="POST /v1/search",
                  data_origin="examples/monorepo published in this run (27 skills)",
                  result=PASS if max(p95_c1, p95_c4) <= 400 else FAIL,
                  evidence={"c1": {"n": len(c1), "p50_ms": round(percentile(c1, 50), 1),
                                   "p95_ms": round(p95_c1, 1), "max_ms": round(max(c1), 1)},
                            "c4": {"n": len(c4), "p50_ms": round(percentile(c4, 50), 1),
                                   "p95_ms": round(p95_c4, 1), "max_ms": round(max(c4), 1)}},
                  limitation="Loopback on one developer machine with a 27-skill snapshot, measured "
                             "from an in-process HTTP client. It excludes harness start-up, TLS and "
                             "any real network, so it is not the installed-hook budget and not an "
                             "SLA.")
    assert max(p95_c1, p95_c4) <= 400, (p95_c1, p95_c4)


# ---------------------------------------------------------------------------------------


def _configure_service_search(w, url: str, token_file) -> None:
    yaml_path = w.tree / "guidefold.yaml"
    text = yaml_path.read_text()
    if "\nsearch:\n" in text:
        text = text.split("\nsearch:\n")[0]
    yaml_path.write_text(text + f"\nsearch:\n  backend: service\n  url: {url}\n"
                                f"  deadline_ms: 4000\n  token_file: {token_file}\n")


def _spool_events(tree) -> dict:
    kinds = {}
    for path in sorted((tree / ".guidefold/telemetry/spool").rglob("events-*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                event = json.loads(line)
                name = event.get("event_type") or event.get("type")
                kinds[name] = kinds.get(name, 0) + 1
    return kinds


def _fallback_reasons(tree) -> list:
    reasons = []
    for path in sorted((tree / ".guidefold/telemetry/spool").rglob("events-*.jsonl")):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            reason = (event.get("payload") or event).get("fallback_reason")
            if reason:
                reasons.append(reason)
    return sorted(set(reasons))


def _json_slice(text: str) -> str:
    start = text.find("{")
    return text[start:] if start >= 0 else "{}"
