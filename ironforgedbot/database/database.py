from contextlib import asynccontextmanager
import logging
import os

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: Optional[str] = None) -> None:
        self._url = url or os.getenv("DATABASE_URL")
        self._engine: Optional[AsyncEngine] = None
        self._SessionFactory: Optional[sessionmaker] = None
        self._initialized = False

    def _initialize(self) -> None:
        """Lazy initialization of database connection."""
        if self._initialized:
            return
            
        if not self._url:
            raise RuntimeError("DATABASE_URL must be set")

        logger.info("Initializing database connection")
        
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
        
        self._initialized = True
        logger.info("Database connection initialized successfully")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager that yields a Session and commits/rolls back.
        Usage:
            async with db.get_session() as session:
                ...
        """
        self._initialize()
        if self._SessionFactory is None:
            raise RuntimeError("Database not properly initialized")
        async with self._SessionFactory() as session:
            try:
                logger.debug("Database session started")
                yield session
                # You can choose to commit here, or do it manually in your code
                # await session.commit()
                logger.debug("Database session completed successfully")
            except Exception as e:
                logger.error(f"Database session error: {e}", exc_info=True)
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
        if self._engine is not None:
            logger.info("Disposing database connections")
            await self._engine.dispose()
            logger.info("Database connections disposed")


db = Database()
