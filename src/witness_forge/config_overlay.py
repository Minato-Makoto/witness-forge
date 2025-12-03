from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .config import WitnessConfig


class ConfigOverlay:
    """Runtime overlay loader that merges active_evolution.json onto base config without mutating the source file."""

    def __init__(self, base_config: WitnessConfig, overlay_path: Path):
        self.base = base_config
        self.overlay_path = overlay_path
        self.active_patch = self._load_patch()

    def _load_patch(self) -> Optional[Dict[str, Any]]:
        if not self.overlay_path.exists():
            return None
        try:
            return json.loads(self.overlay_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def apply(self) -> WitnessConfig:
        if not self.active_patch:
            return self.base

        cfg_dict = self.base.model_dump()
        overrides = self.active_patch.get("overrides", {}) or {}
        for dotted_key, value in overrides.items():
            self._set_nested(cfg_dict, dotted_key, value)

        return WitnessConfig.model_validate(cfg_dict)

    def _set_nested(self, target: Dict[str, Any], dotted_key: str, value: Any) -> None:
        keys = dotted_key.split(".")
        node = target
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value


__all__ = ["ConfigOverlay"]
