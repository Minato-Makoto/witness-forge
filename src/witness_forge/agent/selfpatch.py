from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..config import SelfPatchConfig


class SelfPatchError(RuntimeError):
    pass


ConfirmFn = Callable[[str], bool]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


@dataclass
class PatchEntry:
    file: str
    operation: str
    content: str
    sha256_old: str
    sha256_new: str


class SelfPatchManager:
    def __init__(
        self,
        cfg: SelfPatchConfig,
        *,
        allow_selfpatch: bool = False,
        confirm_callback: Optional[ConfirmFn] = None,
    ):
        self.cfg = cfg
        self.allow_selfpatch = allow_selfpatch
        self.confirm_callback = confirm_callback
        self.base_dir = Path(cfg.patches_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "backups").mkdir(exist_ok=True)
        self.audit_log = self.base_dir / "audit.log"

    def refresh(self, cfg: SelfPatchConfig) -> None:
        self.cfg = cfg

    def _env_ok(self) -> bool:
        return os.getenv("WITNESS_FORGE_ALLOW_SELF_PATCH", "").lower() in {"1", "true", "yes"}

    def _ensure_allowed(self) -> None:
        if not self.cfg.enabled:
            raise SelfPatchError("SelfPatch đang tắt trong config.")
        if not self.allow_selfpatch:
            raise SelfPatchError("Chưa bật --allow-selfpatch.")
        if not self._env_ok():
            raise SelfPatchError("Thiếu env WITNESS_FORGE_ALLOW_SELF_PATCH=true.")

    def _list_patch_files(self) -> List[Path]:
        return sorted(self.base_dir.glob("patch-*.json"))

    def scan_patches(self) -> List[dict]:
        patches = []
        for path in self._list_patch_files():
            patches.append({"id": path.name, "path": str(path)})
        return patches

    def _load_patch(self, patch_id: str) -> Dict:
        path = Path(patch_id)
        if not path.is_absolute():
            path = self.base_dir / patch_id
        if not path.exists():
            raise SelfPatchError(f"Patch {patch_id} không tồn tại.")
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        payload["__path"] = str(path)
        return payload

    def _parse_entries(self, payload: Dict) -> List[PatchEntry]:
        entries = payload.get("changes") or [payload]
        parsed: List[PatchEntry] = []
        for item in entries:
            entry = PatchEntry(
                file=item["file"],
                operation=item.get("operation", "replace"),
                content=item.get("content", ""),
                sha256_old=item.get("sha256_old", ""),
                sha256_new=item.get("sha256_new", ""),
            )
            parsed.append(entry)
        return parsed

    def _relativize(self, path: Path) -> Path:
        if not path.is_absolute():
            return path
        try:
            return path.relative_to(Path.cwd())
        except ValueError:
            return Path(path.name)

    def _lint_python(self, source: str, file_path: str) -> None:
        try:
            ast.parse(source, filename=file_path)
        except SyntaxError as exc:  # pragma: no cover - AST handles
            raise SelfPatchError(f"Lỗi cú pháp trong patch {file_path}: {exc}") from exc

    def validate_patch(self, patch_id: str) -> Dict:
        payload = self._load_patch(patch_id)
        entries = self._parse_entries(payload)
        for entry in entries:
            target = Path(entry.file)
            current_bytes = target.read_bytes() if target.exists() else b""
            current_sha = _sha256(current_bytes)
            if entry.operation != "add" and entry.sha256_old and current_sha != entry.sha256_old:
                raise SelfPatchError(f"SHA mismatch cho {entry.file}")
            if entry.file.endswith(".py") and entry.content:
                self._lint_python(entry.content, entry.file)
            if any(token in entry.content for token in ("requests.", "urllib", "subprocess.Popen")):
                meta = payload.get("meta", {})
                if not meta.get("allow_network"):
                    raise SelfPatchError("Patch thêm network/code nguy hiểm mà không có meta allow_network.")
        if self.cfg.validator_cmd:
            self._run_validator(payload)
        return payload

    def _run_validator(self, payload: Dict) -> None:
        if not self.cfg.run_validators:
            return
        cmd = self.cfg.validator_cmd
        if not cmd:
            return
        proc = subprocess.run(
            cmd.split(),
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            raise SelfPatchError(f"Validator thất bại: {proc.stderr.strip()}")

    def dry_run_apply(self, patch_id: str) -> str:
        payload = self.validate_patch(patch_id)
        entries = self._parse_entries(payload)
        workdir = Path(tempfile.mkdtemp(prefix="selfpatch-"))
        try:
            for entry in entries:
                rel = self._relativize(Path(entry.file))
                target = workdir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if entry.operation == "remove":
                    continue
                target.write_text(entry.content, encoding="utf-8")
                if entry.file.endswith(".py"):
                    self._lint_python(entry.content, entry.file)
            if self.cfg.run_validators:
                subprocess.run(
                    ["pytest", "-q", "-k", "selfpatch"],
                    check=False,
                    timeout=60,
                    text=True,
                    capture_output=True,
                )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        return "Dry-run OK"

    def apply_patch(self, patch_id: str) -> str:
        self._ensure_allowed()
        payload = self.validate_patch(patch_id)
        entries = self._parse_entries(payload)
        summary = payload.get("description", patch_id)
        if self.cfg.require_confirmation:
            if not self.confirm_callback or not self.confirm_callback(f"Áp dụng SelfPatch {summary}?"):
                raise SelfPatchError("Người dùng từ chối áp dụng SelfPatch.")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_root = self.base_dir / "backups" / f"{Path(patch_id).stem}-{stamp}"
        manifest: Dict[str, str] = {}

        for entry in entries:
            target = Path(entry.file)
            rel = self._relativize(target)
            backup_path = backup_root / rel
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                backup_path.write_bytes(target.read_bytes())
                manifest[str(rel)] = str(target)
            if entry.operation == "remove":
                if target.exists():
                    target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry.content, encoding="utf-8")
            if entry.sha256_new:
                new_sha = _sha256(target.read_bytes())
                if new_sha != entry.sha256_new:
                    raise SelfPatchError(f"SHA mới không khớp cho {entry.file}")

        self._append_audit(
            {
                "timestamp": stamp,
                "patch": patch_id,
                "author": payload.get("author", "unknown"),
                "action": "apply",
            }
        )
        if manifest:
            (backup_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return f"Đã áp dụng {patch_id}"

    def revert_patch(self, backup_id: str) -> str:
        self._ensure_allowed()
        backup_root = self.base_dir / "backups" / backup_id
        if not backup_root.exists():
            raise SelfPatchError(f"Backup {backup_id} không tồn tại.")
        if self.cfg.require_confirmation:
            if not self.confirm_callback or not self.confirm_callback(f"Revert từ {backup_id}?"):
                raise SelfPatchError("Người dùng từ chối revert.")
        manifest_path = backup_root / "manifest.json"
        manifest = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for path in backup_root.rglob("*"):
            if path.is_dir():
                continue
            if path == manifest_path:
                continue
            rel = path.relative_to(backup_root)
            target = Path(manifest.get(str(rel), str(rel)))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        self._append_audit(
            {
                "timestamp": time.strftime("%Y%m%d-%H%M%S"),
                "patch": backup_id,
                "action": "revert",
            }
        )
        return f"Đã revert từ {backup_id}"

    def _append_audit(self, entry: Dict) -> None:
        with self.audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


__all__ = ["SelfPatchManager", "SelfPatchError"]
