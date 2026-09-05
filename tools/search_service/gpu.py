#!/usr/bin/env python3
"""Pinned SKILLRET/TEI adapter and resumable document encoding (operator only)."""
import argparse, base64, hashlib, json, os, shutil, struct, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.serve_spike.repository import canonical

MODEL = "ThakiCloud/SKILLRET-Embedding-0.6B"
REVISION = "0e10886e80a0aacc9efddc28282a258e2ab7eae1"
WEIGHTS_SHA = "f73118cac018ffa7ebb5a1ffbdf82034490dfb7f2559558f1e79277f1e8de172"
PROMPT = "Instruct: Given a skill search query, retrieve relevant skills that match the query\nQuery: "
IMAGE = "ghcr.io/huggingface/text-embeddings-inference@sha256:e47e625ced2385d3dbfdee79ba0380204578e0b27ef1a926783f9b3486aaf109"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare(args):
    source = args.source.resolve()
    dest = args.output.resolve()
    if source == dest:
        raise ValueError("adapter must not overwrite checkpoint")
    if sha(source / "model.safetensors") != WEIGHTS_SHA:
        raise ValueError("checkpoint weights mismatch")
    dest.mkdir(parents=True, exist_ok=True)
    for name in [
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
        "config_sentence_transformers.json",
    ]:
        target = dest / name
        if target.exists():
            if sha(target) != sha(source / name):
                raise ValueError("existing adapter file differs: " + name)
        elif name.endswith(".safetensors"):
            try:
                os.link(source / name, target)
            except OSError:
                shutil.copyfile(source / name, target)
        else:
            shutil.copyfile(source / name, target)
    config = json.loads((source / "config.json").read_text())
    if config["rope_parameters"]["rope_type"] != "default":
        raise ValueError("unsupported rope configuration")
    config["rope_theta"] = config["rope_parameters"]["rope_theta"]
    (dest / "config.json").write_bytes(canonical(config) + b"\n")
    (dest / "sentence_bert_config.json").write_bytes(
        canonical({"max_seq_length": 8192, "do_lower_case": False}) + b"\n"
    )
    (dest / "1_Pooling").mkdir(exist_ok=True)
    (dest / "2_Normalize").mkdir(exist_ok=True)
    pooling = {
        "word_embedding_dimension": 1024,
        "pooling_mode_cls_token": False,
        "pooling_mode_mean_tokens": False,
        "pooling_mode_max_tokens": False,
        "pooling_mode_mean_sqrt_len_tokens": False,
        "pooling_mode_weightedmean_tokens": False,
        "pooling_mode_lasttoken": True,
        "include_prompt": True,
    }
    (dest / "1_Pooling/config.json").write_bytes(canonical(pooling) + b"\n")
    modules = [
        {
            "idx": i,
            "name": str(i),
            "path": path,
            "type": "sentence_transformers.models." + kind,
        }
        for i, path, kind in [
            (0, "", "Transformer"),
            (1, "1_Pooling", "Pooling"),
            (2, "2_Normalize", "Normalize"),
        ]
    ]
    (dest / "modules.json").write_bytes(canonical(modules) + b"\n")
    manifest = {
        "format": "guidefold-encoder-v1",
        "model_id": MODEL,
        "revision": REVISION,
        "weights_sha256": WEIGHTS_SHA,
        "tei_image": IMAGE,
        "dtype": "float16",
        "dimensions": 1024,
        "max_length": 8192,
        "pooling": "last_token",
        "normalize": True,
        "query_prompt": PROMPT,
        "document_format": "name | description | skill_md-stripped-v1",
        "adapter_version": 1,
        "files_sha256": {
            name: sha(dest / name)
            for name in [
                "config.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "config_sentence_transformers.json",
                "sentence_bert_config.json",
                "modules.json",
                "1_Pooling/config.json",
            ]
        },
    }
    identity = hashlib.sha256(canonical(manifest)).hexdigest()
    (dest / "guidefold-encoder.json").write_bytes(canonical(manifest) + b"\n")
    env = ROOT / ".guidefold/compose/gpu.env"
    env.parent.mkdir(parents=True, exist_ok=True)
    env.write_text(
        f"GUIDEFOLD_ENCODER_ID={identity}\nGUIDEFOLD_MODEL_DIR={dest}\nGUIDEFOLD_PORT=18765\n"
    )
    print(
        json.dumps(
            {
                "encoder_id": identity,
                "model_directory": str(dest),
                "env_file": str(env),
                "weights_unchanged": True,
            }
        ),
        flush=True,
    )


def embed(url, texts):
    req = urllib.request.Request(
        url.rstrip("/") + "/embed",
        data=json.dumps(
            {"inputs": texts, "normalize": True, "truncate": True}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def encode_documents(args):
    import math

    snapshot = json.loads(args.snapshot.read_bytes())
    data = snapshot["snapshot"]
    assert hashlib.sha256(canonical(data)).hexdigest() == snapshot["sha256"]
    manifest = json.loads((args.model / "guidefold-encoder.json").read_bytes())
    identity = hashlib.sha256(canonical(manifest)).hexdigest()
    info = json.load(urllib.request.urlopen(args.url.rstrip("/") + "/info"))
    assert (
        info["served_model_name"] == identity
        and info["model_dtype"] == "float16"
        and info["max_input_length"] == 8192
    )
    cache = ROOT / ".guidefold/embedding-cache" / identity
    cache.mkdir(parents=True, exist_ok=True)
    document_texts = {}
    source_files = {}
    if args.skillret_split:
        from tools.eval import corpora, skillret
        from tools.serve_spike.server import load_cli_snapshot

        path = (
            corpora.corpus_dir("skillret")
            / "data/skills"
            / f"{args.skillret_split}.jsonl"
        )
        raw = [json.loads(line) for line in path.open()]
        cli, _ = load_cli_snapshot(ROOT / "skills/guidefold/scripts/guidefold")
        taxonomy = json.loads(
            (corpora.corpus_dir("skillret") / "data/taxonomy.json").read_text()
        )
        _, _, node_of = skillret.build_taxonomy(cli, taxonomy)
        converted, mapping = skillret.build_cards(raw, node_of)
        if canonical(converted) != canonical(data["cards"]):
            raise ValueError("raw corpus does not match published cards")
        for skill in raw:
            body = (skill.get("skill_md") or "").strip() or (
                skill.get("description") or ""
            )
            document_texts[mapping[skill["id"]]] = " | ".join(
                [
                    (skill.get("name") or "").strip(),
                    (skill.get("description") or "").strip(),
                    body.strip(),
                ]
            )
        source_files = {
            "skillret_split": args.skillret_split,
            "skills_sha256": sha(path),
            "formatter": "ThakiCloud/SKILLRET skillret/eval.py build_skill_text",
        }
    vectors = {}
    miss = []
    for urn, card in sorted(data["cards"].items()):
        # Product _body is SKILL.md; benchmark conversion's body differs, so raw corpus is explicit.
        text = document_texts.get(
            urn,
            " | ".join(
                [
                    card["name"].strip(),
                    card["description"].strip(),
                    card["_body"].strip(),
                ]
            ),
        )
        key = hashlib.sha256(
            canonical({"encoder_id": identity, "text": text, "role": "document"})
        ).hexdigest()
        path = cache / (key + ".f32le")
        revision = hashlib.sha256(
            json.dumps(card, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        if path.exists():
            vectors[urn] = {
                "revision": revision,
                "f32le": base64.b64encode(path.read_bytes()).decode(),
            }
        else:
            miss.append((urn, revision, text, path))
    print(
        json.dumps(
            {
                "documents": len(data["cards"]),
                "cached": len(vectors),
                "to_encode": len(miss),
                "encoder_id": identity,
            }
        ),
        flush=True,
    )
    for offset in range(0, len(miss), args.batch):
        chunk = miss[offset : offset + args.batch]
        rows = embed(args.url, [v[2] for v in chunk])
        if len(rows) != len(chunk):
            raise ValueError("encoder row count mismatch")
        for (urn, revision, text, path), row in zip(chunk, rows):
            if (
                len(row) != 1024
                or not all(math.isfinite(x) for x in row)
                or abs(sum(x * x for x in row) - 1) > 0.002
            ):
                raise ValueError("invalid vector")
            raw = struct.pack("<1024f", *row)
            temp = path.with_suffix(".tmp")
            temp.write_bytes(raw)
            temp.replace(path)
            vectors[urn] = {
                "revision": revision,
                "f32le": base64.b64encode(raw).decode(),
            }
        if offset // args.batch % 25 == 0:
            print(f"Encoded {min(offset+args.batch,len(miss))}/{len(miss)}", flush=True)
    payload = {
        "format": "guidefold-embeddings-v1",
        "repo_id": data["repo_id"],
        "snapshot_id": "repository:" + snapshot["sha256"],
        "encoder": manifest,
        "vectors": vectors,
        "document_source": source_files,
    }
    output = {
        "embeddings": payload,
        "sha256": hashlib.sha256(canonical(payload)).hexdigest(),
    }
    args.output.write_bytes(canonical(output) + b"\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "vectors": len(vectors),
                "encoder_id": identity,
                "sha256": output["sha256"],
            }
        ),
        flush=True,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--source", type=Path, required=True)
    a.add_argument("--output", type=Path, default=ROOT / ".guidefold/tei-model")
    b = sub.add_parser("encode")
    b.add_argument("--snapshot", type=Path, required=True)
    b.add_argument("--skillret-split", choices=["train", "test"])
    b.add_argument("--model", type=Path, default=ROOT / ".guidefold/tei-model")
    b.add_argument("--url", default="http://127.0.0.1:18766")
    b.add_argument("--batch", type=int, choices=range(1, 17), default=8)
    b.add_argument(
        "--output", type=Path, default=ROOT / ".guidefold/compose/embeddings.json"
    )
    args = p.parse_args()
    prepare(args) if args.command == "prepare" else encode_documents(args)


if __name__ == "__main__":
    main()
