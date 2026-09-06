#!/usr/bin/env python3
"""Post-hoc diagnostic (recorded as such in the report): did E1 learn our generator's query
distribution, or did training damage the encoder? E0 vs E1 on (a) 1,000 composite queries — same
generator, same style, NEVER seen by E1 (E1 trained on per-skill rows only) — and (b) 1,000 of E1's
own per-skill training queries (memorisation check). CPU-only so it can run beside E2 training.
Skill vectors: the dev_dense int8 caches already produced for E0 and E1 (same order asserted)."""
import json, random, sys, time, os
import numpy as np
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ["HF_HUB_OFFLINE"] = "1"
W = "/home/mike/projects/gf-e"; D = "/home/mike/.cache/guidefold/family-e-data"
C = W + "/tools/eval/.dev-dense-cache"
PROMPT = "Instruct: a skill search query, retrieve relevant skills that match the query\nQuery: "
SRC = {"E0": "/home/mike/.cache/guidefold/models/ThakiCloud__SKILLRET-Embedding-0.6B/0e10886e80a0aacc9efddc28282a258e2ab7eae1",
       "E1": "/home/mike/.cache/guidefold/finetune-checkpoints/E1/final"}
order = {k: json.load(open(f"{C}/{k}/skill_order.json")) for k in SRC}
assert order["E0"] == order["E1"], "skill order differs between caches"
urns = order["E0"]; id2row = {u.rsplit(":", 1)[1]: i for i, u in enumerate(urns)}
S = {k: np.load(f"{C}/{k}/skill_vectors.i8.npy").astype(np.float32) for k in SRC}
for k in S: S[k] /= (np.linalg.norm(S[k], axis=1, keepdims=True) + 1e-9)
rng = random.Random(20260906)
per = [json.loads(l) for l in open(f"{D}/per-skill-dev.jsonl")]; per = [r for r in per if r.get("queries") and r["skill_id"] in id2row]
comp = [json.loads(l) for l in open(f"{D}/composite-dev.jsonl")]; comp = [r for r in comp if r.get("query") and all(s in id2row for s in r["skill_ids"])]
ps = rng.sample(per, 1000); cs = rng.sample(comp, 1000)
cases = [("per_skill_train", rng.choice(r["queries"]), {r["skill_id"]}) for r in ps] + [("composite_unseen", r["query"], set(r["skill_ids"])) for r in cs]
from sentence_transformers import SentenceTransformer
import torch
def metrics(k):
    m = SentenceTransformer(SRC[k], device="cpu", model_kwargs={"dtype": torch.float32}); m.max_seq_length = 256
    t = time.time(); Q = m.encode([PROMPT + q for _, q, _ in cases], batch_size=32, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    print(k, "encoded", len(cases), "queries in", round(time.time() - t, 1), "s", flush=True)
    out = []
    for (kind, q, gold), qv in zip(cases, Q):
        sc = S[k] @ qv; top = np.argsort(-sc)[:10]; topids = [urns[i].rsplit(":", 1)[1] for i in top]
        out.append({"kind": kind, "hit1": float(topids[0] in gold), "recall10": len(gold & set(topids)) / len(gold),
                    "all_gold4": float(gold <= set(topids[:4]))})
    del m; return out
R = {k: metrics(k) for k in SRC}
def boot(a, b, n=1000, seed=0):
    a, b = np.asarray(a), np.asarray(b); d = b - a; r = np.random.RandomState(seed); idx = r.randint(0, len(d), (n, len(d)))
    bs = d[idx].mean(1); return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
res = {}
for kind in ("per_skill_train", "composite_unseen"):
    for met in ("hit1", "recall10", "all_gold4"):
        a = [x[met] for x in R["E0"] if x["kind"] == kind]; b = [x[met] for x in R["E1"] if x["kind"] == kind]
        d, lo, hi = boot(a, b); res[f"{kind}/{met}"] = {"E0": float(np.mean(a)), "E1": float(np.mean(b)), "delta_pp": 100 * d, "ci95_pp": [100 * lo, 100 * hi], "n": len(a)}
        print(f"{kind:17s} {met:9s} E0={np.mean(a):.3f} E1={np.mean(b):.3f} Δ={100*d:+.1f}pp [{100*lo:.1f}, {100*hi:.1f}]", flush=True)
json.dump({"note": __doc__, "prompt": PROMPT, "n_per_kind": 1000, "seed": 20260906, "results": res}, open(f"{D}/diag-e1-style.json", "w"), indent=1)
print("wrote", f"{D}/diag-e1-style.json")
