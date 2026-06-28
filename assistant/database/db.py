"""
Async SQLite database wrapper using SQLAlchemy 2 + aiosqlite.
Handles schema creation and provides a session factory.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from assistant.config import settings


class Base(DeclarativeBase):
    pass


class Database:
    """Singleton async DB wrapper. Call `await db.init()` once at startup."""

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def init(self) -> None:
        db_path = settings.memory_db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        url = f"sqlite+aiosqlite:///{db_path}"
        self._engine = create_async_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

        # Enable WAL for concurrent reads
        async with self._engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA foreign_keys=ON"))

        # Create all tables
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialised at {}", db_path)

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connection closed.")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if self._session_factory is None:
            raise RuntimeError("Database not initialised. Call await db.init() first.")
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# Global singleton
_db_instance: Database = Database()


async def get_db() -> Database:
    """Return the initialised database singleton."""
    return _db_instance
