# Field-aware fusion spike

Start with [PROTOCOL.md](PROTOCOL.md); run `run.py` with the existing GPU venv, then `qa.py`. No downloads or production modifications.

The completed six-arm DEV experiment **does not pass** the prospective field-MLP gate. See [the full Polish readout](../../../docs/research/2026-09-06-agent-skill-scan/field-aware-results.md), results.json and qa-results.json. Sparse-only learned fusion is a nominated hypothesis, not an admitted improvement. Read IMPLEMENTATION-NOTES.md for the pre-training correction, larger token budget, truncation, candidate construction and timing limits.
