from __future__ import annotations

import types
import sys
from pathlib import Path

import pytest

from witness_forge.config import ModelConfig
from witness_forge.forge import loader as loader_mod
from witness_forge.forge.loader import ForgeLoader


def test_detect_backend_gguf(tmp_path: Path) -> None:
    gguf = tmp_path / "model.gguf"
    gguf.write_text("dummy", encoding="utf-8")
    cfg = ModelConfig(path=str(gguf))
    assert ForgeLoader._detect_backend(cfg) == ModelConfig.ModelBackend.LLAMA_CPP


def test_load_llama_cpp_stream(monkeypatch, tmp_path: Path) -> None:
    gguf = tmp_path / "m.gguf"
    gguf.write_text("dummy", encoding="utf-8")

    captured = {}

    class DummyLlama:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def create_completion(self, prompt, max_tokens=0, temperature=0.0, top_p=0.0, stream=False, stop=None, **kwargs):
            assert stream is True
            captured["stop"] = stop
            yield {"choices": [{"text": f"echo:{prompt}"}]}

    dummy_mod = types.SimpleNamespace(Llama=DummyLlama, llama_gpu_support=lambda: False, LlamaGrammar=types.SimpleNamespace(from_string=lambda x: x))
    monkeypatch.setattr(loader_mod, "importlib", types.SimpleNamespace(import_module=lambda name: dummy_mod))
    monkeypatch.setitem(sys.modules, "llama_cpp", dummy_mod)

    cfg = ModelConfig(path=str(gguf), backend=ModelConfig.ModelBackend.LLAMA_CPP, n_gpu_layers=2, n_ctx=2048, n_threads=3)
    tok, mdl, gen_fn = ForgeLoader.load_model(cfg)
    assert tok is not None and mdl is not None
    chunks = list(gen_fn("hi", {"max_new_tokens": 8, "temperature": 0.5, "top_p": 0.9}))
    assert any("echo:hi" in ch for ch in chunks)
    assert captured["n_gpu_layers"] == 2
    assert captured["n_ctx"] == 2048
    assert captured["n_threads"] == 3
    assert isinstance(captured["stop"], list) and len(captured["stop"]) > 0


def test_load_llama_cpp_missing(monkeypatch, tmp_path: Path) -> None:
    gguf = tmp_path / "x.gguf"
    gguf.write_text("dummy", encoding="utf-8")

    def _raise(name):
        raise ImportError("no llama_cpp")

    monkeypatch.setattr(loader_mod, "importlib", types.SimpleNamespace(import_module=_raise))
    cfg = ModelConfig(path=str(gguf), backend=ModelConfig.ModelBackend.LLAMA_CPP)
    with pytest.raises(RuntimeError):
        ForgeLoader.load_model(cfg)


def test_gguf_auto_detection(monkeypatch, tmp_path: Path) -> None:
    gguf = tmp_path / "my-gpt-model.gguf"
    gguf.write_text("dummy", encoding="utf-8")

    captured = {}

    class DummyLlama:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.metadata = {}

        def create_completion(self, prompt, max_tokens=0, temperature=0.0, top_p=0.0, stream=False, stop=None, **kwargs):
            assert stream is True
            captured["stop"] = stop
            yield {"choices": [{"text": f"echo:{prompt}"}]}

    dummy_mod = types.SimpleNamespace(Llama=DummyLlama, llama_gpu_support=lambda: True, LlamaGrammar=types.SimpleNamespace(from_string=lambda x: x))
    monkeypatch.setattr(loader_mod, "importlib", types.SimpleNamespace(import_module=lambda name: dummy_mod))
    monkeypatch.setitem(sys.modules, "llama_cpp", dummy_mod)

    cfg = ModelConfig(
        path=str(gguf),
        backend=ModelConfig.ModelBackend.LLAMA_CPP,
        family="auto",
        n_ctx=2048,
        n_threads=1,
    )
    tok, mdl, gen_fn = ForgeLoader.load_model(cfg)
    assert tok is not None and mdl is not None
    chunks = list(gen_fn("hi", {"max_new_tokens": 4, "temperature": 0.5, "top_p": 0.9}))
    assert any("echo:hi" in ch for ch in chunks)
    assert captured.get("model_type") == "gpt"
    assert captured.get("n_ctx") == 2048
    assert cfg.family == "gpt"
