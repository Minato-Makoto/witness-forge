from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class DecodingStrategy:
    """
    Small helper that keeps baseline decoding parameters and applies overrides.
    """

    temperature: float = 0.7
    top_p: float = 0.9
    max_new_tokens: int = 512
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.2

    def as_dict(self) -> Dict[str, float]:
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_new_tokens": self.max_new_tokens,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
        }

    def apply(self, overrides: Dict[str, float] | None = None) -> Dict[str, float]:
        params = self.as_dict()
        if overrides:
            params.update(overrides)
        return params


def build_decoding_strategy(base: Dict[str, float]) -> DecodingStrategy:
    return DecodingStrategy(
        temperature=float(base.get("temperature", 0.7)),
        top_p=float(base.get("top_p", 0.9)),
        max_new_tokens=int(base.get("max_new_tokens", 512)),
        presence_penalty=float(base.get("presence_penalty", 0.0)),
        frequency_penalty=float(base.get("frequency_penalty", 0.2)),
    )


__all__ = ["DecodingStrategy", "build_decoding_strategy"]
