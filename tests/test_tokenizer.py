"""tokenize(): the one shared tokenizer used by both Index build and Router query time
(ROUTER-SPEC "Determinism by construction"). NFC normalize, ASCII-only lowercase (never
str.lower()), split on [a-z0-9]+."""


def test_splits_on_alnum_runs_and_lowercases_ascii(gf):
    assert gf.tokenize("Hello, World! v2.0 --flag") == ["hello", "world", "v2", "0", "flag"]


def test_ascii_only_lowercase_does_not_use_unicode_case_folding(gf):
    assert gf.tokenize("HELLO World") == ["hello", "world"]
    # U+0130 (dotted capital I) is outside our A-Z translate table. str.lower() would expand it
    # to a two-codepoint "i" + combining-dot-above (locale/version-sensitive); our ascii-only
    # translate leaves it untouched, so it is simply not a token character, deterministically.
    assert gf.tokenize("İstanbul") == ["stanbul"]


def test_nfc_normalization_makes_decomposed_and_precomposed_forms_equivalent(gf):
    decomposed = "éclair"   # "e" + combining acute accent (U+0301)
    precomposed = "éclair"  # single precomposed codepoint (é = e-acute)
    # Without NFC, the decomposed form's bare ascii "e" would wrongly tokenize as its own
    # one-letter token (["e", "clair"]) while the precomposed form (no bare ascii "e" at
    # all) would not (["clair"]) -- the same word would tokenize two different ways.
    assert gf.tokenize(decomposed) == gf.tokenize(precomposed) == ["clair"]


def test_deterministic_across_repeated_calls(gf):
    text = "The Quick Brown Fox, 123 times!"
    assert gf.tokenize(text) == gf.tokenize(text) == ["the", "quick", "brown", "fox", "123", "times"]


def test_empty_and_none_input(gf):
    assert gf.tokenize("") == []
    assert gf.tokenize(None) == []
