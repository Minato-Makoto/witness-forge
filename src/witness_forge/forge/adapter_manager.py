from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple, Union

from ..config import AdapterConfig, AdapterQuantizationConfig, ModelConfig, WitnessConfig
from .adapter_utils import apply_adapter as _legacy_apply

log = logging.getLogger(__name__)


AdapterSource = Union[WitnessConfig, ModelConfig, AdapterConfig]


@dataclass
class AdapterInfo:
    enabled: bool
    path: str
    source: str
    note: str = ""


def apply_adapter_if_configured(
    model: Any,
    config: AdapterSource,
    *,
    adapter_override_path: Optional[str] = None,
    strict: bool = False,
) -> Tuple[Any, AdapterInfo]:
    adapter_cfg = _select_adapter_config(config)
    if adapter_cfg is None or not adapter_cfg.enabled:
        return model, AdapterInfo(False, "", "auto", "disabled")

    override_path = adapter_override_path or adapter_cfg.path or ""
    if not override_path:
        log.warning("Adapter bật nhưng thiếu đường dẫn. Bỏ qua.")
        return model, AdapterInfo(False, "", "auto", "missing_path")

    if not Path(override_path).exists():
        log.error("Adapter path %s không tồn tại.", override_path)
        if strict:
            raise FileNotFoundError(override_path)
        return model, AdapterInfo(False, override_path, "auto", "path_missing")

    try:
        _validate_quantization(adapter_cfg.quantization)
        wrapped_model, status = _legacy_apply(model, adapter_cfg, override_path=override_path)
        return wrapped_model, AdapterInfo(True, override_path, status.get("mode", "peft"), status.get("status", "attached"))
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Gắn adapter thất bại, fallback về backbone: %s", exc)
        if strict:
            raise
        return model, AdapterInfo(False, override_path, "auto", f"error:{exc}")


def _select_adapter_config(config: AdapterSource) -> Optional[AdapterConfig]:
    if isinstance(config, AdapterConfig):
        return config
    if isinstance(config, WitnessConfig):
        if config.adapter and config.adapter.enabled:
            return config.adapter
        return config.model.adapter
    if isinstance(config, ModelConfig):
        return config.adapter
    return None


def _validate_quantization(quant_cfg: AdapterQuantizationConfig) -> None:
    if not quant_cfg or not quant_cfg.enabled:
        return
    method = (quant_cfg.method or "bitsandbytes").lower()
    if method == "bitsandbytes" and quant_cfg.bits not in {4, 8}:
        raise ValueError("bitsandbytes chỉ hỗ trợ 4-bit hoặc 8-bit cho adapter.")
    if method in {"awq", "gptq"} and quant_cfg.bits not in {4}:
        log.warning("Adapter %s đang thử %s-bit. AWQ/GPTQ thường yêu cầu 4-bit.", method, quant_cfg.bits)


__all__ = ["apply_adapter_if_configured", "AdapterInfo"]
