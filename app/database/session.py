"""Database session management with SQLAlchemy 2.0 AsyncEngine."""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

# Engine configuration
engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

# SQLite does not support standard connection pooling parameters (pool_size, max_overflow)
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": 20,
            "max_overflow": 10,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }
    )

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing transactional database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
