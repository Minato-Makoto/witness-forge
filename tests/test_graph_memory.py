from __future__ import annotations

from witness_forge.memory.graph_rag import GraphMemory


def test_graph_memory_add_and_search(tmp_path):
    path = tmp_path / "graph.json"
    gm = GraphMemory(str(path))
    node1 = gm.add("Hello world", [])
    node2 = gm.add("Another hello planet", [node1])

    results = gm.search("hello", top_k=5)
    texts = [t for t, _score in results]
    assert "Hello world" in texts
    assert "Another hello planet" in texts

    gm.save()
    # Reload to ensure persistence
    gm2 = GraphMemory(str(path))
    results2 = gm2.search("planet", top_k=3)
    assert any("planet" in t.lower() for t, _ in results2)
