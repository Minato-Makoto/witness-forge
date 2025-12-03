import os
import sqlite3
import time
from typing import Callable, List, Optional, Sequence


class MemoryStore:
    def __init__(self, path: str):
        self.path = path
        self._init()
        self._semantic_hook: Optional[tuple[Callable[[Sequence[str]], Sequence], object]] = None

    def _init(self):
        conn = sqlite3.connect(self.path)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS messages(ts REAL, role TEXT, text TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS memories(ts REAL, text TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")
        conn.commit()
        conn.close()

    def add_message(self, role: str, text: str):
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO messages VALUES(?,?,?)", (time.time(), role, text))
        conn.commit()
        conn.close()

    def add_memory(self, text: str):
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO memories VALUES(?,?)", (time.time(), text))
        conn.commit()
        conn.close()
        self._maybe_index_semantic(text)

    def recent_memories(self, n: int = 64) -> List[str]:
        conn = sqlite3.connect(self.path)
        cur = conn.execute("SELECT text FROM memories ORDER BY ts DESC LIMIT ?", (n,))
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        return rows

    def attach_semantic_hook(
        self,
        encoder: Callable[[Sequence[str]], Sequence],
        vector_store,
    ) -> None:
        self._semantic_hook = (encoder, vector_store)

    def _maybe_index_semantic(self, text: str) -> None:
        if not self._semantic_hook or not text.strip():
            return
        encoder, vector_store = self._semantic_hook
        vector = encoder([text])
        try:
            vector_store.add(text, vector[0])
        except Exception:
            pass

    def prune_old_memories(self, max_age_days: int) -> int:
        """Remove memories older than max_age_days. Pass <= 0 to disable."""
        if max_age_days <= 0:
            return 0
        cutoff_ts = time.time() - (max_age_days * 86400)
        conn = sqlite3.connect(self.path)
        cursor = conn.execute(
            "DELETE FROM memories WHERE ts < ?", (cutoff_ts,)
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def prune_by_count(self, max_count: int) -> int:
        """Keep only the most recent max_count memories. Pass <= 0 to disable."""
        if max_count <= 0:
            return 0
        conn = sqlite3.connect(self.path)
        cursor = conn.execute(
            "DELETE FROM memories WHERE rowid NOT IN "
            "(SELECT rowid FROM memories ORDER BY ts DESC LIMIT ?)",
            (max_count,)
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def auto_prune(self, max_age: int, max_count: int) -> None:
        """Auto-prune based on config"""
        self.prune_old_memories(max_age)
        self.prune_by_count(max_count)

    def clear_all(self) -> int:
        """Clear all memories and messages. Returns total deleted count."""
        conn = sqlite3.connect(self.path)
        cursor1 = conn.execute("DELETE FROM memories")
        cursor2 = conn.execute("DELETE FROM messages")
        deleted = cursor1.rowcount + cursor2.rowcount
        conn.commit()
        conn.close()
        
        # Clear vector index if attached
        if self._semantic_hook:
            _, vector_store = self._semantic_hook
            try:
                vector_store.clear()
            except (AttributeError, Exception):
                # Vector store may not have clear() method
                pass
        
        return deleted
