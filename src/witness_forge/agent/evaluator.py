from __future__ import annotations
from typing import Dict, List


class Evaluator:
    def quick_scores(self, text: str, history: List[str], last_user: str) -> Dict[str, float]:
        """
        Lightweight reflex scoring without persona/thematic heuristics.
        """
        tokens = text.split()
        n = max(1, len(tokens))

        unique_ratio = len(set(tokens)) / float(n)
        repetition = max(0.0, min(1.0, unique_ratio))

        brevity = max(0.0, min(1.0, 1.0 - (n / 1200.0)))

        q = set(last_user.lower().split())
        r = {t.lower() for t in tokens}
        overlap = len(q & r) / max(1, len(q))
        relevance = max(0.0, min(1.0, overlap))

        reflex_score = round(0.45 * relevance + 0.35 * repetition + 0.20 * brevity, 4)
        return {
            "repetition": repetition,
            "relevance": relevance,
            "brevity": brevity,
            "reflex_score": reflex_score,
        }
