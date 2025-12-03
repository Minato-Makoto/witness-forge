from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..config import ModelConfig, WitnessConfig
from ..forge.loader import ForgeLoader


def build_base_decode(model_cfg: ModelConfig) -> Dict[str, float]:
    """
    Normalize decode parameters into a plain dict.
    """
    return {
        "max_new_tokens": model_cfg.max_new_tokens,
        "temperature": model_cfg.temperature,
        "top_p": model_cfg.top_p,
        "presence_penalty": model_cfg.presence_penalty,
        "frequency_penalty": model_cfg.frequency_penalty,
        "repetition_penalty": model_cfg.repetition_penalty,
        "no_repeat_ngram_size": model_cfg.no_repeat_ngram_size,
    }


def load_brain(
    model_cfg: ModelConfig,
    witness_cfg: Optional[WitnessConfig] = None,
    *,
    path_override: Optional[str] = None,
    name_suffix: str = "",
) -> Tuple[Any, Any, Any, Dict[str, float]]:
    """
    Load a model/tokenizer/generate_fn trio for one brain path.
    """
    effective_cfg = model_cfg
    if path_override:
        effective_cfg = model_cfg.model_copy(
            update={
                "path": str(Path(path_override)),
                "name": f"{model_cfg.name}{name_suffix}" if model_cfg.name else Path(path_override).name,
            }
        )
    tok, mdl, gen_fn = ForgeLoader.load_model(effective_cfg, witness_cfg=witness_cfg)
    base_decode = build_base_decode(effective_cfg)
    return tok, mdl, gen_fn, base_decode


def unload_model(model: Any) -> None:
    """
    Best-effort release of model resources.
    """
    if model is None:
        return
    try:
        if hasattr(model, "close"):
            model.close()
    finally:
        try:
            import gc

            gc.collect()
        except Exception:
            pass


__all__ = ["build_base_decode", "load_brain", "unload_model"]
