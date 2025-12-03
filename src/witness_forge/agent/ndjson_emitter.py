from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional


def make_event(event_type: str, content: str, *, brain: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Build a normalized NDJSON event object.
    """
    event: Dict[str, Any] = {"type": event_type, "content": content or ""}
    if brain:
        event["brain"] = brain
    if meta:
        event["meta"] = meta
    return event


def to_line(event: Dict[str, Any]) -> str:
    """
    Serialize a single event to an NDJSON line (UTF-8, no ASCII forcing).
    """
    return json.dumps(event, ensure_ascii=False)


def to_lines(events: Iterable[Dict[str, Any]]) -> List[str]:
    """
    Serialize a list/iterator of events to NDJSON lines.
    """
    return [to_line(evt) for evt in events]


def wrap(event_type: str, content: str, *, brain: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Convenience helper to build a single-item NDJSON event list.
    """
    return [make_event(event_type, content, brain=brain, meta=meta)]


__all__ = ["make_event", "to_line", "to_lines", "wrap"]
