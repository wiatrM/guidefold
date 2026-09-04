"""Tests for the shared tokenizer (tools/bakeoff/tokenizer.py).

`skills/guidefold/scripts/guidefold` must implement a byte-identical
`tokenize()`; this fixed-input/fixed-output test is the contract both
implementations must satisfy.
"""
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tokenizer import tokenize  # noqa: E402


def test_fixed_input_fixed_output():
    text = "Postgres-Auth: Turnstile's RBAC_Policies (v2026.09) — café résumé naïve 42 checks!"
    expected = [
        "postgres",
        "auth",
        "turnstile",
        "s",
        "rbac",
        "policies",
        "v2026",
        "09",
        "cafe",
        "resume",
        "naive",
        "42",
        "checks",
    ]
    assert tokenize(text) == expected


def test_empty_and_none_like_inputs():
    assert tokenize("") == []
    assert tokenize("   ") == []
    assert tokenize("!!!---___...") == []


def test_accented_words_fold_onto_their_base_letter_instead_of_being_dropped():
    # The defect this fixes: an ASCII-only filter over merely-NFC-normalised text
    # drops every non-ASCII letter wholesale, shredding accented words down to
    # their consonant skeleton instead of folding them onto a base letter. NFKD +
    # strip-combining-marks folds the accent away and keeps the base letter.
    assert tokenize("naïve café RÉSUMÉ") == ["naive", "cafe", "resume"]
    assert tokenize("Zürich Ansprüche") == ["zurich", "anspruche"]
    assert tokenize("señor mañana") == ["senor", "manana"]


def test_non_latin_scripts_still_fall_through_as_separators():
    # Accent-folding only folds diacritics onto a base Latin letter; it does not
    # transliterate other scripts. Non-Latin letters remain non-[a-z0-9] and are
    # still discarded -- unchanged by the accent-folding fix, and correct: those
    # words fall back to the BM25/OOV path, not silently mistranslated.
    assert tokenize("ΣΙΓΜΑ") == []


def test_ascii_only_lowercase_does_not_use_unicode_casefold():
    # A non-ASCII uppercase letter with no NFKD decomposition (Greek Sigma has no
    # accent to fold away) must still be left untouched by the ASCII-only lower
    # map, not run through str.lower()'s version-dependent Unicode case table --
    # observable at the tokenize() level as "still discarded" either way, since
    # neither the upper nor the lower form of a non-Latin letter is in [a-z0-9].
    assert tokenize("Σ") == []
    assert tokenize("Σ") == tokenize("σ")
    # And directly on the helper itself, so this stays a real regression test
    # even though both branches happen to produce the same tokenize() output:
    from tokenizer import _ascii_lower  # noqa: E402  (local import keeps the intent obvious)

    assert _ascii_lower("Σ") == "Σ"


def test_turkish_dotted_i_folds_to_plain_ascii_i_via_nfkd():
    # 'İ' (Latin capital I with dot above, U+0130) is the classic case where
    # Python's str.lower() is version/locale-sensitive ('İ'.lower() produces
    # 'i' + a combining dot above on a non-Turkish locale, not plain 'i'). NFKD
    # decomposes U+0130 into 'I' + a combining dot above *before* the
    # ASCII-only-lowercase step ever sees it, so stripping combining marks
    # reduces it to plain ASCII 'I' deterministically (Unicode decomposition
    # data, not a locale table). This is a documented, intentional behaviour
    # change from the pre-fix tokenizer, which dropped 'İ' as a bare non-ASCII
    # separator and produced ["stanbul"].
    assert tokenize("İstanbul") == ["istanbul"]


def test_ascii_uppercase_is_lowercased():
    assert tokenize("ABC abc AbC123") == ["abc", "abc", "abc123"]


def test_nfc_and_nfd_input_tokenize_identically():
    # "caf" + 'e' + combining acute accent U+0301 is the NFD spelling of
    # "café". Folding accents (NFKD + strip-combining) rather than merely
    # NFC-composing means precomposed and decomposed input fold onto the exact
    # same base letters regardless of which form the input arrived in.
    nfd_form = "caf" + "e" + "́"  # combining acute accent
    nfc_form = "café"
    assert unicodedata.normalize("NFC", nfd_form) == nfc_form  # sanity check on the fixture itself
    assert tokenize(nfd_form) == ["cafe"]
    assert tokenize(nfd_form) == tokenize(nfc_form)


def test_e_vs_e_is_identical_for_both_input_forms():
    # The coordinator's own worked example: precomposed vs decomposed "e"-with-
    # acute-accent must tokenize identically. Built from explicit code points
    # (\u00e9 = precomposed; "e" + \u0301 = base letter + combining acute), not
    # two visually-identical literals, so the test genuinely exercises two
    # different on-disk byte sequences rather than the same one typed twice.
    precomposed = "\u00e9 vs \u00e9"
    decomposed = "e\u0301 vs e\u0301"
    assert precomposed != decomposed  # sanity check: genuinely different code points
    assert tokenize(precomposed) == ["e", "vs", "e"]
    assert tokenize(decomposed) == ["e", "vs", "e"]
    assert tokenize(precomposed) == tokenize(decomposed)


def test_identifiers_with_no_accents_are_unchanged():
    assert tokenize("Kubernetes") == ["kubernetes"]
    assert tokenize("TurnstileAuth") == ["turnstileauth"]
    assert tokenize("postgres_auth-v2") == ["postgres", "auth", "v2"]


def test_order_is_preserved():
    assert tokenize("zebra apple 9 mango 1") == ["zebra", "apple", "9", "mango", "1"]


def test_idempotent_on_already_tokenized_words():
    words = ["kafka", "topic", "consumer", "group", "checkpoint"]
    assert tokenize(" ".join(words)) == words
