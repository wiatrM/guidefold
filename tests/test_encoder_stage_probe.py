"""CPU-only checks for instrumentation ownership and interval accounting."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("e11b_encoder_stage_probe", ROOT / "tools/serve_spike/encoder_stage_probe.py")
stage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stage
spec.loader.exec_module(stage)


@pytest.mark.parametrize("intervals,expected", [([], 0), ([(1, 5), (2, 3)], 4),
    ([(5, 7), (1, 2)], 3), ([(1, 3), (2, 5), (5, 6)], 5)])
def test_union_counts_nested_and_disjoint_cpu_spans_once(intervals, expected):
    assert stage.union_duration(intervals) == expected


def test_union_rejects_reversed_interval():
    with pytest.raises(ValueError, match="negative_stage_interval"):
        stage.union_duration([(2, 1)])


def test_patches_restore_owned_and_inherited_callables():
    class Owner:
        def call(self, value):
            return value + 1
    inherited, owned = Owner(), Owner()
    owned.call = lambda value: value + 2
    original_owned = owned.call
    patches = stage.Patches()
    patches.set(inherited, "call", lambda value: value + 9)
    patches.set(owned, "call", lambda value: value + 10)
    assert inherited.call(1) == 10
    patches.close()
    patches.close()
    assert "call" not in vars(inherited)
    assert inherited.call(1) == 2
    assert owned.call is original_owned


class FakeEvent:
    def record(self):
        pass
    def query(self):
        return True
    def elapsed_time(self, other):
        return 0.125


class Features:
    device = SimpleNamespace(type="cpu")
    shape = (1, 7)
    def sum(self, dim):
        assert dim == 1
        return SimpleNamespace(tolist=lambda: [5])


class Tokenizer:
    def __call__(self, inputs, **kwargs):
        return {"input_ids": Features(), "attention_mask": Features()}


class Transformer:
    def __init__(self):
        self.tokenizer = Tokenizer()
    def forward(self, features):
        return features


class Pooling:
    def forward(self, features):
        return features


class Normalize:
    def __init__(self, functional):
        self.functional = functional
    def forward(self, features):
        return self.functional.normalize(features)


class Model:
    def __init__(self, torch):
        self.modules = [Transformer(), Pooling(), Normalize(torch.nn.functional)]
    def named_children(self):
        return [(str(i), module) for i, module in enumerate(self.modules)]
    def to(self, device):
        return self
    def eval(self):
        return self
    def preprocess(self, inputs, **kwargs):
        return self.modules[0].tokenizer(inputs, **kwargs)


@pytest.mark.parametrize("fail", [False, True])
def test_reversible_wrappers_observe_required_stages_and_restore_after_error(monkeypatch, fail):
    functional = SimpleNamespace(normalize=lambda data: data)
    torch = SimpleNamespace(nn=SimpleNamespace(functional=functional),
        cuda=SimpleNamespace(Event=lambda **kwargs: FakeEvent(), synchronize=lambda: None))
    model = Model(torch)
    module = sys.modules[Model.__module__]
    transfer = lambda data, device: data
    monkeypatch.setattr(module, "batch_to_device", transfer, raising=False)
    original_tokenizer_call = Tokenizer.__call__
    original_normalize = functional.normalize
    original_forward = model.modules[0].forward

    def encode(inputs, is_query):
        assert is_query is True
        model.to("cuda")
        model.eval()
        features = model.preprocess(inputs)
        features = module.batch_to_device(features, "cuda")
        for part in model.modules:
            features = part.forward(features)
        result = functional.normalize(features)
        if fail:
            raise RuntimeError("controlled_failure")
        return result

    encoder = SimpleNamespace(_model=model, _encode_uncached=encode)
    with stage.StageRecorder(encoder, torch) as recorder:
        if fail:
            with pytest.raises(RuntimeError, match="controlled_failure"):
                recorder.measure("fixture text that is never persisted")
        else:
            vector, row = recorder.measure("fixture text that is never persisted")
            assert "input_ids" in vector
            assert row["token_lengths_with_prompt"] == {"padded_tokens": 7, "nonpadding_tokens": [5]}
            assert row["stage_calls"] == {"model_to": 1, "model_eval": 1, "tokenizer": 1,
                "preprocess": 1, "host_to_device": 1, "transformer_forward": 1,
                "pooling": 1, "normalize_module": 1, "normalize_final": 1}
            assert row["event_waits_after_numpy_return"] == 0
            assert set(row["cuda_stream_span_ms"]) == {"host_to_device", "transformer_forward",
                                                       "pooling", "normalize_module", "normalize_final"}
    assert Tokenizer.__call__ is original_tokenizer_call
    assert functional.normalize is original_normalize
    assert module.batch_to_device is transfer
    assert "forward" not in vars(model.modules[0])
    assert model.modules[0].forward == original_forward
    assert "preprocess" not in vars(model)


@pytest.mark.parametrize("args", [["--count", "19"], ["--count", "41"],
    ["--profiler-count", "4"], ["--profiler-count", "-1"]])
def test_cli_rejects_invalid_workload_before_loading_torch(args, monkeypatch, tmp_path):
    monkeypatch.setattr(stage, "run", lambda *_: pytest.fail("validation must precede model work"))
    with pytest.raises(SystemExit) as error:
        stage.main([*args, "--output", str(tmp_path / "unused.json")])
    assert error.value.code == 2