from __future__ import annotations

from typing import List, Optional, Tuple

from .graph_rag import GraphMemory
from .retrieval import Retriever


class HybridRetriever:
    """
    Combines VectorStore-based retriever with GraphMemory results.
    """

    def __init__(
        self,
        base_retriever: Retriever,
        graph: Optional[GraphMemory] = None,
        k: int = 6,
    ):
        self.base = base_retriever
        self.graph = graph
        self.k = k

    def retrieve(self, query: str) -> List[str]:
        seen = set()
        items: List[str] = []
        if self.base:
            for item in self.base.retrieve(query)[: self.k]:
                if item not in seen:
                    items.append(item)
                    seen.add(item)
        if self.graph:
            for text, _score in self.graph.search(query, top_k=self.k):
                if text not in seen:
                    items.append(text)
                    seen.add(text)
        return items[: self.k]

    def graph_view(self, clusters: int = 4) -> List[List[str]]:
        if self.base and hasattr(self.base, "graph"):
            try:
                return self.base.graph(clusters)
            except Exception:
                pass
        return []


__all__ = ["HybridRetriever"]
