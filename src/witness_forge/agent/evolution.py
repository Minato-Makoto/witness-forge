from __future__ import annotations


import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..config import EvolutionConfig
from .self_patch import AutoPatchEngine
from .self_upgrade import SelfUpgrade


ConfirmFn = Callable[[str], bool]


@dataclass
class EvolutionProposal:
    kind: str
    description: str
    apply: Callable[[], str]


class EvolutionController:
    """
    Simple heuristic-based evolution orchestrator.
    """

    def __init__(
        self,
        cfg: EvolutionConfig,
        upgrade: SelfUpgrade,
        autopatch: AutoPatchEngine,
        confirm: Optional[ConfirmFn],
    ):
        self.cfg = cfg
        self.upgrade = upgrade
        self.autopatch = autopatch
        self.confirm = confirm
        self.cycles = 0
        self.patch_path = Path("patches/active_evolution.json")

    def refresh(self, cfg: EvolutionConfig) -> None:
        self.cfg = cfg

    def maybe_evolve(self, loop_state: Dict) -> List[str]:
        if not self.cfg.enabled:
            return []
        if self.cfg.max_cycles != -1 and self.cycles >= self.cfg.max_cycles:
            return []
        proposals = self._build_proposals(loop_state)
        applied: List[str] = []
        for prop in proposals:
            if self.cfg.permissions == "manual":
                if not self.confirm or not self.confirm(f"Approve upgrade? ({prop.description})"):
                    continue
            try:
                result = prop.apply()
            except PermissionError:
                # Expected when patching protected files or config in model dir
                continue
            except Exception as exc:  # pragma: no cover - defensive
                applied.append(f"[evolution-error] {exc}")
                continue
            applied.append(result)
            self.cycles += 1
        return applied

    def _build_proposals(self, loop_state: Dict) -> List[EvolutionProposal]:
        scores = loop_state.get("scores", {})
        proposals: List[EvolutionProposal] = []
        reflex_score = scores.get("reflex_score", 0.0)

        active_patch = self._load_active_patch()
        if active_patch and active_patch.get("state") == "stable":
            # Unfreeze if score drops too low (performance degraded)
            if reflex_score < self.cfg.tune_threshold:
                self._unfreeze_patch()
                # Continue to propose tuning below
            else:
                return proposals

        if reflex_score >= self.cfg.sync_threshold:
            proposals.extend(self._propose_freeze())
            return proposals

        if reflex_score < self.cfg.tune_threshold:
            proposals.extend(self._propose_tune(loop_state))

        return proposals

    def _propose_tune(self, loop_state: Dict) -> List[EvolutionProposal]:
        tuned = loop_state.get("tuned", {}) or {}
        base_decode = loop_state.get("base_decode", {}) or {}
        current_temp = tuned.get("temperature", base_decode.get("temperature", 0.7))
        step = max(0.0, float(self.cfg.incremental_step))
        new_temp = max(0.4, float(current_temp) - step)
        deltas = {"model.temperature": new_temp}
        return [
            EvolutionProposal(
                kind="runtime_tune",
                description=f"Tune temperature: {current_temp:.2f} → {new_temp:.2f}",
                apply=lambda: self._update_active_patch(deltas, loop_state),
            )
        ]

    def _propose_freeze(self) -> List[EvolutionProposal]:
        return [
            EvolutionProposal(
                kind="converged",
                description="State converged - freezing evolved baseline",
                apply=lambda: self._freeze_active_patch(),
            )
        ]

    def _update_active_patch(self, deltas: Dict, loop_state: Dict) -> str:
        patch_path = self.patch_path
        patch_path.parent.mkdir(parents=True, exist_ok=True)
        if patch_path.exists():
            try:
                patch = json.loads(patch_path.read_text(encoding="utf-8"))
            except Exception:
                patch = {}
        else:
            patch = {
                "version": 1,
                "created_at": datetime.now().isoformat(),
                "state": "evolving",
                "evolution_history": [],
            }

        overrides = patch.setdefault("overrides", {})
        overrides.update(deltas)

        patch["state"] = patch.get("state", "evolving")
        patch["last_updated"] = datetime.now().isoformat()
        patch["current_reflex_score"] = loop_state.get("scores", {}).get("reflex_score", 0)
        history = patch.setdefault("evolution_history", [])
        history.append(
            {
                "turn": len(history) + 1,
                "score": patch["current_reflex_score"],
                "tuned": deltas,
            }
        )
        max_turns = max(1, int(getattr(self.cfg, "max_history_turns", 50) or 50))
        if len(history) > max_turns:
            patch["evolution_history"] = history[-max_turns:]

        patch_path.write_text(json.dumps(patch, indent=2), encoding="utf-8")
        # Format deltas to match metrics style: just key=value
        parts = []
        for k, v in deltas.items():
            key_name = k.split('.')[-1]  # Get last part: "model.temperature" -> "temperature"
            if isinstance(v, float):
                parts.append(f"[italic grey70]{key_name}[/]=[green]{v:.3f}[/]")
            else:
                parts.append(f"[italic grey70]{key_name}[/]=[green]{v}[/]")
        formatted = " ".join(parts)
        return formatted  # Return styled string, no [evolution] prefix

    def _freeze_active_patch(self) -> str:
        patch_path = self.patch_path
        if not patch_path.exists():
            return "no active patch to freeze"

        try:
            patch = json.loads(patch_path.read_text(encoding="utf-8"))
        except Exception:
            return "failed to read active patch"

        now_str = datetime.now().isoformat()
        patch["state"] = "stable"
        patch["converged_at"] = now_str
        patch["last_updated"] = now_str

        # Snapshot backup disabled - uncomment below to re-enable
        # snapshot = patch_path.parent / f"converged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        # snapshot.write_text(json.dumps(patch, indent=2), encoding="utf-8")
        patch_path.write_text(json.dumps(patch, indent=2), encoding="utf-8")

        overrides = patch.get("overrides", {})
        # Format overrides to match metrics style: key=value
        parts = []
        for k, v in overrides.items():
            key_name = k.split('.')[-1]  # Get last part: "model.temperature" -> "temperature"
            if isinstance(v, float):
                parts.append(f"[italic grey70]{key_name}[/]=[green]{v:.3f}[/]")
            else:
                parts.append(f"[italic grey70]{key_name}[/]=[green]{v}[/]")
        formatted = " ".join(parts)
        return formatted  # Just the temperature=X.XXX, no prefix or archive info

    def _load_active_patch(self) -> Optional[Dict]:
        if not self.patch_path.exists():
            return None
        try:
            return json.loads(self.patch_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _unfreeze_patch(self) -> None:
        """Unfreeze a stable patch when performance degrades."""
        if not self.patch_path.exists():
            return
        try:
            patch = json.loads(self.patch_path.read_text(encoding="utf-8"))
            patch["state"] = "evolving"
            patch["last_updated"] = datetime.now().isoformat()
            self.patch_path.write_text(json.dumps(patch, indent=2), encoding="utf-8")
        except Exception:
            pass


__all__ = ["EvolutionController"]
