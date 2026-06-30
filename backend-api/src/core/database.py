"""
Purpose: Core database connectivity and session management.
Responsibilities:
- Initialize the SQLAlchemy 2.0 async engine.
- Configure connection pooling suitable for production loads.
- Provide a FastAPI dependency (`get_db`) for injecting async sessions.
Dependencies: sqlalchemy.ext.asyncio, src.core.config
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings

logger = logging.getLogger(__name__)

# Fail fast if config is somehow loaded but URI is missing
if not settings.SQLALCHEMY_DATABASE_URI:
    logger.critical("Database URI is missing. Cannot initialize database engine.")
    raise ValueError("SQLALCHEMY_DATABASE_URI must be configured.")

# Production connection pooling configuration:
# pool_size: Standard number of connections kept open. (Set to 20 to support high concurrency)
# max_overflow: Temporary burst connections allowed above pool_size.
# pool_timeout: How long to wait for a connection before throwing a TimeoutError.
# pool_pre_ping: Pessimistic checking. Emits "SELECT 1" to ensure connection is alive before use.
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,
    echo=settings.LOG_LEVEL == "DEBUG",  # Only echo raw SQL if we are explicitly debugging
)

# Session factory tailored for async operations
# expire_on_commit=False is crucial for async SQLAlchemy to prevent DetachedInstanceErrors
# when accessing model attributes outside of the immediate transaction context.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for injecting database sessions.
    Automatically handles yielding the session, catching errors, rolling back
    failed transactions, and safely closing the connection back to the pool.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database transaction rolled back due to error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
