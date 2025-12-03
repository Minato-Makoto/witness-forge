#!/usr/bin/env python
"""
Smoke test Witness Forge: loader mock, SelfPatch dry-run, ToolRunner sandbox.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import hashlib

from witness_forge.agent.selfpatch import SelfPatchManager
from witness_forge.config import SelfPatchConfig, ToolsConfig
from witness_forge.forge.loader import ForgeLoader
from witness_forge.tools.runner import ToolRunner


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    tok, mdl, gen_fn = ForgeLoader._mock()
    assert tok is not None and gen_fn is not None
    print("[smoke] Loader mock OK.")

    tmp = Path(tempfile.mkdtemp())
    target = tmp / "demo.txt"
    target.write_text("smoke", encoding="utf-8")
    patch_dir = tmp / "patches"
    patch_dir.mkdir()
    payload = {
        "author": "smoke",
        "description": "noop",
        "changes": [
            {
                "file": str(target),
                "operation": "replace",
                "content": "smoke+patch",
                "sha256_old": _sha("smoke"),
                "sha256_new": _sha("smoke+patch"),
            }
        ],
    }
    (patch_dir / "patch-000.json").write_text(json.dumps(payload), encoding="utf-8")
    cfg = SelfPatchConfig(enabled=False, patches_dir=str(patch_dir))
    mgr = SelfPatchManager(cfg, allow_selfpatch=False, confirm_callback=lambda msg: True)
    mgr.dry_run_apply("patch-000.json")
    print("[smoke] SelfPatch dry-run OK.")

    tool_cfg = ToolsConfig(
        allow_exec=True,
        require_confirm=False,
        whitelist=[re.escape(sys.executable)],
    )
    runner = ToolRunner(tool_cfg, confirm_callback=None, db_path=str(tmp / "tools.sqlite3"))
    runner.execute(sys.executable, ["-c", "print('tool ok')"])
    print("[smoke] ToolRunner OK.")


if __name__ == "__main__":
    main()
