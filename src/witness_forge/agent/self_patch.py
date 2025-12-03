from __future__ import annotations

import ast
import json
import shutil
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..config import AutoPatchConfig
from .selfpatch import SelfPatchError, SelfPatchManager


ConfirmFn = Callable[[str], bool]


class AutoPatchEngine:
    """
    Ark-like evolution kernel. Generates structured patches safely.
    """

    def __init__(
        self,
        cfg: AutoPatchConfig,
        manager: SelfPatchManager,
        confirm_callback: Optional[ConfirmFn] = None,
    ):
        self.cfg = cfg
        self.manager = manager
        self.confirm = confirm_callback
        self.auto_dir = Path(cfg.base_dir)
        self.auto_dir.mkdir(parents=True, exist_ok=True)

    def refresh(self, cfg: AutoPatchConfig) -> None:
        self.cfg = cfg

    def stage_instruction(self, instruction: str, *, author: str = "autopatch") -> str:
        payload = self._load_instruction(instruction)
        patch = self._build_patch_payload(payload, author=author)
        return self._persist_patch(patch)

    def apply_pending(self) -> List[str]:
        if not self.cfg.apply_on_boot:
            return []
        applied: List[str] = []
        for path in sorted(self.manager.base_dir.glob("autopatch-*.json")):
            if not path.exists():
                continue
            if self.confirm and not self.confirm(f"Áp dụng auto patch {path.name}?"):
                continue
            try:
                self.manager.apply_patch(path.name)
                applied.append(path.name)
            except SelfPatchError:
                continue
        return applied

    def _load_instruction(self, instruction: str) -> Dict:
        candidate = instruction.strip()
        if candidate.startswith("@"):
            path = Path(candidate[1:])
            data = path.read_text(encoding="utf-8")
            return json.loads(data)
        return json.loads(candidate)

    def _build_patch_payload(self, payload: Dict, *, author: str) -> Dict:
        target_path = Path(payload["target"])
        edits = payload.get("patch") or []
        if not edits:
            raise SelfPatchError("AutoPatch thiếu patch entries.")
        if len(edits) > self.cfg.max_depth:
            raise SelfPatchError("AutoPatch vượt quá giới hạn max_depth.")

        original = target_path.read_text(encoding="utf-8")
        updated = original
        for entry in edits:
            find = entry["find"]
            replace = entry["replace"]
            if find not in updated:
                raise SelfPatchError(f"Không tìm thấy đoạn '{find[:32]}' trong {target_path}.")
            updated = updated.replace(find, replace, 1)
        if target_path.suffix == ".py":
            ast.parse(updated, filename=str(target_path))

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        return {
            "author": author,
            "timestamp": timestamp,
            "description": payload.get("description", "auto patch"),
            "meta": {"auto": True},
            "changes": [
                {
                    "file": str(target_path),
                    "operation": "replace",
                    "content": updated,
                    "sha256_old": "",
                    "sha256_new": "",
                }
            ],
        }

    def _persist_patch(self, patch: Dict) -> str:
        name = f"autopatch-{patch['timestamp']}.json"
        auto_path = self.auto_dir / name
        auto_path.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")
        target_path = self.manager.base_dir / name
        shutil.copy2(auto_path, target_path)
        if self.cfg.dry_run:
            self.manager.dry_run_apply(target_path.name)
        return str(target_path)


__all__ = ["AutoPatchEngine"]
