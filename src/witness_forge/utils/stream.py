from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional


@dataclass
class StreamSettings:
    width: int = 100
    flush_each: bool = True


def consume_stream(
    generator: Iterable[str],
    on_chunk: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Consume a token/segment generator, optionally streaming to a sink.
    Returns the concatenated text.
    """
    chunks: list[str] = []
    for chunk in generator:
        if not isinstance(chunk, str):
            chunk = str(chunk)
        chunks.append(chunk)
        if on_chunk:
            on_chunk(chunk)
    return "".join(chunks)


def console_sink(console, settings: StreamSettings | None = None) -> Callable[[str], None]:
    """
    Build a streaming sink for Rich console-like objects.
    """
    settings = settings or StreamSettings()

    def _write(chunk: str) -> None:
        console.print(chunk, end="", soft_wrap=True, width=settings.width)
        if settings.flush_each and hasattr(console, "file") and hasattr(console.file, "flush"):
            console.file.flush()

    return _write


__all__ = ["consume_stream", "console_sink", "StreamSettings"]
