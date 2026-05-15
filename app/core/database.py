"""Database configuration and session management."""

from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool, QueuePool
from app.core.config import settings


def get_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    """
    Create an async SQLAlchemy engine.

    Args:
        database_url: PostgreSQL async connection string
        echo: Whether to echo SQL statements

    Returns:
        AsyncEngine instance
    """
    # Use NullPool for serverless, QueuePool for standard deployments
    pool_class = NullPool if settings.environment == "production" else QueuePool

    # NullPool does not accept pool_size or max_overflow
    pool_kwargs = {}
    if pool_class is not NullPool:
        pool_kwargs = {"pool_size": 20, "max_overflow": 0}

    return create_async_engine(
        database_url,
        echo=echo,
        pool_class=pool_class,
        **pool_kwargs,
        pool_pre_ping=True,
    )


def get_async_session_local(engine: AsyncEngine) -> async_sessionmaker:
    """
    Create an async session factory.

    Args:
        engine: AsyncEngine instance

    Returns:
        async_sessionmaker instance
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# Initialize engine and session factory
engine = get_engine(settings.database_url)
async_session_local = get_async_session_local(engine)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to get a database session.

    Yields:
        AsyncSession instance
    """
    async with async_session_local() as session:
        yield session


async def init_db() -> None:
    """
    Initialize the database (create all tables).

    This is called on application startup.
    In production, prefer running `alembic upgrade head` instead.
    """
    # Import Base after models are defined
    try:
        from app.models import Base

        # Create all tables (idempotent)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


async def dispose_db() -> None:
    """
    Dispose of the database engine.

    This is called on application shutdown.
    """
    await engine.dispose()
