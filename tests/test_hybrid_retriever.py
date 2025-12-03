from __future__ import annotations

from witness_forge.memory.graph_rag import GraphMemory
from witness_forge.memory.hybrid_retriever import HybridRetriever


class DummyRetriever:
    def retrieve(self, query: str):
        return ["alpha match", "beta value"]

    def graph(self, clusters: int = 4):
        return [["alpha match"], ["beta value"]]


def test_hybrid_retriever_merges_graph_and_vector(tmp_path):
    base = DummyRetriever()
    gm = GraphMemory(str(tmp_path / "g.json"))
    gm.add("graph item one", [])
    hr = HybridRetriever(base, gm, k=4)

    results = hr.retrieve("graph")
    # Should include vector + graph (deduped) with limit k
    assert "graph item one" in results
    assert "alpha match" in results
    assert len(results) <= 4
