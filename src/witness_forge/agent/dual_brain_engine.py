from __future__ import annotations

from typing import Any, Dict, List, Optional

from .witness import WitnessAgent


class DualBrainEngine:
    """
    Minimal dual-brain orchestrator:
    - path1 = primary brain
    - path2 = secondary brain (optional)
    - force_dual=True runs both even if path2 is missing (fallback to path1 twice)
    """

    def __init__(self, path1: WitnessAgent, path2: Optional[WitnessAgent] = None, *, force_dual: bool = False) -> None:
        self.path1 = path1
        self.path2 = path2
        self.force_dual = force_dual

    def step(
        self,
        user_input: str,
        *,
        system_instruction: Optional[str] = None,
        context_memory: Optional[List[str]] = None,
        stream_analysis=None,
        stream_final=None,
    ) -> Dict[str, Any]:
        ctx = context_memory or []
        events: List[Dict[str, Any]] = []
        lines: List[str] = []

        primary = self.path1.step(
            user_input,
            role="witness",
            context_memory=ctx,
            return_events=True,
            system_instruction=system_instruction,
            stream=stream_analysis,
        )
        events.extend(primary.get("events", []))
        lines.extend(primary.get("lines", []))
        loop_state = primary.get("loop_state")

        dual_active = self.force_dual or self.path2 is not None
        if dual_active:
            # Inject separator between brains
            if stream_analysis:
                stream_analysis("\n\n")
                
            secondary_agent = self.path2 or self.path1
            
            # Use continuation mode if using the same agent instance (shared history)
            is_shared = secondary_agent is self.path1
            # print(f"[DEBUG] Path1: {id(self.path1)}, Path2: {id(self.path2)}, Secondary: {id(secondary_agent)}, IsShared: {is_shared}")
            secondary = secondary_agent.step(
                user_input,
                role="servant",
                context_memory=ctx,
                return_events=True,
                system_instruction=system_instruction,
                stream=stream_final,
                continuation=is_shared,
            )
            events.extend(secondary.get("events", []))
            lines.extend(secondary.get("lines", []))
            if loop_state is None:
                loop_state = secondary.get("loop_state")

        return {
            "events": events,
            "lines": lines,
            "loop_state": loop_state,
        }


__all__ = ["DualBrainEngine"]
