"""tests/test_scope_card_cap.py -- the 80-line scope card, by construction.

Pilot Core rehearsal 2026-09-15 §5 item 3: with ~80 skills in one node (the ordinary shape
under zero-config, ADR-0050) `materialize` aborted with "scope card for `_root` exceeds 80
lines", so `install` wrote no index artifact and the hook stayed idle until somebody ran
`guidefold index` by hand. The cap is a rule (CONVENTIONS §9); a card that cannot fit must be
shortened, never refused.
"""
import argparse
from types import SimpleNamespace

import pytest

from _helpers import write_guidefold_yaml, write_skill

CAP = 80


def _flat_repo(root, count, digest="Rotate the signing keys without downtime."):
    write_guidefold_yaml(root, publisher="acme", nodes={"_root": {"paths": ["**"],
                                                                 "owner": "platform"}})
    for i in range(count):
        write_skill(root / ".agents" / "skills" / f"skill-{i:03d}",
                    name=f"skill-{i:03d}",
                    description=f"[acme] Procedure number {i} for this repository",
                    metadata={"scope": "_root", "owner": "platform", "status": "active",
                              "digest": f"{digest} ({i})"})
    return root


def _card(gf, root):
    cfg = gf.load_map(root)
    gf.cmd_materialize(argparse.Namespace(check=False), root, cfg)
    return (root / "AGENTS.md").read_text(encoding="utf-8")


def test_a_hundred_skills_in_one_node_still_produce_a_card_within_the_cap(gf, tmp_path, capsys):
    root = _flat_repo(tmp_path / "flat", 100)
    card = _card(gf, root)
    capsys.readouterr()
    lines = card.splitlines()
    assert len(lines) <= CAP, f"{len(lines)} lines:\n{card}"
    # The card still says what it left out, and how to get it.
    assert "more skill" in card, card
    assert "guidefold find" in card, card
    # Digests only, and the ones it kept are real entries.
    assert "urn:skill:acme:_root:skill-" in card


def test_a_long_node_md_never_aborts_the_card_either(gf, tmp_path, capsys):
    """A node with no skills at all can still blow the cap through its NODE.md. The clamp has
    to be the last thing that runs, not an allowance inside the bullet budget."""
    root = tmp_path / "wordy"
    write_guidefold_yaml(root, publisher="acme", nodes={"_root": {"paths": ["**"],
                                                                 "owner": "platform"}})
    (root / ".agents").mkdir(parents=True, exist_ok=True)
    (root / ".agents" / "NODE.md").write_text(
        "\n".join(f"Paragraph {i} about this node." for i in range(200)), encoding="utf-8")
    card = _card(gf, root)
    capsys.readouterr()
    assert len(card.splitlines()) <= CAP, card


def test_materialize_writes_every_generated_file_for_a_flat_repository(gf, tmp_path, capsys):
    root = _flat_repo(tmp_path / "files", 100)
    _card(gf, root)
    capsys.readouterr()
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    assert (root / "GEMINI.md").read_text(encoding="utf-8") == "@AGENTS.md\n"


def test_install_builds_the_index_even_when_materialize_refuses(gf, tmp_path, monkeypatch,
                                                                capsys):
    """`install` ran materialize and index inside one try, so a card that refused to render took
    the index artifact down with it -- and the hook has nothing to read without that artifact."""
    root = _flat_repo(tmp_path / "install", 3)
    calls = []

    def boom(a, r, cfg):
        raise SystemExit("guidefold: scope card for _root exceeds 80 lines")

    monkeypatch.setattr(gf, "cmd_materialize", boom)
    monkeypatch.setattr(gf, "cmd_index", lambda a, r, cfg: calls.append("index"))
    monkeypatch.setattr(gf, "_pivot_root", lambda p=None: root)
    monkeypatch.setenv("GUIDEFOLD_CACHE", str(tmp_path / "cache"))
    args = SimpleNamespace(path=str(root), harness="claude", dry_run=False, api=None, org=None,
                           repo=None, no_materialize=False)
    with pytest.raises(SystemExit) as exc:
        gf.cmd_install(args)
    out = capsys.readouterr().out
    assert exc.value.code == 0, out
    assert calls == ["index"], out
    assert "exceeds 80 lines" in out      # the failure is reported, not hidden
