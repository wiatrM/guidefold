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
import argparse
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--base-id", default="E0"); ap.add_argument("--base-src", default="/home/mike/.cache/guidefold/models/ThakiCloud__SKILLRET-Embedding-0.6B/0e10886e80a0aacc9efddc28282a258e2ab7eae1")
ap.add_argument("--cand-id", default="E1"); ap.add_argument("--cand-src", default="/home/mike/.cache/guidefold/finetune-checkpoints/E1/final")
ap.add_argument("--out", default=None, help="result JSON (default: <D>/diag-<cand>-style.json)")
ap.add_argument("--skill-vectors", choices=["cache", "encode"], default="cache",
                help="cache: dev_dense int8 caches for both ids (fast); encode: embed the 10,123 skills here on CPU for the candidate (slow, only when no cache exists)")
A = ap.parse_args()
SRC = {A.base_id: A.base_src, A.cand_id: A.cand_src}
order = {k: json.load(open(f"{C}/{k}/skill_order.json")) for k in SRC if os.path.isfile(f"{C}/{k}/skill_order.json")}
urns = order[A.base_id]; id2row = {u.rsplit(":", 1)[1]: i for i, u in enumerate(urns)}
S = {}
for k in SRC:
    if k in order:
        assert order[k] == urns, "skill order differs between caches"
        S[k] = np.load(f"{C}/{k}/skill_vectors.i8.npy").astype(np.float32)
        S[k] /= (np.linalg.norm(S[k], axis=1, keepdims=True) + 1e-9)
rng = random.Random(20260906)
per = [json.loads(l) for l in open(f"{D}/per-skill-dev.jsonl")]; per = [r for r in per if r.get("queries") and r["skill_id"] in id2row]
comp = [json.loads(l) for l in open(f"{D}/composite-dev.jsonl")]; comp = [r for r in comp if r.get("query") and all(s in id2row for s in r["skill_ids"])]
ps = rng.sample(per, 1000); cs = rng.sample(comp, 1000)
cases = [("per_skill_train", rng.choice(r["queries"]), {r["skill_id"]}) for r in ps] + [("composite_unseen", r["query"], set(r["skill_ids"])) for r in cs]
from sentence_transformers import SentenceTransformer
import torch
sys.path.insert(0, W + "/tools/eval")
def skill_texts():
    import corpora, dev_sparse, dev_dense
    skills = corpora.load_skillret_dev()["skills"]
    cards, nodes, sidurn, _ = dev_sparse.corpus_to_cards(skills)
    texts = dev_dense.skill_texts_for_cards(cards)
    return [texts[u] for u in urns]
def metrics(k):
    m = SentenceTransformer(SRC[k], device="cpu", model_kwargs={"dtype": torch.float32}); m.max_seq_length = 256
    if k not in S:  # no dev_dense cache for this candidate: embed the skills here (CPU, cap 2048 tokens — recorded)
        m.max_seq_length = 2048
        t = time.time(); V = m.encode(skill_texts(), batch_size=8, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        print(k, "encoded", len(V), "skills on CPU (cap 2048) in", round(time.time() - t, 1), "s", flush=True)
        S[k] = V.astype(np.float32); m.max_seq_length = 256
    t = time.time(); Q = m.encode([PROMPT + q for _, q, _ in cases], batch_size=32, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    print(k, "encoded", len(cases), "queries in", round(time.time() - t, 1), "s", flush=True)
    out = []
    for (kind, q, gold), qv in zip(cases, Q):
        sc = S[k] @ qv; top = np.argsort(-sc)[:10]; topids = [urns[i].rsplit(":", 1)[1] for i in top]
        out.append({"kind": kind, "hit1": float(topids[0] in gold), "recall10": len(gold & set(topids)) / len(gold),
                    "all_gold4": float(gold <= set(topids[:4]))})
    del m; return out
R = {k: metrics(k) for k in (A.base_id, A.cand_id)}
def boot(a, b, n=1000, seed=0):
    a, b = np.asarray(a), np.asarray(b); d = b - a; r = np.random.RandomState(seed); idx = r.randint(0, len(d), (n, len(d)))
    bs = d[idx].mean(1); return float(d.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
res = {}
for kind in ("per_skill_train", "composite_unseen"):
    for met in ("hit1", "recall10", "all_gold4"):
        a = [x[met] for x in R[A.base_id] if x["kind"] == kind]; b = [x[met] for x in R[A.cand_id] if x["kind"] == kind]
        d, lo, hi = boot(a, b); res[f"{kind}/{met}"] = {"base": float(np.mean(a)), "cand": float(np.mean(b)), "delta_pp": 100 * d, "ci95_pp": [100 * lo, 100 * hi], "n": len(a)}
        print(f"{kind:17s} {met:9s} {A.base_id}={np.mean(a):.3f} {A.cand_id}={np.mean(b):.3f} Δ={100*d:+.1f}pp [{100*lo:.1f}, {100*hi:.1f}]", flush=True)
g = res["composite_unseen/recall10"]
guard = {"rule": "v2.8 §4c rule 1: recall@10 on unseen same-generator composite: delta >= 0 and CI low > -2pp",
         "delta_pp": g["delta_pp"], "ci95_pp": g["ci95_pp"], "pass": bool(g["delta_pp"] >= 0 and g["ci95_pp"][0] > -2.0)}
print("FORGETTING GUARD", A.cand_id, "vs", A.base_id, "->", "PASS" if guard["pass"] else "FAIL", guard, flush=True)
out = A.out or f"{D}/diag-{A.cand_id}-style.json"
json.dump({"note": __doc__, "base": A.base_id, "candidate": A.cand_id, "prompt": PROMPT, "n_per_kind": 1000, "seed": 20260906,
           "skill_vectors": {k: ("dev_dense int8 cache" if k in order else "CPU encode cap 2048") for k in SRC}, "results": res, "guard": guard},
          open(out, "w"), indent=1)
print("wrote", out)
