"""
Async session factory and ``get_db`` dependency.

``get_db`` is written as an async generator so it integrates with
FastAPI's dependency injection in later phases, and can also be used
directly with ``async for`` in scripts or tests.

Example (future FastAPI usage)::

    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.infrastructure.database.session import get_db

    @router.get("/properties/{id}")
    async def get_property(
        property_id: int,
        db: AsyncSession = Depends(get_db),
    ) -> PropertySchema:
        ...
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.connection import engine

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,   # keep objects usable after commit without reload
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional async database session.

    The session is committed on clean exit and rolled back on any
    exception, then closed in both cases.

    Yields:
        An :class:`AsyncSession` bound to the application engine.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
