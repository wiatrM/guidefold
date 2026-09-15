"""ADR-0050: `guidefold.yaml` is an optional override. Without it the scope map is inferred
from the tree's skill directories and CODEOWNERS, and every command works.

Two fixtures, both built in tmp dirs (no second committed fixture):

  * `no_yaml_meridian` — a copy of `examples/monorepo` with `guidefold.yaml` removed and a
    CODEOWNERS written in. Meridian is the realistic shape: several teams, nested directories.
    Its SKILL.md files were authored against the DECLARED node names (`atlas`, `[forge/geo]`
    description prefixes, `metadata.owner` per node), so `validate` reports errors on it — that
    is expected and is exactly what the file buys you: `guidefold.yaml` is how an organisation
    names its nodes something other than its folders. The inferred name follows the directory
    (`platforms.atlas`).
  * `inferred_repo` — a small tree written by the test, authored against the inferred names, so
    `validate` can be asserted green.
"""
import json
import os
import shutil
import subprocess

import pytest

CODEOWNERS = (
    "* @meridian/platform-engineering\n"
    "platforms/atlas/ @meridian/atlas-platform\n"
    "platforms/atlas/identity/ @meridian/identity-platform\n"
    "infra/relay/ @meridian/relay-infra\n"
)


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)


@pytest.fixture
def no_yaml_meridian(tmp_path, fixture_root):
    dest = tmp_path / "meridian-no-yaml"
    shutil.copytree(fixture_root, dest)
    shutil.rmtree(dest / ".guidefold", ignore_errors=True)
    (dest / "guidefold.yaml").unlink()
    (dest / ".github").mkdir(exist_ok=True)
    (dest / ".github" / "CODEOWNERS").write_text(CODEOWNERS, encoding="utf-8")
    return dest


@pytest.fixture
def inferred_repo(tmp_path):
    """A tree authored against the names inference produces, so `validate` has nothing to say."""
    root = tmp_path / "acme-platform"
    for directory, name, owner in (
        ("services/billing", "invoice-runs", "billing-team"),
        ("services/billing/tax", "tax-rules", "tax-team"),
        ("infra", "terraform-layout", "platform"),
    ):
        skill = root / directory / ".agents" / "skills" / name
        skill.mkdir(parents=True)
        node = directory.replace("/", ".")
        skill.joinpath("SKILL.md").write_text(
            "---\n"
            f"name: {name}\n"
            f'description: "[{directory}] What {name} covers in enough words to be a real '
            f'description. Use when working on {name} in this repository."\n'
            "metadata:\n"
            f"  scope: {node}\n"
            f"  owner: {owner}\n"
            "  status: active\n"
            "---\n"
            f"# {name}\n\nBody.\n", encoding="utf-8")
    (root / "CODEOWNERS").write_text(
        "* @acme/platform\n"
        "services/billing/ @acme/billing-team\n"
        "services/billing/tax/ @acme/tax-team\n"
        "infra/ @acme/platform\n", encoding="utf-8")
    return root


# --- the inference itself --------------------------------------------------------------------

def test_nodes_follow_the_directories_that_hold_skill_directories(gf, no_yaml_meridian):
    cfg = gf.load_map(no_yaml_meridian)

    assert cfg["_source"] == "inferred"
    # Every node's paths glob is its own directory, and the intermediate directories exist so
    # ancestors() never names a node the map does not hold.
    assert cfg["nodes"]["platforms.atlas.identity.turnstile"]["paths"] == \
        ["platforms/atlas/identity/turnstile/**"]
    for ancestor in gf.ancestors("platforms.atlas.identity.turnstile"):
        assert ancestor in cfg["nodes"], ancestor
    assert cfg["nodes"]["_root"]["paths"] == ["**"]
    # Meridian declares `atlas` for the same directory: naming nodes differently is what the
    # file is for (ADR-0050 §3).
    assert "atlas" not in cfg["nodes"]


def test_owners_come_from_codeowners_with_the_last_matching_rule_winning(gf, no_yaml_meridian):
    cfg = gf.load_map(no_yaml_meridian)

    assert cfg["nodes"]["_root"]["owner"] == "platform-engineering"
    assert cfg["nodes"]["platforms.atlas"]["owner"] == "atlas-platform"
    assert cfg["nodes"]["platforms.atlas.identity"]["owner"] == "identity-platform"
    # A deeper directory with no rule of its own inherits the last rule that matched it.
    assert cfg["nodes"]["platforms.atlas.identity.turnstile"]["owner"] == "identity-platform"
    # A whole-repo `*` rule matches every path, so a directory with no rule of its own still
    # reads as the repository's owner — CODEOWNERS' own semantics, not a guess by guidefold.
    assert cfg["nodes"]["libs.auth-sdk"]["owner"] == "platform-engineering"


def test_no_codeowners_at_all_is_unknown_not_an_error(gf, no_yaml_meridian):
    (no_yaml_meridian / ".github" / "CODEOWNERS").unlink()
    cfg = gf.load_map(no_yaml_meridian)
    assert {spec["owner"] for spec in cfg["nodes"].values()} == {"unknown"}


def test_the_publisher_falls_back_through_credentials_remote_and_directory(gf, tmp_path,
                                                                          inferred_repo):
    cfg = gf.load_map(inferred_repo)
    assert (cfg["publisher"], cfg["publisher_source"]) == ("acme-platform", "directory")

    _git(inferred_repo, "init", "-q", "-b", "main")
    _git(inferred_repo, "remote", "add", "origin", "git@github.com:acme-corp/platform.git")
    cfg = gf.load_map(inferred_repo)
    assert (cfg["publisher"], cfg["publisher_source"]) == ("acme-corp", "git_remote")

    # A caller that already knows the answer (report --base, build_tree.py) wins over both.
    cfg = gf.load_map(inferred_repo, "Explicit Corp")
    assert (cfg["publisher"], cfg["publisher_source"]) == ("explicit-corp", "caller")


def test_a_declared_file_still_wins_and_says_so(gf, fixture_root):
    cfg = gf.load_map(fixture_root)
    assert cfg["_source"] == "guidefold_yaml"
    assert cfg["publisher"] == "meridian"
    assert "atlas" in cfg["nodes"] and "platforms.atlas" not in cfg["nodes"]


def test_inference_is_deterministic(gf, no_yaml_meridian):
    first = gf.load_map(no_yaml_meridian)
    second = gf.load_map(no_yaml_meridian)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# --- the commands ----------------------------------------------------------------------------

def test_where_resolves_the_inferred_node_at_a_nested_cwd(run_cli, no_yaml_meridian):
    nested = no_yaml_meridian / "platforms" / "atlas" / "identity" / "turnstile"
    env = {**os.environ, "GUIDEFOLD_ROOT": str(no_yaml_meridian),
           "GUIDEFOLD_CACHE": str(no_yaml_meridian / ".cache")}
    result = run_cli(["where"], cwd=nested, env=env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["node"] == "platforms.atlas.identity.turnstile"
    assert payload["owner"] == "identity-platform"


def test_index_builds_and_the_hook_resolves_from_nodes_json(run_cli, no_yaml_meridian, tmp_path):
    """The hook never reads guidefold.yaml or PyYAML (E1.5). It resolves cwd -> node from the
    nodes.json inside the artifact `index` built — which is where an inferred map reaches it."""
    env = {**os.environ, "GUIDEFOLD_CACHE": str(tmp_path / ".cache-hook")}
    built = run_cli(["index"], cwd=no_yaml_meridian, env=env)
    assert built.returncode == 0, built.stderr

    nested = no_yaml_meridian / "platforms" / "atlas" / "identity" / "turnstile"
    result = run_cli(["hook"], cwd=no_yaml_meridian, env=env,
                     input=json.dumps({"cwd": str(nested)}))
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "[guidefold] scope=platforms.atlas.identity.turnstile owner=identity-platform "
        "chain=platforms.atlas.identity.turnstile→platforms.atlas.identity→platforms.atlas"
        "→platforms→_root\n")


def test_doctor_reports_the_inferred_map_and_never_fails_for_absence(run_cli, no_yaml_meridian,
                                                                     tmp_path):
    env = {**os.environ, "GUIDEFOLD_CACHE": str(tmp_path / ".cache-doctor")}
    result = run_cli(["doctor", "--json"], cwd=no_yaml_meridian, env=env)
    payload = json.loads(result.stdout)
    by_name = {c["name"]: c for c in payload["checks"]}

    assert by_name["guidefold-yaml"]["status"] == "ok"
    assert "no guidefold.yaml" in by_name["guidefold-yaml"]["detail"]
    assert "CODEOWNERS" in by_name["guidefold-yaml"]["detail"]
    assert "only if this map is wrong" in by_name["guidefold-yaml"]["fix"]
    assert by_name["guidefold-yaml-nodes"]["status"] == "ok"
    assert by_name["guidefold-yaml-globs"]["status"] == "ok"
    # A repository that configured nothing has published nothing: local backend, no GCP project
    # to fail over.
    assert by_name["registry-backend"]["status"] == "ok"


def test_validate_passes_on_a_tree_authored_against_the_inferred_names(run_cli, inferred_repo,
                                                                      tmp_path):
    env = {**os.environ, "GUIDEFOLD_ROOT": str(inferred_repo),
           "GUIDEFOLD_CACHE": str(tmp_path / ".cache-validate")}
    result = run_cli(["validate"], cwd=inferred_repo, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 errors" in result.stdout


def test_materialize_writes_a_card_per_inferred_node(run_cli, inferred_repo, tmp_path):
    env = {**os.environ, "GUIDEFOLD_ROOT": str(inferred_repo),
           "GUIDEFOLD_CACHE": str(tmp_path / ".cache-materialize")}
    result = run_cli(["materialize"], cwd=inferred_repo, env=env)
    assert result.returncode == 0, result.stderr
    card = (inferred_repo / "services" / "billing" / "AGENTS.md").read_text()
    assert "# Scope: services.billing" in card
    assert "Owner: billing-team" in card
    assert (inferred_repo / ".github" / "instructions" / "services.billing.instructions.md").is_file()


def test_report_base_works_when_neither_side_has_the_file(run_cli, inferred_repo, tmp_path):
    _git(inferred_repo, "init", "-q", "-b", "main")
    _git(inferred_repo, "config", "user.email", "t@e.st")
    _git(inferred_repo, "config", "user.name", "T")
    _git(inferred_repo, "add", "-A")
    _git(inferred_repo, "commit", "-q", "-m", "base")
    base = _git(inferred_repo, "rev-parse", "HEAD").stdout.strip()
    shutil.rmtree(inferred_repo / "infra" / ".agents" / "skills" / "terraform-layout")

    jpath = tmp_path / "report.json"
    env = {**os.environ, "GUIDEFOLD_ROOT": str(inferred_repo),
           "GUIDEFOLD_CACHE": str(tmp_path / ".cache-report")}
    result = run_cli(["report", "--base", base, "--json", str(jpath)], cwd=inferred_repo, env=env)
    assert result.returncode == 0, result.stdout + result.stderr

    payload = json.loads(jpath.read_text())
    # The base was inferred at the ref, with the same publisher, so the URNs line up and only
    # the deleted skill shows as removed.
    assert payload["changes"]["skills"]["removed"] == \
        ["urn:skill:acme-platform:infra:terraform-layout"]
    assert payload["changes"]["skills"]["added"] == []


def test_scan_still_reports_the_missing_file_as_an_advisory_suggestion(run_cli, inferred_repo,
                                                                      tmp_path):
    """`scan` already tolerated the absent file through `_tolerant_config`, and U1 AC2's advisory
    suggestions are unchanged by ADR-0050 — they are what a console scope-map proposal is built
    from, and they stay advisory: nothing in the manifest feeds back into node_for()/urn()."""
    env = {**os.environ, "GUIDEFOLD_CACHE": str(tmp_path / ".cache-scan")}
    result = run_cli(["scan", "--dry-run", "--json"], cwd=inferred_repo, env=env)
    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout)
    assert [f["path"] for f in manifest["files"] if f["kind"] == "skill"]
    suggestions = {entry["path"]: entry for entry in manifest["suggestions"]}
    assert suggestions, "every skill should carry a suggestion while the file is absent"
    for entry in suggestions.values():
        assert "guidefold_yaml_missing" in entry["reasons"]
    assert suggestions["services/billing/.agents/skills/invoice-runs/SKILL.md"]["suggested_owner"] \
        == "billing-team"


# --- what must NOT change --------------------------------------------------------------------

def test_a_repository_with_the_file_produces_byte_identical_cards_and_nodes(gf, fixture_root):
    """No ranking change (ADR-0050 §3): the declared path is untouched by this feature."""
    cfg = gf.load_map(fixture_root)
    index = gf.Index.build(fixture_root, cfg)
    assert index.nodes == {n: s for n, s in cfg["nodes"].items()}
    assert len(index.cards) == 26


def test_loading_an_inferred_map_needs_no_pyyaml(run_cli, inferred_repo, tmp_path, monkeypatch):
    """Existence is tested before PyYAML is imported, so a repository with no file needs nothing
    installed. Proven by running `where` in an interpreter where importing yaml raises."""
    blocker = tmp_path / "no-yaml-path"
    blocker.mkdir()
    (blocker / "yaml.py").write_text("raise ImportError('PyYAML is not installed here')\n")
    env = {**os.environ, "GUIDEFOLD_ROOT": str(inferred_repo),
           "GUIDEFOLD_CACHE": str(tmp_path / ".cache-noyaml"),
           "PYTHONPATH": str(blocker)}
    result = run_cli(["where"], cwd=inferred_repo, env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["node"] == "_root"
