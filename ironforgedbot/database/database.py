from contextlib import asynccontextmanager
import os

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str = None) -> None:
        self._url = url or os.getenv("DATABASE_URL")
        if not self._url:
            raise RuntimeError("DATABASE_URL must be set")

        self._engine: AsyncEngine = create_async_engine(
            self._url,
            echo=False,  # True for SQL debug
            pool_pre_ping=True,
            future=True,
        )

        self._SessionFactory = sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager that yields a Session and commits/rolls back.
        Usage:
            async with db.get_session() as session:
                ...
        """
        async with self._SessionFactory() as session:
            try:
                yield session
                # You can choose to commit here, or do it manually in your code
                # await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                # optional: close() is auto-called by async contextmanager
                await session.close()

    async def dispose(self) -> None:
        """
        Cleanly close all connections in the pool.
        Call at application shutdown.
        """
        await self._engine.dispose()


db = Database()
