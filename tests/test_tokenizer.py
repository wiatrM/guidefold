"""tokenize(): the one shared tokenizer used by both Index build and Router query time
(ROUTER-SPEC "Determinism by construction"). NFKD-normalize and strip combining marks (folds
accented Latin letters onto their base letter instead of dropping them), ASCII-only lowercase
(never str.lower()), split on [a-z0-9]+.

Must stay byte-identical to tools/bakeoff/tokenizer.py -- see tools/bakeoff/tests/test_tokenizer.py
for the CI-side copy of this same contract.
"""
import unicodedata


def test_splits_on_alnum_runs_and_lowercases_ascii(gf):
    assert gf.tokenize("Hello, World! v2.0 --flag") == ["hello", "world", "v2", "0", "flag"]


def test_ascii_only_lowercase_does_not_use_unicode_case_folding(gf):
    assert gf.tokenize("HELLO World") == ["hello", "world"]
    # A non-ASCII uppercase letter with no NFKD decomposition (Greek Sigma has no accent to
    # fold away) must still be left untouched by the ASCII-only lower map, not run through
    # str.lower()'s version-dependent Unicode case table -- observable at the tokenize()
    # level as "still discarded" either way, since neither the upper nor the lower form of a
    # non-Latin letter is in [a-z0-9].
    assert gf.tokenize("Σ") == []          # Greek capital Sigma
    assert gf.tokenize("Σ") == gf.tokenize("σ")  # == lowercase sigma
    # And directly on the helper itself, so this stays a real regression test even though
    # both branches happen to produce the same tokenize() output:
    assert gf._ascii_lower("Σ") == "Σ"


def test_turkish_dotted_i_folds_to_plain_ascii_i_via_nfkd(gf):
    # 'I' with dot above (U+0130) is the classic case where Python's str.lower() is
    # version/locale-sensitive. NFKD decomposes U+0130 into 'I' + a combining dot above
    # *before* the ASCII-only-lowercase step ever sees it, so stripping combining marks
    # reduces it to plain ASCII 'I' deterministically (Unicode decomposition data, not a
    # locale table). This is a documented, intentional behaviour change from the pre-fix
    # tokenizer, which NFC-normalized only and then dropped 'I-with-dot' as a bare non-ASCII
    # separator, producing ["stanbul"].
    assert gf.tokenize("İstanbul") == ["istanbul"]


def test_accented_words_fold_onto_their_base_letter_instead_of_being_dropped(gf):
    # The defect this fixes: an ASCII-only filter over merely-NFC-normalised text drops
    # every non-ASCII letter wholesale, shredding accented words down to their consonant
    # skeleton instead of folding them onto a base letter. NFKD + strip-combining-marks
    # folds the accent away and keeps the base letter.
    assert gf.tokenize("naïve café RÉSUMÉ") == ["naive", "cafe", "resume"]
    assert gf.tokenize("Zürich Ansprüche") == ["zurich", "anspruche"]
    assert gf.tokenize("señor mañana") == ["senor", "manana"]


def test_non_latin_scripts_still_fall_through_as_separators(gf):
    # Accent-folding only folds diacritics onto a base Latin letter; it does not
    # transliterate other scripts. Non-Latin letters remain non-[a-z0-9] and are still
    # discarded -- unchanged by the accent-folding fix, and correct: those words fall back
    # to the BM25/OOV path, not silently mistranslated.
    assert gf.tokenize("ΣΙΓΜΑ") == []  # "SIGMA" in Greek letters


def test_nfkd_fold_makes_decomposed_and_precomposed_forms_equivalent(gf):
    # "e" + combining acute accent (U+0301) is the NFD spelling of "e-acute"; U+00E9 is
    # the single precomposed codepoint. Built from explicit \uXXXX escapes, not two
    # visually identical literals, so the test genuinely exercises two different
    # on-disk byte sequences rather than the same one typed twice (a literal accented
    # character embedded directly in source can silently get re-normalised to a single
    # form by editing tools -- see tools/bakeoff/tests/test_tokenizer.py for the sibling
    # test and the same rationale).
    precomposed = "\u00e9clair"
    decomposed = "e\u0301clair"
    assert precomposed != decomposed  # sanity check: genuinely different code points
    assert unicodedata.normalize("NFC", decomposed) == unicodedata.normalize("NFC", precomposed)
    # Folding accents (NFKD + strip-combining) rather than merely NFC-composing means
    # both forms fold onto the exact same ASCII base letters: "eclair", not "clair" --
    # an NFC-only pass would leave the accented "e" as a single non-[a-z0-9] codepoint
    # for the ASCII-only filter to drop wholesale, losing the base letter entirely.
    assert gf.tokenize(precomposed) == ["eclair"]
    assert gf.tokenize(decomposed) == ["eclair"]
    assert gf.tokenize(precomposed) == gf.tokenize(decomposed)


def test_e_vs_e_is_identical_for_both_input_forms(gf):
    # Built from explicit code points (U+00E9 = precomposed; "e" + U+0301 = base
    # letter + combining acute), not two visually-identical literals -- see rationale above.
    precomposed = "\u00e9 vs \u00e9"
    decomposed = "e\u0301 vs e\u0301"
    assert precomposed != decomposed  # sanity check: genuinely different code points
    assert gf.tokenize(precomposed) == ["e", "vs", "e"]
    assert gf.tokenize(decomposed) == ["e", "vs", "e"]
    assert gf.tokenize(precomposed) == gf.tokenize(decomposed)


def test_deterministic_across_repeated_calls(gf):
    text = "The Quick Brown Fox, 123 times!"
    assert gf.tokenize(text) == gf.tokenize(text) == ["the", "quick", "brown", "fox", "123", "times"]


def test_empty_and_none_input(gf):
    assert gf.tokenize("") == []
    assert gf.tokenize(None) == []
