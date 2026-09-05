"""Versioned, bounded harness context. No filesystem reads or learned ranking here."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re

VERSION = "1.1"
IDENTIFIER = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}\Z")
CONTEXT_FIELDS = {"schema_version", "request_id", "session_id", "task_id", "query_source",
                  "harness", "workspace", "intent", "stack", "constraints", "capabilities",
                  "loaded_skills", "budget"}


class ContextError(ValueError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code, self.status = code, status


def obj(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ContextError("invalid_context_fields")
    return value


def string(value, maximum=128, identifier=False):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ContextError("invalid_context_value")
    # JSON permits lone surrogates; reject them before logging/serialization.
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ContextError("invalid_context_value") from None
    if any(ord(c) < 32 for c in value) or (identifier and not IDENTIFIER.fullmatch(value)):
        raise ContextError("invalid_context_value")
    return value


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ContextError("invalid_context_budget")


def strings(value, count=16, maximum=128):
    if not isinstance(value, list) or len(value) > count:
        raise ContextError("invalid_context_list")
    for item in value:
        string(item, maximum)


def relative_path(value):
    string(value, 1024)
    if value == ".":
        return value
    if (value.startswith("/") or "\\" in value or ":" in value
            or any(part in ("", ".", "..") for part in value.split("/"))):
        raise ContextError("invalid_relative_path")
    return value


def validate(payload, endpoint):
    base = ({"query", "node", "profile", "deadline_ms"} if endpoint == "/v1/search"
            else {"skill_id", "revision", "search_id", "deadline_ms"})
    unknown = set(payload) - base - CONTEXT_FIELDS
    if unknown:
        raise ContextError("unknown_request_field")
    new = bool(set(payload) & CONTEXT_FIELDS)
    if not new:
        return False
    if payload.get("schema_version") != VERSION:
        raise ContextError("unsupported_schema_version")
    for key in ("request_id", "session_id", "task_id"):
        if key in payload:
            string(payload[key], identifier=True)
    if "query_source" in payload and payload["query_source"] not in ("user", "agent", "adapter"):
        raise ContextError("invalid_query_source")
    if "harness" in payload:
        for value in obj(payload["harness"], ("name", "version", "adapter_version"), ("name",)).values():
            string(value, identifier=True)
    if "workspace" in payload:
        work = obj(payload["workspace"], ("repo_id", "revision", "cwd", "target_paths"), ("repo_id",))
        string(work["repo_id"], identifier=True)
        if "revision" in work:
            string(work["revision"], identifier=True)
        if "cwd" in work:
            relative_path(work["cwd"])
        paths = work.get("target_paths", [])
        if not isinstance(paths, list) or len(paths) > 32:
            raise ContextError("invalid_target_paths")
        for item in paths:
            obj(item, ("path", "source"), ("path", "source"))
            relative_path(item["path"])
            if item["source"] not in ("user_explicit", "edited", "inferred"):
                raise ContextError("invalid_path_source")
        if "cwd" not in work and not paths:
            raise ContextError("missing_workspace_path")
        if "node" in payload:
            raise ContextError("node_and_workspace_are_exclusive")
    if "intent" in payload:
        intent = obj(payload["intent"], ("action", "goal", "source"), ("action",))
        if intent["action"] not in ("implement", "debug", "review", "test", "migrate", "deploy", "document", "explore"):
            raise ContextError("invalid_intent_action")
        if "goal" in intent:
            string(intent["goal"], 2048)
        if "source" in intent and intent["source"] not in ("user", "agent", "adapter"):
            raise ContextError("invalid_intent_source")
    if "stack" in payload:
        stack = obj(payload["stack"], ("languages", "technologies", "source", "manifest_revision"))
        for key in ("languages", "technologies"):
            if key in stack:
                strings(stack[key])
        if "source" in stack and stack["source"] not in ("manifest", "user", "inferred"):
            raise ContextError("invalid_stack_source")
        if "manifest_revision" in stack:
            string(stack["manifest_revision"], identifier=True)
    for key in ("constraints", "capabilities"):
        if key in payload:
            strings(payload[key])
    if "loaded_skills" in payload:
        loaded = payload["loaded_skills"]
        if not isinstance(loaded, list) or len(loaded) > 32:
            raise ContextError("invalid_loaded_skills")
        for item in loaded:
            obj(item, ("skill_id", "revision", "state"), ("skill_id", "revision", "state"))
            string(item["skill_id"], 512)
            string(item["revision"], 512)
            if item["state"] not in ("hydrated", "exposed", "unknown"):
                raise ContextError("invalid_loaded_skill_state")
    if "budget" in payload:
        budget = obj(payload["budget"], ("max_cards", "max_bytes", "remaining_skill_tokens"))
        for name, low, high in (("max_cards", 0, 4), ("max_bytes", 0, 262144),
                                ("remaining_skill_tokens", 0, 65536)):
            if name in budget:
                integer(budget[name], low, high)
    return True


def map_path(nodes, path):
    if path == ".":
        return "_root"
    matches = [(len(pattern), node) for node, spec in nodes.items()
               for pattern in spec.get("paths", [])
               if fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path + "/", pattern)]
    if not matches:
        raise ContextError("unmapped_workspace_path", 422)
    best = max(length for length, _ in matches)
    winners = {node for length, node in matches if length == best}
    if len(winners) != 1:
        raise ContextError("ambiguous_workspace_path", 422)
    node = next(iter(winners))
    # A catch-all cannot identify an unknown component. Explicit root remains available.
    if node == "_root" and all(pattern in ("*", "**") for pattern in nodes[node].get("paths", [])):
        raise ContextError("unmapped_workspace_path", 422)
    return node


def resolve(engine, payload):
    work = payload.get("workspace")
    warnings = []
    if work:
        identity = getattr(engine, "repository", None)
        if identity is None:
            raise ContextError("repository_context_unavailable", 409)
        if work["repo_id"] != identity["repo_id"]:
            raise ContextError("repository_mismatch", 409)
        if "revision" in work and work["revision"] != identity["revision"]:
            raise ContextError("repository_revision_mismatch", 409)
        if "revision" not in work:
            warnings.append("repository_revision_not_supplied")
        targets = work.get("target_paths", [])
        trusted = [item for item in targets if item["source"] in ("user_explicit", "edited")]
        selected = trusted or targets
        paths = [item["path"] for item in selected] if selected else [work["cwd"]]
        scopes = sorted({map_path(engine.nodes, path) for path in paths})
        source = "target_paths" if selected else "cwd"
        if selected and not trusted:
            warnings.append("scope_from_inferred_paths")
        if len(scopes) > 4:
            raise ContextError("too_many_resolved_scopes", 422)
    else:
        scopes, source = [payload.get("node", "_root")], "node"
        identity = getattr(engine, "repository", None)
    if any(node not in engine.nodes for node in scopes):
        raise ContextError("invalid_node")
    unused = [{"field": key, "reason": "ranking_signal_not_admitted"}
              for key in ("intent", "stack", "constraints", "capabilities") if key in payload]
    return {
        "resolved_scopes": scopes,
        "scope_source": source,
        "scope_owners": {node: engine.nodes[node].get("owner") for node in scopes},
        "repository": identity,
        "scope_map_revision": hashlib.sha256(json.dumps(engine.nodes, sort_keys=True).encode()).hexdigest(),
        "used_fields": (["workspace"] if work else ["node"]),
        "unused_fields": unused,
        "warnings": warnings,
        "scope_is_authorization": False,
    }


def loaded_ids(engine, payload, context):
    loaded = set()
    for item in payload.get("loaded_skills", []):
        sid = item["skill_id"]
        if item["state"] == "hydrated" and engine.revisions.get(sid) == item["revision"]:
            loaded.add(sid)
        else:
            context["warnings"].append("unconfirmed_or_stale_loaded_skill")
    if "loaded_skills" in payload:
        context["used_fields"].append("loaded_skills")
    return loaded


def apply_budget(cards, payload, context):
    # Return a canonical card rendering so the adapter can measure its actual tokenizer.
    rendered = "\n".join(f"- {c['skill_id']}@{c['revision']}: {c['description']}" for c in cards)
    used = len(rendered.encode("utf-8"))
    budget = payload.get("budget", {})
    caps = [budget[key] for key in ("max_bytes", "remaining_skill_tokens") if key in budget]
    fits = not caps or used <= min(caps)
    context["delivery_status"] = "ok" if fits else "cannot_fit"
    context["budget_accounting"] = {
        "candidate_rendered_bytes": used, "returned_rendered_bytes": used if fits else 0,
        "token_accounting": "utf8_byte_proxy_adapter_must_verify" if "remaining_skill_tokens" in budget else "not_requested",
    }
    if "remaining_skill_tokens" in budget:
        context["warnings"].append("verify_final_harness_token_count")
    if budget:
        context["used_fields"].append("budget")
    # Never truncate a selected pack into a seemingly complete dependency closure.
    return (cards, rendered) if fits else ([], "")
