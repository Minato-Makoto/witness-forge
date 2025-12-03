from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import torch

try:  # optional dependency
    from peft import (
        LoraConfig,
        PeftConfig,
        PeftModel,
        TaskType,
        get_peft_model,
        prepare_model_for_kbit_training,
    )
except ImportError:  # pragma: no cover - optional
    PeftConfig = None  # type: ignore[assignment]
    PeftModel = None  # type: ignore[assignment]
    TaskType = None  # type: ignore[assignment]
    LoraConfig = None  # type: ignore[assignment]
    get_peft_model = None  # type: ignore[assignment]
    prepare_model_for_kbit_training = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

try:
    from ..config import AdapterConfig
except Exception:  # pragma: no cover - prevents circular import errors on type checking
    AdapterConfig = Any  # type: ignore[assignment, misc]


def adapter_compatibility_check(model, adapter_path: str) -> Tuple[bool, str]:
    if not adapter_path:
        return False, "adapter path empty"
    if not os.path.isdir(adapter_path):
        return False, f"adapter path {adapter_path} không tồn tại"
    if PeftConfig is None:
        return False, "chưa cài peft (pip install .[lora])"
    try:
        cfg = PeftConfig.from_pretrained(adapter_path)
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"không đọc được PeftConfig: {exc}"
    target = getattr(cfg, "base_model_name_or_path", "")
    base = getattr(getattr(model, "config", None), "name_or_path", "")
    if target and base and target not in base:
        log.warning("Adapter base %s khác với model %s", target, base)
    return True, target or ""


def _maybe_prepare_for_kbit(model):
    if PeftModel is None or prepare_model_for_kbit_training is None:  # type: ignore[truthy-function]
        return model
    is_4bit = bool(getattr(model, "is_loaded_in_4bit", False))
    is_8bit = bool(getattr(model, "is_loaded_in_8bit", False))
    if not (is_4bit or is_8bit):
        return model
    try:
        return prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)  # type: ignore[arg-type]
    except Exception:  # pragma: no cover - optional path
        return model


def apply_adapter(
    model,
    adapter_cfg: AdapterConfig,
    *,
    override_path: Optional[str] = None,
) -> Tuple[object, Dict[str, Any]]:
    if not adapter_cfg.enabled:
        return model, {"status": "skipped", "reason": "disabled"}

    if PeftModel is None:
        log.warning("Không thể gắn adapter vì chưa cài peft. Chạy pip install .[lora]")
        return model, {"status": "skipped", "reason": "peft_missing"}

    adapter_path = override_path or adapter_cfg.path or ""
    adapter_type = adapter_cfg.type
    load_mode = adapter_cfg.load_mode

    if not adapter_path:
        # Prevent silent in-memory LoRA generation which hides config errors
        raise ValueError("Adapter enabled but 'path' is empty. Set path or disable adapter.")
        # return _generate_in_memory_adapter(model, adapter_cfg)

    ok, note = adapter_compatibility_check(model, adapter_path)
    if not ok:
        log.error("Adapter không hợp lệ: %s", note)
        raise RuntimeError(note)

    if adapter_type == "qlora":
        model = _maybe_prepare_for_kbit(model)

    status: Dict[str, Any] = {"status": "attached", "adapter": adapter_path, "mode": load_mode}
    load_kwargs: Dict[str, Any] = {"is_trainable": False}
    dtype = _resolve_dtype(adapter_cfg.dtype)
    if dtype is not None:
        load_kwargs["dtype"] = dtype

    try:
        peft_model = PeftModel.from_pretrained(model, adapter_path, **load_kwargs)
    except Exception as exc:  # pragma: no cover - heavy path
        log.error("Không thể load adapter %s: %s", adapter_path, exc)
        raise

    if load_mode == "merge" and adapter_type != "qlora":
        if hasattr(peft_model, "merge_and_unload"):
            merged = peft_model.merge_and_unload()
            status["status"] = "merged"
            return merged, status
    return peft_model, status


def _generate_in_memory_adapter(model, adapter_cfg: AdapterConfig) -> Tuple[object, Dict[str, Any]]:
    if LoraConfig is None or get_peft_model is None:
        raise RuntimeError("peft chưa có sẵn để tạo LoRA mới.")
    target_modules = adapter_cfg.target_modules or _guess_lora_targets(model)
    task_type = TaskType.CAUSAL_LM if TaskType is not None else "CAUSAL_LM"
    lora_conf = LoraConfig(
        r=adapter_cfg.r,
        lora_alpha=adapter_cfg.alpha,
        lora_dropout=adapter_cfg.dropout,
        bias=adapter_cfg.bias,
        target_modules=target_modules,
        init_lora_weights=adapter_cfg.init_lora_weights,
        task_type=task_type,
    )
    if adapter_cfg.type == "qlora":
        model = _maybe_prepare_for_kbit(model)
    peft_model = get_peft_model(model, lora_conf)
    return peft_model, {
        "status": "generated",
        "adapter": "in-memory",
        "mode": adapter_cfg.load_mode,
        "target_modules": target_modules,
    }


def _guess_lora_targets(model) -> List[str]:
    candidates = set()
    for name, module in getattr(model, "named_modules", lambda: [])():
        if not callable(module):
            continue
        if any(key in name.lower() for key in ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj")):
            candidates.add(name.split(".")[-1])
    if not candidates:
        candidates.update({"q_proj", "v_proj"})
    return sorted(candidates)


def _resolve_dtype(candidate: Optional[str]):
    if not candidate:
        return None
    if candidate == "auto":
        return None
    mapping = {
        "float32": torch.float32,
        "float16": torch.float16,
        "half": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
    }
    return mapping.get(candidate.lower())


__all__ = ["apply_adapter", "adapter_compatibility_check"]
