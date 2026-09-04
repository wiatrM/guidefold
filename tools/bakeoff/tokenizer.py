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
  1. NFKD-normalise the input (`unicodedata.normalize("NFKD", text)`), then strip
     every combining mark the decomposition produced (`unicodedata.combining(c)`).
     This *folds* accented Latin letters onto their base letter instead of
     dropping them: "café" and "naïve" decompose into base-letter + combining-
     accent pairs, and stripping only the combining marks leaves "cafe" / "naive"
     -- ASCII, and identical whether the input arrived pre- or de-composed
     ("café" NFC vs "café" NFD tokenize identically, which an NFC-only
     first pass cannot guarantee: NFC recomposes the *input* but does nothing for
     a base letter that only carries a combining mark in a decomposed script, and
     either way an ASCII-only filter after plain NFC would drop the composed
     accented letter wholesale rather than fold it). This step is corpus-content
     data, not a locale table: `unicodedata`'s decomposition data is part of the
     Unicode standard, so it is exactly as deterministic-forever as the NFC step
     it replaces -- see PR "fix: fold accents in the shared tokenizer instead of
     dropping them" for the corpus-quality bug this fixes (every non-ASCII-
     scripted word was being shredded to its consonant skeleton, e.g. 'RÉSUMÉ'
     -> ['r', 'sum'] instead of ['resume']).
  2. ASCII-only lowercase: map `A-Z` -> `a-z` one code point at a time.
     Do NOT use `str.lower()` — its Unicode case-folding table is version-
     dependent (it has shifted between CPython 3.11 and 3.13 for scripts
     outside ASCII), which would make word ids non-reproducible across
     interpreter versions. Mapping only `A-Z` is deterministic forever. (Most
     accented Latin uppercase letters no longer reach this step as non-ASCII
     code points at all -- step 1's NFKD decomposition already reduced them to
     a plain ASCII base letter -- so this step's scope is now mostly composed
     of scripts NFKD does not decompose, e.g. Cyrillic/Greek, which fall through
     step 3 as OOV either way.)
  3. Split on the regex `[a-z0-9]+` and return the matches, in order.
     Everything that is not `[a-z0-9]` after step 2 (punctuation, non-Latin
     scripts, whitespace, underscores, hyphens) is a separator and is
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


def _fold_accents(text: str) -> str:
    """NFKD-decompose, then drop every combining mark the decomposition produced.

    Folds accented/diacritic Latin letters onto their base ASCII letter (e.g.
    'é' -> 'e + combining acute' -> 'e') instead of discarding the whole
    character the way an ASCII-only filter over NFC input would. Scripts with
    no such decomposition (Cyrillic, Greek, CJK, ...) pass through unchanged and
    remain non-ASCII, falling through step 3 of `tokenize()` as before -- this
    only folds diacritics, it does not transliterate scripts.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str) -> list[str]:
    """Fold accents (NFKD + strip combining marks), ASCII-lowercase, split on
    [a-z0-9]+. Returns words in order.

    See module docstring: this must stay byte-identical to the copy that
    `skills/guidefold/scripts/guidefold` will implement.
    """
    if not text:
        return []
    folded = _fold_accents(text)
    lowered = _ascii_lower(folded)
    return _WORD_RE.findall(lowered)


if __name__ == "__main__":
    import sys

    for line in sys.stdin:
        print(tokenize(line.rstrip("\n")))
