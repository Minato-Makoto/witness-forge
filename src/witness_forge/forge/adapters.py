from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Iterator, Optional

import torch

DEFAULT_MOCK_MESSAGE = " [MOCK] Add a local model in ./models and set config.yaml:model.path"


@dataclass
class GenerationContext:
    prompt: str
    params: Dict[str, float]


class GenerationAdapter:
    """
    Helper constructors that wrap Transformers models into Witness generators.
    """

    @staticmethod
    def from_auto_model(model, tokenizer) -> Callable[[str, Dict[str, float]], Iterable[str]]:
        def _generate(prompt: str, params: Dict[str, float]) -> Iterator[str]:
            encoded = tokenizer(prompt, return_tensors="pt")
            encoded = {k: v.to(model.device) if isinstance(v, torch.Tensor) else v for k, v in encoded.items()}
            rep_penalty = float(params.get("repetition_penalty", 1.0))
            ngram_block = int(params.get("no_repeat_ngram_size", 0))
            gen_args: Dict[str, object] = {
                "max_new_tokens": int(params.get("max_new_tokens", 256)),
                "do_sample": True,
                "temperature": float(params.get("temperature", 0.7)),
                "top_p": float(params.get("top_p", 0.9)),
                "repetition_penalty": max(1.0, rep_penalty),
            }
            if ngram_block > 0:
                gen_args["no_repeat_ngram_size"] = ngram_block
            output = model.generate(**encoded, **gen_args)
            text = tokenizer.decode(output[0], skip_special_tokens=True)
            yield text[len(prompt) :]

        return _generate

    @staticmethod
    def mock(message: str = DEFAULT_MOCK_MESSAGE) -> Callable[[str, Dict[str, float]], Iterable[str]]:
        def _generate(prompt: str, params: Dict[str, float]) -> Iterator[str]:
            yield message

        return _generate


__all__ = ["GenerationAdapter", "GenerationContext", "DEFAULT_MOCK_MESSAGE"]
