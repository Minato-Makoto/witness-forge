from __future__ import annotations

import os
import re
import shlex
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from ..config import ToolsConfig


ConfirmFn = Callable[[str], bool]


class ToolRunner:
    """
    Sandboxed subprocess runner with whitelist + audit logging.
    """

    def __init__(
        self,
        cfg: ToolsConfig,
        *,
        confirm_callback: Optional[ConfirmFn] = None,
        db_path: str | Path = "./witness.sqlite3",
    ):
        self.db_path = Path(db_path)
        self._allowlist: List[str] = cfg.resolved_whitelist()
        self.cfg = cfg
        self.confirm = confirm_callback

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def refresh(self, cfg: ToolsConfig) -> None:
        self.cfg = cfg
        self._allowlist = cfg.resolved_whitelist()

    def list_allowlist(self) -> List[str]:
        return list(self._allowlist)

    def allow(self, pattern: str) -> None:
        if pattern not in self._allowlist:
            self._allowlist.append(pattern)

    def deny(self, pattern: str) -> None:
        if pattern in self._allowlist:
            self._allowlist.remove(pattern)

    def run_tool(self, command: str, *, dry_run: bool = True, label: str | None = None) -> Dict[str, object]:
        raw_tokens = shlex.split(command, posix=os.name != "nt")
        tokens = [self._strip_quotes(tok) for tok in raw_tokens]
        if not tokens:
            raise ValueError("Thiếu command.")
        binary = tokens[0]
        self._ensure_allowed(binary)
        summary = label or f"tool: {command}"
        if not dry_run and self.cfg.require_confirm:
            if not self.confirm or not self.confirm(summary):
                raise PermissionError("Người dùng từ chối chạy công cụ.")
        if dry_run:
            return {"status": "dry-run", "cmd": command, "allowed": True}
        if not self.cfg.allow_exec:
            raise PermissionError("Tool execution đang bị khoá trong config.")
        env = self._build_env()
        timeout = max(1, int(self.cfg.sandbox.max_runtime_seconds))
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        start = time.time()
        proc = subprocess.Popen(
            tokens,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            creationflags=creationflags,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            duration = time.time() - start
            stdout_clip = (stdout or "")[: self.cfg.sandbox.max_stdout_bytes]
            stderr_clip = (stderr or "")[: self.cfg.sandbox.max_stdout_bytes]
            self._log_execution(command, proc.returncode, stdout_clip, stderr_clip, proc.pid or -1, duration)
            return {
                "status": "completed",
                "returncode": proc.returncode,
                "stdout": stdout_clip,
                "stderr": stderr_clip,
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            duration = time.time() - start
            stdout_clip = (stdout or "")[: self.cfg.sandbox.max_stdout_bytes]
            stderr_clip = ((stderr or "") + "\n[timeout]").strip()[: self.cfg.sandbox.max_stdout_bytes]
            self._log_execution(command, -1, stdout_clip, stderr_clip, proc.pid or -1, duration)
            raise

    def execute(self, cmd: str, args: Iterable[str]) -> Dict[str, object]:
        arg_list = list(args)
        quoted = [cmd, *[shlex.quote(arg) for arg in arg_list]]
        command = " ".join(filter(None, quoted))
        label = " ".join([cmd, *arg_list]).strip()
        return self.run_tool(command, dry_run=False, label=label or cmd)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _ensure_allowed(self, binary: str) -> None:
        if not self._allowlist:
             # Original behavior: strict check
             # If allowlist is empty and allow_exec is True, this might fail or pass depending on implementation details not fully visible here,
             # but the fix was explicitly adding defaults. Reverting removes defaults.
             # If the original code raised PermissionError on empty allowlist, we should keep it or revert to whatever it was.
             # Based on the diff, the original code had:
             # if not self._allowlist: raise PermissionError(...)
             raise PermissionError("Allowlist rỗng. Không thể chạy công cụ.")
        name = Path(binary).name
        for candidate in {binary, name}:
            for pattern in self._allowlist:
                if not pattern:
                    continue
                try:
                    if re.fullmatch(pattern, candidate):
                        return
                except re.error:
                    if candidate == pattern:
                        return
        raise PermissionError(f"Công cụ {binary} không nằm trong whitelist.")

    def _build_env(self) -> Dict[str, str]:
        safe: Dict[str, str] = {"PATH": os.environ.get("PATH", ""), "WITNESS_FORGE_OFFLINE": "1"}
        for key in ("SYSTEMROOT", "COMSPEC", "TEMP", "TMP"):
            if val := os.environ.get(key):
                safe[key] = val
        return safe

    def _log_execution(
        self,
        command: str,
        returncode: int,
        stdout: str,
        stderr: str,
        pid: int,
        duration: float,
    ) -> None:
        if not self.db_path:
            return
        if self.db_path and self.db_path.parent:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cmd TEXT NOT NULL,
                    start_ts TEXT,
                    end_ts TEXT,
                    returncode INTEGER,
                    stdout_blob TEXT,
                    stderr_blob TEXT,
                    pid INTEGER,
                    duration REAL
                )
                """
            )
            now = time.time()
            conn.execute(
                """
                INSERT INTO tool_logs
                (cmd, start_ts, end_ts, returncode, stdout_blob, stderr_blob, pid, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    command,
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - duration)),
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                    returncode,
                    stdout,
                    stderr,
                    pid,
                    duration,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _strip_quotes(token: str) -> str:
        if len(token) >= 2 and token[0] == token[-1] and token[0] in {'"', "'"}:
            return token[1:-1]
        return token


__all__ = ["ToolRunner"]
