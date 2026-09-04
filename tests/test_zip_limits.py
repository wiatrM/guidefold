import os
import zipfile

import pytest


def _make_skill_dir(root, name="widget", extra_files=None):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: widget\n---\nbody\n")
    for relpath, content in (extra_files or {}).items():
        p = d / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)
    return d


def test_zip_skill_dir_is_deterministic(gf, tmp_path):
    skill_dir = _make_skill_dir(tmp_path, extra_files={"references/notes.md": "# Notes\n\nSome extra text.\n"})
    zip1, zip2 = tmp_path / "one.zip", tmp_path / "two.zip"

    gf.zip_skill_dir(skill_dir, zip1)
    gf.zip_skill_dir(skill_dir, zip2)

    assert zip1.read_bytes() == zip2.read_bytes()
    with zipfile.ZipFile(zip1) as z:
        assert sorted(z.namelist()) == ["SKILL.md", "references/notes.md"]


def test_zip_skill_dir_excludes_git_and_pycache(gf, tmp_path):
    skill_dir = _make_skill_dir(tmp_path, extra_files={
        "__pycache__/junk.pyc": "not real bytecode",
        ".git/HEAD": "ref: refs/heads/main\n",
    })
    zpath = tmp_path / "clean.zip"
    gf.zip_skill_dir(skill_dir, zpath)
    with zipfile.ZipFile(zpath) as z:
        assert z.namelist() == ["SKILL.md"]


def test_zip_skill_dir_rejects_oversized_file(gf, tmp_path):
    big = b"x" * (gf.ZIP_MAX_FILE + 1)
    skill_dir = _make_skill_dir(tmp_path, extra_files={"references/huge.bin": big})
    with pytest.raises(SystemExit):
        gf.zip_skill_dir(skill_dir, tmp_path / "out.zip")


def test_zip_skill_dir_rejects_oversized_compressed_total(gf, tmp_path):
    # Incompressible content: each file is under the 1 MB per-file cap, but four of them
    # together are comfortably over the 500 KB *compressed archive* cap.
    skill_dir = _make_skill_dir(tmp_path, extra_files={
        f"references/blob-{i}.bin": os.urandom(200 * 1024) for i in range(4)
    })
    with pytest.raises(SystemExit):
        gf.zip_skill_dir(skill_dir, tmp_path / "out.zip")
