from __future__ import annotations

import json
import time
from typing import Callable, Dict, Iterable, List, Optional

from rich.console import Console
from rich.style import Style


class StreamRenderer:
    """
    Renderer for CLI output with time and token tracking.
    Encapsulates all UI-related logic for metrics display.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.style_analysis = Style(color="cyan", bold=False)
        self.style_final = Style(color="green", bold=True)
        self.style_other = Style(color="white")
        self.start_time = time.time()
        self.generation_start_time: float | None = None
        self.token_count = 0

    def render_lines(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.stream(line)
        self.end()

    def stream(self, line: str) -> None:
        raw_line = line.strip()
        style = self.style_other
        try:
            event = json.loads(line)
            event_type = event.get("type", "event")
            style = self._style_for(event_type)
            
            # Special formatting for metric events
            if event_type == "metric":
                meta = event.get("meta", {})
                k = meta.get("k", 0.0)
                state = meta.get("state", "unknown")
                temp = meta.get("temperature", 0.0)
                reflex = meta.get("reflex_score", 0.0)
                raw_line = f"Flame: T={temp:.3f} state={state} k={k:.4f} reflex={reflex:.3f}"
            else:
                # Extract content from event (not raw JSON)
                raw_line = event.get("content", "")
        except Exception:
            pass
        self.console.print(raw_line, style=style, end="\n")

    def end(self) -> None:
        elapsed = time.time() - self.start_time
        self.console.print(f"{elapsed:.2f}s", style="italic grey70")

    def _style_for(self, label: str) -> Style:
        if label == "analysis":
            return self.style_analysis
        if label == "final":
            return self.style_final
        return self.style_other

    # === New methods for generation tracking ===

    def start_generation(self) -> None:
        """Start tracking time and tokens for a new generation."""
        self.generation_start_time = time.time()
        self.token_count = 0

    def create_stream_callback(
        self,
        user_callback: Optional[Callable[[str], None]] = None,
        style: str = "green bold",
    ) -> Callable[[str], None]:
        """
        Create a streaming callback that tracks tokens and optionally calls user's callback.
        
        Args:
            user_callback: Optional user callback to invoke with each token
            style: Rich console style for output
        
        Returns:
            Callback function for streaming
        """
        def callback(token: str) -> None:
            self.token_count += 1
            if user_callback:
                user_callback(token)
            else:
                self.console.print(token, style=style, end="")
        
        return callback

    def print_metrics(
        self,
        loop_info: Optional[str] = None,
        loop_state: Optional[Dict] = None,
        evolutions: Optional[List[str]] = None,
    ) -> None:
        """
        Print performance and evolution metrics.
        
        Args:
            loop_info: Optional loop debug info (Effective Temperature line)
            loop_state: Loop state dict to extract temperature from
            evolutions: List of evolution messages
        """
        # Print loop info (Effective Temperature line)
        if loop_info:
            self.console.print(loop_info, style="grey70 italic")

        # Calculate elapsed time
        elapsed = 0.0
        if self.generation_start_time:
            elapsed = time.time() - self.generation_start_time

        # Extract current temperature from loop state
        loop_state = loop_state or {}
        tuned = loop_state.get("tuned", {}) or {}
        base_decode = loop_state.get("base_decode", {}) or {}
        current_temp = tuned.get("temperature", base_decode.get("temperature", 0.7))

        # Build metrics line: time=X.XXs tokens=XX temperature=X.XXX
        metrics_parts = []
        metrics_parts.append(f"[italic grey70]time[/]=[green]{elapsed:.2f}s[/]")
        metrics_parts.append(f"[italic grey70]tokens[/]=[green]{self.token_count}[/]")
        
        # Check if evolution messages contain temperature tuning
        has_evolution_temp = False
        if evolutions:
            for note in evolutions:
                if not note.strip().lower().endswith("(no diff)"):
                    # Check if this evolution message contains temperature
                    if "temperature" in note.lower():
                        has_evolution_temp = True
                    metrics_parts.append(note)
        
        # Only add temperature if evolution didn't already include it
        if not has_evolution_temp:
            metrics_parts.append(f"[italic grey70]temperature[/]=[green]{current_temp:.3f}[/]")

        self.console.print(" ".join(metrics_parts))


__all__ = ["StreamRenderer"]
