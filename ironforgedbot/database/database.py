from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base

DATABASE_URL = "sqlite+aiosqlite:///ironforged_bot.db"

Base = declarative_base()


class Database:
    _instance = None

    def __init__(self):
        """Ensure only one instance is created."""
        if not hasattr(self, "engine"):
            self.engine = create_async_engine(DATABASE_URL, echo=True)
            self.async_session_factory = async_sessionmaker(
                bind=self.engine, expire_on_commit=False, class_=AsyncSession
            )

    async def init_db(self):
        """Initialize the database and create tables."""
        async with self.engine.begin() as conn:
            print(Base.metadata.tables.keys())
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self):
        """Returns a new session instance in an async context."""
        async with self.async_session_factory() as session:
            yield session

    async def close(self):
        """Close the database connection."""
        await self.engine.dispose()


db = Database()
