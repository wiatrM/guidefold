"""derive.py — F5 offline enrichment: derive `triggers`, `negative_triggers`, `requires` and
`similar` for skills that carry only name/description/body (DENSE-PROGRAM.md §4, family F5).

Pure, deterministic, no LLM (an LLM pass is a later dev-budget experiment — see
`LLM_EXTENSION_POINT` below for where it would plug in). Reuses the shared tokenizer
(`tools/bakeoff/tokenizer.py`) for every tokenized comparison, exactly as the shipped BM25F
field-matching and `negative_triggers` hard-filter do at query time — this module never
reimplements tokenization.

Rules, in order of preference (docs/reports/bakeoff/DENSE-PROGRAM.md §4, F5 row):

  1. Section mining — a curated heading/sentence pattern set finds "when to use" and
     "do not use" material and extracts short phrases from it. Usage -> `triggers`,
     exclusion -> `negative_triggers`. Capped (<=12 / <=8) and precision-biased: several
     patterns the design note suggested (bare "triggers"/"activate"/"anti-patterns" headings)
     were measured against the 2 037-skill real corpus and dropped or narrowed because they are
     dominated by off-topic headings (database/workflow "triggers", language "anti-patterns")
     that would otherwise poison `negative_triggers` — see the module docstring of
     `EXCLUSION_HEADING_RE` and the F5 report for the measurement.
  2. Edge mining — mentions of other skills' names/ids in a skill's own text, classified by
     the section heading (when the mention falls inside a dependency- or related-shaped
     section) or by a local sentence-level cue (in unheaded prose), and falling back to a
     low-confidence bare-mention `similar` edge otherwise. Self-edges are never emitted;
     `requires` cycles are detected and demoted to `similar`.
  3. Existing fields win — an input that already carries `requires`/`triggers`/
     `negative_triggers` keeps them verbatim; derived items are only ever appended, each
     marked `derived: true` in provenance (existing ones are marked `derived: false`).

`derive()` takes the whole corpus at once (not skill-by-skill) because edge mining (rule 2)
needs the full candidate set of other skills' names/ids to look for mentions of, and cycle
detection (end of rule 2) needs the full accepted-`requires` graph built so far.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "tools" / "bakeoff") not in sys.path:
    sys.path.insert(0, str(_ROOT / "tools" / "bakeoff"))
from tokenizer import tokenize  # noqa: E402  (shared tokenizer — never reimplemented here)

# --------------------------------------------------------------------------------- caps & data
TRIGGERS_CAP = 12
NEGATIVE_TRIGGERS_CAP = 8
MIN_PHRASE_TOKENS = 3        # drop a candidate phrase with <= 2 tokens (spec: "≤ 2 tokens")
MAX_PHRASE_TOKENS = 8
MIN_NAME_TOKENS = 2          # a "name" mention must tokenize to >= 2 tokens to count (edge mining)
MIN_ID_CHARS = 7             # an "id" mention must be >= 7 raw chars to count (edge mining)
# A derived negative_trigger phrase recurring identically across more than this many skills (or
# this fraction of the corpus, whichever is larger) is boilerplate, not skill-specific signal —
# see the corpus-wide guard in `derive()`.
NEG_BOILERPLATE_MIN_SKILLS = 15
NEG_BOILERPLATE_FRACTION = 0.01

STOPWORDS = frozenset("""
a an the this that these those is are was were be been being to of in on for with and or but
if when not use using used it its your you we our can will shall should would may might do does
did at by as from into onto over under about above below than then so such no nor also more most
some any all each every other another same own just only very via per up down out off again once
here there where why how what which who whom i me my mine myself
""".split())

LLM_EXTENSION_POINT = None
"""Deliberately unused. A later dev-budget experiment (DENSE-PROGRAM.md §4, F5 dev budget item
"whether an LLM pass is allowed") would slot in here as an additional, opt-in rule run *after*
section/edge mining and *before* rule 3's existing-fields merge — e.g. `derive(skills, llm=fn)`
calling `fn(skill, current_enrichment) -> Enrichment` to propose extra low-confidence items, still
subject to the same caps and cycle checks. Nothing in this PR calls an LLM; this constant exists
only to mark the seam."""


@dataclass
class Enrichment:
    triggers: list = field(default_factory=list)
    negative_triggers: list = field(default_factory=list)
    requires: list = field(default_factory=list)
    similar: list = field(default_factory=list)
    provenance: dict = field(default_factory=lambda: {
        "triggers": [], "negative_triggers": [], "requires": [], "similar": [],
    })

    def to_dict(self) -> dict:
        return {
            "triggers": list(self.triggers),
            "negative_triggers": list(self.negative_triggers),
            "requires": list(self.requires),
            "similar": list(self.similar),
            "provenance": {k: list(v) for k, v in self.provenance.items()},
        }


# --------------------------------------------------------------------------- heading patterns
# Matched against a *normalized* heading (markdown stripped, leading "N." numbering stripped,
# lowercased by the regex's re.I flag). `search`, not `fullmatch` — real headings carry suffixes
# ("When to Use This Skill", "Do Not Use This Skill When ..."). Anchored at `^` so a heading that
# merely *mentions* "use" or "requires" deep inside a longer, unrelated title does not match.
USAGE_HEADING_RE = re.compile(
    r"^(when\s+to\s+use|use\s+this\s+skill\b|use\s+cases?\b|when\s+to\s+activate|"
    r"trigger\s+(phrases?|conditions?)\b|how\s+to\s+(use|activate)\s+this\s+skill)",
    re.I,
)

# "anti-?patterns" and bare "triggers"/"activate" were in the spec's suggested pattern set but are
# measurably dangerous on the 2 037-skill real corpus: headings like "Anti-Patterns Specific to
# Rust" (code-style anti-patterns, one per language, ~15 occurrences) and "N8N Webhook Trigger" /
# "Trigger.dev Integration" (workflow-tool nouns, dozens of occurrences) vastly outnumber genuine
# "don't use this skill" headings that merely say "anti-patterns" or "triggers". Since
# `negative_triggers` is hard-filtering at query time (ADR/CONVENTIONS.md §4a), this rule only
# matches headings that are unambiguously about *not using the skill itself* — see the F5 report
# for the measured heading-frequency table that drove this narrowing.
EXCLUSION_HEADING_RE = re.compile(
    r"^(do\s*not\s*use|don.t\s*use|when\s+not\s+to\s+(use|activate)|out\s+of\s+scope|"
    r"not\s+for\b|avoid\s+this\s+skill|avoid\s+(when|if))",
    re.I,
)

EDGE_DEPENDENCY_HEADING_RE = re.compile(
    r"^(prerequisites?\b|dependenc(y|ies)\b|depends\s+on\b|requires\b|built\s+on\b|"
    r"first\s+run\b|after\s+(installing|running)\b)",
    re.I,
)

EDGE_RELATED_HEADING_RE = re.compile(
    r"^(related(\s+skills?)?\b|see\s+also\b|alternatives?\b|instead\s+of\b|similar(\s+skills?)?\b|"
    r"skills\s+to\s+invoke\b)",
    re.I,
)

# Sentence-level cues, used (a) inside unheaded prose to find inline "use when X" / "do not use for
# Y" sentences (real skills often fold these into the description rather than a heading — measured
# on SkillRetBench, see the F5 report), and (b) to classify a bare skill-name mention found in
# unheaded prose during edge mining.
USAGE_SENTENCE_RE = re.compile(r"\buse\s+(?:this\s+skill\s+|it\s+)?(when|for|if)\b", re.I)
EXCLUSION_SENTENCE_RE = re.compile(
    r"\b(do\s*not\s*use|don.t\s*use|not\s+for|avoid\s+(when|if)|out\s+of\s+scope)\b", re.I
)
DEPENDENCY_CUE_RE = re.compile(
    r"\b(requires?|depends?\s+on|dependency|prerequisites?|built\s+on|first\s+run|"
    r"after\s+(installing|running))\b",
    re.I,
)
RELATED_CUE_RE = re.compile(r"\b(related|see\s+also|alternatives?|instead\s+of|similar)\b", re.I)

_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
_BULLET_LINE_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_CODE_RE = re.compile(r"`([^`]*)`")
_MD_EMPHASIS_RE = re.compile(r"[*_~>#]{1,3}")
_PAREN_RE = re.compile(r"\([^)]*\)")
_LEADING_NUMBERING_RE = re.compile(r"^\d+[.)]\s*")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


# ------------------------------------------------------------------------------ text utilities
def _clean_markdown(text: str) -> str:
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _MD_CODE_RE.sub(r"\1", text)
    text = _MD_EMPHASIS_RE.sub("", text)
    text = _BULLET_LINE_RE.sub(r"\1", text)
    return text.strip()


def _normalize_heading(heading: str) -> str:
    h = _clean_markdown(heading or "")
    h = _LEADING_NUMBERING_RE.sub("", h)
    return h.strip().rstrip(":").strip()


def _split_sentences(text: str) -> list:
    text = _clean_markdown(text or "")
    return [p.strip() for p in _SENTENCE_SPLIT_RE.split(text) if p.strip()]


def _split_sections(body: str):
    """[(heading_or_None, [content_line, ...]), ...] — index 0 always has heading None (the
    content, if any, before the first markdown heading)."""
    sections = []
    cur_heading = None
    cur_lines = []
    for line in (body or "").splitlines():
        m = _HEADING_LINE_RE.match(line.strip())
        if m:
            sections.append((cur_heading, cur_lines))
            cur_heading = m.group(2).strip()
            cur_lines = []
        else:
            cur_lines.append(line)
    sections.append((cur_heading, cur_lines))
    return sections


def _sections_with_description(body: str, description: str):
    sections = _split_sections(body)
    lead = [description] if description else []
    sections[0] = (sections[0][0], lead + sections[0][1])
    return sections


def _extract_items(content: str) -> list:
    """Bullet items if the section has bullets, else sentence-split paragraph text."""
    lines = [l for l in content.splitlines() if l.strip()]
    bullets = []
    for l in lines:
        m = _BULLET_LINE_RE.match(l)
        if m:
            bullets.append(_clean_markdown(m.group(1)))
    if bullets:
        return bullets
    return _split_sentences(content)


def _cue_remainder(text: str, cue_re: "re.Pattern") -> str:
    """Text after the *last* word of the cue match to the end of the sentence — "Use when X" ->
    "X"; "Do NOT use for Y (Z)" -> "Y (Z)" (the parenthetical is stripped later, in
    `_finalize_phrase`, since it usually names an alternative skill — edge-mining territory, not
    trigger-phrase territory)."""
    m = cue_re.search(text)
    if not m:
        return ""
    return text[m.end():].strip(" \t-:—")


def _finalize_phrase(raw: str, seen_tokenforms: set, min_content_tokens: int = 1) -> "str | None":
    """Clean, cap, dedupe-by-tokenized-form. Returns None if the phrase should be dropped.

    `min_content_tokens` (non-stopword tokens required) defaults to 1 — merely "not
    stopword-only" — for `triggers`, which only ever feed BM25F soft scoring. `negative_triggers`
    callers pass 2: the router's hard filter (`Router.policy_filter`, guidefold:~1131) matches a
    negative trigger by *unordered token-SET containment* (`set(ttoks) <= qtoks`), not phrase or
    substring match — order and adjacency don't matter, and there is no length floor in the
    router itself. A phrase with only one non-stopword token plus common connectives (e.g. "for
    the domain") is therefore a real hazard: it hard-drops any query that happens to contain that
    one content word alongside ubiquitous words like "for"/"the", regardless of context. Requiring
    2 independent content tokens makes an accidental full-set match far less likely. See the F5
    report for the measured boilerplate phrases (e.g. "You need a different domain", 221x) this
    catches."""
    raw = _PAREN_RE.sub("", raw or "")
    raw = raw.strip(" \t.,:;!-—")
    if not raw:
        return None
    # Drop a second clause glued on with "or"/";" beyond the first — keep the phrase list short
    # and one-idea-per-item rather than long run-on bullets.
    raw = re.split(r"\s+or\s+|;", raw, maxsplit=1)[0].strip()
    toks = tokenize(raw)
    if len(toks) <= MIN_PHRASE_TOKENS - 1:
        return None
    if sum(1 for t in toks if t not in STOPWORDS) < min_content_tokens:
        return None
    if len(toks) > MAX_PHRASE_TOKENS:
        toks = toks[:MAX_PHRASE_TOKENS]
        raw = " ".join(toks)
        if len(toks) <= MIN_PHRASE_TOKENS - 1:
            return None
        if sum(1 for t in toks if t not in STOPWORDS) < min_content_tokens:
            return None
    key = tuple(toks)
    if key in seen_tokenforms:
        return None
    seen_tokenforms.add(key)
    return raw


# --------------------------------------------------------------------------- edge-mining setup
def _build_candidates(skills: list) -> dict:
    """length -> {token_tuple: [skill_id, ...]} for every skill whose name (>= 2 tokens) or id
    (>= 7 raw chars) can serve as a whole-phrase mention target. A short id like "git" or "test"
    never qualifies via the id rule alone (spec: "avoid git/test-style false hits")."""
    candidates: dict = {}
    for s in skills:
        sid = str(s["id"])
        name_toks = tuple(tokenize(s.get("name") or ""))
        if len(name_toks) >= MIN_NAME_TOKENS:
            candidates.setdefault(len(name_toks), {}).setdefault(name_toks, []).append(sid)
        if len(sid) >= MIN_ID_CHARS:
            id_toks = tuple(tokenize(sid))
            if id_toks:
                candidates.setdefault(len(id_toks), {}).setdefault(id_toks, []).append(sid)
    return candidates


def _find_mentions(tokens: list, self_id: str, candidates: dict, lengths: list) -> list:
    found = []
    n = len(tokens)
    for L in lengths:
        if L > n:
            continue
        table = candidates.get(L)
        if not table:
            continue
        for i in range(n - L + 1):
            ids = table.get(tuple(tokens[i:i + L]))
            if not ids:
                continue
            for sid in ids:
                if sid != self_id:
                    found.append(sid)
    return found


def _reachable(graph: dict, start: str, goal: str) -> bool:
    """Is `goal` reachable from `start` following existing `requires` edges? Used to test whether
    adding start(=target)->...  would close a cycle back to the edge's source."""
    if start == goal:
        return True
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for nxt in graph.get(cur, ()):
            if nxt == goal:
                return True
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


# ------------------------------------------------------------------------------------ per-skill
@dataclass
class _PerSkill:
    triggers: list
    trig_prov: list
    neg: list
    neg_prov: list
    req_candidates: list   # [(target, confidence, cue, span), ...]
    sim_candidates: list   # [(target, confidence, cue, span), ...]


def _mine_skill(skill: dict, candidates: dict, lengths: list) -> _PerSkill:
    sid = str(skill["id"])
    sections = _sections_with_description(skill.get("body") or "", skill.get("description") or "")

    triggers, trig_prov = [], []
    neg, neg_prov = [], []
    req_candidates, sim_candidates = [], []
    seen_trig_forms, seen_neg_forms = set(), set()
    seen_edge_targets = set()

    for heading, lines in sections:
        content = "\n".join(lines)
        h_norm = _normalize_heading(heading) if heading else None
        is_usage = bool(h_norm) and bool(USAGE_HEADING_RE.search(h_norm))
        is_exclusion = bool(h_norm) and bool(EXCLUSION_HEADING_RE.search(h_norm))
        is_dep_edge = bool(h_norm) and bool(EDGE_DEPENDENCY_HEADING_RE.search(h_norm))
        is_rel_edge = bool(h_norm) and bool(EDGE_RELATED_HEADING_RE.search(h_norm))

        if is_usage and len(triggers) < TRIGGERS_CAP:
            for item in _extract_items(content):
                if len(triggers) >= TRIGGERS_CAP:
                    break
                # A combined heading ("When to use / when NOT to use") is `is_usage` only (the
                # exclusion regex is anchored at the heading start and does not also match), but
                # its bullet *items* can still individually be "do not use ..." -- reroute those
                # to negative_triggers instead of mislabelling them as triggers (mirrors the fix
                # for the same substring hazard in the unheaded-prose loop below).
                if len(neg) < NEGATIVE_TRIGGERS_CAP and EXCLUSION_SENTENCE_RE.search(item):
                    cleaned = _cue_remainder(item, EXCLUSION_SENTENCE_RE) or item
                    phrase = _finalize_phrase(cleaned, seen_neg_forms, min_content_tokens=2)
                    if phrase:
                        neg.append(phrase)
                        neg_prov.append({"phrase": phrase, "rule": "section_mining",
                                          "heading": heading, "derived": True})
                    continue
                # Most "when to use" bullets repeat a "Use when/for/if ..." cue verbatim
                # ("- Use when the user asks for BuyWhere MCP setup ..."); strip it so the
                # phrase is the condition, not the boilerplate. Falls back to the raw item
                # unchanged when no cue is present.
                cleaned = _cue_remainder(item, USAGE_SENTENCE_RE) or item
                phrase = _finalize_phrase(cleaned, seen_trig_forms)
                if phrase:
                    triggers.append(phrase)
                    trig_prov.append({"phrase": phrase, "rule": "section_mining",
                                       "heading": heading, "derived": True})

        if is_exclusion and len(neg) < NEGATIVE_TRIGGERS_CAP:
            for item in _extract_items(content):
                if len(neg) >= NEGATIVE_TRIGGERS_CAP:
                    break
                cleaned = _cue_remainder(item, EXCLUSION_SENTENCE_RE) or item
                phrase = _finalize_phrase(cleaned, seen_neg_forms, min_content_tokens=2)
                if phrase:
                    neg.append(phrase)
                    neg_prov.append({"phrase": phrase, "rule": "section_mining",
                                      "heading": heading, "derived": True})

        # Sentence-level usage/exclusion cues in *unheaded* prose (real skills often fold "use
        # when X" / "do not use for Y" into the description rather than a heading).
        if h_norm is None:
            for sentence in _split_sentences(content):
                # Exclusion is checked FIRST and is exclusive with usage for the same sentence:
                # "Do not use for X" / "Never use when Y" contains the literal substring "use
                # for"/"use when" that USAGE_SENTENCE_RE also matches, with no negation-awareness
                # of its own -- checking usage unconditionally on every sentence turned every
                # "do not use for X" exclusion into an *extra, exactly-backwards* trigger "X" (a
                # concrete false positive found by test_enrich_apply.py's real-fixture
                # contradiction check; see the F5 report). A sentence naming a real "do not use"
                # cue is exclusion-only.
                is_excl_sentence = bool(EXCLUSION_SENTENCE_RE.search(sentence))
                if len(triggers) < TRIGGERS_CAP and not is_excl_sentence and USAGE_SENTENCE_RE.search(sentence):
                    phrase = _finalize_phrase(_cue_remainder(sentence, USAGE_SENTENCE_RE), seen_trig_forms)
                    if phrase:
                        triggers.append(phrase)
                        trig_prov.append({"phrase": phrase, "rule": "sentence_mining",
                                           "heading": None, "derived": True})
                if len(neg) < NEGATIVE_TRIGGERS_CAP and is_excl_sentence:
                    phrase = _finalize_phrase(
                        _cue_remainder(sentence, EXCLUSION_SENTENCE_RE), seen_neg_forms, min_content_tokens=2
                    )
                    if phrase:
                        neg.append(phrase)
                        neg_prov.append({"phrase": phrase, "rule": "sentence_mining",
                                          "heading": None, "derived": True})

        # Edge mining: mentions of other skills, everywhere, classified by section/sentence context.
        for sentence in _split_sentences(content):
            toks = tokenize(sentence)
            if not toks:
                continue
            for target in _find_mentions(toks, sid, candidates, lengths):
                if target == sid or target in seen_edge_targets:
                    continue
                span = sentence[:160]
                if is_dep_edge:
                    req_candidates.append((target, "high", f"heading:{heading}", span))
                elif is_rel_edge:
                    sim_candidates.append((target, "high", f"heading:{heading}", span))
                else:
                    dep = DEPENDENCY_CUE_RE.search(sentence)
                    rel = RELATED_CUE_RE.search(sentence)
                    if dep:
                        req_candidates.append((target, "medium", dep.group(0), span))
                    elif rel:
                        sim_candidates.append((target, "medium", rel.group(0), span))
                    else:
                        sim_candidates.append((target, "low", "bare_mention", span))
                seen_edge_targets.add(target)

    return _PerSkill(triggers, trig_prov, neg, neg_prov, req_candidates, sim_candidates)


# --------------------------------------------------------------------------------------- derive
def derive(skills: list) -> dict:
    """skills: [{"id":..., "name":..., "description":..., "body":..., ["requires": [...],]
    ["triggers": [...],] ["negative_triggers": [...]]}, ...] -> {skill_id: Enrichment}.

    Pure function: no filesystem, no network. See module docstring for the three rules.
    """
    by_id = {str(s["id"]): s for s in skills}
    candidates = _build_candidates(skills)
    lengths = sorted(candidates)

    mined = {sid: _mine_skill(s, candidates, lengths) for sid, s in by_id.items()}

    results = {sid: Enrichment() for sid in by_id}

    # --- triggers / negative_triggers: existing fields win, derived items are appended -------
    for sid, s in by_id.items():
        m = mined[sid]
        r = results[sid]
        existing_trig = [str(x) for x in (s.get("triggers") or [])]
        existing_neg = [str(x) for x in (s.get("negative_triggers") or [])]
        seen_trig_forms = {tuple(tokenize(x)) for x in existing_trig}
        seen_neg_forms = {tuple(tokenize(x)) for x in existing_neg}

        r.triggers.extend(existing_trig)
        r.provenance["triggers"].extend(
            {"phrase": x, "rule": "existing", "heading": None, "derived": False} for x in existing_trig
        )
        for phrase, prov in zip(m.triggers, m.trig_prov):
            if len(r.triggers) >= TRIGGERS_CAP:
                break
            if tuple(tokenize(phrase)) in seen_trig_forms:
                continue
            seen_trig_forms.add(tuple(tokenize(phrase)))
            r.triggers.append(phrase)
            r.provenance["triggers"].append(prov)

        r.negative_triggers.extend(existing_neg)
        r.provenance["negative_triggers"].extend(
            {"phrase": x, "rule": "existing", "heading": None, "derived": False} for x in existing_neg
        )
        for phrase, prov in zip(m.neg, m.neg_prov):
            if len(r.negative_triggers) >= NEGATIVE_TRIGGERS_CAP:
                break
            if tuple(tokenize(phrase)) in seen_neg_forms:
                continue
            seen_neg_forms.add(tuple(tokenize(phrase)))
            r.negative_triggers.append(phrase)
            r.provenance["negative_triggers"].append(prov)

    # --- requires: existing fields win (seeded into the graph first, trusted, no cycle-check
    # among themselves), then derived candidates are added greedily in a stable order, demoting
    # any edge that would close a cycle to `similar` instead. --------------------------------
    graph = {sid: set() for sid in by_id}
    for sid, s in by_id.items():
        for target in (s.get("requires") or []):
            target = str(target)
            if target == sid:
                continue
            results[sid].requires.append(target)
            results[sid].provenance["requires"].append(
                {"target": target, "rule": "existing", "derived": False}
            )
            if target in graph:
                graph[sid].add(target)

    for sid in sorted(by_id):
        for target, conf, cue, span in mined[sid].req_candidates:
            if target == sid or target in results[sid].requires:
                continue
            if _reachable(graph, target, sid):
                mined[sid].sim_candidates.append((target, "demoted", "cycle_demoted", span))
                continue
            graph[sid].add(target)
            results[sid].requires.append(target)
            results[sid].provenance["requires"].append(
                {"target": target, "rule": "edge_mining", "cue": cue, "span": span,
                 "derived": True, "confidence": conf}
            )

    # --- corpus-wide boilerplate guard for negative_triggers ------------------------------------
    # `negative_triggers` is a hard filter (Router.policy_filter: unordered token-SET containment,
    # no length floor in the router itself) so an identical derived phrase repeated across many
    # skills is a precision hazard out of proportion to its provenance: if a query happens to
    # contain every one of that phrase's tokens, EVERY skill carrying it is dropped, and a phrase
    # shared verbatim by dozens of otherwise-unrelated skills is, by definition, boilerplate from
    # a shared authoring template rather than skill-specific signal (measured on the 2 037-skill
    # reference corpus: "You need a different domain" recurred in 221 skills; two more forms in 49
    # each; the next most common derived form recurred in only 11 — see the F5 report for the full
    # frequency table). Only *derived* phrases are ever removed here — an authored phrase repeated
    # by its own author is that author's choice (rule 3, existing fields win) and is left alone no
    # matter how common.
    if by_id:
        form_skill_counts: dict = {}
        for r in results.values():
            seen_forms_this_skill = set()
            for prov in r.provenance["negative_triggers"]:
                if not prov.get("derived"):
                    continue
                key = tuple(tokenize(prov["phrase"]))
                if key in seen_forms_this_skill:
                    continue
                seen_forms_this_skill.add(key)
                form_skill_counts[key] = form_skill_counts.get(key, 0) + 1
        threshold = max(NEG_BOILERPLATE_MIN_SKILLS, NEG_BOILERPLATE_FRACTION * len(by_id))
        boilerplate_forms = {k for k, n in form_skill_counts.items() if n > threshold}
        if boilerplate_forms:
            for r in results.values():
                kept_phrases, kept_prov = [], []
                for phrase, prov in zip(r.negative_triggers, r.provenance["negative_triggers"]):
                    if prov.get("derived") and tuple(tokenize(phrase)) in boilerplate_forms:
                        continue
                    kept_phrases.append(phrase)
                    kept_prov.append(prov)
                r.negative_triggers = kept_phrases
                r.provenance["negative_triggers"] = kept_prov

    # --- similar: every sim candidate not already a `requires` edge for this skill, deduped ---
    for sid in by_id:
        r = results[sid]
        seen = set(r.requires)
        for target, conf, cue, span in mined[sid].sim_candidates:
            if target == sid or target in seen:
                continue
            seen.add(target)
            r.similar.append(target)
            r.provenance["similar"].append(
                {"target": target, "rule": "edge_mining", "cue": cue, "span": span,
                 "derived": True, "confidence": conf}
            )

    return results
