import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "integrations" / "chrome-extension"


def test_extension_has_a_minimal_manifest_and_no_credential_permissions():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["permissions"] == ["activeTab"]
    assert "cookies" not in manifest.get("permissions", [])
    assert "storage" not in manifest.get("permissions", [])


def test_popup_only_derives_a_public_github_repository_and_never_stores_tokens():
    source = (ROOT / "popup.js").read_text(encoding="utf-8")
    assert "github.com" in source
    assert "chrome.tabs.query" in source
    assert "chrome.tabs.create" in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "token" not in source.lower()
