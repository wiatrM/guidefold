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

VOCAB_SIZE = 900
NODE_COUNT = 25
CARD_COUNT = 2000
FIFTEEN_MB = 15 * 1024 * 1024


def _make_vocab(rng):
    # Fake but word-shaped tokens (consonant/vowel alternation) so tokenize() sees plausible
    # natural-language terms rather than e.g. pure digit strings it might treat specially.
    consonants, vowels = "bcdfghjklmnprstvwz", "aeiou"

    def word():
        n = rng.randint(3, 5)
        chars = []
        for i in range(n):
            pool = consonants if i % 2 == 0 else vowels
            chars.append(rng.choice(pool))
        return "".join(chars)
    return [word() for _ in range(VOCAB_SIZE)]


def _make_nodes():
    # A flat set of team nodes plus _root, similar in shape to a real guidefold.yaml at scale.
    nodes = {"_root": {"paths": ["**"], "owner": "platform"}}
    for i in range(NODE_COUNT):
        nodes[f"team{i:02d}"] = {"paths": [f"team{i:02d}/**"], "owner": f"team-{i:02d}"}
    return nodes


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
        desc_words = [rng.choice(vocab) for _ in range(15)]
        body_words = [rng.choice(vocab) for _ in range(120)]
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
