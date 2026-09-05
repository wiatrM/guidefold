#!/usr/bin/env python3
"""tools/eval/composer_model.py — the model composer (ADR-0024 §4, DENSE-PROGRAM.md v2.4 family C).

Evaluated ONLY here, in tools/eval/. It never imports, shells out to, or otherwise touches
`skills/guidefold/scripts/guidefold` — ADR-0024 §4's "two admitted implementations behind one
interface" keeps the model composer entirely outside the shipped CLI, which stays stdlib+PyYAML
only. This module knows nothing about `Router`, `Index`, or the product's ranking; it is a pure
function of (query text, a short list of already-ranked, already-admissible candidate dicts) to a
selection — the same interface `Router._select_composed` implements deterministically inside the
CLI. A caller (an eval harness) is responsible for deciding a query needs this at all — ADR-0024
§4's cost-bounding detector — and for building the candidate list from its own already-scored,
already-policy-filtered pipeline.

Calls the local `claude` CLI (this repo's own coding assistant, used here purely as a lightweight
JSON API — see the flags on CLAUDE_FLAGS below) with `--model haiku --output-format json`. A
minimal system prompt and `--tools ""` avoid loading this repo's CLAUDE.md/skill context, which
otherwise multiplies cost and latency roughly 30x for no benefit to a single-turn JSON-in/JSON-out
call (measured 2026-09-05: $0.0516 -> $0.0015/call, 6s -> 2.5s).

Replay cache: keyed by (query_id, sha256 of the exact candidate list sent — urn/name/description/
digest, canonically serialized). A dev/eval run that is interrupted and resumed, or re-run after
adding an arm, never re-pays for a query whose candidate set is unchanged; the cache is
invalidated automatically the moment upstream ranking changes what the composer even sees,
without the caller having to reason about staleness. Stored as an append-only JSONL file so a
crash mid-run loses at most the one in-flight call.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(__file__).resolve().parent / ".composer-model-cache"
CACHE_FILE = CACHE_DIR / "cache.jsonl"

DEFAULT_MODEL = "haiku"
DEFAULT_K = 4
DEFAULT_TIMEOUT_S = 30

SYSTEM_PROMPT = (
    "You select which of a short list of software skill/tool cards are needed to fully answer a "
    "user request. Reply with ONLY a single JSON object, no markdown fences, no commentary: "
    '{"selected": ["<urn>", ...], "cannot_fit": <bool>}. "selected" holds at most '
    f"{DEFAULT_K} urns, copied verbatim from the candidate list, ordered most-important first. "
    'Set "cannot_fit" to true if the request genuinely needs more distinct skills than fit in '
    f"{DEFAULT_K} slots — still return your best {DEFAULT_K} in that case, do not return fewer "
    "just because more would be needed. Never invent a urn that was not in the candidate list."
)

CLAUDE_FLAGS = ["--safe-mode", "--tools", "", "--no-session-persistence",
                "--system-prompt", SYSTEM_PROMPT]


# --------------------------------------------------------------------------- prompt
def build_prompt(query: str, candidates: list[dict], k: int = DEFAULT_K) -> str:
    """`candidates` are dicts with at least urn/name/description; digest and triggers are
    included when present. Truncates description/digest defensively (a card's own author-written
    text, but this is a cost-bounded call and a runaway field must not blow up the prompt)."""
    lines = [f"Request: {query!r}", "", f"Candidate skills (choose at most {k}):"]
    for c in candidates:
        desc = (c.get("description") or c.get("digest") or "")[:300]
        lines.append(f"- urn={c['urn']!r} name={c.get('name', '')!r} description={desc!r}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- model call
def call_model(prompt: str, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT_S) -> dict:
    """Runs the local `claude -p` CLI once. Returns {"ok": bool, "raw": str, "error": str|None,
    "latency_s": float, "cost_usd": float|None}. Never raises: a subprocess failure, timeout, or
    malformed wrapper JSON is reported in the dict, not thrown, so a whole eval run never dies on
    one bad call."""
    t0 = time.time()
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--output-format", "json", *CLAUDE_FLAGS],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "raw": "", "error": f"timeout after {timeout}s",
                "latency_s": time.time() - t0, "cost_usd": None}
    except FileNotFoundError as e:
        return {"ok": False, "raw": "", "error": f"claude CLI not found: {e}",
                "latency_s": time.time() - t0, "cost_usd": None}
    latency_s = time.time() - t0
    if proc.returncode != 0:
        return {"ok": False, "raw": proc.stdout, "error": f"exit {proc.returncode}: {proc.stderr[:500]}",
                "latency_s": latency_s, "cost_usd": None}
    try:
        wrapper = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {"ok": False, "raw": proc.stdout, "error": f"wrapper not JSON: {e}",
                "latency_s": latency_s, "cost_usd": None}
    result = wrapper.get("result", "")
    cost = wrapper.get("cost_usd") or wrapper.get("total_cost_usd")
    return {"ok": True, "raw": result, "error": None, "latency_s": latency_s, "cost_usd": cost}


# --------------------------------------------------------------------------- parsing
def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def parse_selection(raw: str, candidate_urns: set, k: int = DEFAULT_K) -> dict:
    """Parses the model's reply into {"selected": [urn, ...], "cannot_fit": bool, "error": str|None}.
    Defensive by construction: a hallucinated urn is dropped (never trusted onto the wire), a
    selection over k is truncated (never silently — see the cannot_fit flag), and any parse
    failure degrades to an empty, cannot_fit=True result rather than raising — the model's output
    is untrusted text, not a contract."""
    try:
        obj = json.loads(_strip_fences(raw))
        selected_raw = obj.get("selected", [])
        cannot_fit = bool(obj.get("cannot_fit", False))
        if not isinstance(selected_raw, list):
            raise ValueError("'selected' is not a list")
    except Exception as e:
        return {"selected": [], "cannot_fit": True, "error": f"parse failure: {e}"}
    selected = [u for u in selected_raw if isinstance(u, str) and u in candidate_urns]
    if len(selected) < len(selected_raw):
        # the model returned something that wasn't a verbatim candidate urn (hallucinated or
        # malformed) — dropped, never trusted onto the wire, but flag it for visibility.
        cannot_fit = True
    if len(selected) > k:
        selected = selected[:k]
        cannot_fit = True
    return {"selected": selected, "cannot_fit": cannot_fit, "error": None}


# --------------------------------------------------------------------------- replay cache
def _cache_key(query_id: str, candidates: list[dict]) -> str:
    payload = json.dumps(
        [{"urn": c["urn"], "name": c.get("name", ""), "description": c.get("description", ""),
          "digest": c.get("digest", "")} for c in candidates],
        sort_keys=True, ensure_ascii=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{query_id}:{digest}"


class ReplayCache:
    """Append-only JSONL cache, loaded fully into memory on construction (dev-set scale: at most
    a few thousand records). One record per (query_id, candidate-set) pair actually sent to the
    model — never per query alone, so a re-ranked candidate set for the same query_id (a
    different arm) is correctly treated as a cache miss."""

    def __init__(self, path: Path = CACHE_FILE):
        self.path = path
        self.data: dict[str, dict] = {}
        if path.exists():
            with path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    self.data[rec["key"]] = rec

    def get(self, key: str) -> Optional[dict]:
        return self.data.get(key)

    def put(self, key: str, record: dict) -> None:
        self.data[key] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    def __len__(self) -> int:
        return len(self.data)


# --------------------------------------------------------------------------- entry point
def compose(query_id: str, query: str, candidates: list[dict], k: int = DEFAULT_K,
            model: str = DEFAULT_MODEL, cache: Optional[ReplayCache] = None,
            timeout: int = DEFAULT_TIMEOUT_S) -> dict:
    """Returns {"selected": [urn,...], "cannot_fit": bool, "cached": bool, "latency_s": float,
    "cost_usd": float|None, "error": str|None}. `candidates` should already be ADR-0024 §4's
    admissible, ranked, <=15-item pool — this function does not filter, rank, or cap it further
    beyond urn validation in parse_selection.
    """
    candidate_urns = {c["urn"] for c in candidates}
    key = _cache_key(query_id, candidates)
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            out = dict(hit["result"])
            out["cached"] = True
            out["latency_s"] = 0.0
            return out

    prompt = build_prompt(query, candidates, k=k)
    called = call_model(prompt, model=model, timeout=timeout)
    if not called["ok"]:
        result = {"selected": [], "cannot_fit": True, "error": called["error"]}
    else:
        result = parse_selection(called["raw"], candidate_urns, k=k)

    out = {**result, "cached": False, "latency_s": called["latency_s"], "cost_usd": called["cost_usd"]}
    if cache is not None:
        cache.put(key, {"key": key, "query_id": query_id, "model": model, "result": {
            "selected": result["selected"], "cannot_fit": result["cannot_fit"], "error": result["error"],
        }, "cost_usd": called["cost_usd"], "ts": time.time()})
    return out


def main(argv=None) -> int:
    """Tiny manual smoke-test entry point: `python3 tools/eval/composer_model.py "<query>" urn1 urn2 ...`
    — not used by the dev harness (which calls `compose()` directly), kept for quick manual checks
    against the real `claude` CLI without spinning up the full eval harness."""
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print("usage: composer_model.py <query> <urn> [urn ...]", file=sys.stderr)
        return 2
    query, urns = args[0], args[1:]
    candidates = [{"urn": u, "name": u.rsplit(":", 1)[-1], "description": u} for u in urns]
    out = compose("manual", query, candidates)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
