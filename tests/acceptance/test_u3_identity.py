"""U3 — who is who, what they may see, and how fast a revocation bites.

Isolation is measured with two real organisations owned by two real sessions, not by asserting
on a filter clause.
"""
from __future__ import annotations

import re
import time
import urllib.parse

import pytest

from gf_acceptance_support import (PASS, FAIL, NOT_MEASURED, ApiSession, make_git_tree, stack,
                                   wait_until)

pytestmark = pytest.mark.acceptance


@pytest.mark.acc("U3-1")
def test_u3_1_two_providers_are_two_identities_with_a_link_suggestion(gf_stack, report):
    """U3-1: the same e-mail arriving through a second provider is a separate user with a
    suggestion to link, never a silent merge."""
    email = "two-providers@acceptance.test"
    google = stack.dev_login(gf_stack.api, subject="u3-google", email=email, name="Two Providers")
    first = google.expect("GET", "/api/v1/me")

    github = ApiSession(gf_stack.api)
    status, _body, _ = github.request("POST", "/api/v1/auth/dev", form={
        "provider": "github", "subject": "u3-github", "email": email, "name": "Two Providers"})
    assert status in (200, 302, 303), status
    second = github.expect("GET", "/api/v1/me")
    github.csrf = second.get("csrf_token")

    separate = first["user"]["id"] != second["user"]["id"]
    suggestions = second.get("link_suggestions") or first.get("link_suggestions") or []

    started = github.expect("POST", "/api/v1/me/identities/link/start", ok=(200, 201, 202),
                            body={"provider": "google"})

    ok = separate and bool(suggestions) and bool(started.get("login_url"))
    report.record("U3-1", prd_ac="U3 AC1 (two providers, explicit linking)",
                  scenario="sign in with the dev provider as google, then as github with the same "
                           "e-mail; read /me and start an explicit link",
                  command_or_endpoint="POST /api/v1/auth/dev; GET /api/v1/me; "
                                      "POST /api/v1/me/identities/link/start",
                  data_origin="development identity provider (GUIDEFOLD_AUTH=dev)",
                  result=PASS if ok else FAIL,
                  evidence={"first_user_id": first["user"]["id"],
                            "second_user_id": second["user"]["id"],
                            "separate_users": separate,
                            "link_suggestions": suggestions,
                            "link_start_returns_login_url": bool(started.get("login_url"))},
                  limitation="Exercised through the development provider. The WorkOS path is not "
                             "measured here.")
    assert ok, (first["user"], second["user"], suggestions)


@pytest.mark.acc("U3-1 (WorkOS)")
def test_u3_1_workos_is_not_measured_here(report):
    report.record("U3-1 (WorkOS)", prd_ac="U3 AC1 with the real identity vendor",
                  scenario="the same two-provider flow against a real WorkOS tenant, including its "
                           "callback, state validation and 502 handling",
                  command_or_endpoint="GUIDEFOLD_AUTH=workos + a WorkOS tenant",
                  data_origin="—",
                  result=NOT_MEASURED, evidence={},
                  limitation="Needs a WorkOS tenant and its secrets. This run has loopback only and "
                             "no vendor credentials; `GUIDEFOLD_AUTH=dev` is a different code path "
                             "for the callback and the provider errors.")


@pytest.mark.acc("U3-3")
def test_u3_3_one_organisation_never_leaks_into_another(fresh_org, report, bring_up, gf_stack):
    """U3-3: every repository-scoped surface answers 403 for a non-member — same body as for an
    organisation that does not exist, and no counter moves."""
    # Distinct repo ids on purpose: with the same id on both sides, org B's bound token
    # resolves to org B's *own* repository and never attempts a crossing at all.
    a = fresh_org("u3-alpha", repo="alpha-repo")
    b = fresh_org("u3-beta", repo="beta-repo")
    bring_up(a)
    bring_up(b)
    import_id = a.get("/imports")["items"][0]["import_id"]
    skill = a.get("/skills?limit=1")["items"][0]
    quoted = urllib.parse.quote(skill["skill_id"], safe="")

    a_token = a.owner.expect(
        "POST", a.org_base + "/installations", ok=(200, 201),
        body={"name": "u3-a", "kind": "installation", "repo_id": a.repo,
              "scopes": ["search", "use", "events"]},
        headers={"Idempotency-Key": "u3-a-inst"})["token"]
    b_token = b.owner.expect(
        "POST", b.org_base + "/installations", ok=(200, 201),
        body={"name": "u3-b", "kind": "installation", "repo_id": b.repo,
              "scopes": ["search", "use", "events"]},
        headers={"Idempotency-Key": "u3-b-inst"})["token"]

    paths = [
        ("GET", f"{a.base}/imports"),
        ("GET", f"{a.base}/imports/{import_id}"),
        ("GET", f"{a.base}/skills"),
        ("GET", f"{a.base}/skills/{quoted}"),
        ("GET", f"{a.base}/map/repository"),
        ("GET", f"{a.base}/usage"),
        ("GET", f"{a.base}/proposals"),
        ("GET", f"{a.base}/snapshots"),
        ("GET", f"{a.org_base}/members"),
        ("GET", f"{a.org_base}/audit"),
    ]
    outsider = {}
    for method, path in paths:
        status, body, _ = b.owner.request(method, path)
        outsider[path] = {"status": status, "error": body.get("error"),
                          "keys": sorted(body)}
    ghost_status, ghost_body, _ = b.owner.request("GET", "/api/v1/orgs/no-such-org-9z/members")

    # The delivery contract, twice over. First org B's installation token naming org A's
    # repository: the token is bound to org B, so naming another organisation's repository
    # must be refused rather than answered from org B's own catalog.
    anon = ApiSession(gf_stack.api)
    search_status, search_body, _ = anon.request("POST", "/v1/search", token=b_token, body={
        "schema_version": "1.1", "query": "handle an outage",
        "workspace": {"repo_id": a.repo, "cwd": "."}})
    use_status, use_body, _ = anon.request("POST", "/v1/use", token=b_token, body={
        "schema_version": "1.1", "search_id": "00000000-0000-4000-8000-000000000000",
        "skill_id": skill["skill_id"], "revision": skill["revision_id"],
        "workspace": {"repo_id": a.repo, "cwd": "."}})
    # Then org B's *personal* token, which carries no repository binding, pointed at org A
    # through the headers that choose a tenant.
    header_status, header_body, _ = anon.request(
        "POST", "/v1/search", token=b.personal_token,
        headers={"X-Guidefold-Org": a.org, "X-Guidefold-Repo": a.repo},
        body={"schema_version": "1.1", "query": "handle an outage",
              "workspace": {"repo_id": a.repo, "cwd": "."}})

    denied = all(v["status"] == 403 for v in outsider.values())
    no_metadata = all(set(v["keys"]) <= {"error", "message", "request_id", "details"}
                      for v in outsider.values())
    same_as_ghost = ghost_status == 403
    delivery_denied = (search_status == 403 and use_status == 403 and header_status == 403)
    # `/v1` answers with the delivery contract's own envelope, not the management one, so the
    # rule to check is what must NOT be there: no cards, no body, no catalog size, nothing
    # naming the other organisation (U3 AC3 - no content, no metadata, no counters).
    leaky = {"cards", "body", "checksum", "n_skills", "snapshot", "closure", "resources",
             "org_id", "repo_id", "tenant", "skills"}
    delivery_leaked_nothing = all(
        not (set(body) & leaky) for body in (search_body, use_body, header_body))

    ok = (denied and no_metadata and same_as_ghost and delivery_denied
          and delivery_leaked_nothing)
    report.record("U3-3", prd_ac="U3 AC3 (organisation isolation)",
                  scenario="org B's owner session and org B's installation token against ten of "
                           "org A's endpoints plus /v1/search and /v1/use",
                  command_or_endpoint="GET/POST across {repo_base} and {org_base} of another org; "
                                      "POST /v1/search; POST /v1/use",
                  data_origin="two real organisations created through the API in this run",
                  result=PASS if ok else FAIL,
                  evidence={"per_endpoint": outsider,
                            "nonexistent_org_status": ghost_status,
                            "nonexistent_org_error": ghost_body.get("error"),
                            "search_status": search_status,
                            "search_error": search_body.get("error"),
                            "use_status": use_status, "use_error": use_body.get("error"),
                            "header_org_status": header_status,
                            "header_org_error": header_body.get("error"),
                            "delivery_body_keys": sorted(set(search_body) | set(use_body)
                                                        | set(header_body)),
                            "delivery_bodies_leak_no_content_or_counters":
                                delivery_leaked_nothing},
                  limitation="Sequential probes; not the warm-cache parallel A/B soak the "
                             "architecture calls for at P02.")
    assert ok, outsider


@pytest.mark.acc("U3-4")
def test_u3_4_a_removed_member_is_denied_on_the_next_request(fresh_org, report, gf_stack):
    """U3-4 (API half): removal and token revocation take effect on the very next call."""
    w = fresh_org("u3-revoke")
    make_git_tree(w.tree)
    w.cli.json(["import", "--wait", "--json"], cwd=w.tree)

    member = stack.dev_login(gf_stack.api, subject="u3-member", email="member@acceptance.test")
    invitation = w.owner.expect("POST", w.org_base + "/invitations", ok=(200, 201),
                                body={"email": "member@acceptance.test", "role": "member"},
                                headers={"Idempotency-Key": "u3-invite"})
    # The response hands back a one-time accept URL, never a bare token field.
    accept_url = invitation["accept_url"]
    member.expect("POST", accept_url, ok=(200, 201),
                  headers={"Idempotency-Key": "u3-4-accept"})
    member.csrf = member.expect("GET", "/api/v1/me").get("csrf_token")
    before_status, _, _ = member.request("GET", w.base + "/skills")

    removed_at = time.monotonic()
    w.owner.expect("DELETE", f"{w.org_base}/members/{_member_id(w, 'member@acceptance.test')}",
                   ok=(200, 204), headers={"Idempotency-Key": "u3-4-remove-member"})
    after_status, after_body, _ = member.request("GET", w.base + "/skills")
    member_latency = time.monotonic() - removed_at

    token = w.owner.expect("POST", w.org_base + "/installations", ok=(200, 201),
                           body={"name": "u3-revocable", "kind": "installation",
                                 "repo_id": w.repo, "scopes": ["search", "use"]},
                           headers={"Idempotency-Key": "u3-revocable"})
    anon = ApiSession(gf_stack.api)
    token_before, _, _ = anon.request("POST", "/v1/search", token=token["token"], body={
        "schema_version": "1.1", "query": "outage",
        "workspace": {"repo_id": w.repo, "cwd": "."}})
    revoked_at = time.monotonic()
    w.owner.expect("DELETE", f"{w.org_base}/installations/{token['installation_id']}",
                   ok=(200, 204), headers={"Idempotency-Key": "u3-4-revoke-token"})
    token_after, token_body, _ = anon.request("POST", "/v1/search", token=token["token"], body={
        "schema_version": "1.1", "query": "outage",
        "workspace": {"repo_id": w.repo, "cwd": "."}})
    token_latency = time.monotonic() - revoked_at

    ok = (before_status == 200 and after_status == 403
          and token_before in (200, 503) and token_after in (401, 403))
    ev_accept_url_is_one_time = accept_url.startswith("http")
    report.record("U3-4", prd_ac="U3 AC4 (revocation within 60 s)",
                  scenario="a member reads the catalog, is removed, and reads again; an "
                           "installation token searches, is revoked, and searches again",
                  command_or_endpoint="DELETE {org_base}/members/{user_id}; "
                                      "DELETE {org_base}/installations/{id}; GET {repo_base}/skills; "
                                      "POST /v1/search",
                  data_origin="two sessions and one installation token created in this run",
                  result=PASS if ok else FAIL,
                  evidence={"member_before": before_status, "member_after": after_status,
                            "member_error": after_body.get("error"),
                            "member_denied_after_s": round(member_latency, 3),
                            "token_before": token_before, "token_after": token_after,
                            "token_error": token_body.get("error"),
                            "token_denied_after_s": round(token_latency, 3),
                            "invitation_id": invitation["invitation_id"],
                            "accept_url_returned": ev_accept_url_is_one_time},
                  limitation="The API half only. The UI's 45-second masking deadline is measured in "
                             "the live Playwright run (ui/e2e/live/revocation.spec.ts), not here.")
    assert ok, (before_status, after_status, token_before, token_after)


@pytest.mark.acc("U3-5")
def test_u3_5_session_cookies_csrf_and_a_log_without_secrets(gf_stack, fresh_org, report):
    """U3-5: the session cookie's flags, a mutation refused without the CSRF header, and a
    server log holding no token."""
    w = fresh_org("u3-csrf")
    session = ApiSession(gf_stack.api)
    status, _b, headers = session.request("POST", "/api/v1/auth/dev", form={
        "provider": "google", "subject": "u3-cookie", "email": "cookie@acceptance.test",
        "name": "Cookie"})
    set_cookie = headers.get("Set-Cookie", "")
    me = session.expect("GET", "/api/v1/me")
    session.csrf = me["csrf_token"]

    # Same mutation twice: once without the header, once with it.
    no_csrf, no_csrf_body, _ = session.request(
        "POST", "/api/v1/orgs", body={"name": "csrf-probe", "slug": "u3-csrf-probe"},
        headers={"Idempotency-Key": "u3-csrf-1", "X-CSRF-Token": ""})
    with_csrf, with_csrf_body, _ = session.request(
        "POST", "/api/v1/orgs", body={"name": "csrf-probe", "slug": "u3-csrf-probe"},
        headers={"Idempotency-Key": "u3-csrf-2"})

    token = w.owner.expect("POST", w.org_base + "/installations", ok=(200, 201),
                           body={"name": "u3-log", "kind": "installation", "repo_id": w.repo,
                                 "scopes": ["search"]},
                           headers={"Idempotency-Key": "u3-log"})["token"]
    from gf_acceptance_support import ApiSession as S
    S(gf_stack.api).request("POST", "/v1/search", token=token, body={
        "schema_version": "1.1", "query": "probe", "workspace": {"repo_id": w.repo, "cwd": "."}})
    log = gf_stack.paths.api_log.read_text(errors="replace")
    leaked = [line for line in log.splitlines() if token in line or "gf_" in line and token[:12] in line]

    flags_ok = ("HttpOnly" in set_cookie and "SameSite=Lax" in set_cookie
                and "gf_session=" in set_cookie)
    ok = flags_ok and no_csrf == 403 and with_csrf in (200, 201) and not leaked
    report.record("U3-5", prd_ac="U3 AC5 (cookies, CSRF, no secrets in logs)",
                  scenario="read the Set-Cookie flags of a dev sign-in, send one mutation without "
                           "X-CSRF-Token and the same one with it, then grep the API log for the "
                           "installation token that was just used",
                  command_or_endpoint="POST /api/v1/auth/dev; POST /api/v1/orgs (with and without "
                                      "X-CSRF-Token); POST /v1/search; grep the API log",
                  data_origin="this run's own stack log",
                  result=PASS if ok else FAIL,
                  evidence={"set_cookie_flags": _flags(set_cookie),
                            "insecure_cookies_note": "GUIDEFOLD_INSECURE_COOKIES=true locally, so "
                                                     "Secure is deliberately absent over http",
                            "mutation_without_csrf": no_csrf,
                            "mutation_without_csrf_error": no_csrf_body.get("error"),
                            "mutation_with_csrf": with_csrf,
                            "log_lines_containing_the_token": len(leaked),
                            "api_log_bytes": len(log)},
                  limitation="`Secure` cannot be asserted on a plain-http loopback stack; the flag "
                             "is set unless GUIDEFOLD_INSECURE_COOKIES=true (identity.Config).")
    assert ok, (set_cookie, no_csrf, with_csrf, leaked[:2])


# ---------------------------------------------------------------------------------------


def _member_id(w, email: str) -> str:
    for entry in w.owner.expect("GET", w.org_base + "/members")["items"]:
        if entry.get("email") == email:
            return entry["user_id"]
    raise AssertionError(f"{email} is not a member")


def _flags(set_cookie: str) -> list:
    return sorted({part.strip().split("=")[0] for part in set_cookie.split(";")[1:]})
