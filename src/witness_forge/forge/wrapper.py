from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Protocol, Any, Dict


class LLMModel(ABC):
    """
    Backend-agnostic LLM interface. Returns an iterator to support streaming.
    """

    @abstractmethod
    def generate_iter(self, prompt: str, params: Dict[str, Any]) -> Iterator[str]:
        """
        Yield text chunks for the given prompt and decoding params.
        """
        raise NotImplementedError


class TokenizerLike(Protocol):
    def __call__(self, prompt: str, return_tensors: str | None = None) -> Any:  # pragma: no cover - protocol
        ...

    def decode(self, ids, skip_special_tokens: bool = True) -> str:  # pragma: no cover - protocol
        ...


__all__ = ["LLMModel", "TokenizerLike"]
