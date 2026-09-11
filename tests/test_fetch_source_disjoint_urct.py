import importlib.util
from pathlib import Path


MODULE = Path(__file__).parents[1] / "tools" / "pilot" / "fetch_source_disjoint_urct.py"
spec = importlib.util.spec_from_file_location("fetch_source_disjoint_urct", MODULE)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_repo_name_accepts_only_one_github_owner_and_repository():
    assert module.repo_name("https://github.com/obra/superpowers.git") == "obra__superpowers"


def test_repo_name_rejects_non_github_remote():
    try:
        module.repo_name("https://example.com/obra/superpowers.git")
    except ValueError as exc:
        assert "GitHub" in str(exc)
    else:
        raise AssertionError("non-GitHub remotes must be rejected")
