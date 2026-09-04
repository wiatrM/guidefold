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
        "caf",
        "r",
        "sum",
        "na",
        "ve",
        "42",
        "checks",
    ]
    assert tokenize(text) == expected


def test_empty_and_none_like_inputs():
    assert tokenize("") == []
    assert tokenize("   ") == []
    assert tokenize("!!!---___...") == []


def test_ascii_only_lowercase_does_not_use_unicode_casefold():
    # 'İ' (Latin capital I with dot above, U+0130) is not in A-Z, so ASCII-only
    # lowercasing must leave it untouched -> it is a non-[a-z0-9] separator,
    # not merged into a word, unlike what str.lower()/str.casefold() would do
    # in locales/tables where it maps to a multi-codepoint lowercase form.
    assert tokenize("İstanbul") == ["stanbul"]


def test_ascii_uppercase_is_lowercased():
    assert tokenize("ABC abc AbC123") == ["abc", "abc", "abc123"]


def test_nfc_normalisation_composes_before_splitting():
    # "caf" + 'e' + combining acute accent U+0301 is the NFD spelling of
    # "café". NFC-normalising first composes 'e' + U+0301 into a single
    # non-ASCII code point 'é', which is then dropped as a separator -- so
    # this must tokenize identically to the precomposed string, not as
    # ["caf", "e"].
    nfd_form = "caf" + "e" + "\u0301"  # combining acute accent
    nfc_form = "café"
    assert unicodedata.normalize("NFC", nfd_form) == nfc_form  # sanity check on the fixture itself
    assert tokenize(nfd_form) == ["caf"]
    assert tokenize(nfd_form) == tokenize(nfc_form)


def test_order_is_preserved():
    assert tokenize("zebra apple 9 mango 1") == ["zebra", "apple", "9", "mango", "1"]


def test_idempotent_on_already_tokenized_words():
    words = ["kafka", "topic", "consumer", "group", "checkpoint"]
    assert tokenize(" ".join(words)) == words
