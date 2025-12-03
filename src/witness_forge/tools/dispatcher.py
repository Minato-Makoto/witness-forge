from __future__ import annotations

import io
import os
import re
import shlex
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .runner import ToolRunner
from . import file_io


class ToolDispatcher:
    """
    Lightweight router around ToolRunner with guardrails for Python, shell, and file access.
    """

    def __init__(
        self,
        tool_runner: ToolRunner,
        *,
        allow_python: bool,
        allow_powershell: bool,
        allow_bat: bool,
        allow_filesystem_write: bool,
        max_bytes: int,
        local_llm_entrypoint: Optional[str],
        allowed_write_dirs: Optional[List[str]] = None,
        vision_agent: Optional[object] = None,
    ) -> None:
        self.tool_runner = tool_runner
        self.allow_python = allow_python
        self.allow_powershell = allow_powershell
        self.allow_bat = allow_bat
        self.allow_filesystem_write = allow_filesystem_write
        self.max_bytes = max_bytes
        self.local_llm_entrypoint = local_llm_entrypoint
        self.internet_enabled = False
        self.allowed_write_dirs = [Path(p).expanduser().resolve() for p in (allowed_write_dirs or [])]
        self.vision_agent = vision_agent

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def enabled_tool_names(self) -> List[str]:
        names: List[str] = ["run", "open"]
        if self.allow_powershell:
            names.append("pwsh")
        if self.allow_bat:
            names.append("bat")
        if self.allow_python:
            names.append("python")
        if self.allow_filesystem_write:
            names.append("write")
        if self.local_llm_entrypoint:
            names.append("llm")
        if self.internet_enabled:
            names.append("vision_action")
        names.extend(["list", "read_input"])
        # Preserve declaration order while removing duplicates.
        seen = set()
        ordered = []
        for item in names:
            if item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered

    def dispatch(self, action: str, payload: str) -> Dict[str, Any]:
        """
        Route tool invocation based on action name.
        """
        name = action.strip().lower()
        if name in {"run", "shell"}:
            return self.run_shell(payload)
        if name in {"pwsh", "powershell"}:
            return self.run_shell(payload, prefer_powershell=True)
        if name in {"bat"}:
            return self.run_shell(payload, prefer_bat=True)
        if name in {"python", "py"}:
            return self.run_python(payload)
        if name in {"open", "read"}:
            return self.open_path(payload)
        if name in {"write", "save"}:
            return self.write_file(payload)
        if name in {"list", "ls"}:
            return self.list_path(payload)
        if name in {"read_input", "readinput"}:
            return self.read_input(payload)
        if name == "llm":
            return self.run_llm(payload)
        if name in {"vision_action"}:
            return self.vision_action(payload)
        # Fallback: treat action as a binary name executed via ToolRunner.
        return self.run_tool(name, self._split_args(payload))

    def run_shell(
        self,
        cmd: str,
        *,
        prefer_powershell: bool = False,
        prefer_bat: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a shell command through ToolRunner using the platform shell.
        """
        shell, args = self._build_shell_command(cmd, prefer_powershell=prefer_powershell, prefer_bat=prefer_bat)
        return self._clip_result(self.tool_runner.execute(shell, args))

    def run_python(self, code: str) -> Dict[str, Any]:
        """
        Execute Python code in-process with a minimal sandbox.
        """
        if not self.allow_python:
            raise PermissionError("Python execution is disabled by configuration.")

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        # Provide a small safe builtins set while keeping import available for flexibility.
        safe_globals = {"__name__": "__witness_tool__", "__builtins__": self._safe_builtins()}
        local_vars: Dict[str, Any] = {}
        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code, safe_globals, local_vars)
            return {
                "stdout": stdout_buf.getvalue()[: self.max_bytes],
                "stderr": stderr_buf.getvalue()[: self.max_bytes],
                "returncode": 0,
            }
        except Exception as exc:  # pragma: no cover - error branch
            err = stderr_buf.getvalue() + f"{exc}"
            return {"stdout": stdout_buf.getvalue()[: self.max_bytes], "stderr": err[: self.max_bytes], "returncode": 1}

    def open_path(self, path: str) -> Dict[str, Any]:
        """
        Read a file or list directory contents.
        """
        try:
            data = file_io.read_file(path, max_bytes=self.max_bytes)
            if data["type"] == "binary":
                stdout = data["base64"]
            else:
                stdout = data["content"]
            return {"stdout": stdout, "stderr": "", "returncode": 0}
        except Exception as exc:  # pragma: no cover - defensive
            return {"stdout": "", "stderr": str(exc), "returncode": 1}

    def write_file(self, path_content: str) -> Dict[str, Any]:
        """
        Write content to a file. Input format: "<path>::<content>".
        """
        if not self.allow_filesystem_write:
            raise PermissionError("Filesystem write is disabled.")
        if "::" not in path_content:
            raise ValueError("Input must follow '<path>::<content>' format.")
        path_str, content = path_content.split("::", 1)
        target = Path(path_str).expanduser().resolve()
        if self.allowed_write_dirs and not self._is_allowed_path(target):
            raise PermissionError(f"Path {target} is outside allowed_write_dirs.")
        target.parent.mkdir(parents=True, exist_ok=True)
        clipped = content[: self.max_bytes]
        target.write_text(clipped, encoding="utf-8")
        return {
            "stdout": f"wrote {len(clipped)} bytes to {target}",
            "stderr": "",
            "returncode": 0,
        }

    def list_path(self, path: str) -> Dict[str, Any]:
        try:
            matches = file_io.list_dir(path)
            return {"stdout": "\n".join(matches)[: self.max_bytes], "stderr": "", "returncode": 0}
        except Exception as exc:
            return {"stdout": "", "stderr": str(exc), "returncode": 1}

    def read_input(self, path: str) -> Dict[str, Any]:
        try:
            data = file_io.read_input_file(path, max_bytes=self.max_bytes)
            return {"stdout": data, "stderr": "", "returncode": 0}
        except Exception as exc:
            return {"stdout": "", "stderr": str(exc), "returncode": 1}

    def run_tool(self, tool_name: str, args: Iterable[str]) -> Dict[str, Any]:
        """
        Run a tool directly via ToolRunner (whitelist + sandbox enforced).
        """
        return self._clip_result(self.tool_runner.execute(tool_name, args))

    def run_llm(self, payload: str) -> Dict[str, Any]:
        if not self.local_llm_entrypoint:
            raise PermissionError("local_llm_entrypoint is not configured.")
        tokens = self._split_args(payload)
        return self.run_tool(self.local_llm_entrypoint, tokens)

    def vision_action(self, payload: str) -> Dict[str, Any]:
        if not self.internet_enabled:
            raise PermissionError("Internet tools are disabled.")
        if self.vision_agent is None:
            return {"stdout": "", "stderr": "Vision agent not configured", "returncode": 1}
        return self._clip_result(self.vision_agent.execute(payload))

    def set_internet_access(self, enabled: bool) -> None:
        self.internet_enabled = bool(enabled)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_shell_command(
        self,
        cmd: str,
        *,
        prefer_powershell: bool,
        prefer_bat: bool,
    ) -> tuple[str, List[str]]:
        if prefer_powershell and not self.allow_powershell:
            raise PermissionError("PowerShell execution is disabled.")

        if prefer_bat and not self.allow_bat:
            raise PermissionError("Batch execution is disabled.")

        # Block accidental .bat execution unless explicitly allowed.
        if cmd.lower().strip().endswith(".bat") and not self.allow_bat:
            raise PermissionError("Running .bat files is disabled.")

        if os.name == "nt":
            if self.allow_powershell and (prefer_powershell or not prefer_bat):
                return "powershell", ["-NoProfile", "-NonInteractive", "-Command", cmd]
            return "cmd.exe", ["/c", cmd]

        # POSIX shell
        return "bash", ["-lc", cmd]

    def _is_allowed_path(self, target: Path) -> bool:
        for base in self.allowed_write_dirs:
            try:
                target.relative_to(base)
                return True
            except ValueError:
                continue
        return False

    def _clip_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        clipped = dict(result)
        if "stdout" in clipped and isinstance(clipped["stdout"], str):
            clipped["stdout"] = clipped["stdout"][: self.max_bytes]
        if "stderr" in clipped and isinstance(clipped["stderr"], str):
            clipped["stderr"] = clipped["stderr"][: self.max_bytes]
        return clipped

    @staticmethod
    def _split_args(payload: str) -> List[str]:
        if not payload:
            return []
        return shlex.split(payload, posix=os.name != "nt")

    @staticmethod
    def _safe_builtins() -> Dict[str, Any]:
        allowed = [
            "abs",
            "all",
            "any",
            "bool",
            "dict",
            "enumerate",
            "float",
            "int",
            "len",
            "list",
            "max",
            "min",
            "print",
            "range",
            "str",
            "__import__",
        ]
        builtins_obj = __builtins__
        if isinstance(builtins_obj, dict):
            return {name: builtins_obj[name] for name in allowed if name in builtins_obj}
        return {name: getattr(builtins_obj, name) for name in allowed if hasattr(builtins_obj, name)}


__all__ = ["ToolDispatcher"]
