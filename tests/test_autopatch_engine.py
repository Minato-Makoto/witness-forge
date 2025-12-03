import json
from pathlib import Path

import pytest

from witness_forge.agent.self_patch import AutoPatchEngine
from witness_forge.agent.selfpatch import SelfPatchManager
from witness_forge.config import AutoPatchConfig, SelfPatchConfig


def test_autopatch_stage_instruction(monkeypatch, tmp_path):
    target = tmp_path / "persona.py"
    target.write_text("print('warm')\n", encoding="utf-8")
    patches_dir = tmp_path / "patches"
    patches_dir.mkdir()
    cfg = SelfPatchConfig(
        enabled=True,
        patches_dir=str(patches_dir),
        require_confirmation=False,
        run_validators=False,
    )
    auto_cfg = AutoPatchConfig(
        enabled=True,
        base_dir=str(tmp_path / "auto"),
        dry_run=False,
    )
    monkeypatch.setenv("WITNESS_FORGE_ALLOW_SELF_PATCH", "true")
    manager = SelfPatchManager(cfg, allow_selfpatch=True, confirm_callback=lambda msg: True)
    engine = AutoPatchEngine(auto_cfg, manager, confirm_callback=lambda msg: True)

    instruction = json.dumps(
        {
            "target": str(target),
            "patch": [
                {"find": "warm", "replace": "fire"},
            ],
        }
    )
    path = engine.stage_instruction(instruction)
    assert Path(path).exists()
    assert any(p.name.startswith("autopatch-") for p in patches_dir.iterdir())
