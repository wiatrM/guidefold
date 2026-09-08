"""Tests for tools/train/finetune.py — the family E fine-tuning runner (DENSE-PROGRAM.md v2.6).

Actual GPU training (cmd_train's SentenceTransformer/old_fit/MultipleNegativesRankingLoss/
NoDuplicatesDataLoader calls) is never exercised here — it needs the GPU venv and a real base
model, and is run manually (see docs/reports/bakeoff/DEV-E-synthetic-training-2026-09-05.md for
that transcript). What's tested for real, on tiny synthetic fixtures: the join between the three
generated-data files into training rows (the one place a silent drop would quietly ship a weaker
recipe without any test noticing), its per-reason drop counters, the hard-negatives index's
order-independent composite key, seeding, and the resumable-checkpoint picker.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TRAIN_DIR = REPO_ROOT / "tools" / "train"
sys.path.insert(0, str(TRAIN_DIR))

import finetune  # tools/train/finetune.py -- itself inserts TRAIN_DIR/EVAL_DIR onto sys.path


# --------------------------------------------------------------------------- torch-free module boundary
def test_finetune_module_imports_cleanly_with_torch_blocked(monkeypatch):
    """cmd_train is the only subcommand that needs torch/sentence-transformers, and it reaches
    them only inside its own function body -- never at module scope -- so importing finetune.py
    (and, transitively, synth_queries.py) must succeed even with torch poisoned. Same technique as
    tests/test_dev_dense.py's own torch-boundary test."""
    monkeypatch.setitem(sys.modules, "torch", None)
    import importlib
    import importlib.util
    from importlib.machinery import SourceFileLoader

    class _TorchIsForbidden:
        def find_spec(self, name, path=None, target=None):
            if name == "torch" or name.startswith("torch."):
                raise ImportError("torch must not be imported at finetune module scope")
            return None

    blocker = _TorchIsForbidden()
    sys.meta_path.insert(0, blocker)
    try:
        loader = SourceFileLoader("finetune_torch_check", str(TRAIN_DIR / "finetune.py"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        assert hasattr(module, "build_training_rows")
    finally:
        sys.meta_path.remove(blocker)


# --------------------------------------------------------------------------- fixtures
def _skills():
    return [
        {"id": "s1", "name": "invoice-reconciler", "description": "match invoices to POs",
         "body": "reconcile vendor invoices against purchase orders",
         "major": "finance", "sub": "accounts-payable"},
        {"id": "s2", "name": "po-status-lookup", "description": "look up PO approval status",
         "body": "returns the current stage of a purchase order",
         "major": "finance", "sub": "accounts-payable"},
        {"id": "s3", "name": "vendor-onboarding", "description": "onboard a new vendor",
         "body": "collects tax forms and verifies banking details",
         "major": "finance", "sub": "vendor-management"},
        {"id": "s4", "name": "log-tailer", "description": "tail a service log",
         "body": "streams the last N lines of a log file", "major": "ops", "sub": "observability"},
    ]


def _per_skill_rec(skill_id, queries):
    return {"skill_id": skill_id, "raw": None, "queries": queries}


def _hard_neg_flat(skill_id, negs):
    return {"skill_ids": [skill_id], "hard_negatives": negs}


def _hard_neg_composite(skill_ids, by_skill):
    return {"skill_ids": list(skill_ids), "hard_negatives_by_skill": by_skill}


# --------------------------------------------------------------------------- skill_text_for_training
def test_skill_text_for_training_never_truncates_body():
    long_body = "word " * (finetune.synth_queries.MAX_BODY_CHARS // len("word ") + 500)
    skill = {"id": "s1", "name": "n", "description": "d", "body": long_body}
    text = finetune.skill_text_for_training(skill)
    assert long_body.strip() in text  # full body present, not cut at MAX_BODY_CHARS like the
                                        # generator prompt's own skill_text(..., default) would be
    truncated = finetune.synth_queries.skill_text(skill)  # default max_body_chars
    assert len(truncated) < len(text)


# --------------------------------------------------------------------------- _load_jsonl
def test_load_jsonl_skips_blank_lines(tmp_path):
    p = tmp_path / "f.jsonl"
    p.write_text('{"a": 1}\n\n{"a": 2}\n')
    assert finetune._load_jsonl(p) == [{"a": 1}, {"a": 2}]


def test_load_jsonl_missing_file_is_empty_list(tmp_path):
    assert finetune._load_jsonl(tmp_path / "does-not-exist.jsonl") == []


# --------------------------------------------------------------------------- _hard_negatives_index
def test_hard_negatives_index_splits_flat_and_composite_records():
    per_skill, composite = finetune._hard_negatives_index([
        _hard_neg_flat("s1", ["s2", "s3", "s4"]),
        _hard_neg_composite(["s1", "s2"], {"s1": ["s3"], "s2": ["s4"]}),
    ])
    assert per_skill == {"s1": ["s2", "s3", "s4"]}
    assert composite == {("s1", "s2"): {"s1": ["s3"], "s2": ["s4"]}}


def test_hard_negatives_index_composite_key_is_order_independent():
    """A composite hard-negatives record written with skill_ids in one order must still be found
    by a training-row join that has the same set in a different order -- sample_hard_negatives is
    fully deterministic given (skill_id, gold_set, seed), so the join key is the *set*, not the
    order the generator happened to sample them in."""
    _, composite = finetune._hard_negatives_index([
        _hard_neg_composite(["s2", "s1"], {"s1": ["s3"], "s2": ["s4"]}),
    ])
    assert ("s1", "s2") in composite


# --------------------------------------------------------------------------- build_training_rows
def test_build_training_rows_per_skill_happy_path():
    hard_negs = [_hard_neg_flat("s1", ["s2", "s3", "s4"])]
    per_skill = [_per_skill_rec("s1", ["how do I match an invoice to a PO?",
                                        "reconcile vendor invoices"])]
    out = finetune.build_training_rows(_skills(), per_skill, [], hard_negs, n_neg=3)
    rows, stats = out["rows"], out["stats"]
    assert stats["per_skill_rows"] == 2
    assert stats["total_rows"] == 2
    assert all(r["kind"] == "per_skill" for r in rows)
    assert rows[0]["positive_id"] == "s1"
    assert rows[0]["positive_text"] == finetune.skill_text_for_training(_skills()[0])
    assert rows[0]["negative_ids"] == ["s2", "s3", "s4"]
    assert len(rows[0]["negative_texts"]) == 3
    assert all(neg not in (rows[0]["positive_text"],) for neg in rows[0]["negative_texts"])


def test_build_training_rows_drops_rows_with_no_queries():
    out = finetune.build_training_rows(
        _skills(), [_per_skill_rec("s1", None)], [], [_hard_neg_flat("s1", ["s2", "s3", "s4"])])
    assert out["stats"]["dropped_no_queries"] == 1
    assert out["stats"]["total_rows"] == 0


def test_build_training_rows_drops_rows_for_unknown_skill():
    out = finetune.build_training_rows(
        _skills(), [_per_skill_rec("s-nope", ["q"])], [], [])
    assert out["stats"]["dropped_unknown_skill"] == 1


def test_build_training_rows_drops_rows_missing_hard_negatives():
    out = finetune.build_training_rows(
        _skills(), [_per_skill_rec("s1", ["q"])], [], [])  # no hard-negatives record for s1 at all
    assert out["stats"]["dropped_no_hard_negatives"] == 1


def test_build_training_rows_drops_rows_with_wrong_negative_count():
    out = finetune.build_training_rows(
        _skills(), [_per_skill_rec("s1", ["q"])], [],
        [_hard_neg_flat("s1", ["s2"])], n_neg=3)  # only 1 negative, not 3
    assert out["stats"]["dropped_wrong_negative_count"] == 1


def test_build_training_rows_drops_rows_with_unknown_negative_id():
    out = finetune.build_training_rows(
        _skills(), [_per_skill_rec("s1", ["q"])], [],
        [_hard_neg_flat("s1", ["s2", "s3", "s-ghost"])], n_neg=3)
    assert out["stats"]["dropped_unknown_negative_id"] == 1
    assert out["stats"]["total_rows"] == 0


def test_build_training_rows_composite_one_row_per_gold_skill_with_its_own_negatives():
    composite = [{"skill_ids": ["s1", "s2"], "raw": None,
                  "query": "onboard a vendor and reconcile their first invoice"}]
    hard_negs = [_hard_neg_composite(["s1", "s2"], {"s1": ["s3", "s4", "s2"],
                                                      "s2": ["s3", "s4", "s1"]})]
    # note: gold-excluding negatives would never include s1/s2 themselves in real sampling; this
    # fixture only needs *some* 3-length lists to exercise the join, not realistic sampling.
    out = finetune.build_training_rows(_skills(), [], composite, hard_negs, n_neg=3)
    rows, stats = out["rows"], out["stats"]
    assert stats["composite_rows"] == 2
    by_positive = {r["positive_id"]: r for r in rows}
    assert set(by_positive) == {"s1", "s2"}
    assert all(r["query"] == composite[0]["query"] for r in rows)
    assert by_positive["s1"]["negative_ids"] == ["s3", "s4", "s2"]
    assert by_positive["s2"]["negative_ids"] == ["s3", "s4", "s1"]


def test_build_training_rows_composite_join_tolerates_reordered_skill_ids():
    """The query record and the hard-negatives record may list skill_ids in different orders
    (independent pipeline stages); the join must still succeed."""
    composite = [{"skill_ids": ["s2", "s1"], "query": "q"}]
    hard_negs = [_hard_neg_composite(["s1", "s2"], {"s1": ["s3", "s4", "s2"],
                                                      "s2": ["s3", "s4", "s1"]})]
    out = finetune.build_training_rows(_skills(), [], composite, hard_negs, n_neg=3)
    assert out["stats"]["composite_rows"] == 2


def test_build_training_rows_composite_drops_when_hard_negatives_missing():
    composite = [{"skill_ids": ["s1", "s2"], "query": "q"}]
    out = finetune.build_training_rows(_skills(), [], composite, [], n_neg=3)
    assert out["stats"]["dropped_no_hard_negatives"] == 1
    assert out["stats"]["total_rows"] == 0


def test_build_training_rows_composite_skips_query_with_no_query_text():
    composite = [{"skill_ids": ["s1", "s2"], "query": None}]
    out = finetune.build_training_rows(_skills(), [], composite, [], n_neg=3)
    assert out["stats"]["dropped_no_queries"] == 1


# --------------------------------------------------------------------------- _seed_everything
def test_seed_everything_makes_random_deterministic():
    import random
    finetune._seed_everything(20260905)
    a = [random.random() for _ in range(5)]
    finetune._seed_everything(20260905)
    b = [random.random() for _ in range(5)]
    assert a == b


# --------------------------------------------------------------------------- _latest_checkpoint_dir
def test_latest_checkpoint_dir_none_when_path_missing(tmp_path):
    assert finetune._latest_checkpoint_dir(tmp_path / "nope") is None


def test_latest_checkpoint_dir_none_when_no_numbered_subdirs(tmp_path):
    (tmp_path / "final").mkdir()
    assert finetune._latest_checkpoint_dir(tmp_path) is None


def test_latest_checkpoint_dir_picks_highest_step_and_ignores_non_numeric(tmp_path):
    for name in ("100", "2000", "500", "final"):
        (tmp_path / name).mkdir()
    got = finetune._latest_checkpoint_dir(tmp_path)
    assert got == tmp_path / "2000"


# --------------------------------------------------------------------------- CLI wiring
def test_require_gpu_venv_raises_unless_force_any_python():
    with pytest.raises(SystemExit):
        finetune._require_gpu_venv(False)
    finetune._require_gpu_venv(True)  # must not raise


def test_cmd_rows_end_to_end_via_main(tmp_path, capsys):
    skills_file = tmp_path / "skills.json"
    skills_file.write_text(json.dumps(_skills()))
    per_skill_file = tmp_path / "per_skill.jsonl"
    per_skill_file.write_text(json.dumps(_per_skill_rec("s1", ["q1", "q2"])) + "\n")
    hard_neg_file = tmp_path / "hard_negs.jsonl"
    hard_neg_file.write_text(json.dumps(_hard_neg_flat("s1", ["s2", "s3", "s4"])) + "\n")
    out_file = tmp_path / "rows.jsonl"

    rc = finetune.main([
        "rows", "--skills-file", str(skills_file),
        "--per-skill-file", str(per_skill_file),
        "--hard-negatives-file", str(hard_neg_file),
        "--out", str(out_file),
    ])
    assert rc == 0
    lines = [json.loads(l) for l in out_file.read_text().splitlines() if l]
    assert len(lines) == 2
    captured = capsys.readouterr()
    assert '"per_skill_rows": 2' in captured.out


def test_run_subcommand_n_negatives_defaults_to_hard_negatives_n(tmp_path):
    skills_file = tmp_path / "skills.json"
    skills_file.write_text(json.dumps(_skills()))
    per_skill_file = tmp_path / "per_skill.jsonl"
    per_skill_file.write_text("")
    hard_neg_file = tmp_path / "hard_negs.jsonl"
    hard_neg_file.write_text("")

    seen = []
    import argparse as _argparse

    def fake_cmd_rows(args):
        seen.append(args)
        return 0

    orig = finetune.cmd_rows
    finetune.cmd_rows = fake_cmd_rows
    try:
        finetune.main([
            "rows", "--skills-file", str(skills_file),
            "--per-skill-file", str(per_skill_file),
            "--hard-negatives-file", str(hard_neg_file),
        ])
    finally:
        finetune.cmd_rows = orig
    assert seen[-1].n_negatives == finetune.HARD_NEGATIVES_N == 3


# --------------------------------------------------------------------------- eval regime must not inherit the train cap
class _FakeTok:
    def __init__(self, n):
        self.model_max_length = n


class _FakeST:
    def __init__(self, cap, tok_cap):
        self.max_seq_length = cap
        self.tokenizer = _FakeTok(tok_cap)


def test_restore_eval_seq_length_undoes_train_cap_on_model_and_tokenizer():
    """SentenceTransformer.save() persists max_seq_length into tokenizer_config.json, so a
    checkpoint trained with a 1024 cap would be *evaluated* at 1024 while E0 is evaluated at the
    base's 8192 -- a changed document representation, not a training effect (E1, 2026-09-06).
    The cap must be undone before save on both the model and its tokenizer."""
    m = _FakeST(cap=1024, tok_cap=1024)
    finetune.restore_eval_seq_length(m, 8192)
    assert m.max_seq_length == 8192
    assert m.tokenizer.model_max_length == 8192


def test_restore_eval_seq_length_noop_when_base_had_no_limit():
    m = _FakeST(cap=512, tok_cap=512)
    finetune.restore_eval_seq_length(m, None)
    assert m.max_seq_length == 512 and m.tokenizer.model_max_length == 512
