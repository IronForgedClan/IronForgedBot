from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite+aiosqlite:///bot_database.db"

# Create the async database engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Define the declarative base class for models
Base = declarative_base()

# Create async session factory
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


# Function to get an async session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# Function to initialize the database (create tables)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
