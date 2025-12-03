from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .flame_core import FlameCore, FlameParams
from .evaluator import Evaluator
from ..config import ReflexTuningParams, AdapterTuningParams


@dataclass
class LoopConfig:
    reflex_min_score: float
    heart_beta: float
    flame_params: FlameParams
    reward_temperature: float = 0.02
    max_temperature: float = 1.2
    min_temperature: float = 0.4
    max_new_tokens: int = 1024
    reflex_tuning: ReflexTuningParams = ReflexTuningParams()
    adapter_tuning: AdapterTuningParams = AdapterTuningParams()
    flame_embedder_model: str = "all-MiniLM-L6-v2"
    flame_embedder_cache: str | None = None
    flame_embedder_device: str | None = None


class Loops:
    def __init__(self, cfg: LoopConfig, vocab: dict[str, int], adapter_mode: str = "none"):
        self.cfg = cfg
        self.flame = FlameCore(
            cfg.flame_params,
            embedder_model=cfg.flame_embedder_model,
            cache_folder=cfg.flame_embedder_cache,
            device=cfg.flame_embedder_device,
            vocab=vocab,
        )
        self.eval = Evaluator()
        self.adapter_mode = adapter_mode

    def after_generation(
        self,
        last_user: str,
        sys_hint: str,
        anchors: List[str],
        base_decode: Dict[str, float],
        output_text: str,
        history: List[str],
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        # 1) Flame step → state + phase
        state, phase = self.flame.step(last_user, sys_hint, anchors)
        tuned = self.flame.modulate_decoding(base_decode, state, phase, beta=self.cfg.heart_beta)

        # 2) Reflex evaluation (minimal, NDJSON-safe)
        scores = self.eval.quick_scores(output_text, history, last_user)
        reflex_score = scores["reflex_score"]

        # 3) Reflex tuning
        params = self.cfg.reflex_tuning
        if reflex_score < self.cfg.reflex_min_score:
            tuned["temperature"] = max(
                params.min_temperature,
                tuned["temperature"] - params.temperature_penalty_step
            )
            tuned["frequency_penalty"] = min(
                params.max_penalty,
                tuned.get("frequency_penalty", 0.2) + params.frequency_penalty_step
            )
            tuned["presence_penalty"] = min(
                params.max_penalty,
                tuned.get("presence_penalty", 0.0) + params.presence_penalty_step
            )
        else:
            tuned["temperature"] = max(
                self.cfg.min_temperature,
                tuned["temperature"] - self.cfg.reward_temperature,
            )

        if self.adapter_mode != "none":
            adapter_params = self.cfg.adapter_tuning
            tuned["max_new_tokens"] = min(
                adapter_params.max_tokens,
                tuned.get("max_new_tokens", 512)
            )
            tuned["temperature"] = min(
                adapter_params.temperature_limit,
                tuned["temperature"]
            )
            if self.adapter_mode == "qlora":
                tuned["top_p"] = min(
                    adapter_params.qlora_top_p,
                    tuned.get("top_p", 0.9)
                )

        tuned["temperature"] = min(self.cfg.max_temperature, max(self.cfg.min_temperature, tuned["temperature"]))
        tuned["max_new_tokens"] = min(self.cfg.max_new_tokens, tuned.get("max_new_tokens", self.cfg.max_new_tokens))

        loop_state = {
            "state": state,
            "phase": phase,
            "scores": scores,
            "base_decode": base_decode,
            "tuned": tuned,
            "heart_beta": self.cfg.heart_beta,
        }

        return tuned, loop_state
