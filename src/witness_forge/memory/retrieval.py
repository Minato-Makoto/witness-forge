from typing import List, Optional

from .embedding import BaseEmbedder
from .store import MemoryStore
from .vector_store import VectorStore


def build_vocab_from_mem(mem: List[str], min_freq: int = 2) -> dict[str, int]:
    vocab = {}
    for text in mem:
        for token in text.lower().split():
            if not token.isalpha():
                continue
            if token not in vocab and sum(1 for m in mem if token in m.lower()) >= min_freq:
                vocab[token] = len(vocab)
    return vocab


class Retriever:
    def __init__(
        self,
        store: MemoryStore,
        embedder: BaseEmbedder,
        vector_store: Optional[VectorStore],
        k: int = 6,
    ):
        self.store = store
        self.embedder = embedder
        self.vector_store = vector_store
        self.k = k

    def retrieve(self, query: str) -> List[str]:
        if self.vector_store and query.strip():
            vector = self.embedder.embed([query])
            if len(vector):
                matches = self.vector_store.search(vector[0], self.k)
                if matches:
                    return [text for text, _ in matches]
        return self.store.recent_memories(self.k)

    def graph(self, clusters: int = 4) -> List[List[str]]:
        if self.vector_store:
            return self.vector_store.graph(clusters)
        recents = self.store.recent_memories(self.k * clusters)
        step = max(1, len(recents) // clusters)
        return [recents[i : i + step] for i in range(0, len(recents), step)]
