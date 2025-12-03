import hashlib
import json
import os
from pathlib import Path

from witness_forge.agent.selfpatch import SelfPatchManager
from witness_forge.config import SelfPatchConfig


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_selfpatch_apply_and_revert(monkeypatch, tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("old", encoding="utf-8")
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()

    old_bytes = target.read_bytes()
    payload = {
        "author": "tester",
        "description": "update file",
        "changes": [
            {
                "file": str(target),
                "operation": "replace",
                "content": "new text",
                "sha256_old": hashlib.sha256(old_bytes).hexdigest(),
                "sha256_new": _sha("new text"),
            }
        ],
    }
    patch_path = patches_dir / "patch-123.json"
    patch_path.write_text(json.dumps(payload), encoding="utf-8")

    cfg = SelfPatchConfig(
        enabled=True,
        patches_dir=str(patches_dir),
        require_confirmation=False,
        run_validators=False,
    )
    monkeypatch.setenv("WITNESS_FORGE_ALLOW_SELF_PATCH", "true")
    mgr = SelfPatchManager(cfg, allow_selfpatch=True, confirm_callback=lambda msg: True)

    mgr.dry_run_apply(patch_path.name)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == payload["changes"][0]["sha256_old"]
    mgr.apply_patch(patch_path.name)
    assert target.read_text(encoding="utf-8") == "new text"

    backups = sorted((patches_dir / "backups").iterdir())
    assert backups
    mgr.revert_patch(backups[-1].name)
    assert target.read_text(encoding="utf-8").startswith("old")
