"""The pinned real-data corpora (tools/eval/corpora.py).

Two layers. The manifest itself is always tested — it is committed and CI must catch a malformed
edit. The corpora are tested only where they are on disk: CI has no cache, so those tests skip
with a reason that says exactly how to fetch. A skip here is not a pass; it is "not measured on
this machine", and the report that quotes these corpora must come from a machine where they ran.
"""
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gf_corpora", ROOT / "tools" / "eval" / "corpora.py")
C = importlib.util.module_from_spec(spec)
sys.modules["gf_corpora"] = C
spec.loader.exec_module(C)


# ------------------------------------------------------------------ manifest (always)
def test_manifest_pins_a_revision_and_a_hash_for_every_file():
    m = C.manifest()
    assert set(m["corpora"]) == {"skillret", "skillretbench"}
    for name, c in m["corpora"].items():
        assert len(c["revision"]) == 40, f"{name}: revision must be a full commit sha"
        assert c["license"] == "apache-2.0"
        assert c["files"], f"{name}: no files pinned"
        for rel, v in c["files"].items():
            assert len(v["sha256"]) == 64, f"{name}/{rel}: bad sha256"
            assert v["bytes"] > 0


def test_manifest_row_counts_match_the_papers():
    f = C.manifest()["corpora"]["skillret"]["files"]
    assert f["data/skills/test.jsonl"]["rows"] == 6006       # SkillRet v3 eval pool
    assert f["data/queries/test.jsonl"]["rows"] == 4392      # SkillRet v3 eval queries


def _needs(name):
    problems = C.verify(name)
    if problems:
        pytest.skip(f"{name} not on this machine or not the pinned revision: {problems[0]}")


# ------------------------------------------------------------------ corpora (when present)
def test_skillret_is_the_pinned_revision_byte_for_byte():
    _needs("skillret")
    assert C.verify("skillret") == []


def test_skillret_schema_and_multi_skill_share():
    _needs("skillret")
    d = C.load_skillret()
    assert len(d["skills"]) == 6006 and len(d["queries"]) == 4392
    s, q = d["skills"][0], d["queries"][0]
    assert {"id", "name", "major", "sub", "body"} <= set(s)
    assert {"id", "query", "skill_ids", "k"} <= set(q)
    ks = [x["k"] for x in d["queries"]]
    assert sum(1 for k in ks if k > 1) / len(ks) > 0.5      # 51 % multi-skill: the all_required@4 test bed
    majors = {x["major"] for x in d["skills"]}
    assert len(majors) == 6                                   # two-level taxonomy -> node tree


def test_skillretbench_is_the_pinned_revision_byte_for_byte():
    _needs("skillretbench")
    assert C.verify("skillretbench") == []


def test_skillretbench_schema_maps_onto_our_metadata():
    _needs("skillretbench")
    d = C.load_skillretbench()
    skills = d["corpus"]["skills"]; queries = d["queries"]["queries"]
    assert len(skills) == 501 and len(queries) == 1250
    s = skills[0]
    assert {"skill_id", "trigger_phrases", "anti_triggers", "composable_skills", "category", "full_text"} <= set(s)
    settings = {q["setting"] for q in queries}
    assert settings == {"single_skill", "multi_skill_composition", "distractor", "outdated_redundant", "budget_constrained"}
    assert "gold_skills" in queries[0] and "distractor_skills" in queries[0]
