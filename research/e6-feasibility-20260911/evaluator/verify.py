import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
if (root / "answer.txt").exists():
    data=(root / "answer.txt").read_bytes(); print("answer_bytes",repr(data), file=sys.stderr)
    assert data == b"GUIDEfold feasibility task one OK.\n"
elif (root / "settings.json").exists():
    data=(root / "settings.json").read_bytes(); print("settings_bytes",repr(data), file=sys.stderr)
    assert json.loads(data) == {"feature_enabled": True, "owner": "platform"}
elif (root / "notes.md").exists():
    text=(root / "notes.md").read_text(); assert "# Notes" in text and "## Release checklist" in text and "- [ ] run tests" in text
elif (root / "config.yaml").exists():
    text=(root / "config.yaml").read_text(); assert "service: api" in text and "healthcheck: /health" in text and "healthcheck: absent" not in text
else: raise AssertionError("unknown workspace fixture")
print("VERIFIER_PASS")
