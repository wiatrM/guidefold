"""Static shape checks for the `guidefold-search worker` image (E-worker deployability).

The API image (`services/search/Dockerfile`) is intentionally Python-free
(`.agents/skills/module-boundaries-go/SKILL.md`): the request-serving process must never
be able to reach a Python interpreter, even through a compromised or malformed import.
`import.parse` needs one anyway -- it shells out to the repository's own trusted
`tools/worker/build_tree.py`, which imports the CLI's own parser plus a small, fully
traced set of `tools/serve_spike`/`tools/search_service` modules -- so that work moves
to a *separate* image, `services/search/Dockerfile.worker`, built from the exact same Go
build stage (same module, same commit) so both images run the identical binary.

These are static, offline checks: no `docker build`/`docker compose config` is possible
in this environment (no daemon, no sudo), so this file greps and parses the Dockerfile,
`compose.yaml` and `.dockerignore` text directly rather than exercising a real build.
`tests/test_k8s_release.py` separately covers the Helm chart's `worker.*` values/template.
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "services/search/Dockerfile"
DOCKERFILE_WORKER = REPO_ROOT / "services/search/Dockerfile.worker"
COMPOSE = REPO_ROOT / "compose.yaml"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"

DIGEST_RE = re.compile(r"@sha256:[0-9a-f]{64}$")

# The complete, transitively-checked set of paths the worker image may copy from the
# repository (see the module docstring and Dockerfile.worker's own comments for the
# import trace). Nothing else -- and in particular nothing under private/, experiment/,
# .guidefold/ or research/ -- may appear in a COPY instruction.
ALLOWED_COPY_SOURCES = {
    "services/search/go.mod",
    "services/search/go.sum",
    "services/search/",
    "skills/guidefold/scripts/guidefold",
    "tools/worker/build_tree.py",
    "tools/serve_spike/repository.py",
    "tools/serve_spike/context.py",
    "tools/serve_spike/server.py",
    "tools/search_service/index.py",
}

FORBIDDEN_PREFIXES = ("private/", "experiment/", ".guidefold/", "research/")


def _lines():
    text = DOCKERFILE_WORKER.read_text()
    # Strip comment lines and blank lines; keep instruction lines only.
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _from_stages():
    return [line for line in _lines() if line.startswith("FROM ")]


def _copy_instructions():
    return [line for line in _lines() if line.startswith("COPY ")]


def _copy_sources(instruction):
    """All source arguments of a COPY instruction, excluding a leading --from=... flag
    and the trailing destination path."""
    parts = instruction.split()
    assert parts[0] == "COPY"
    parts = parts[1:]
    parts = [p for p in parts if not p.startswith("--")]
    # Last token is the destination; everything before it is a source.
    return parts[:-1]


def test_dockerfile_worker_exists():
    assert DOCKERFILE_WORKER.is_file(), "services/search/Dockerfile.worker is missing"


def _build_stage_instructions(lines):
    """The instruction lines (comments/blanks already stripped by `_lines()`-style
    callers) from `FROM golang:... AS build` up to, but excluding, the next `FROM`."""
    start = next(i for i, l in enumerate(lines) if l.startswith("FROM golang:") and "AS build" in l)
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("FROM "))
    return lines[start:end]


def _instruction_lines(path):
    text = path.read_text()
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_worker_reuses_the_exact_api_build_stage():
    """Identical build-stage *instructions* in both Dockerfiles (comments aside) is how
    two separate images end up running the same Go binary for the same commit --
    Docker has no cross-file stage include, so textual identity is the only way to
    guarantee this without a build."""
    api_stage = _build_stage_instructions(_instruction_lines(DOCKERFILE))
    worker_stage = _build_stage_instructions(_instruction_lines(DOCKERFILE_WORKER))
    assert api_stage == worker_stage, (
        "Dockerfile.worker's build stage must be instruction-identical to Dockerfile's "
        "(same base image, same COPY/RUN commands) so both images build the same "
        "binary from the same commit"
    )
    joined = "\n".join(api_stage)
    assert "CGO_ENABLED=0" in joined and "-trimpath" in joined


def test_runtime_base_image_is_pinned_by_digest():
    stages = _from_stages()
    assert len(stages) == 2, f"expected exactly two build stages, found {stages}"
    runtime_from = stages[1]
    assert "python:3.12-slim" in runtime_from, runtime_from
    image_ref = runtime_from.split()[1]
    assert DIGEST_RE.search(image_ref), (
        f"runtime base image must be pinned by @sha256:<64 hex>, got: {image_ref!r}"
    )
    assert "AS " not in runtime_from or "build" not in runtime_from.split("AS ")[1]


def test_copies_exactly_the_allowlisted_paths():
    seen = set()
    for instruction in _copy_instructions():
        if "--from=build" in instruction:
            # The compiled binary itself, not a repository path.
            continue
        for source in _copy_sources(instruction):
            seen.add(source)
            for forbidden in FORBIDDEN_PREFIXES:
                assert not source.startswith(forbidden), (
                    f"Dockerfile.worker must never COPY from {forbidden!r}, "
                    f"found source {source!r}"
                )
    assert seen == ALLOWED_COPY_SOURCES, (
        f"unexpected COPY sources: extra={seen - ALLOWED_COPY_SOURCES}, "
        f"missing={ALLOWED_COPY_SOURCES - seen}"
    )


def test_runs_as_non_root_user():
    user_lines = [line for line in _lines() if line.startswith("USER ")]
    assert user_lines, "Dockerfile.worker must set a USER instruction"
    user = user_lines[-1].split(None, 1)[1].strip()
    assert user not in ("root", "root:root", "0", "0:0"), (
        f"Dockerfile.worker must not run as root, got USER {user!r}"
    )


def test_entrypoint_runs_the_worker_subcommand_with_no_shell():
    text = DOCKERFILE_WORKER.read_text()
    match = re.search(r'^ENTRYPOINT\s+(\[.*\])\s*$', text, re.MULTILINE)
    assert match, "Dockerfile.worker must set an exec-form ENTRYPOINT"
    entrypoint = match.group(1)
    # Exec form (a JSON array), not shell form -- no `sh -c` wrapping needed or wanted.
    assert entrypoint.startswith("["), "ENTRYPOINT must use exec form, not shell form"
    assert "guidefold-search" in entrypoint and "worker" in entrypoint


def test_python_dependency_is_pinned():
    text = DOCKERFILE_WORKER.read_text()
    match = re.search(r'PyYAML==([0-9][0-9.]*[0-9])', text)
    assert match, "PyYAML must be installed at a pinned version, not left floating"


def test_worker_dir_env_points_away_from_tmp():
    text = DOCKERFILE_WORKER.read_text()
    match = re.search(r"GUIDEFOLD_WORKER_DIR=(\S+)", text)
    assert match, "Dockerfile.worker must set GUIDEFOLD_WORKER_DIR"
    value = match.group(1).rstrip("\\").strip()
    assert value != "/tmp" and not value.startswith("/tmp/"), (
        "the worker must materialise import trees outside of /tmp"
    )


def test_api_dockerfile_still_has_no_python():
    """The other side of the split: the API image must stay exactly as Python-free as
    it was before the worker image existed."""
    text = DOCKERFILE.read_text()
    assert "python" not in text.lower(), (
        "services/search/Dockerfile must not gain a Python runtime; "
        "that belongs only in Dockerfile.worker"
    )
    assert "distroless" in text


def _compose():
    return yaml.safe_load(COMPOSE.read_text())


def test_compose_has_a_worker_service_with_no_ports():
    compose = _compose()
    services = compose["services"]
    assert "worker" in services, "compose.yaml must define a `worker` service"
    worker = services["worker"]
    assert "ports" not in worker, (
        "the worker only leases jobs from gfm.jobs; it must never publish a port"
    )
    assert worker["build"]["dockerfile"] == "services/search/Dockerfile.worker"


def test_compose_worker_is_locked_down_like_the_api_service():
    compose = _compose()
    api = compose["services"]["api"]
    worker = compose["services"]["worker"]
    for service, name in ((api, "api"), (worker, "worker")):
        assert service.get("read_only") is True, f"{name} must run read_only"
        assert service.get("cap_drop") == ["ALL"], f"{name} must drop all capabilities"
    # The worker's own scratch directory must be a mounted tmpfs, matching
    # GUIDEFOLD_WORKER_DIR=/work baked into the image -- never a writable image layer.
    assert any(
        entry.startswith("/work:") or entry == "/work"
        for entry in worker.get("tmpfs", [])
    ), "worker must mount /work as tmpfs (GUIDEFOLD_WORKER_DIR)"


def test_compose_worker_runs_with_operator_database_credentials():
    """`publish.build` writes the immutable catalog, which the API role deliberately cannot.

    `schema.grantsSQL` grants `guidefold_api` SELECT on `gf.*` and INSERT only on `gf.events`
    and `gf.search_shadow`, so a worker inheriting the API's role fails every publication with
    `permission denied for table snapshots`. The worker is an operator job in that split, like
    the `migrate` and `publish` services, and must carry the same credentials they do."""
    compose = _compose()
    worker = compose["services"]["worker"]
    api = compose["services"]["api"]
    assert api["environment"]["PGUSER"] == "guidefold_api", (
        "the request-serving API must keep the least-privilege role")
    assert worker["environment"]["PGUSER"] == "postgres", (
        "the worker publishes the catalog and needs the operator role")
    assert worker["environment"]["PG_PASSWORD_FILE"] == "/run/secrets/postgres_password"
    assert "postgres_password" in worker["secrets"]


def test_compose_worker_overrides_policy_source_for_its_own_image_layout():
    """The shared `&environment` anchor points GUIDEFOLD_POLICY_SOURCE at
    /app/policy-source, which only exists in the API image. Without an override here,
    the worker's unconditional startup-time policySHA() read (main.go's `run()`, before
    dispatching to any subcommand) would fail against a path this image never has."""
    compose = _compose()
    worker_env = compose["services"]["worker"]["environment"]
    assert worker_env["GUIDEFOLD_POLICY_SOURCE"] != "/app/policy-source"
    assert "skills/guidefold/scripts/guidefold" in worker_env["GUIDEFOLD_POLICY_SOURCE"]


def test_compose_worker_has_a_generator_default():
    compose = _compose()
    worker_env = compose["services"]["worker"]["environment"]
    assert "GUIDEFOLD_GENERATOR" in worker_env
    assert "none" in worker_env["GUIDEFOLD_GENERATOR"]


def test_dockerignore_still_denies_private_and_research_trees():
    text = DOCKERIGNORE.read_text()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    assert lines[0] == "**", ".dockerignore must start by denying everything"
    for forbidden in ("private", "experiment", ".guidefold", "research"):
        assert f"!{forbidden}/" not in lines and not any(
            l.startswith(f"!{forbidden}/") for l in lines
        ), f"{forbidden}/ must not be re-allowed into any build context"


def _dockerignore_allows(path, allow_patterns):
    """A minimal, sufficient (not general-purpose) match against this repo's actual
    .dockerignore shape: exact-path allow lines, and `!<dir>/**` allow lines that
    un-ignore an entire subtree."""
    if path in allow_patterns:
        return True
    for pattern in allow_patterns:
        if pattern.endswith("/**") and path.startswith(pattern[: -len("**")]):
            return True
    return False


def test_dockerignore_allows_every_path_the_worker_copies():
    text = DOCKERIGNORE.read_text()
    allow_patterns = {
        l.strip()[1:] for l in text.splitlines() if l.strip().startswith("!")
    }
    for source in ALLOWED_COPY_SOURCES:
        assert _dockerignore_allows(source, allow_patterns), (
            f"{source!r} is COPYed by Dockerfile.worker but not un-ignored by any "
            f".dockerignore `!...` line"
        )
