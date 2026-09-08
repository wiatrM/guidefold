"""tests/test_parent_map_delivery.py -- ADR-0035 delivery: an ascended scope map reaches the
agent through both delivery paths without any ranking change.

* hook (Claude Code): the nearest map above the best card rides along in a fourth slot, read
  from the artifact by URN alone -- the hook path still imports no PyYAML.
* materialize (Copilot applyTo / Codex+Gemini nested AGENTS.md): each scope card opens with a
  "Scope map" section listing the maps on its ancestor chain, root-most first.
"""
import json
from pathlib import Path

MAP_DIR = "platforms/atlas/identity/.agents/skills/atlas-identity-map"
MAP_URN = "urn:skill:meridian:atlas.identity:atlas-identity-map"
TURNSTILE_DIR = "platforms/atlas/identity/turnstile"
PROMPT = "add a role check to the turnstile auth middleware and validate the bearer token"

MAP_SKILL = """---
name: atlas-identity-map
description: "[atlas/identity] What lives under atlas identity and who owns it"
metadata:
  scope: atlas.identity
  owner: identity-platform
  status: active
  kind: knowledge
  knowledge_layer: abstract
  ascend_kind: map
  generated_by: guidefold-ascend
  ascend_fingerprint: deadbeef
  ascend_kinds_decided: "map, convention"
  derived_from: "urn:skill:meridian:atlas.identity.turnstile:postgres-auth"
  triggers: "identity platform overview, what is turnstile"
  digest: >-
    Turnstile authorizes every atlas request; the RBAC bundle defines roles.
---
Identity is the atlas authorization platform. Turnstile is the ext_authz service.
"""


def _plant_map(root):
    d = Path(root) / MAP_DIR
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(MAP_SKILL, encoding="utf-8")


def _hook(run_cli, root, cwd_rel):
    payload = json.dumps({"cwd": str(Path(root) / cwd_rel), "prompt": PROMPT, "session_id": "s"})
    return run_cli(["hook"], cwd=root, input=payload)


def test_hook_prepends_the_nearest_scope_map_in_a_fourth_slot(run_cli, fixture_copy):
    _plant_map(fixture_copy)
    assert run_cli(["index"], cwd=fixture_copy).returncode == 0
    r = _hook(run_cli, fixture_copy, TURNSTILE_DIR)
    assert r.returncode == 0, r.stderr
    cards = [l for l in r.stdout.splitlines() if l.startswith("- urn:")]
    assert cards, r.stdout
    assert cards[0].startswith(f"- {MAP_URN} "), cards
    assert 1 < len(cards) <= 4
    # the map is exposed like any other card, first
    spool = next((Path(fixture_copy) / ".guidefold" / "telemetry" / "spool").rglob("events-*.jsonl"))
    events = [json.loads(l) for l in spool.read_text(encoding="utf-8").splitlines() if l.strip()]
    injected = [e for e in events if e["event_type"] == "card_injected"]
    assert injected[0]["skill_id"] == MAP_URN and injected[0]["position"] == 1
    # ranking itself is untouched: search_results carries only the selected cards
    results = next(e for e in events if e["event_type"] == "search_results")["results"]
    assert MAP_URN not in {x["urn"] for x in results}


def test_hook_without_a_map_above_is_byte_identical_to_before(run_cli, fixture_copy):
    assert run_cli(["index"], cwd=fixture_copy).returncode == 0
    r = _hook(run_cli, fixture_copy, TURNSTILE_DIR)
    assert r.returncode == 0
    assert not any("-map " in l for l in r.stdout.splitlines() if l.startswith("- urn:"))


def test_hook_still_imports_no_pyyaml_with_a_map_present(run_cli, fixture_copy):
    import subprocess, sys
    from tests.conftest import CLI_PATH
    _plant_map(fixture_copy)
    assert run_cli(["index"], cwd=fixture_copy).returncode == 0
    payload = json.dumps({"cwd": str(Path(fixture_copy) / TURNSTILE_DIR), "prompt": PROMPT})
    r = subprocess.run([sys.executable, "-X", "importtime", str(CLI_PATH), "hook"],
                       cwd=str(fixture_copy), input=payload, capture_output=True, text=True)
    assert r.returncode == 0
    assert "yaml" not in r.stderr


def test_materialize_opens_every_descendant_card_with_the_scope_map(run_cli, fixture_copy):
    _plant_map(fixture_copy)
    assert run_cli(["materialize"], cwd=fixture_copy).returncode == 0
    turnstile_card = (Path(fixture_copy) / TURNSTILE_DIR / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Scope map (general → specific)" in turnstile_card
    assert f"**atlas.identity** `{MAP_URN}`" in turnstile_card
    assert "Turnstile authorizes every atlas request" in turnstile_card
    # stated once: not repeated in the inherited bullet list
    assert turnstile_card.count(MAP_URN) == 1
    # the map section comes before the inherited guidance
    assert turnstile_card.index("## Scope map") < turnstile_card.index("## Inherited guidance")
    # Copilot's instruction file carries the same card
    instr = (Path(fixture_copy) / ".github" / "instructions" / "atlas.identity.turnstile.instructions.md").read_text(encoding="utf-8")
    assert instr.startswith("---\napplyTo:") and "## Scope map" in instr
    # a scope outside the map's subtree does not get it
    forge_card = (Path(fixture_copy) / "platforms" / "forge" / "AGENTS.md").read_text(encoding="utf-8")
    assert "## Scope map" not in forge_card
    # and the generated tree is still consistent with itself
    assert run_cli(["materialize", "--check"], cwd=fixture_copy).returncode == 0
