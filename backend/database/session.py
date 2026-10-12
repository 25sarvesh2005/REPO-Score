"""
Async PostgreSQL database session management and connectivity health checks.
"""

from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import settings
from backend.observability.logger import get_logger

logger = get_logger("reposcore.database")

from sqlalchemy import event, text


def _create_engine() -> AsyncEngine:
    if "sqlite" in settings.DATABASE_URL:
        eng = create_async_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False, "timeout": 30},
            echo=settings.DEBUG,
        )

        @event.listens_for(eng.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=15000")
            cursor.close()

        return eng

    return create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )


# Create asynchronous engine
engine: AsyncEngine = _create_engine()

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider for FastAPI route endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> str:
    """Verify database connection liveness by issuing SELECT 1."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            scalar = result.scalar()
            if scalar == 1:
                return "connected"
            return "unexpected_result"
    except Exception as exc:
        logger.warning(f"Database readiness health check failed: {exc}")
        return "disconnected"
