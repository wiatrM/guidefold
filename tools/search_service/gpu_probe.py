#!/usr/bin/env python3
"""Numerical equivalence only: pinned TEI GPU versus PyTorch FP16."""
import argparse, hashlib, json, os, sys
from itertools import islice
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.gpu import embed, PROMPT, WEIGHTS_SHA, sha
from tools.serve_spike.probe import load_queries
from tools.eval import corpora
from tools.serve_spike.repository import canonical


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--url", default="http://127.0.0.1:18766")
    p.add_argument(
        "--output", type=Path, default=ROOT / ".guidefold/checks/gpu-numerical.json"
    )
    args = p.parse_args()
    if sha(args.source / "model.safetensors") != WEIGHTS_SHA:
        raise ValueError("wrong checkpoint")
    queries, workload = load_queries(40)
    with (corpora.corpus_dir("skillret") / "data/skills/train.jsonl").open() as f:
        skills = [json.loads(x) for x in islice(f, 32)]
    docs = [
        " | ".join(
            [
                (s.get("name") or "").strip(),
                (s.get("description") or "").strip(),
                (
                    (s.get("skill_md") or "").strip() or s.get("description") or ""
                ).strip(),
            ]
        )
        for s in skills
    ]
    texts = (
        [PROMPT + q["query"] for q in queries]
        + docs
        + ["a", "한국어 API 검색", "Zażółć gęślą jaźń", "foo bar " * 3000]
    )
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer

    print("Capturing TEI vectors for 76 inputs", flush=True)
    a = np.asarray([embed(args.url, [text])[0] for text in texts], dtype=np.float32)
    torch.set_num_threads(8)
    m = SentenceTransformer(
        str(args.source),
        device="cuda",
        model_kwargs={"dtype": torch.float16, "attn_implementation": "sdpa"},
        trust_remote_code=False,
    )
    m.eval()
    m.max_seq_length = 8192
    with torch.inference_mode():
        b = m.encode(
            texts,
            batch_size=1,
            prompt="",
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)
    b /= np.linalg.norm(b, axis=1, keepdims=True)
    cosine = np.sum(a * b, axis=1)
    import urllib.request

    result = {
        "kind": "tei_pytorch_numerical_equivalence",
        "n": len(texts),
        "queries": 40,
        "documents": 32,
        "synthetic": 4,
        "minimum_cosine": float(cosine.min()),
        "mean_cosine": float(cosine.mean()),
        "max_absolute_error": float(np.abs(a - b).max()),
        "criterion_minimum_cosine": 0.999,
        "passed": bool(cosine.min() >= 0.999),
        "cosines": [float(x) for x in cosine],
        "workload": workload,
        "weights_sha256": WEIGHTS_SHA,
        "tei_info": json.load(urllib.request.urlopen(args.url + "/info")),
        "inputs_sha256": hashlib.sha256(canonical(texts)).hexdigest(),
        "query_labels_used": False,
        "quality_evaluated": False,
        "timing_is_slo_measurement": False,
    }
    args.output.write_bytes(canonical(result) + b"\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("cosines", "workload")}
        ),
        flush=True,
    )
    if not result["passed"]:
        raise SystemExit("numerical equivalence failed")


if __name__ == "__main__":
    main()
