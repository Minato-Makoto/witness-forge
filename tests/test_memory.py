from witness_forge.memory.store import MemoryStore


def test_memory_store_roundtrip(tmp_path):
    store = MemoryStore(str(tmp_path / "witness.sqlite3"))
    store.add_memory("first")
    store.add_memory("second")
    memories = store.recent_memories(1)
    assert memories[0] == "second"


def test_message_logging(tmp_path):
    store = MemoryStore(str(tmp_path / "witness.sqlite3"))
    store.add_message("user", "hello")
    store.add_message("assistant", "hi there")
    recent = store.recent_memories()
    assert recent == []
