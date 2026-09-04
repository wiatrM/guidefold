"""Shared builders for throwaway guidefold monorepos used across the test suite.

Not a test module itself (no ``test_`` prefix) so pytest never collects it; test files import
from it directly, e.g. ``from _helpers import build_tmp_repo``.
"""
import json

import yaml


def default_nodes():
    """A tiny but real hierarchy: _root, a team node, and a nested sub-team node with subteams."""
    return {
        "_root": {"paths": ["**"], "owner": "platform"},
        "teamA": {"paths": ["teamA/**"], "owner": "team-a"},
        "teamA.sub": {"paths": ["teamA/sub/**"], "owner": "team-a-sub", "subteams": ["team-a-sub-oncall"]},
    }


def write_guidefold_yaml(root, *, publisher="acme", nodes=None, backend="local"):
    """Write guidefold.yaml at `root` and return the config dict that was written."""
    cfg = {
        "publisher": publisher,
        "registry": {"backend": backend, "project": "test-project", "location": "global"},
        "nodes": nodes if nodes is not None else default_nodes(),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "guidefold.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return cfg


def write_skill(skill_dir, *, name, description, metadata=None, license="Apache-2.0",
                 body="# Title\n\nBody text.\n", raw_metadata=None):
    """Write a SKILL.md under `skill_dir`.

    `metadata` values are written as scalar YAML strings (the registry rule, ADR-0010) via
    json.dumps so no manual escaping is needed. Pass `raw_metadata` (a verbatim YAML block,
    already indented) instead when a test deliberately needs a non-scalar value.
    """
    skill_dir.mkdir(parents=True, exist_ok=True)
    if raw_metadata is not None:
        meta_block = raw_metadata.rstrip("\n")
    else:
        meta_block = "\n".join(f"  {k}: {json.dumps(str(v))}" for k, v in (metadata or {}).items())
    text = (
        "---\n"
        f"name: {name}\n"
        f"description: {json.dumps(description)}\n"
        f"license: {license}\n"
        "metadata:\n"
        f"{meta_block}\n"
        "---\n"
        f"{body}"
    )
    (skill_dir / "SKILL.md").write_text(text)
    return skill_dir


def build_tmp_repo(root):
    """A small, fully-valid monorepo: _root + teamA + teamA.sub, three skills, with a
    requires chain (sub-service -> team-a-basics). For tests that need to mutate a real tree."""
    write_guidefold_yaml(root)
    write_skill(
        root / ".agents" / "skills" / "root-conventions",
        name="root-conventions",
        description="[acme] Root-level conventions for the acme monorepo. Use when unsure which node applies.",
        metadata={"scope": "_root", "owner": "platform", "status": "active", "since": "2026-09-04"},
    )
    write_skill(
        root / "teamA" / ".agents" / "skills" / "team-a-basics",
        name="team-a-basics",
        description="[teamA] How team A builds and ships its service. Use when working under teamA/.",
        metadata={"scope": "teamA", "owner": "team-a", "status": "active", "since": "2026-09-04"},
    )
    write_skill(
        root / "teamA" / "sub" / ".agents" / "skills" / "sub-service",
        name="sub-service",
        description="[teamA/sub] Conventions for team A's sub service. Use when working under teamA/sub/.",
        metadata={
            "scope": "teamA.sub", "owner": "team-a-sub", "status": "active", "since": "2026-09-04",
            "requires": "urn:skill:acme:teamA:team-a-basics",
        },
    )
    return root


def call_kind(cmd):
    """Classify a recorded `gcloud alpha agent-registry ...` argv for the mocked-registry tests."""
    tail = cmd[3:]  # drop "gcloud alpha agent-registry"
    if tail[:2] == ["skills", "describe"]:
        return "describe"
    if tail[:2] == ["skills", "create"]:
        return "create"
    if tail[:3] == ["skills", "revisions", "create"]:
        return "revisions-create"
    if tail[:3] == ["skills", "revisions", "list"]:
        return "revisions-list"
    if tail[:3] == ["skills", "revisions", "delete"]:
        return "revisions-delete"
    if tail[:3] == ["skills", "revisions", "download"]:
        return "revisions-download"
    if tail[:2] == ["skills", "update"]:
        if any(a.startswith("--default-revision=") for a in tail):
            return "update-default-revision"
        if "--target-state=active" in tail:
            return "update-target-active"
        if "--target-state=deprecated" in tail:
            return "update-target-deprecated"
        return "update-metadata"
    if tail[:2] == ["skills", "search"]:
        return "search"
    return "unknown:" + " ".join(tail[:3])
