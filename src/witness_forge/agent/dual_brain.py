from __future__ import annotations

from typing import Any, Dict, List, Optional

from .dual_brain_engine import DualBrainEngine
from .ndjson_emitter import to_lines
from .witness import WitnessAgent


class DualBrain(DualBrainEngine):
    """
    NDJSON-first dual brain wrapper.
    """

    def __init__(self, witness_agent: WitnessAgent, servant_agent: Optional[WitnessAgent] = None, *, force_dual: bool = False) -> None:
        super().__init__(witness_agent, servant_agent, force_dual=force_dual)

    def step(
        self,
        user_input: str,
        context: Optional[List[str]] = None,
        *,
        system_instruction: Optional[str] = None,
        stream_analysis=None,
        stream_final=None,
    ) -> Dict[str, Any]:
        result = super().step(
            user_input,
            context_memory=context or [],
            system_instruction=system_instruction,
            stream_analysis=stream_analysis,
            stream_final=stream_final,
        )
        if not result.get("lines"):
            result["lines"] = to_lines(result.get("events", []))
        return result


__all__ = ["DualBrain", "DualBrainEngine"]
