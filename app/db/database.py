from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings
# Replace with your actual PostgreSQL connection string (using asyncpg driver)
DATABASE_URL = setings.database_url
#"sqlite+aiosqlite:///./test.db"

# Create the asynchronous engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
    connect_args={"check_same_thread": False}, # please note: remove from production
)

# Create the sessionmaker factory
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Dependency to get the database session in FastAPI endpoints
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

