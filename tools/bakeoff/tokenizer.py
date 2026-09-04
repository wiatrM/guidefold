"""tokenizer.py — THE shared tokenizer (ROUTER-SPEC-v2.md, "[R] One tokenizer, shared by CI and hook").

This module must stay trivially portable to the stdlib-only, single-file
`skills/guidefold/scripts/guidefold` CLI: it uses only `unicodedata` and `re`
from the standard library, nothing else.

IMPORTANT: `skills/guidefold/scripts/guidefold` must contain a byte-identical
(same algorithm, same output for the same input) implementation of `tokenize()`
below. CI (this package) and the hook (the shipped CLI) tokenize corpus words
and query text with this exact procedure so that word ids agree between the
tier-1 static table built here and the integer arithmetic the hook does at
query time. If you change this function, the corresponding function in
`skills/guidefold/scripts/guidefold` must change identically in the same
commit, or word ids silently drift between CI and the hook.

Algorithm (fixed, do not "improve" without updating both copies):
  1. NFC-normalise the input (`unicodedata.normalize("NFC", text)`).
  2. ASCII-only lowercase: map `A-Z` -> `a-z` one code point at a time.
     Do NOT use `str.lower()` — its Unicode case-folding table is version-
     dependent (it has shifted between CPython 3.11 and 3.13 for scripts
     outside ASCII), which would make word ids non-reproducible across
     interpreter versions. Mapping only `A-Z` is deterministic forever.
  3. Split on the regex `[a-z0-9]+` and return the matches, in order.
     Everything that is not `[a-z0-9]` after step 2 (punctuation, non-ASCII
     letters, whitespace, underscores, hyphens) is a separator and is
     discarded, never merged into a token.

The teacher's own tokenizer (byte-level BPE) is completely different and is
never used for tier 1: distillation runs per *word* (this tokenizer's output),
not per BPE token (ROUTER-SPEC-v2.md, stage 1 line: "the teacher's byte-level
BPE needs `\\p{L}` classes that stdlib `re` does not have, so the distillation
is per-word, not per-BPE-token").
"""
from __future__ import annotations

import re
import unicodedata

_WORD_RE = re.compile(r"[a-z0-9]+")

_UPPER_TO_LOWER = {chr(c): chr(c + 32) for c in range(ord("A"), ord("Z") + 1)}


def _ascii_lower(text: str) -> str:
    """Map A-Z -> a-z one code point at a time. Never touches non-ASCII code points."""
    return "".join(_UPPER_TO_LOWER.get(ch, ch) for ch in text)


def tokenize(text: str) -> list[str]:
    """NFC-normalise, ASCII-lowercase, split on [a-z0-9]+. Returns words in order.

    See module docstring: this must stay byte-identical to the copy that
    `skills/guidefold/scripts/guidefold` will implement.
    """
    if not text:
        return []
    normalised = unicodedata.normalize("NFC", text)
    lowered = _ascii_lower(normalised)
    return _WORD_RE.findall(lowered)


if __name__ == "__main__":
    import sys

    for line in sys.stdin:
        print(tokenize(line.rstrip("\n")))
