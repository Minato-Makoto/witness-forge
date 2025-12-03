from __future__ import annotations

import json
from pathlib import Path

from witness_forge.agent.evolution import EvolutionController
from witness_forge.config import EvolutionConfig, WitnessConfig
from witness_forge.config_overlay import ConfigOverlay


class DummyUpgrade:
    def propose(self, *_args, **_kwargs):
        return "noop"

    def apply(self, *_args, **_kwargs):
        return "applied"


class DummyAutoPatch:
    def refresh(self, *_args, **_kwargs):
        return None


def test_config_overlay_applies_overrides(tmp_path: Path):
    base = WitnessConfig()
    patch_path = tmp_path / "active_evolution.json"
    patch_path.write_text(json.dumps({"overrides": {"model.temperature": 0.5}}), encoding="utf-8")

    overlay = ConfigOverlay(base, patch_path)
    merged = overlay.apply()

    assert base.model.temperature != merged.model.temperature
    assert merged.model.temperature == 0.5


def test_evolution_tunes_and_writes_patch(tmp_path: Path):
    cfg = EvolutionConfig(
        enabled=True,
        permissions="auto",
        tune_threshold=0.5,
        sync_threshold=0.7,
        incremental_step=0.1,
        max_history_turns=5,
    )
    controller = EvolutionController(cfg, DummyUpgrade(), DummyAutoPatch(), confirm=None)
    controller.patch_path = tmp_path / "active_evolution.json"

    loop_state = {
        "scores": {"reflex_score": 0.4},
        "tuned": {"temperature": 0.7},
        "base_decode": {"temperature": 0.7},
    }

    notes = controller.maybe_evolve(loop_state)
    assert notes  # tuning happened
    data = json.loads(controller.patch_path.read_text(encoding="utf-8"))
    assert data["overrides"]["model.temperature"] == 0.6  # 0.7 - 0.1
    assert data["state"] in {"evolving", "stable"}
    assert data["evolution_history"]


def test_evolution_freeze_marks_stable(tmp_path: Path):
    cfg = EvolutionConfig(
        enabled=True,
        permissions="auto",
        tune_threshold=0.5,
        sync_threshold=0.6,
        incremental_step=0.05,
    )
    controller = EvolutionController(cfg, DummyUpgrade(), DummyAutoPatch(), confirm=None)
    controller.patch_path = tmp_path / "active_evolution.json"
    controller.patch_path.write_text(
        json.dumps({"state": "evolving", "overrides": {"model.temperature": 0.55}}, indent=2),
        encoding="utf-8",
    )

    loop_state = {"scores": {"reflex_score": 0.8}}
    notes = controller.maybe_evolve(loop_state)
    assert notes
    data = json.loads(controller.patch_path.read_text(encoding="utf-8"))
    assert data["state"] == "stable"
    # Snapshot archive is intentionally disabled; ensure file remains stable without extra copies
    snapshots = list(controller.patch_path.parent.glob("converged_*.json"))
    assert snapshots == []
