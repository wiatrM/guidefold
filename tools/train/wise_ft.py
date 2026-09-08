#!/usr/bin/env python3
"""tools/train/wise_ft.py — weight-space interpolation between two SentenceTransformer checkpoints
(WiSE-FT, Wortsman et al. 2022): theta(alpha) = alpha * theta_base + (1 - alpha) * theta_finetuned.

DENSE-PROGRAM.md v2.8 §4c, family E's E5 slot: the standard remedy when a full fine-tune
memorises its training pairs and loses general retrieval (the §3b diagnosis of E1). No training,
no data: one pass over the safetensors, written as a new checkpoint directory that is a copy of
the fine-tuned checkpoint's layout (tokenizer, pooling, config, and the family's train_meta.json
with an added `wise_ft` record) with only model.safetensors replaced.

Both checkpoints must have identical tensor names and shapes; dtype of the output follows the
fine-tuned checkpoint (bf16 here). Usage:

  python tools/train/wise_ft.py --base <E0 dir> --finetuned <E1 dir> --alpha 0.5 --out <dir>
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def interpolate(base_dir: Path, ft_dir: Path, alpha: float, out_dir: Path) -> dict:
    import torch
    from safetensors.torch import load_file, save_file
    b = load_file(str(base_dir / "model.safetensors"))
    f = load_file(str(ft_dir / "model.safetensors"))
    if set(b) != set(f):
        missing = sorted(set(b) ^ set(f))[:5]
        raise SystemExit(f"wise_ft: tensor names differ between checkpoints, e.g. {missing}")
    out = {}
    n_params = 0
    for k, tb in b.items():
        tf = f[k]
        if tb.shape != tf.shape:
            raise SystemExit(f"wise_ft: shape mismatch on {k}: {tuple(tb.shape)} vs {tuple(tf.shape)}")
        mixed = alpha * tb.to(torch.float32) + (1.0 - alpha) * tf.to(torch.float32)
        out[k] = mixed.to(tf.dtype).contiguous()
        n_params += tf.numel()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(ft_dir, out_dir, ignore=shutil.ignore_patterns("model.safetensors", "checkpoint-*"))
    save_file(out, str(out_dir / "model.safetensors"), metadata={"format": "pt"})
    meta_path = out_dir / "train_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
    meta["wise_ft"] = {"base": str(base_dir), "finetuned": str(ft_dir), "alpha": alpha,
                       "n_params": n_params, "dtype": str(next(iter(out.values())).dtype)}
    meta["identity"] = out_dir.parent.name if out_dir.name == "final" else out_dir.name
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True))
    return meta["wise_ft"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True)
    p.add_argument("--finetuned", required=True)
    p.add_argument("--alpha", type=float, required=True, help="weight on the BASE model")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    if not (0.0 <= a.alpha <= 1.0):
        raise SystemExit("wise_ft: --alpha must be in [0, 1]")
    rec = interpolate(Path(a.base), Path(a.finetuned), a.alpha, Path(a.out))
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
