"""E1.4 acceptance: 'synthesize a 2000-skill corpus, assert artifact <= 15 MB'.

Builds a synthetic 2000-card Index (via Index.from_cards, bypassing the filesystem tree scan --
there is no real 2000-skill monorepo to point at) with a realistic spread of natural-language-ish
vocabulary and per-node distribution, serializes it through the exact same
_serialize_artifact_files() the real `guidefold index` command uses, and measures the total
on-disk size the same way write_index_artifact() would (files + manifest.json).

This release ships w_dense=0 (no distilled word table yet, ADR-0020) -- reported explicitly below
so the size breakdown is never mistaken for including the dense channel.
"""
import json
import random

# A 900-word vocabulary understates the artifact: postings size is driven by term diversity.
# Measured sweep at 2000 cards -- 900 -> 1.99 MB, 5k -> 2.28 MB, 20k -> 3.00 MB, 40k -> 3.64 MB.
# 40k is the realistic order of magnitude for a 2000-skill corpus, so the assertion is made there.
# Corpus profile measured from 889 real SKILL.md files (benjaminasterA/antigravity-awesome-skills,
# MIT) rather than invented. Synthetic filler made this test optimistic in two ways that both
# understate the artifact: its documents were 120 tokens where real ones run to 803, and its terms
# were sampled uniformly where real text is Zipfian. See ADR-0021 for the full measurement.
#
#   measured:  889 skills -> 26,489 distinct terms, 757,089 tokens, 852 tokens/skill
#   Heaps:     V = 620.2 * n^0.553   (exponent in the natural-language range 0.4-0.6)
# Profile measured on a real 2 111-skill corpus (103 MB, gitignored under experiment/), which made
# the 2000-skill row measurable instead of projected. Both earlier estimates were optimistic:
#
#   at ~2000 skills   synthetic   from-889 projection   MEASURED at 2111
#   distinct terms       41,473              41,473            56,059  (+35%)
#   tokens/skill            120                 852             1,127
#   sparse artifact     3.47 MB             4.97 MB           5.40 MB
#   + 34k word table      83.5%               91.8%             96.5%
#
# Heaps refitted on that corpus: V = 1475.8 * n^0.475 (the 889-skill corpus gave 620.2 * n^0.553).
# The two real corpora disagree on both parameters — a Heaps fit is a property of the corpus, not
# of the domain — so these constants are indicative and get re-measured when a bigger corpus lands.
REAL_TOKENS_PER_SKILL = 1127
REAL_HEAPS_K = 1475.8
REAL_HEAPS_BETA = 0.475
REAL_SPARSE_BYTES_PER_SKILL = 2681        # 5,660,305 B / 2,111 skills, measured
VOCAB_SIZE = int(REAL_HEAPS_K * (2000 ** REAL_HEAPS_BETA))   # ~56,000 at 2000 skills
ZIPF_EXPONENT = 1.142                                        # measured on the same corpus
NODE_COUNT = 25
CARD_COUNT = 2000
FIFTEEN_MB = 15 * 1024 * 1024


def _make_nodes():
    # A flat set of team nodes plus _root, similar in shape to a real guidefold.yaml at scale.
    nodes = {"_root": {"paths": ["**"], "owner": "platform"}}
    for i in range(NODE_COUNT):
        nodes[f"team{i:02d}"] = {"paths": [f"team{i:02d}/**"], "owner": f"team-{i:02d}"}
    return nodes


def _make_vocab(rng):
    """A frequency-sorted vocabulary of distinct word-shaped tokens.

    Order matters: `_zipf` indexes into this list, so index 0 must be the most frequent term.
    Lengths run 4-8 characters because the real corpus averages that; 3-character tokens made the
    earlier synthetic vocabulary collide constantly and understated the distinct-term count.
    """
    consonants, vowels = "bcdfghjklmnprstvwz", "aeiou"

    def word():
        n = rng.randint(4, 8)
        return "".join(rng.choice(consonants if i % 2 == 0 else vowels) for i in range(n))

    out = set()
    while len(out) < VOCAB_SIZE:
        out.add(word())
    return sorted(out)


def _zipf(rng):
    """Index into a frequency-sorted vocabulary, Zipf-distributed with the measured exponent."""
    # inverse-transform on a truncated zeta-ish tail; exact shape does not matter, the skew does
    u = rng.random()
    return min(int((u ** (-1.0 / (ZIPF_EXPONENT - 1))) - 1), VOCAB_SIZE - 1)


def _make_cards(rng, vocab):
    from _router_helpers import make_card
    node_names = [f"team{i:02d}" for i in range(NODE_COUNT)]
    cards = {}
    urns = []
    for i in range(CARD_COUNT):
        node = node_names[i % NODE_COUNT]
        name = f"skill-{i:04d}"
        urn = f"urn:skill:synthetic:{node}:{name}"
        urns.append(urn)
        # Zipfian draw, matching the measured slope: a few terms dominate, ~53% are hapax.
        # Uniform sampling spreads postings evenly and makes the artifact look smaller than it is.
        desc_words = [vocab[_zipf(rng)] for _ in range(15)]
        body_words = [vocab[_zipf(rng)] for _ in range(REAL_TOKENS_PER_SKILL)]
        triggers = [" ".join(rng.choice(vocab) for _ in range(3)) for _ in range(2)]
        requires = [urns[rng.randrange(i)]] if i > 0 and rng.random() < 0.15 else []
        cards[urn] = make_card(
            urn, node, name=name,
            description=" ".join(desc_words),
            digest=" ".join(desc_words[:8]),
            triggers=triggers,
            body=" ".join(body_words),
            requires=requires,
        )
    return cards


def test_2000_skill_synthetic_corpus_artifact_is_at_most_15mb(gf, tmp_path):
    rng = random.Random(20260904)
    vocab = _make_vocab(rng)
    nodes = _make_nodes()
    cards = _make_cards(rng, vocab)

    idx = gf.Index.from_cards(cards, nodes, word_vectors=None)
    assert len(idx.cards) == CARD_COUNT

    files = gf._serialize_artifact_files(idx)
    dest = tmp_path / "artifact"
    dest.mkdir()
    sizes = {}
    for fname, data in files.items():
        (dest / fname).write_bytes(data)
        sizes[fname] = len(data)

    # Same manifest shape write_index_artifact() would produce (format_version/git_sha/etc. are
    # all small fixed-size fields; checksums is one sha256 hex string per file -- all negligible
    # next to postings/cards/terms, but included so the total is the real on-disk artifact size).
    manifest = {
        "format_version": 1, "git_sha": "synthetic0", "build_time": "2026-01-01T00:00:00+00:00",
        "builder": "test", "teacher": {"id": None, "hf_commit_sha": None, "license": None},
        "student_dims": gf._dense_dims(idx), "quant_scale": 127, "weights": idx.weights,
        "counts": {"cards": len(idx.cards), "terms": len(idx.idf), "words": len(idx.word_vectors)},
        "checksums": {name: "0" * 64 for name in files},  # placeholder, same length as a real sha256 hexdigest
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
    (dest / "manifest.json").write_bytes(manifest_bytes)
    sizes["manifest.json"] = len(manifest_bytes)

    total = sum(sizes.values())
    breakdown = "\n".join(f"  {name}: {n:,} bytes" for name, n in sorted(sizes.items(), key=lambda kv: -kv[1]))
    assert manifest["student_dims"] == 0  # this release ships no dense channel -- words.bin/vectors.i8 are empty
    assert sizes.get("words.bin", 0) == 0
    assert sizes.get("vectors.i8", 0) == 0
    assert total <= FIFTEEN_MB, (
        f"2000-skill synthetic artifact is {total:,} bytes (> {FIFTEEN_MB:,} budget)\n{breakdown}"
    )
    print(f"\n2000-skill synthetic artifact: {total:,} bytes ({total / 1024 / 1024:.2f} MiB) "
          f"of a {FIFTEEN_MB:,}-byte (15 MiB) budget, {manifest['counts']['terms']:,} distinct terms\n{breakdown}")


def test_projected_size_with_a_dense_word_table_still_fits_15mb(gf, tmp_path):
    """The sparse artifact is only a third of the story, and quoting it alone is misleading.

    `vectors.i8` / `words.bin` / `words.idx` are empty in this release (`w_dense = 0`, ADR-0020 --
    the distilled table arrives with E1.3). When it does, it becomes the single largest file in the
    artifact, so the budget has to be checked against the *projected* total rather than against
    today's sparse-only measurement.

    Sizes are arithmetic, not guesses: an int8 word table is `vocab x dims` bytes, the skill
    vectors are `cards x dims`, and the integer norms are 8 bytes per card.
    """
    rng = random.Random(20260904)
    idx = gf.Index.from_cards(_make_cards(rng, _make_vocab(rng)), _make_nodes(), word_vectors=None)
    sparse = sum(len(b) for b in gf._serialize_artifact_files(idx).values())

    # Honest caveat on this projection. Two independent routes to the 2000-skill sparse size
    # disagree by ~20%: this test's synthetic-with-real-profile corpus gives ~3.97 MB, while
    # extrapolating the *direct* measurement of 889 real SKILL.md files gives ~4.97 MB (ADR-0021).
    # A generated Zipf draw does not reproduce real term co-occurrence, so it packs postings better
    # than reality does. Where they disagree, trust the direct measurement and take the lower
    # vocabulary cap: the ~34k figure in ADR-0021 is safe under BOTH, which is why it is the number
    # the distillation must honour rather than the ~42k this test alone would allow.
    DIMS = 256
    def projected(vocab_words):
        word_table = vocab_words * DIMS          # int8, one byte per dimension
        word_index = vocab_words * 8             # offset table
        skill_vectors = CARD_COUNT * DIMS
        return sparse + word_table + word_index + skill_vectors

    at_40k = projected(40_000)
    # Where does it actually stop fitting? Solve rather than guess.
    per_word = 256 + 8
    max_words = (FIFTEEN_MB - sparse - CARD_COUNT * DIMS) // per_word

    # 40k words fits -- with about 6% to spare, not the 87% the sparse-only number implies.
    assert at_40k <= FIFTEEN_MB, f"projected {at_40k:,} bytes at 40k words exceeds {FIFTEEN_MB:,}"
    # ...and the headroom is genuinely thin: a 60k vocabulary does not fit.
    assert projected(60_000) > FIFTEEN_MB, (
        "a 60k-word table was expected to blow the budget; if it now fits, the sparse side shrank "
        "and the vocabulary guidance should be re-derived rather than silently kept")

    print(f"\nprojected artifact at {DIMS} dims, {CARD_COUNT} skills:")
    print(f"  sparse only (this release)   {sparse:>12,} bytes  ({100*sparse/FIFTEEN_MB:5.1f}% of budget)")
    print(f"  + dense table @ 34k words    {projected(34_000):>12,} bytes  ({100*projected(34_000)/FIFTEEN_MB:5.1f}%)")
    print(f"  + dense table @ 40k words    {at_40k:>12,} bytes  ({100*at_40k/FIFTEEN_MB:5.1f}%)")
    print(f"  + dense table @ 60k words    {projected(60_000):>12,} bytes  ({100*projected(60_000)/FIFTEEN_MB:5.1f}%)  OVER")
    print(f"  => max vocabulary that fits at {DIMS} dims: {max_words:,} words")
