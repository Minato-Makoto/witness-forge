from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

import yaml

from .selfpatch import SelfPatchManager
from ..config import SelfUpgradeConfig
from .self_patch_manager import ControlledPatchManager


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SelfUpgrade:
    def __init__(
        self,
        config_path: str,
        patch_dir: str = "./patches",
        *,
        selfpatch: Optional[SelfPatchManager] = None,
        upgrade_cfg: Optional[SelfUpgradeConfig] = None,
        controller: Optional[ControlledPatchManager] = None,
        memory_db_path: Optional[str] = None,
    ):
        self.config_path = config_path
        self.patch_dir = patch_dir
        self.selfpatch = selfpatch
        self.cfg = upgrade_cfg or SelfUpgradeConfig(patch_dir=patch_dir)
        os.makedirs(self.cfg.patch_dir, exist_ok=True)
        self.controller = controller or ControlledPatchManager(
            self.cfg,
            repo_root=Path.cwd(),
            db_path=memory_db_path,
        )

    def propose(self, reason: str, deltas: Dict) -> str:
        if self.controller:
            patch_path = self.controller.generate_config_patch(
                self.config_path,
                deltas,
                reason,
                author="self_upgrade",
            )
            return str(patch_path) if patch_path else ""
        ts = time.strftime("%Y%m%d-%H%M%S")
        path = os.path.join(self.patch_dir, f"patch-{ts}.json")
        config_file = Path(self.config_path)
        raw_text = config_file.read_text(encoding="utf-8")
        cfg = yaml.safe_load(raw_text) or {}
        updated = copy.deepcopy(cfg)
        for dotted, value in deltas.items():
            cursor = updated
            keys = dotted.split(".")
            for key in keys[:-1]:
                cursor = cursor.setdefault(key, {})
            cursor[keys[-1]] = value
        new_yaml = yaml.safe_dump(updated, allow_unicode=True, sort_keys=False)
        payload = {
            "author": "self_upgrade",
            "timestamp": ts,
            "description": reason,
            "changes": [
                {
                    "file": self.config_path,
                    "operation": "replace",
                    "content": new_yaml,
                    "sha256_old": _sha256_text(raw_text),
                    "sha256_new": _sha256_text(new_yaml),
                }
            ],
            "meta": {"allow_network": False, "type": "config"},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return path

    def apply(self, patch_path: str, dry_run: bool = False) -> str:
        if not patch_path:
            return "[upgrade] skipped (no diff)"
        if self.controller:
            result = self.controller.apply_patch(
                patch_path,
                dry_run=dry_run,
                applied_by="self-upgrade",
            )
            return f"[upgrade] {result['status']} {result.get('sha256', '')}"
        if not self.selfpatch:
            return "[upgrade] Patch đã tạo, dùng /selfpatch apply để hoàn tất."
        return self.selfpatch.apply_patch(os.path.basename(patch_path))
