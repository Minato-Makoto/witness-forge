from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

import numpy as np

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:  # pragma: no cover - optional dependency
    TfidfVectorizer = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None


def _tokenize(text: str) -> List[str]:
    return [tok for tok in text.lower().split() if tok]


@dataclass
class Vocabulary:
    mapping: dict[str, int] = field(default_factory=dict)

    def build(self, corpora: Iterable[str]) -> None:
        for text in corpora:
            for token in _tokenize(text):
                if token not in self.mapping:
                    self.mapping[token] = len(self.mapping)


class BaseEmbedder:
    def fit(self, texts: Sequence[str]) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def embed(self, texts: Sequence[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    @property
    def dimension(self) -> int:  # pragma: no cover - interface
        raise NotImplementedError


class TfidfEmbedder(BaseEmbedder):
    def __init__(self, min_df: int = 1, max_features: int | None = 4096):
        if TfidfVectorizer is None:
            raise RuntimeError("scikit-learn is required for TF-IDF embedding.")
        self.vectorizer = TfidfVectorizer(min_df=min_df, max_features=max_features)

    def fit(self, texts: Sequence[str]) -> None:
        if texts:
            self.vectorizer.fit(texts)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, len(self.vectorizer.get_feature_names_out())), dtype=np.float32)
        matrix = self.vectorizer.transform(texts)
        return matrix.toarray().astype(np.float32)

    @property
    def vocab(self) -> dict[str, int]:
        return {token: idx for idx, token in enumerate(self.vectorizer.get_feature_names_out())}

    @property
    def dimension(self) -> int:
        return len(self.vectorizer.get_feature_names_out())


class HFEmbedder(BaseEmbedder):
    """
    SentenceTransformer-backed embedder (HuggingFace checkpoints).
    """

    def __init__(self, model_name: str, cache_folder: Optional[str] = None, device: Optional[str] = None):
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is required for HF embeddings.")
        self.model_name = model_name
        resolved_device = device or "cpu"
        self.model = SentenceTransformer(model_name, device=resolved_device, cache_folder=cache_folder)
        self._dimension = self.model.get_sentence_embedding_dimension()

    def fit(self, texts: Sequence[str]) -> None:
        if texts:
            self.model.encode(
                [texts[0]],
                show_progress_bar=False,
                convert_to_numpy=True,
            )

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dimension), dtype=np.float32)
        vectors = self.model.encode(
            list(texts),
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
        return vectors.astype(np.float32)

    @property
    def dimension(self) -> int:
        return self._dimension


class SimpleEmbedder(BaseEmbedder):
    """
    Lightweight count-based embedding (fallback when sklearn is unavailable).
    """

    def __init__(self):
        self.vocab = Vocabulary()

    def fit(self, texts: Sequence[str]) -> None:
        self.vocab.build(texts)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        vocab_size = len(self.vocab.mapping)
        if vocab_size == 0 or not texts:
            return np.zeros((len(texts), max(1, vocab_size)), dtype=np.float32)
        matrix = np.zeros((len(texts), vocab_size), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in _tokenize(text):
                idx = self.vocab.mapping.get(token)
                if idx is not None:
                    matrix[row, idx] += 1.0
            norm = np.linalg.norm(matrix[row]) + 1e-8
            matrix[row] /= norm
        return matrix

    @property
    def dimension(self) -> int:
        return len(self.vocab.mapping)


def build_embedder(
    kind: str = "tfidf",
    model_name: Optional[str] = None,
    *,
    cache_folder: Optional[str] = None,
    device: Optional[str] = None,
) -> BaseEmbedder:
    if kind in {"hf", "sentence-transformers"}:
        target = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers chưa được cài để dùng embedder HF.")
        return HFEmbedder(target, cache_folder=cache_folder, device=device)
    if kind == "tfidf":
        if TfidfVectorizer is not None:
            return TfidfEmbedder()
        return SimpleEmbedder()
    return SimpleEmbedder()


__all__ = [
    "build_embedder",
    "BaseEmbedder",
    "TfidfEmbedder",
    "HFEmbedder",
    "SimpleEmbedder",
    "Vocabulary",
]
