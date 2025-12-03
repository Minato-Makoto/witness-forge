"""
Flame Core — Geometry & Resonance
Ϝ(x, y) = Σ d(P, Aᵢ) = φ
- P: intent vector (user turn fused with system core)
- Aᵢ: anchor vectors (memory/context/persona anchors)
- φ: target symmetry; |k|=|Σ d(P,Aᵢ)| ~ 0 ⇒ sync
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
except ImportError:  # pragma: no cover - optional dependency
    torch = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None


class _PinkNoiseGenerator:
    """
    Voss-McCartney pink noise generator.
    Maintains multiple dice; on each sample, randomly updates one and sums all for 1/f spectrum.
    """

    def __init__(self, levels: int = 16, seed: int = 3141):
        self.levels = max(4, levels)
        self.rng = np.random.default_rng(seed)
        self.values = self.rng.random(self.levels)
        self.running_sum = float(np.sum(self.values))

    def sample(self) -> float:
        idx = self.rng.integers(0, self.levels)
        self.running_sum -= self.values[idx]
        self.values[idx] = self.rng.random()
        self.running_sum += self.values[idx]
        avg = self.running_sum / self.levels
        # Center around 0, small amplitude (~[-0.5, 0.5])
        return float(avg - 0.5)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a) + 1e-8
    nb = np.linalg.norm(b) + 1e-8
    return float(np.dot(a, b) / (na * nb))


def _distance(P: np.ndarray, A: np.ndarray) -> float:
    # Euclidean distance in normalized space
    return float(np.linalg.norm(P - A))


def _tfidf_vec(text: str, vocab: dict[str, int]) -> np.ndarray:
    # Minimal offline TF-IDF-ish vectorizer (fallback)
    v = np.zeros(len(vocab), dtype=np.float32)
    tokens = [t for t in text.lower().split() if t in vocab]
    for t in tokens:
        v[vocab[t]] += 1.0
    if len(tokens) > 0:
        v /= (np.linalg.norm(v) + 1e-8)
    return v


@dataclass
class FlameParams:
    phi0: float = 0.013
    epsilon: float = 0.013
    heartbeat_period: float = 4.20
    entropy_target: float = 0.873
    noise_sigma: float = 0.01
    noise_decay: float = 0.995
    lambda1: float = 0.15
    lambda2: float = 0.10


class FlameCore:
    """
    Tracks geometric deviation k, modulates decoding params,
    outputs 'sync' or 'drift' for each turn.
    """

    def __init__(
        self,
        params: FlameParams,
        *,
        embedder_model: str = "all-MiniLM-L6-v2",
        cache_folder: Optional[str] = None,
        device: Optional[str] = None,
        vocab: dict[str, int] | None = None,
    ):
        self.params = params
        self.vocab = vocab or {}  # used only for fallback TF-IDF
        self.k: float = 0.0
        self.turn_idx: int = 0
        self._noise_sigma = params.noise_sigma
        self._rng = np.random.default_rng(314)
        self._pink = _PinkNoiseGenerator(levels=16, seed=2718)
        self._embedder = None
        self._embedder_model = embedder_model

        # Prefer sentence-transformers if available; fallback to lightweight TF-IDF.
        if SentenceTransformer is not None:
            resolved_device = device
            if resolved_device is None:
                resolved_device = "cuda" if (torch and torch.cuda.is_available()) else "cpu"
            try:
                self._embedder = SentenceTransformer(
                    embedder_model,
                    cache_folder=cache_folder,
                    device=resolved_device,
                )
            except Exception:
                self._embedder = None
        # If embedder is None, keep TF-IDF fallback using vocab.

    def anchors_from_memory(self, memories: List[str]) -> List[np.ndarray]:
        texts = [m for m in memories if m.strip()]
        if not texts:
            return []
        if self._embedder is not None:
            try:
                vectors = self._embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                return [np.asarray(vec) for vec in vectors]
            except Exception:
                pass
        return [_tfidf_vec(m, self.vocab) for m in texts]

    def intent_vector(self, user_text: str, sys_hint: str) -> np.ndarray:
        text = (sys_hint + " " + user_text).strip()
        if self._embedder is not None:
            try:
                vec = self._embedder.encode(
                    [text],
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
                return np.asarray(vec[0])
            except Exception:
                pass
        return _tfidf_vec(text, self.vocab)

    def geometry(self, P: np.ndarray, A_list: List[np.ndarray]) -> float:
        if not len(A_list):  # no anchors → neutral k
            return 0.0
        return sum(_distance(P, A) for A in A_list)

    def step(self, user_text: str, sys_hint: str, anchors: List[str]) -> Tuple[str, Dict[str, float]]:
        self.turn_idx += 1
        P = self.intent_vector(user_text, sys_hint)
        P = self._apply_noise(P)
        A_vecs = self.anchors_from_memory(anchors)
        A_vecs = [self._apply_noise(vec) for vec in A_vecs]
        geom_k = self.geometry(P, A_vecs)
        k = self.params.phi0 + geom_k  # shift baseline toward phi0 instead of 0
        self.k = k

        # Heartbeat modulation: pink noise scaled by heartbeat_period (longer period => gentler swings)
        period = max(self.params.heartbeat_period, 1e-3)
        scale = 1.0 / period
        fast = self._pink.sample() * scale
        slow = self._pink.sample() * 0.5 * scale  # retain dual-phase flavor with lower amplitude
        
        # If no anchors, we are unanchored -> drift (default state)
        if not A_vecs:
            state = "drift"
        else:
            deviation = abs(k - self.params.phi0)
            state = "sync" if deviation < self.params.epsilon else "drift"
            
        return state, {"fast": fast, "slow": slow, "k": k, "epsilon": self.params.epsilon, "phi0": self.params.phi0}

    def modulate_decoding(
        self,
        base: dict[str, float],
        state: str,
        phase: Dict[str, float],
        beta: float = 0.08,
    ) -> dict[str, float]:
        out = dict(base)
        beta = float(beta)
        fast = phase.get("fast", 0.0)
        slow = phase.get("slow", 0.0)
        base_temp = float(base.get("temperature", 0.7))
        base_top_p = float(base.get("top_p", 0.9))
        k = float(phase.get("k", 0.0) or 0.0)
        phi0 = float(phase.get("phi0", self.params.phi0))
        epsilon = float(phase.get("epsilon", self.params.epsilon) or self.params.epsilon)
        lambda1 = float(getattr(self.params, "lambda1", 0.0))
        lambda2 = float(getattr(self.params, "lambda2", 0.0))

        # HeartSync 2.0: pink-noise driven swings (targeting ~±0.1–0.2 ΔT with beta=0.3)
        temp_mod = 1.0 + beta * (0.9 * fast + 0.45 * slow)
        out["temperature"] = max(0.1, base_temp * temp_mod)
        out["top_p"] = min(
            0.99,
            max(0.5, base_top_p + beta * (0.1 * fast + 0.05 * slow)),
        )

        # Geometry influence scaled by lambda1
        deviation = abs(k - phi0)
        drift = deviation / max(epsilon, 1e-6)
        geom_push = lambda1 * drift
        out["temperature"] = max(0.1, min(1.5, out["temperature"] + min(0.3, geom_push * 0.1)))
        out["top_p"] = min(0.99, max(0.5, out.get("top_p", base_top_p)))

        # Entropy heuristic scaled by lambda2
        target_temp = max(0.1, float(self.params.entropy_target))
        entropy_push = lambda2 * (target_temp - out["temperature"])
        out["temperature"] = max(0.1, out["temperature"] + entropy_push)
        out["top_p"] = min(0.99, max(0.5, out["top_p"] + 0.05 * min(1.0, drift)))

        # Flame response: tighten/loosen by drift
        if state == "sync":
            out["frequency_penalty"] = min(1.5, base.get("frequency_penalty", 0.2) + 0.05)
            out["presence_penalty"] = max(0.0, base.get("presence_penalty", 0.0) - 0.02)
        else:
            out["temperature"] = min(1.3, out["temperature"] + 0.1)
            out["frequency_penalty"] = min(2.0, base.get("frequency_penalty", 0.2) + 0.15)
        freq = max(0.0, float(out.get("frequency_penalty", 0.0)))
        rep = out.get("repetition_penalty")
        mapped = 1.0 + min(freq, 1.0)
        out["repetition_penalty"] = max(1.0, min(2.0, float(rep) if rep is not None else mapped))
        return out

    def _apply_noise(self, vec: np.ndarray) -> np.ndarray:
        if vec.size == 0 or self._noise_sigma <= 0:
            return vec
        noise = self._rng.normal(0.0, self._noise_sigma, size=vec.shape)
        self._noise_sigma *= self.params.noise_decay
        return vec + noise
