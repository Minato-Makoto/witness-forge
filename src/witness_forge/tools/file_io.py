from __future__ import annotations

import base64
from pathlib import Path
from typing import List, Optional


def _ensure_allowed(target: Path, allowed_write_dirs: Optional[List[str]] = None) -> None:
    if not allowed_write_dirs:
        return
    resolved = target.resolve()
    for base in allowed_write_dirs:
        try:
            if resolved.is_relative_to(Path(base).resolve()):
                return
        except AttributeError:
            # Python < 3.9 fallback
            base_path = Path(base).resolve()
            try:
                resolved.relative_to(base_path)
                return
            except ValueError:
                continue
    raise PermissionError(f"Path {resolved} is outside allowed_write_dirs.")


def _is_binary_bytes(data: bytes) -> bool:
    return b"\0" in data


def read_file(path: str, *, max_bytes: int = 65536) -> dict:
    target = Path(path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    data = target.read_bytes()[:max_bytes]
    if _is_binary_bytes(data):
        return {"type": "binary", "base64": base64.b64encode(data).decode("ascii")}
    try:
        text = data.decode("utf-8")
        return {"type": "text", "content": text}
    except UnicodeDecodeError:
        # Fallback with replacement to avoid crashing
        text = data.decode("utf-8", errors="replace")
        return {"type": "text", "content": text}


def write_file(path: str, content: str, *, allowed_write_dirs: Optional[List[str]] = None, max_bytes: int = 65536) -> dict:
    target = Path(path).expanduser().resolve()
    _ensure_allowed(target, allowed_write_dirs)
    target.parent.mkdir(parents=True, exist_ok=True)
    clipped = content[:max_bytes]
    target.write_text(clipped, encoding="utf-8")
    return {"path": str(target), "bytes": len(clipped)}


def list_dir(path: str, pattern: Optional[str] = None) -> List[str]:
    target = Path(path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    if target.is_file():
        return [target.name]
    entries: List[Path] = []
    if pattern:
        entries = list(target.glob(pattern))
    else:
        entries = list(target.iterdir())
    return sorted(str(p) for p in entries)


def read_input_file(path: str, *, max_bytes: int = 65536) -> str:
    """
    Read user-provided input file with basic safeguards.
    Returns text (with replacement for undecodable bytes). Binary files are base64-encoded.
    """
    data = read_file(path, max_bytes=max_bytes)
    if data["type"] == "binary":
        return f"[binary base64] {data['base64']}"
    return data["content"]
