"""Tests for tools/enrich/derive.py (F5 offline enrichment, DENSE-PROGRAM.md §4).

Each test pins one rule from the module docstring down with a tiny, hand-built synthetic skill
(id/name/description/body, optionally existing triggers/negative_triggers/requires) rather than
the real corpus, so a later change to the rules has to argue with a named expectation.
"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("gf_enrich_derive", ROOT / "tools" / "enrich" / "derive.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gf_enrich_derive"] = mod
    spec.loader.exec_module(mod)
    return mod


D = _load()


def skill(id, name=None, description="", body="", **kw):
    s = {"id": id, "name": name or id, "description": description, "body": body}
    s.update(kw)
    return s


# ------------------------------------------------------------------------- section mining: usage
def test_usage_heading_extracts_bullets_as_triggers():
    s = skill(
        "s1", "Skill One", "does a thing",
        "## When to Use This Skill\n\n"
        "- Use when the user asks for a database migration\n"
        "- Use when the user wants connection pooling tuned\n",
    )
    out = D.derive([s])["s1"]
    assert "the user asks for a database migration" in out.triggers
    assert "the user wants connection pooling tuned" in out.triggers
    provs = {p["phrase"]: p for p in out.provenance["triggers"]}
    assert provs["the user asks for a database migration"]["heading"] == "When to Use This Skill"
    assert provs["the user asks for a database migration"]["rule"] == "section_mining"
    assert provs["the user asks for a database migration"]["derived"] is True


def test_exclusion_heading_extracts_bullets_as_negative_triggers():
    s = skill(
        "s1", "Skill One", "does a thing",
        "## Do Not Use This Skill When\n\n"
        "- The task is unrelated to database migrations entirely\n"
        "- The project uses a NoSQL datastore instead\n",
    )
    out = D.derive([s])["s1"]
    assert "The task is unrelated to database migrations entirely" in out.negative_triggers
    assert "The project uses a NoSQL datastore instead" in out.negative_triggers
    prov = out.provenance["negative_triggers"][0]
    assert prov["heading"] == "Do Not Use This Skill When"
    assert prov["rule"] == "section_mining"


def test_bare_anti_patterns_and_triggers_headings_are_not_treated_as_exclusion():
    """EXCLUSION_HEADING_RE deliberately excludes bare "anti-patterns"/"triggers"/"activate" --
    measured on the 2 037-skill real corpus to be dominated by off-topic domain content (code
    anti-patterns, workflow-tool nouns), not genuine "don't use this skill" signal. See the F5
    report for the frequency table that drove this."""
    s = skill(
        "s1", "Skill One", "does a thing",
        "## Anti-Patterns\n\n"
        "- Never use a mutable default argument in Python\n"
        "- Never catch a bare Exception in a hot loop\n",
    )
    out = D.derive([s])["s1"]
    assert out.negative_triggers == []


def test_cue_boilerplate_is_stripped_from_extracted_phrase():
    """A "Use when/for/if ..." bullet under a usage heading should keep only the condition, not
    the boilerplate cue itself."""
    s = skill(
        "s1", "Skill One", "",
        "## When to Use\n\n- Use when the user needs a database migration reviewed\n",
    )
    out = D.derive([s])["s1"]
    assert out.triggers == ["the user needs a database migration reviewed"]


def test_sentence_level_cues_in_unheaded_prose():
    """Real skills fold "use when X"/"do not use for Y" into the description with no markdown
    heading at all (SkillRetBench's full_text shape) -- must still be picked up."""
    s = skill(
        "s1", "Skill One",
        "Handles product search. Use this skill when the user wants price comparisons across "
        "merchants. Do not use for unrelated travel booking requests.",
        "",
    )
    out = D.derive([s])["s1"]
    assert any("price comparisons across merchants" in t for t in out.triggers)
    assert any("unrelated travel booking requests" in t for t in out.negative_triggers)
    trig_prov = [p for p in out.provenance["triggers"] if p["rule"] == "sentence_mining"][0]
    assert trig_prov["heading"] is None


# ------------------------------------------------------------------------- caps & dedupe
def test_triggers_capped_at_12():
    bullets = "\n".join(f"- Use when situation number {i} happens in the codebase" for i in range(20))
    s = skill("s1", "Skill One", "", f"## When to Use\n\n{bullets}\n")
    out = D.derive([s])["s1"]
    assert len(out.triggers) == D.TRIGGERS_CAP == 12


def test_negative_triggers_capped_at_8():
    bullets = "\n".join(f"- The task involves unrelated topic number {i} entirely" for i in range(20))
    s = skill("s1", "Skill One", "", f"## Do Not Use This Skill When\n\n{bullets}\n")
    out = D.derive([s])["s1"]
    assert len(out.negative_triggers) == D.NEGATIVE_TRIGGERS_CAP == 8


def test_duplicate_phrases_by_tokenized_form_are_deduped():
    s = skill(
        "s1", "Skill One", "",
        "## When to Use\n\n"
        "- Use when the USER wants a Database Migration\n"
        "- Use when the user wants a database migration\n"  # same tokenized form, different case
        "- Use when the user wants something totally different\n",
    )
    out = D.derive([s])["s1"]
    assert len(out.triggers) == 2


def test_short_phrase_dropped():
    """A candidate phrase tokenizing to <= 2 tokens is dropped (spec: "drop phrases <= 2 tokens")."""
    s = skill("s1", "Skill One", "", "## When to Use\n\n- Use when needed\n- Use when the user asks for X\n")
    out = D.derive([s])["s1"]
    assert not any(len(D.tokenize(t)) <= 2 for t in out.triggers)
    assert any("the user asks for x" in t.lower() for t in out.triggers)


def test_stopword_only_phrase_dropped():
    s = skill("s1", "Skill One", "", "## When to Use\n\n- Use when it is for this and that\n")
    out = D.derive([s])["s1"]
    assert out.triggers == []


def test_negative_trigger_needs_2_content_tokens_triggers_needs_only_1():
    """negative_triggers hard-filters at query time via unordered token-SET containment (no
    length floor in the router) so a phrase with only one non-stopword token among mostly
    connectives is a real precision hazard -- dropped for negative_triggers (min_content_tokens=2)
    but the identically-shaped trigger (BM25 soft-scoring only, no hard-drop risk) is kept."""
    s_neg = skill("s1", "Skill One", "", "## Do Not Use This Skill When\n\n- For the domain\n")
    out = D.derive([s_neg])["s1"]
    assert out.negative_triggers == []  # only 1 content token ("domain") -- dropped

    s_trig = skill("s2", "Skill Two", "", "## When to Use\n\n- For the domain\n")
    out2 = D.derive([s_trig])["s2"]
    assert out2.triggers == ["For the domain"]  # triggers only need min_content_tokens=1


# ------------------------------------------------------------------------- edge mining
def test_dependency_heading_classifies_mention_as_requires():
    other = skill("other-skill-id", "Other Skill Name", "", "")
    s = skill(
        "s1", "Skill One", "",
        "## Prerequisites\n\nRequires Other Skill Name to be run first.\n",
    )
    out = D.derive([s, other])["s1"]
    assert "other-skill-id" in out.requires
    prov = [p for p in out.provenance["requires"] if p["target"] == "other-skill-id"][0]
    assert prov["rule"] == "edge_mining"
    assert prov["confidence"] == "high"


def test_related_heading_classifies_mention_as_similar():
    other = skill("other-skill-id", "Other Skill Name", "", "")
    s = skill(
        "s1", "Skill One", "",
        "## Related Skills\n\nSee also Other Skill Name for alternatives.\n",
    )
    out = D.derive([s, other])["s1"]
    assert "other-skill-id" in out.similar
    assert "other-skill-id" not in out.requires


def test_dependency_cue_in_unheaded_prose_classifies_as_requires():
    other = skill("other-skill-id", "Other Skill Name", "", "")
    s = skill("s1", "Skill One", "This skill depends on Other Skill Name being installed first.", "")
    out = D.derive([s, other])["s1"]
    assert "other-skill-id" in out.requires


def test_bare_mention_with_no_cue_is_low_confidence_similar():
    other = skill("other-skill-id", "Other Skill Name", "", "")
    s = skill("s1", "Skill One", "", "This works well alongside Other Skill Name in a pipeline.\n")
    out = D.derive([s, other])["s1"]
    assert "other-skill-id" in out.similar
    prov = [p for p in out.provenance["similar"] if p["target"] == "other-skill-id"][0]
    assert prov["confidence"] == "low"
    assert prov["cue"] == "bare_mention"


def test_short_id_never_qualifies_as_a_mention_target():
    """"git"/"test"-style short ids must not be pattern-matched as edges (spec: "avoid git/test-
    style false hits")."""
    short = skill("git", "git", "", "")
    s = skill("s1", "Skill One", "", "Run git status before continuing.\n")
    out = D.derive([s, short])["s1"]
    assert "git" not in out.requires
    assert "git" not in out.similar


def test_self_mention_never_produces_an_edge():
    s = skill(
        "s1", "My Skill Name", "",
        "## Related Skills\n\nSee also My Skill Name for more context.\n",
    )
    out = D.derive([s])["s1"]
    assert out.requires == []
    assert out.similar == []


def test_requires_cycle_is_detected_and_demoted_to_similar():
    a = skill("skill-a", "Skill A Name", "", "## Prerequisites\n\nRequires Skill B Name first.\n")
    b = skill("skill-b", "Skill B Name", "", "## Prerequisites\n\nRequires Skill A Name first.\n")
    out = D.derive([a, b])
    # Processed in sorted(by_id) order -- "skill-a" before "skill-b" -- so skill-a's edge to
    # skill-b is accepted first; skill-b's edge back to skill-a would close a 2-cycle and must be
    # demoted to `similar` instead.
    assert "skill-b" in out["skill-a"].requires
    assert "skill-a" not in out["skill-b"].requires
    assert "skill-a" in out["skill-b"].similar
    demoted = [p for p in out["skill-b"].provenance["similar"] if p["target"] == "skill-a"][0]
    assert demoted["cue"] == "cycle_demoted"


# ------------------------------------------------------------------------- existing fields win
def test_existing_triggers_are_kept_verbatim_and_marked_not_derived():
    s = skill(
        "s1", "Skill One", "", "## When to Use\n\n- Use when the user asks for X\n",
        triggers=["a"],  # deliberately below MIN_PHRASE_TOKENS -- existing bypasses that filter
    )
    out = D.derive([s])["s1"]
    assert out.triggers[0] == "a"
    prov = out.provenance["triggers"][0]
    assert prov["rule"] == "existing"
    assert prov["derived"] is False
    # derived items are still appended after the existing one, up to the cap
    assert any("the user asks for x" in t.lower() for t in out.triggers)


def test_existing_requires_is_kept_and_derived_edges_still_added():
    other = skill("other-skill-id", "Other Skill Name", "", "")
    s = skill(
        "s1", "Skill One", "", "## Related Skills\n\nSee also Other Skill Name.\n",
        requires=["some-existing-dep"],
    )
    out = D.derive([s, other])["s1"]
    assert "some-existing-dep" in out.requires
    prov = [p for p in out.provenance["requires"] if p["target"] == "some-existing-dep"][0]
    assert prov["rule"] == "existing" and prov["derived"] is False


def test_existing_negative_trigger_survives_the_boilerplate_guard_no_matter_how_common():
    """Only *derived* negative_trigger phrases are subject to the corpus-wide boilerplate guard;
    an author's own repeated phrase is their choice (rule 3: existing fields win)."""
    skills = [
        skill(f"s{i}", f"Skill Number {i}", "", "", negative_triggers=["not for production use"])
        for i in range(20)
    ]
    out = D.derive(skills)
    for i in range(20):
        assert "not for production use" in out[f"s{i}"].negative_triggers


# ------------------------------------------------------------------------- corpus-wide boilerplate guard
def test_derived_negative_trigger_repeated_across_many_skills_is_dropped_as_boilerplate():
    body = "## Do Not Use This Skill When\n\n- The task needs an entirely different specialist tool\n"
    skills = [skill(f"s{i}", f"Skill Number {i}", "", body) for i in range(20)]
    out = D.derive(skills)
    for i in range(20):
        assert out[f"s{i}"].negative_triggers == []


def test_derived_negative_trigger_shared_by_only_a_few_skills_is_kept():
    body = "## Do Not Use This Skill When\n\n- The task needs an entirely different specialist tool\n"
    skills = [skill(f"s{i}", f"Skill Number {i}", "", body) for i in range(3)]
    out = D.derive(skills)
    for i in range(3):
        assert "The task needs an entirely different specialist tool" in out[f"s{i}"].negative_triggers
