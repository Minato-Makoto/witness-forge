from __future__ import annotations

import copy
import datetime as dt
import difflib
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

from ..config import SelfUpgradeConfig


@dataclass
class PatchPreview:
    sha256: str
    diff: str
    size_kb: float
    path: Path


class ControlledPatchManager:
    """
    Controlled self-upgrade orchestrator.
    Generates JSON patches, validates signatures, runs dry-run tests, and applies atomically.
    """

    def __init__(
        self,
        cfg: SelfUpgradeConfig,
        *,
        repo_root: Optional[Path] = None,
        db_path: Optional[str] = None,
        patch_dir_override: Optional[Path] = None,
        targeted_copy: bool = False,
    ):
        self.cfg = cfg
        root = Path(repo_root or Path.cwd()).resolve()
        if root.is_file():
            root = root.parent
        self.repo_root = root
        self.patch_dir = Path(patch_dir_override or cfg.patch_dir).resolve()
        self.patch_dir.mkdir(parents=True, exist_ok=True)
        (self.patch_dir / "backups").mkdir(exist_ok=True)
        self.db_path = Path(db_path or "./witness.sqlite3")
        self.targeted_copy = targeted_copy

    # ------------------------------------------------------------------ #
    # Patch generation helpers
    # ------------------------------------------------------------------ #

    def generate_config_patch(
        self,
        config_path: str,
        deltas: Dict[str, str],
        description: str,
        *,
        author: str = "self_upgrade",
    ) -> Optional[Path]:
        cfg_path = Path(config_path)
        raw_text = cfg_path.read_text(encoding="utf-8")
        cfg_dict = yaml.safe_load(raw_text) or {}
        updated = self._apply_deltas(cfg_dict, deltas)
        new_yaml = yaml.safe_dump(updated, allow_unicode=True, sort_keys=False)
        if new_yaml == raw_text:
            return None
        change = self._make_change(cfg_path, new_yaml, raw_text)
        payload = self._build_payload(description, [change], author=author, meta={"type": "config"})
        return self._persist_patch(payload)

    def generate_demo_patch(self, description: str = "demo readme patch") -> Path:
        target = self.repo_root / "README.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        original = target.read_text(encoding="utf-8") if target.exists() else ""
        addition = f"\n> Demo patch touched README at {time.strftime('%Y-%m-%d %H:%M:%S')}.\n"
        updated = original + addition
        change = self._make_change(target, updated, original)
        payload = self._build_payload(description, [change], author="cli-demo", meta={"type": "demo"})
        return self._persist_patch(payload)

    def generate_file_patch(
        self,
        target_file: str | Path,
        new_content: str,
        description: str,
        *,
        author: str = "cli",
    ) -> Optional[Path]:
        target = self._resolve_target(str(target_file))
        original = target.read_text(encoding="utf-8") if target.exists() else ""
        if original == new_content:
            return None
        change = self._make_change(target, new_content, original)
        payload = self._build_payload(description, [change], author=author, meta={"type": "file"})
        return self._persist_patch(payload)

    # ------------------------------------------------------------------ #
    # Patch apply / preview
    # ------------------------------------------------------------------ #

    def preview(self, patch_path: str | Path) -> PatchPreview:
        payload, path = self._load_patch(patch_path)
        sha256 = self._ensure_patch_sha(payload)
        diff = self._build_diff(payload)
        size_kb = path.stat().st_size / 1024
        return PatchPreview(sha256=sha256, diff=diff, size_kb=size_kb, path=path)

    def apply_patch(
        self,
        patch_path: str | Path,
        *,
        dry_run: bool = True,
        approval_token: Optional[str] = None,
        force: bool = False,
        applied_by: str = "cli",
    ) -> Dict[str, object]:
        payload, path = self._load_patch(patch_path)
        sha256 = self._ensure_patch_sha(payload)
        self._enforce_size_limit(path)
        self._verify_signature(payload, sha256)
        self.validate_patch_safety(payload)  # NEW
        preview = self._build_diff(payload)
        test_report = self._execute_dry_run(payload)
        if dry_run:
            return {
                "status": "dry-run",
                "sha256": sha256,
                "tests": test_report,
                "diff": preview,
            }
        if test_report["status"] not in {"passed", "skipped"}:
            return {
                "status": "blocked",
                "sha256": sha256,
                "tests": test_report,
                "diff": preview,
            }

        self._enforce_approval(sha256, approval_token, force=force)
        backup_path = self._apply_atomic(payload, sha256)
        self._record_patch(
            sha256=sha256,
            patch_path=str(path),
            diff_preview=preview,
            approval_token=approval_token if approval_token else ("force" if force else ""),
            tests=test_report,
            rollback_path=backup_path,
            applied_by=applied_by,
        )
        return {
            "status": "applied",
            "sha256": sha256,
            "backup": backup_path,
            "tests": test_report,
        }

    # ------------------------------------------------------------------ #
    # Safety & Validation
    # ------------------------------------------------------------------ #

    def validate_patch_safety(self, payload: Dict) -> None:
        """Validate patch doesn't modify protected files or violate model safety"""
        changes = payload.get("changes", [])
        
        # 1. Protected files check
        protected = self.cfg.protected_files or []
        for change in changes:
            target_file = change.get("file", "")
            # Robust check using resolved paths
            try:
                target_path = self._resolve_target(target_file)
                for p in protected:
                    protected_path = self._resolve_target(p)
                    if target_path == protected_path:
                        raise PermissionError(
                            f"Cannot patch protected file: {target_file}\n"
                            f"Protected list: {protected}"
                        )
            except Exception as e:
                if isinstance(e, PermissionError):
                    raise
                # If resolution fails, fall back to simple string check but be careful
                if any(p in target_file for p in protected):
                     raise PermissionError(
                        f"Cannot patch protected file (fallback check): {target_file}"
                    )

        # 2. Model safety checks (only if targeted_copy is active)
        if self.targeted_copy:
            allowed_exts = self.cfg.apply_to_model_allowed_extensions
            for change in changes:
                target = Path(change.get("file", ""))
                if target.suffix not in allowed_exts:
                    raise PermissionError(
                        f"Cannot patch {target.suffix} file in model dir. "
                        f"Allowed: {allowed_exts}"
                    )
                
                # Check read-only
                resolved = self._resolve_target(str(target))
                if resolved.exists() and not os.access(resolved, os.W_OK):
                    raise PermissionError(f"Target file is read-only: {target}")

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _apply_deltas(self, cfg: Dict, deltas: Dict[str, str]) -> Dict:
        updated = copy.deepcopy(cfg)
        for dotted, value in deltas.items():
            cursor = updated
            keys = dotted.split(".")
            for key in keys[:-1]:
                cursor = cursor.setdefault(key, {})
            cursor[keys[-1]] = value
        return updated

    def _make_change(self, path: Path, new_content: str, old_content: str) -> Dict[str, str]:
        current_bytes = path.read_bytes() if path.exists() else b""
        return {
            "file": str(path),
            "operation": "replace",
            "content": new_content,
            "sha256_old": hashlib.sha256(current_bytes).hexdigest() if current_bytes else "",
            "sha256_new": hashlib.sha256(new_content.encode("utf-8")).hexdigest(),
        }

    def _build_payload(self, description: str, changes: List[Dict], *, author: str, meta: Optional[Dict] = None) -> Dict:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        payload = {
            "author": author,
            "timestamp": timestamp,
            "description": description,
            "changes": changes,
            "meta": meta or {},
        }
        payload["meta"]["patch_sha256"] = self._ensure_patch_sha(payload)
        return payload

    def _persist_patch(self, payload: Dict) -> Path:
        name = f"patch-{payload['timestamp']}.json"
        path = self.patch_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _load_patch(self, patch_path: str | Path) -> Tuple[Dict, Path]:
        path = Path(patch_path)
        if not path.is_absolute():
            path = self.patch_dir / patch_path
        if not path.exists():
            raise FileNotFoundError(str(path))
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload, path

    def _build_diff(self, payload: Dict) -> str:
        diffs: List[str] = []
        for change in payload.get("changes", []):
            target = self._resolve_target(change["file"])
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            new = change.get("content", "")
            diff = difflib.unified_diff(
                current.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"{target} (current)",
                tofile=f"{target} (patched)",
            )
            diffs.append("".join(diff))
        return "\n".join(filter(None, diffs)) or "(no diff)"

    def _enforce_size_limit(self, path: Path) -> None:
        limit = self.cfg.max_patch_size_kb or 0
        if limit and path.stat().st_size > limit * 1024:
            raise RuntimeError(f"Patch {path.name} vượt quá kích thước {limit}KB.")

    def _get_dir_size(self, path: Path) -> int:
        total = 0
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total

    def _execute_dry_run(self, payload: Dict) -> Dict[str, object]:
        tmpdir = Path(tempfile.mkdtemp(prefix="wf-patch-"))
        try:
            sandbox = (tmpdir / "repo").resolve()
            if self.targeted_copy:
                sandbox.mkdir(parents=True, exist_ok=True)
            else:
                shutil.copytree(
                    self.repo_root,
                    sandbox,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", ".venv", "models", "data", "__pycache__"),
                )
            self._apply_to_root(payload, sandbox)
            
            # In targeted_copy mode, we likely don't have the full repo/env to run tests
            if self.targeted_copy:
                 return {"status": "skipped", "stdout": "Skipped tests in targeted_copy mode", "stderr": ""}

            tests = self.cfg.dry_run_tests or []
            if not tests:
                return {"status": "skipped", "stdout": "", "stderr": ""}
            cmd = ["pytest", "-q", *tests]
            proc = subprocess.run(
                cmd,
                cwd=sandbox,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            status = "passed" if proc.returncode == 0 else "failed"
            return {
                "status": status,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-8000:],
                "command": cmd,
            }
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _enforce_approval(self, sha256: str, token: Optional[str], *, force: bool) -> None:
        if not self.cfg.require_approval or force:
            return
        expected = f"APPLY PATCH {sha256}"
        if token != expected:
            raise PermissionError("Chuỗi xác nhận không khớp. Hãy nhập 'APPLY PATCH <SHA>'.")

    def _apply_atomic(self, payload: Dict, sha256: str) -> str:
        backup_root = self.patch_dir / "backups" / sha256
        backup_root.mkdir(parents=True, exist_ok=True)
        
        # NEW: Full model backup if targeted_copy enabled
        # NEW: Full model backup if targeted_copy enabled
        # OPTIMIZATION: Default to NOT backing up the entire model folder as it can be huge (GBs).
        # Only backup if explicitly enabled in a future config or if small enough.
        # For now, we disable full model backup to prevent massive disk usage/delays.
        if self.targeted_copy and self.cfg.apply_to_model_backup:
             # Original: Always backup if configured
             model_backup = self.patch_dir / "model_backups" / sha256
             if not model_backup.exists():
                shutil.copytree(
                    self.repo_root, 
                    model_backup, 
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__")
                )
        
        staged: List[Tuple[Path, Path]] = []
        try:
            for change in payload.get("changes", []):
                target = self._resolve_target(change["file"])
                rel = target.relative_to(self.repo_root)
                backup_path = backup_root / rel
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    shutil.copy2(target, backup_path)
                    staged.append((target, backup_path))
                self._apply_change(target, change)
            return str(backup_root)
        except Exception:
            for original, backup in reversed(staged):
                if backup.exists():
                    shutil.copy2(backup, original)
            raise

    def _apply_to_root(self, payload: Dict, root: Path) -> None:
        for change in payload.get("changes", []):
            original = self._resolve_target(change["file"])
            rel = original.relative_to(self.repo_root)
            target = (root / rel).resolve()
            self._apply_change(target, change)

    def _apply_change(self, target: Path, change: Dict) -> None:
        operation = change.get("operation", "replace")
        expected_old = change.get("sha256_old")
        expected_new = change.get("sha256_new")
        current_bytes = target.read_bytes() if target.exists() else b""
        if expected_old and current_bytes and hashlib.sha256(current_bytes).hexdigest() != expected_old:
            raise RuntimeError(f"SHA256 hiện tại của {target} không khớp với patch.")
        if operation == "remove":
            if target.exists():
                target.unlink()
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        content = change.get("content", "")
        if operation == "append":
            mode = "a"
        else:
            mode = "w"
        with target.open(mode, encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        if expected_new:
            new_bytes = target.read_bytes()
            if hashlib.sha256(new_bytes).hexdigest() != expected_new:
                raise RuntimeError(f"SHA256 mới của {target} không khớp patch.")

    def _resolve_target(self, file_path: str, *, root: Optional[Path] = None) -> Path:
        candidate = Path(file_path)
        base = (root or self.repo_root).resolve()
        resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
        if not str(resolved).startswith(str(base)):
            raise RuntimeError(f"Patch cố truy cập ngoài repo: {resolved}")
        return resolved

    def _ensure_patch_sha(self, payload: Dict) -> str:
        meta = payload.setdefault("meta", {})
        existing = meta.get("patch_sha256")
        if existing:
            return existing
        serial = json.dumps(payload.get("changes", []), sort_keys=True, ensure_ascii=False)
        sha256 = hashlib.sha256(serial.encode("utf-8")).hexdigest()
        meta["patch_sha256"] = sha256
        return sha256

    def _verify_signature(self, payload: Dict, sha256: str) -> None:
        signature = payload.get("signature")
        if not signature:
            return
        key_path = Path(self.cfg.signature_key_path)
        if not key_path.exists():
            raise RuntimeError("Patch có chữ ký nhưng thiếu signature_key_path.")
        key = key_path.read_bytes().strip()
        digest = hmac.new(key, sha256.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(digest, signature):
            raise PermissionError("Chữ ký patch không hợp lệ.")

    def _record_patch(
        self,
        *,
        sha256: str,
        patch_path: str,
        diff_preview: str,
        approval_token: str,
        tests: Dict[str, object],
        rollback_path: str,
        applied_by: str,
    ) -> None:
        if not self.db_path:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS patches_applied (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sha256 TEXT NOT NULL,
                    patch_path TEXT NOT NULL,
                    applied_by TEXT,
                    applied_at TEXT NOT NULL,
                    diff TEXT,
                    user_approval TEXT,
                    test_results_json TEXT,
                    rollback_path TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO patches_applied
                (sha256, patch_path, applied_by, applied_at, diff, user_approval, test_results_json, rollback_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sha256,
                    patch_path,
                    applied_by,
                    dt.datetime.utcnow().isoformat(),
                    diff_preview[:8000],
                    approval_token,
                    json.dumps(tests, ensure_ascii=False),
                    rollback_path,
                ),
            )
            conn.commit()
        finally:
            conn.close()


__all__ = ["ControlledPatchManager", "PatchPreview"]
