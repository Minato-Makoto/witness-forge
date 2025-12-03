from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover - optional
    try:
        import faisslite as faiss  # type: ignore
    except ImportError:
        faiss = None  # type: ignore[assignment]


class VectorStore:
    """
    Lightweight sqlite + (optional) faiss-lite index for semantic memories.
    """

    def __init__(
        self,
        db_path: str,
        dim: int,
        *,
        factory: str = "FlatIP",
        metric: str = "cosine",
        normalize: bool = True,
        index_path: str | None = None,
    ):
        self.db_path = db_path
        self.dim = dim
        self.factory = factory
        self.metric = metric
        self.normalize = normalize
        self.index_path = index_path

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_vectors(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              text TEXT,
              embedding BLOB,
              ts REAL
            )
            """
        )
        self.conn.commit()
        self._use_faiss = faiss is not None
        self._records: List[Tuple[int, str]] = []
        self._matrix = np.zeros((0, dim), dtype=np.float32)
        self._index = self._build_index()
        self._load_existing()

    def add(self, text: str, vector: np.ndarray) -> int:
        vec = self._normalize(vector)
        blob = vec.astype(np.float32).tobytes()
        cur = self.conn.execute(
            "INSERT INTO memory_vectors(text, embedding, ts) VALUES(?,?,?)",
            (text, sqlite3.Binary(blob), time.time()),
        )
        self.conn.commit()
        rowid = int(cur.lastrowid)
        self._records.append((rowid, text))
        self._matrix = np.vstack([self._matrix, vec[None, :]]) if self._matrix.size else vec[None, :]
        if self._use_faiss:
            self._index.add(vec.reshape(1, -1))
        return rowid

    def search(self, vector: np.ndarray, top_k: int = 6) -> List[Tuple[str, float]]:
        if not self._records or vector.size == 0:
            return []
        query = self._normalize(vector)
        if self._use_faiss and self._index is not None:
            scores, idxs = self._index.search(query.reshape(1, -1), top_k)
            return self._gather_results(idxs[0], scores[0])
        sims = self._matrix @ query
        top_idx = np.argsort(-sims)[:top_k]
        return [(self._records[i][1], float(sims[i])) for i in top_idx]

    def _gather_results(self, idxs: np.ndarray, scores: np.ndarray) -> List[Tuple[str, float]]:
        results = []
        for i, idx in enumerate(idxs):
            if idx < 0 or idx >= len(self._records):
                continue
            results.append((self._records[idx][1], float(scores[i])))
        return results

    def graph(self, clusters: int = 4) -> List[List[str]]:
        if len(self._records) < clusters or not self._matrix.size:
            return [list(text for _, text in self._records)]
        if faiss is None:
            return self._naive_clusters(clusters)
        kmeans = faiss.Kmeans(self.dim, clusters, niter=10)
        kmeans.train(self._matrix)
        distances, assignments = kmeans.index.search(self._matrix, 1)
        groups: List[List[str]] = [[] for _ in range(clusters)]
        for idx, (rid, text) in enumerate(self._records):
            bucket = int(assignments[idx][0])
            groups[bucket].append(text)
        return [g for g in groups if g]

    def _naive_clusters(self, clusters: int) -> List[List[str]]:
        step = max(1, len(self._records) // clusters)
        buckets = []
        for start in range(0, len(self._records), step):
            chunk = self._records[start : start + step]
            buckets.append([text for _, text in chunk])
        return buckets or [[]]

    def _load_existing(self) -> None:
        cur = self.conn.execute("SELECT id, text, embedding FROM memory_vectors ORDER BY ts ASC")
        records = cur.fetchall()
        if not records:
            return
        matrix = np.zeros((len(records), self.dim), dtype=np.float32)
        for idx, (rowid, text, blob) in enumerate(records):
            vec = np.frombuffer(blob, dtype=np.float32)
            if vec.size != self.dim:
                continue
            matrix[idx] = vec
            self._records.append((rowid, text))
        self._matrix = matrix[: len(self._records)]
        if self._use_faiss and self._matrix.size and self._index is not None:
            self._index.reset()
            self._index.add(self._matrix)

    def _build_index(self):
        if not self._use_faiss:
            return None
        
        if self.index_path and Path(self.index_path).exists():
            try:
                return faiss.read_index(self.index_path)
            except Exception:
                pass  # Fallback to new index if load fails

        metric = faiss.METRIC_INNER_PRODUCT if self.metric == "cosine" else faiss.METRIC_L2
        index = faiss.IndexFlatIP(self.dim) if metric == faiss.METRIC_INNER_PRODUCT else faiss.IndexFlatL2(self.dim)
        return index

    def save(self, path: str | None = None) -> None:
        """Save FAISS index to disk"""
        if not self._use_faiss or self._index is None:
            return
        
        target = path or self.index_path
        if not target:
            return
            
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, target)

    def load(self, path: str) -> None:
        """Load FAISS index from disk"""
        if not self._use_faiss:
            return
        
        if not Path(path).exists():
            raise FileNotFoundError(f"Index not found: {path}")
            
        self._index = faiss.read_index(path)
        self.index_path = path

    def _normalize(self, vector: np.ndarray) -> np.ndarray:
        vec = vector.astype(np.float32)
        if not self.normalize:
            return vec
        norm = np.linalg.norm(vec) + 1e-8
        return vec / norm

    def clear(self) -> int:
        """Clear all vectors from both in-memory cache and SQLite. Returns count deleted."""
        # Get count before clearing
        cursor = self.conn.execute("SELECT COUNT(*) FROM memory_vectors")
        count = cursor.fetchone()[0]
        
        # Clear SQLite table
        self.conn.execute("DELETE FROM memory_vectors")
        self.conn.commit()
        
        # Clear in-memory structures
        self._records.clear()
        self._matrix = np.zeros((0, self.dim), dtype=np.float32)
        
        # Reset FAISS index if using
        if self._use_faiss and self._index is not None:
            self._index.reset()
        
        return count

    def close(self) -> None:
        """Close the SQLite connection."""
        if self.conn:
            self.conn.close()


__all__ = ["VectorStore"]
