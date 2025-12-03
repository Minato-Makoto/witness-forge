from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence, Tuple


ScoreFn = Callable[[str, str], float]


@dataclass
class RerankStrategy:
    """Simple reranker guided by a scoring callback."""

    scorer: ScoreFn

    def rerank(self, query: str, candidates: Sequence[str], limit: int | None = None) -> List[Tuple[str, float]]:
        scored = [(cand, self.scorer(query, cand)) for cand in candidates]
        scored.sort(key=lambda item: item[1], reverse=True)
        if limit is not None:
            scored = scored[:limit]
        return scored


def token_overlap_scorer(query: str, candidate: str) -> float:
    q_tokens = set(query.lower().split())
    c_tokens = set(candidate.lower().split())
    if not q_tokens:
        return 0.0
    return len(q_tokens & c_tokens) / len(q_tokens)


__all__ = ["RerankStrategy", "token_overlap_scorer"]
