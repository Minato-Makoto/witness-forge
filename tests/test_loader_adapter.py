import types
import pytest

import torch

from witness_forge.config import AdapterConfig, ModelConfig, QuantConfig
from witness_forge.forge import loader as loader_mod
from witness_forge.forge.loader import ForgeLoader


def test_loader_attaches_adapter(monkeypatch, tmp_path):
    dummy_path = tmp_path / "model"
    dummy_path.mkdir()

    class DummyTokenizer:
        chat_template = None
        pad_token_id = None
        eos_token_id = 0

        def __call__(self, prompt, return_tensors=None):
            return {"input_ids": []}

    class DummyConfig:
        model_type = ""

    class DummyModel:
        device = "cpu"

        def to(self, device):
            self.device = device

        def eval(self):
            return self

        def parameters(self):
            return iter([])

        def generate(self, **kwargs):
            return []

    monkeypatch.setattr(
        loader_mod,
        "AutoConfig",
        types.SimpleNamespace(from_pretrained=lambda *args, **kwargs: DummyConfig()),
    )
    monkeypatch.setattr(
        loader_mod,
        "AutoTokenizer",
        types.SimpleNamespace(from_pretrained=lambda *args, **kwargs: DummyTokenizer()),
    )
    monkeypatch.setattr(
        loader_mod,
        "AutoModelForCausalLM",
        types.SimpleNamespace(from_pretrained=lambda *args, **kwargs: DummyModel()),
    )

    captured = {}

    def fake_apply(model, config, adapter_override_path=None):
        captured["path"] = getattr(config.adapter, "path", "missing") if hasattr(config, "adapter") else ""
        captured["type"] = getattr(config.adapter, "type", "none") if hasattr(config, "adapter") else "none"
        info = types.SimpleNamespace(enabled=True, path=config.adapter.path, note="attached")
        return model, info

    monkeypatch.setattr(loader_mod, "apply_adapter_if_configured", fake_apply)

    model_cfg = ModelConfig(
        name="dummy",
        path=str(dummy_path),
        adapter=AdapterConfig(enabled=True, path="adapter-path", type="lora"),
        quant=QuantConfig(),
    )

    tok, mdl, gen_fn = ForgeLoader.load_model(model_cfg)
    assert tok is not None
    assert mdl is not None
    assert callable(gen_fn)
    assert captured["path"] == "adapter-path"
    assert captured["type"] == "lora"


def test_loader_raises_on_empty_adapter_path(monkeypatch, tmp_path):
    dummy_path = tmp_path / "model"
    dummy_path.mkdir()
    
    # We don't need full mocking here as we expect failure before loading
    model_cfg = ModelConfig(
        name="dummy",
        path=str(dummy_path),
        adapter=AdapterConfig(enabled=True, path="", type="lora"), # Empty path
        quant=QuantConfig(),
    )
    
    # Mocking just enough to pass initial checks if any
    monkeypatch.setattr(loader_mod, "AutoConfig", types.SimpleNamespace(from_pretrained=lambda *args, **kwargs: types.SimpleNamespace()))
    monkeypatch.setattr(loader_mod, "AutoTokenizer", types.SimpleNamespace(from_pretrained=lambda *args, **kwargs: types.SimpleNamespace()))
    monkeypatch.setattr(loader_mod, "AutoModelForCausalLM", types.SimpleNamespace(from_pretrained=lambda *args, **kwargs: types.SimpleNamespace(eval=lambda: None, to=lambda x: None)))
    
    # We need to ensure apply_adapter_if_configured calls the real one or a version that calls apply_adapter
    # But apply_adapter_if_configured is imported in loader.py. 
    # The actual logic is in adapter_utils.py which is called by adapter_manager.py which is called by loader.py
    # Since we modified adapter_utils.py, we want to ensure that logic is hit.
    # However, loader.py imports apply_adapter_if_configured from adapter_manager.
    
    # Let's just test adapter_utils.apply_adapter directly for this specific check
    from witness_forge.forge import adapter_utils
    
    # Mock PeftModel to avoid early return due to missing dependency
    monkeypatch.setattr(adapter_utils, "PeftModel", True)
    
    with pytest.raises(ValueError, match="Adapter enabled but 'path' is empty"):
        adapter_utils.apply_adapter(None, model_cfg.adapter)


def test_loader_cpu_offload(monkeypatch):
    kwargs = {}
    quant = QuantConfig(cpu_offload_threshold_gb=8.0, max_cpu_memory_gb=16.0)
    monkeypatch.setattr(loader_mod.ForgeLoader, "_gpu_vram_gb", staticmethod(lambda: 6.0))
    ForgeLoader._maybe_enable_cpu_offload(kwargs, quant)
    assert kwargs["device_map"] == "auto"
    assert "max_memory" in kwargs


def test_loader_resolve_dtype_auto():
    dtype = ForgeLoader._resolve_dtype("auto", torch.float16)
    assert dtype == torch.float16
