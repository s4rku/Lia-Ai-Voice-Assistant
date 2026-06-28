"""
Memory store – two layers:

Short-term : rolling deque in RAM (already in ConversationLoop)
Long-term  : ChromaDB vector store + SQLite KnowledgeFact table

The MemoryStore class is the single entry point for Phase 3 memory operations.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import select

from assistant.config import settings
from assistant.core.types import Message, Role
from assistant.database.db import _db_instance as db
from assistant.database.models import (
    ChatMessage,
    ConversationSession,
    KnowledgeFact,
    UserPreference,
)

# chromadb is optional so tests run without it
try:
    import chromadb  # type: ignore
    from chromadb.config import Settings as ChromaSettings  # type: ignore
    _CHROMA_AVAILABLE = True
except ImportError:
    chromadb = None  # type: ignore
    ChromaSettings = None  # type: ignore
    _CHROMA_AVAILABLE = False
    logger.warning("chromadb not installed – long-term semantic memory disabled.")

# sentence-transformers is optional
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _ST_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore
    _ST_AVAILABLE = False


class MemoryStore:
    """
    Manages all persistent memory for Sarku.

    • save_message()         – persist a chat message to SQLite
    • recall_similar()       – semantic search in ChromaDB
    • save_fact()            – store a long-term user fact
    • get_facts()            – retrieve facts by category
    • set_preference() / get_preference()
    """

    def __init__(self) -> None:
        self._chroma_client: Any = None
        self._collection: Any = None
        self._embedder: Any = None
        self._session_id: int | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def init(self) -> None:
        """Set up ChromaDB collection and embedding model."""
        if _CHROMA_AVAILABLE:
            await self._init_chroma()
        if _ST_AVAILABLE:
            await self._init_embedder()

    async def _init_chroma(self) -> None:
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._init_chroma_sync)

    def _init_chroma_sync(self) -> None:
        path = str(settings.memory_chroma_path)
        settings.memory_chroma_path.mkdir(parents=True, exist_ok=True)
        self._chroma_client = chromadb.PersistentClient(path=path)
        self._collection = self._chroma_client.get_or_create_collection(
            name="sarku_memory",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection ready at {}", path)

    async def _init_embedder(self) -> None:
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._init_embedder_sync)

    def _init_embedder_sync(self) -> None:
        self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded.")

    # ── Session management ────────────────────────────────────────────────────
    async def new_session(self) -> int:
        """Create a new ConversationSession row, return its ID."""
        async with db.session() as s:
            sess = ConversationSession(started_at=datetime.utcnow())
            s.add(sess)
            await s.flush()
            self._session_id = sess.id
        logger.debug("New conversation session id={}", self._session_id)
        return self._session_id  # type: ignore[return-value]

    async def close_session(self, summary: str | None = None) -> None:
        if self._session_id is None:
            return
        async with db.session() as s:
            sess = await s.get(ConversationSession, self._session_id)
            if sess:
                sess.ended_at = datetime.utcnow()
                if summary:
                    sess.summary = summary
        self._session_id = None

    # ── Message persistence ───────────────────────────────────────────────────
    async def save_message(
        self,
        role: str,
        content: str,
        tokens: int = 0,
        latency_ms: float = 0.0,
    ) -> None:
        if not self._session_id:
            await self.new_session()

        async with db.session() as s:
            msg = ChatMessage(
                session_id=self._session_id,
                role=role,
                content=content,
                tokens_used=tokens,
                latency_ms=latency_ms,
            )
            s.add(msg)

        # Also index in vector store for semantic recall
        if self._collection and self._embedder and role == "user":
            await self._index_message(content)

    async def _index_message(self, text: str) -> None:
        """Embed and upsert message into ChromaDB."""
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._index_sync, text)

    def _index_sync(self, text: str) -> None:
        vec = self._embedder.encode(text).tolist()
        doc_id = f"msg_{datetime.utcnow().timestamp()}"
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[vec],
            documents=[text],
            metadatas=[{"ts": datetime.utcnow().isoformat(), "role": "user"}],
        )

    # ── Semantic recall ───────────────────────────────────────────────────────
    async def recall_similar(self, query: str, n: int = 5) -> list[str]:
        """Return top-n semantically similar past messages."""
        if not self._collection or not self._embedder:
            return []
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._recall_sync, query, n)

    def _recall_sync(self, query: str, n: int) -> list[str]:
        vec = self._embedder.encode(query).tolist()
        results = self._collection.query(query_embeddings=[vec], n_results=n)
        docs: list[str] = results.get("documents", [[]])[0]
        return docs

    # ── Long-term facts ───────────────────────────────────────────────────────
    async def save_fact(
        self,
        category: str,
        fact: str,
        source: str = "conversation",
        confidence: float = 1.0,
    ) -> None:
        async with db.session() as s:
            s.add(KnowledgeFact(
                category=category,
                fact=fact,
                source=source,
                confidence=confidence,
            ))

    async def get_facts(self, category: str | None = None) -> list[str]:
        async with db.session() as s:
            stmt = select(KnowledgeFact)
            if category:
                stmt = stmt.where(KnowledgeFact.category == category)
            rows = (await s.execute(stmt)).scalars().all()
            return [r.fact for r in rows]

    # ── User preferences ──────────────────────────────────────────────────────
    async def set_preference(self, key: str, value: str) -> None:
        async with db.session() as s:
            existing = (
                await s.execute(select(UserPreference).where(UserPreference.key == key))
            ).scalar_one_or_none()
            if existing:
                existing.value = value
            else:
                s.add(UserPreference(key=key, value=value))

    async def get_preference(self, key: str, default: str = "") -> str:
        async with db.session() as s:
            row = (
                await s.execute(select(UserPreference).where(UserPreference.key == key))
            ).scalar_one_or_none()
            return row.value if row else default


# Module singleton
memory: MemoryStore = MemoryStore()
