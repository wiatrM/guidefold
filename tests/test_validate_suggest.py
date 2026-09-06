"""F5: `guidefold validate --suggest` (docs/MVP.md "3-6 authoring loop").

Ported extractor logic lives in `skills/guidefold/scripts/guidefold` as the `_SUG_*`/`_sug_*`
block directly above `cmd_validate` — a deliberate, reviewable duplicate of
`tools/enrich/derive.py`'s section/sentence mining for `triggers`/`negative_triggers` only (no
edge mining). These tests check: the default `validate` path is untouched by the new flags: the
suggester is deterministic on a synthetic skill; JSON shape; and the corpus-wide
negative_triggers boilerplate guard.
"""
import json
from types import SimpleNamespace

import pytest

from _helpers import write_guidefold_yaml, write_skill


def _run_validate(gf, root, *, suggest=False, as_json=False):
    a = SimpleNamespace(suggest=suggest, json=as_json)
    with pytest.raises(SystemExit) as exc:
        cfg = gf.load_map(root)
        cfg.setdefault("registry", {})
        gf.cmd_validate(a, root, cfg)
    return exc.value.code


# --------------------------------------------------------------- default output untouched
def test_default_validate_output_unaffected_by_new_flags_on_fixture(gf, fixture_root, capsys):
    """cmd_validate(a=None, ...) — the exact call test_validate.py's `_run_validate` makes —
    must keep behaving identically now that `cmd_validate` reads `a.suggest`/`a.json`."""
    cfg = gf.load_map(fixture_root)
    cfg.setdefault("registry", {})
    with pytest.raises(SystemExit) as exc:
        gf.cmd_validate(None, fixture_root, cfg)
    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "26 skills, 0 errors" in out
    assert "suggest" not in out.lower()


def test_suggest_false_matches_plain_validate_byte_for_byte(gf, fixture_root, capsys):
    code_plain = _run_validate(gf, fixture_root)
    out_plain = capsys.readouterr().out
    code_suggest_false = _run_validate(gf, fixture_root, suggest=False, as_json=False)
    out_suggest_false = capsys.readouterr().out
    assert code_plain == code_suggest_false
    assert out_plain == out_suggest_false


# --------------------------------------------------------------- fixture-level suggest behaviour
def test_suggest_on_fixture_finds_known_missing_negative_triggers(gf, fixture_root, capsys):
    """The Meridian fixture is a known, committed quantity: all 26 skills have `triggers` set;
    14 of 26 lack `negative_triggers` (this fact is exactly why the summary line cannot live on
    the default validate path -- see the docstring on `_sug_print_text`)."""
    code = _run_validate(gf, fixture_root, suggest=True, as_json=True)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["skill_count"] == 26
    assert payload["missing_triggers_count"] == 0
    assert len(payload["suggestions"]) == 14
    for s in payload["suggestions"]:
        assert s["missing_triggers"] is False
        assert s["missing_negative_triggers"] is True


def test_suggest_text_mode_ends_with_summary_line(gf, fixture_root, capsys):
    _run_validate(gf, fixture_root, suggest=True, as_json=False)
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()]
    assert lines[-1] == "0 skills without triggers; run with --suggest"


def test_suggest_is_deterministic_across_runs(gf, fixture_root, capsys):
    _run_validate(gf, fixture_root, suggest=True, as_json=True)
    out1 = capsys.readouterr().out
    _run_validate(gf, fixture_root, suggest=True, as_json=True)
    out2 = capsys.readouterr().out
    assert out1 == out2


# --------------------------------------------------------------- synthetic skill: deterministic mining
_USAGE_EXCLUSION_BODY = (
    "# Widget Skill\n\n"
    "Handles widget lifecycle operations for the acme platform.\n\n"
    "## When to use\n\n"
    "- Use when the user asks to create or rotate a widget credential.\n"
    "- Use when debugging a failing widget provisioning job.\n\n"
    "## Do not use\n\n"
    "- Do not use for gadget provisioning (see gadget-provisioning skill).\n"
    "- Do not use for general platform billing questions.\n"
)


def _write_widget_skill(root, **metadata_overrides):
    metadata = {"scope": "_root", "owner": "platform", "status": "active"}
    metadata.update(metadata_overrides)
    write_skill(
        root / ".agents/skills/widget-ops", name="widget-ops",
        description="[acme] widget-ops. Use when touching widget infrastructure.",
        metadata=metadata, body=_USAGE_EXCLUSION_BODY,
    )


def test_suggest_synthetic_skill_missing_both_fields(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    _write_widget_skill(root)
    code = _run_validate(gf, root, suggest=True, as_json=True)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["missing_triggers_count"] == 1
    [s] = payload["suggestions"]
    assert s["missing_triggers"] is True
    assert s["missing_negative_triggers"] is True
    assert s["found_nothing"] is False

    trig_phrases = [t["phrase"] for t in s["suggested_triggers"]]
    neg_phrases = [t["phrase"] for t in s["suggested_negative_triggers"]]
    # "Use when X or Y" keeps only the first clause -- `_sug_finalize_phrase` deliberately drops
    # anything glued on with " or "/";" beyond the first, same as tools/enrich/derive.py.
    assert any("the user asks to create" in p for p in trig_phrases)
    assert any("debugging a failing widget provisioning job" in p for p in trig_phrases)
    assert any("gadget provisioning" in p for p in neg_phrases)
    assert any("general platform billing questions" in p for p in neg_phrases)

    # Evidence is the original, uncleaned bullet text -- not the cleaned/cue-stripped phrase.
    for t in s["suggested_triggers"]:
        assert t["evidence"].lower().startswith("use when")
    for t in s["suggested_negative_triggers"]:
        assert t["evidence"].lower().startswith("do not use")

    assert s["frontmatter_block"].startswith("metadata:\n")
    assert "triggers:" in s["frontmatter_block"]
    assert "negative_triggers:" in s["frontmatter_block"]


def test_suggest_skips_field_already_present(gf, tmp_path, capsys):
    """Only the missing field is suggested — an existing `triggers` is never overridden or
    re-suggested, matching the brief's 'for every skill lacking triggers or negative_triggers'."""
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    _write_widget_skill(root, triggers="rotate widget credentials manually")
    code = _run_validate(gf, root, suggest=True, as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    [s] = payload["suggestions"]
    assert s["missing_triggers"] is False
    assert s["missing_negative_triggers"] is True
    assert s["suggested_triggers"] == []
    assert s["suggested_negative_triggers"]


def test_suggest_found_nothing_when_no_usage_material(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    write_skill(
        root / ".agents/skills/plain", name="plain",
        description="[acme] plain skill with no usage or exclusion material at all.",
        metadata={"scope": "_root", "owner": "platform", "status": "active"},
        body="# Plain\n\nJust some unrelated prose with no cue words whatsoever here.\n",
    )
    code = _run_validate(gf, root, suggest=True, as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    [s] = payload["suggestions"]
    assert s["found_nothing"] is True
    assert s["suggested_triggers"] == []
    assert s["suggested_negative_triggers"] == []


def test_suggest_no_missing_skills_reports_empty(gf, tmp_path, capsys):
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    _write_widget_skill(
        root,
        triggers="rotate widget credentials manually",
        negative_triggers="gadget provisioning tasks",
    )
    code = _run_validate(gf, root, suggest=True, as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["suggestions"] == []
    assert payload["missing_triggers_count"] == 0


def test_suggest_never_writes_to_skill_md(gf, tmp_path, capsys):
    """Suggestions are printed, never written to files (brief requirement)."""
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    _write_widget_skill(root)
    skill_md = root / ".agents/skills/widget-ops/SKILL.md"
    before = skill_md.read_bytes()
    _run_validate(gf, root, suggest=True, as_json=True)
    capsys.readouterr()
    after = skill_md.read_bytes()
    assert before == after


# --------------------------------------------------------------- corpus-wide boilerplate guard
def test_negative_trigger_boilerplate_guard_drops_frequent_derived_phrase(gf, tmp_path, capsys):
    """Mirrors tools/enrich/derive.py's own corpus-wide guard: a *derived* negative_trigger
    phrase repeated identically across more than max(15, 1% of corpus) skills is dropped
    everywhere it was derived (boilerplate from a shared template, not skill-specific signal);
    a phrase unique to one skill, and a repeated *trigger* phrase (no guard on triggers), survive."""
    root = tmp_path / "acme"
    write_guidefold_yaml(root)
    n = 20  # > NEG_BOILERPLATE_MIN_SKILLS (15)
    for i in range(n):
        body = (
            "# Spam Skill\n\n"
            f"Synthetic skill number {i} for the boilerplate-guard test.\n\n"
            "## When to use\n\n"
            "- Use when running routine automated testing sweeps.\n\n"
            "## Do not use\n\n"
            "- Do not use for internal testing purposes.\n"
            f"- Do not use for skill number {i} maintenance tasks.\n"
        )
        write_skill(
            root / f".agents/skills/spam-{i}", name=f"spam-{i}",
            description=f"[acme] spam-{i}. Use when running spam skill {i}.",
            metadata={"scope": "_root", "owner": "platform", "status": "active"},
            body=body,
        )
    code = _run_validate(gf, root, suggest=True, as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert len(payload["suggestions"]) == n

    for s in payload["suggestions"]:
        neg_phrases = [t["phrase"] for t in s["suggested_negative_triggers"]]
        trig_phrases = [t["phrase"] for t in s["suggested_triggers"]]
        # The shared, >15x-repeated derived negative_trigger is dropped everywhere.
        assert not any("internal testing purposes" in p for p in neg_phrases)
        # A per-skill-unique derived negative_trigger is unaffected.
        idx = int(s["urn"].rsplit("-", 1)[-1])
        assert any(f"skill number {idx} maintenance tasks" in p for p in neg_phrases)
        # Triggers have no boilerplate guard (derive.py only guards negative_triggers) -- the
        # identically-repeated trigger phrase survives in every skill.
        assert any("routine automated testing sweeps" in p for p in trig_phrases)
