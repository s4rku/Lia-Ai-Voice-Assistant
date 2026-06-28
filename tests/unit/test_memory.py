"""
Unit tests for the MemoryStore (SQLite layer only – no ChromaDB/embedder).
"""
import pytest
from unittest.mock import AsyncMock, patch

from assistant.memory.store import MemoryStore


@pytest.fixture
async def mem(tmp_path, monkeypatch):
    """Fresh MemoryStore with an in-memory DB."""
    from assistant.config import settings
    monkeypatch.setattr(settings, "memory_db_path", tmp_path / "test.db")
    monkeypatch.setattr(settings, "memory_chroma_path", tmp_path / "chroma")

    from assistant.database.db import Database
    test_db = Database()
    await test_db.init()

    import assistant.memory.store as store_mod
    monkeypatch.setattr(store_mod, "db", test_db)

    store = MemoryStore()
    # Skip ChromaDB / embedding init in tests
    store._chroma_client = None
    store._collection = None
    store._embedder = None
    return store


@pytest.mark.asyncio
async def test_new_session_returns_id(mem):
    sid = await mem.new_session()
    assert isinstance(sid, int)
    assert sid > 0


@pytest.mark.asyncio
async def test_save_and_recall_preference(mem):
    await mem.new_session()
    await mem.set_preference("theme", "dark")
    val = await mem.get_preference("theme")
    assert val == "dark"


@pytest.mark.asyncio
async def test_preference_default(mem):
    val = await mem.get_preference("nonexistent", default="light")
    assert val == "light"


@pytest.mark.asyncio
async def test_save_and_get_facts(mem):
    await mem.save_fact("habit", "User drinks coffee every morning.")
    facts = await mem.get_facts("habit")
    assert any("coffee" in f for f in facts)


@pytest.mark.asyncio
async def test_save_message_without_embedder(mem):
    await mem.new_session()
    # Should not raise even without ChromaDB
    await mem.save_message("user", "Hello Sarku!")
    await mem.save_message("assistant", "Hey there!")


@pytest.mark.asyncio
async def test_recall_similar_without_embedder(mem):
    results = await mem.recall_similar("hello")
    assert results == []
