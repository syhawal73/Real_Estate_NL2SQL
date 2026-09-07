"""
Async SQLAlchemy engine.

The module-level ``engine`` singleton is imported by ``session.py`` and
by test helpers that need to operate at the connection level.

Re-creating the engine (e.g. in tests) is handled by passing a custom
URL to ``create_engine()``.
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config.settings import settings


def create_engine(database_url: str | None = None, echo: bool | None = None) -> AsyncEngine:
    """Instantiate and return an async SQLAlchemy engine.

    Args:
        database_url: Override the URL from settings. Useful in tests.
        echo: Override the SQL-echo flag from settings. Useful in tests.

    Returns:
        A configured :class:`AsyncEngine` instance.
    """
    return create_async_engine(
        database_url or settings.DATABASE_URL,
        echo=echo if echo is not None else settings.DB_ECHO,
        # Re-validate connections pulled from the pool before use.
        pool_pre_ping=True,
        # Conservative pool defaults — tune via env vars in later phases.
        pool_size=5,
        max_overflow=10,
    )


# Application-wide engine singleton.
engine: AsyncEngine = create_engine()
