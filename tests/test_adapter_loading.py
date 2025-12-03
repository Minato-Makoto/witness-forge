import types

import pytest

from witness_forge.config import AdapterConfig, WitnessConfig
from witness_forge.forge import adapter_manager


class DummyModel:
    pass


@pytest.fixture(autouse=True)
def stub_apply(monkeypatch):
    def _fake_apply(model, cfg, override_path=None):
        wrapped = types.SimpleNamespace(cfg=cfg, override=override_path)
        return wrapped, {"status": "attached", "mode": cfg.load_mode}

    monkeypatch.setattr(adapter_manager, "_legacy_apply", _fake_apply)


def test_adapter_skipped_when_disabled(tmp_path):
    model = DummyModel()
    cfg = AdapterConfig(enabled=False)
    wrapped, info = adapter_manager.apply_adapter_if_configured(model, cfg)
    assert wrapped is model
    assert not info.enabled
    assert info.note == "disabled"


def test_adapter_uses_override_and_reports_enabled(tmp_path):
    model = DummyModel()
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    cfg = AdapterConfig(enabled=True, path=str(adapter_dir))
    wrapped, info = adapter_manager.apply_adapter_if_configured(model, cfg)
    assert wrapped.cfg is cfg
    assert info.enabled
    assert info.path == str(adapter_dir)


def test_witness_config_prefers_top_level_adapter(tmp_path):
    model = DummyModel()
    adapter_dir = tmp_path / "adapter"
    adapter_dir.mkdir()
    cfg = WitnessConfig.model_validate(
        {
            "adapter": {
                "enabled": True,
                "path": str(adapter_dir),
            }
        }
    )
    wrapped, info = adapter_manager.apply_adapter_if_configured(model, cfg)
    assert wrapped.cfg.enabled
    assert info.enabled


def test_model_config_adapter_used_when_top_level_disabled(tmp_path):
    model = DummyModel()
    adapter_dir = tmp_path / "adapter_model"
    adapter_dir.mkdir()
    witness_cfg = WitnessConfig()
    model_cfg = witness_cfg.model.model_copy(deep=True)
    model_cfg.adapter.enabled = True
    model_cfg.adapter.path = str(adapter_dir)
    wrapped, info = adapter_manager.apply_adapter_if_configured(model, model_cfg)
    assert wrapped.cfg.path == str(adapter_dir)
    assert info.enabled
