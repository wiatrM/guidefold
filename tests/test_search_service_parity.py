from pathlib import Path


PARITY = Path(__file__).parents[1] / "tools" / "search_service" / "parity.py"


def test_parity_publish_does_not_restart_completed_migration_dependency():
    source = PARITY.read_text(encoding="utf-8")
    assert "'--no-deps'" in source
    assert "compose('--profile','tools','run','--rm','--no-deps','publish'" in source
