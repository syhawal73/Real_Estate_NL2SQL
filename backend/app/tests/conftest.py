"""
pytest fixtures for the property domain tests.

Strategy
--------
- ``db_engine``  (session scope) — one engine for the entire test run.
  Tables are created on setup and dropped on teardown.
- ``seed_data``  (session scope) — minimal representative rows are
  committed once so every test can read them.
- ``db_session`` (function scope) — each test runs inside an outer
  connection-level transaction that is rolled back after the test,
  keeping the seeded rows intact for the next test.
  ``join_transaction_mode="create_savepoint"`` ensures that any
  ``session.commit()`` calls inside the repository promote to a
  SAVEPOINT (not the outer transaction), so the outer rollback still
  undoes all test-side writes.

Environment
-----------
Set ``TEST_DATABASE_URL`` in your environment or in ``.env`` to point
at a dedicated PostgreSQL test database.  The default assumes a local
Postgres instance with no password.

Example::

    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/test_property_db
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.domain.property.models import Base, CityCenter, Property
import app.domain.chat.models  # noqa: F401 — registers ChatSession / ChatMessage with Base

# ---------------------------------------------------------------------------
# Test database URL
# ---------------------------------------------------------------------------
TEST_DATABASE_URL: str = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/test_property_db",
)

# ---------------------------------------------------------------------------
# Minimal seed data — enough to exercise every repository method and filter.
# Values deliberately chosen so filter tests have unambiguous expectations.
# ---------------------------------------------------------------------------
_CITY_CENTERS: list[dict[str, Any]] = [
    {"city": "London",  "latitude": 51.5074, "longitude": -0.1278},
    {"city": "Paris",   "latitude": 48.8566, "longitude":  2.3522},
]

_PROPERTIES: list[dict[str, Any]] = [
    {
        "id": 1,
        "title": "Two-Bed Apartment in Wembley",
        "city": "London",
        "neighbourhood": "Wembley",
        "intent": "rent",
        "price": 1_157,
        "bedrooms": 2,
        "bathrooms": 1,
        "size_sqm": 34,
        "property_type": "apartment",
        "distance_from_city_km": 4.3,
        "description": "A well-presented apartment in Wembley.",
    },
    {
        "id": 2,
        "title": "Three-Bed House in Canary Wharf",
        "city": "London",
        "neighbourhood": "Canary Wharf",
        "intent": "buy",
        "price": 450_000,
        "bedrooms": 3,
        "bathrooms": 2,
        "size_sqm": 120,
        "property_type": "house",
        "distance_from_city_km": 5.1,
        "description": "A spacious house near the financial district.",
    },
    {
        "id": 3,
        "title": "Studio Apartment in Montmartre",
        "city": "Paris",
        "neighbourhood": "Montmartre",
        "intent": "rent",
        "price": 900,
        "bedrooms": 1,
        "bathrooms": 1,
        "size_sqm": 28,
        "property_type": "apartment",
        "distance_from_city_km": 3.2,
        "description": "A cosy studio in the heart of Montmartre.",
    },
]

_TOTAL_SEEDED_PROPERTIES = len(_PROPERTIES)
_TOTAL_SEEDED_CITIES = len(_CITY_CENTERS)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create the test engine and schema once per test session.

    Drops all tables first to ensure a clean slate (idempotent).
    """
    _engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def seed_data(db_engine: AsyncEngine) -> None:
    """Seed representative test rows once per session.

    These rows are committed to the database and remain visible to all
    tests. Each test's changes are rolled back by the ``db_session``
    fixture so the seed state is never mutated.
    """
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            session.add_all([CityCenter(**cc) for cc in _CITY_CENTERS])
            session.add_all([Property(**p) for p in _PROPERTIES])


@pytest_asyncio.fixture(scope="function")
async def db_session(
    db_engine: AsyncEngine,
    seed_data: None,  # noqa: ARG001 — dependency ensures seed runs first
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated async session for each test.

    Opens an outer connection-level transaction that is always rolled
    back after the test, preserving the seeded data for the next test.
    ``join_transaction_mode="create_savepoint"`` ensures session-level
    commits demote to SAVEPOINTs so they cannot escape the outer tx.
    """
    async with db_engine.connect() as conn:
        await conn.begin()
        factory = async_sessionmaker(
            conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with factory() as session:
            yield session
        await conn.rollback()
