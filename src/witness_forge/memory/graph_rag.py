from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx


class GraphMemory:
    """
    Simple graph-based memory using networkx.
    Nodes: id, text
    Edges: relation between texts/entities
    """

    def __init__(self, path: str = "./witness_graph.json"):
        self.path = Path(path)
        self.graph = nx.Graph()
        if self.path.exists():
            self._load()

    def add(self, text: str, related_to: List[str] | None = None) -> str:
        node_id = f"g{int(time.time()*1000)}_{len(self.graph)}"
        self.graph.add_node(node_id, text=text)
        for rel in related_to or []:
            if self.graph.has_node(rel):
                self.graph.add_edge(node_id, rel)
        return node_id

    def search(self, query: str, top_k: int = 6) -> List[Tuple[str, float]]:
        scores: List[Tuple[str, float]] = []
        q_lower = query.lower()
        for node_id, data in self.graph.nodes(data=True):
            text = data.get("text", "")
            if not text:
                continue
            score = self._score_text(q_lower, text.lower())
            if score > 0:
                scores.append((text, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def _score_text(self, query: str, text: str) -> float:
        if query in text:
            return 1.0
        overlap = len(set(query.split()) & set(text.split()))
        return overlap / max(1, len(query.split()))

    def save(self) -> None:
        data = nx.readwrite.json_graph.node_link_data(self.graph, edges="edges")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(__import__("json").dumps(data), encoding="utf-8")

    def _load(self) -> None:
        try:
            payload = self.path.read_text(encoding="utf-8")
            data = __import__("json").loads(payload or "{}")
            try:
                self.graph = nx.readwrite.json_graph.node_link_graph(data, edges="edges")
            except Exception:
                # Fallback to default key if edges param missing in legacy file
                self.graph = nx.readwrite.json_graph.node_link_graph(data)
        except Exception:
            self.graph = nx.Graph()


__all__ = ["GraphMemory"]
