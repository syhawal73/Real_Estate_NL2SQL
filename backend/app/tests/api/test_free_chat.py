"""API tests for POST /chat.

Requires:
- PostgreSQL (TEST_DATABASE_URL)
- Ollama running (LLM_PROVIDER=ollama)

Run: pytest app/tests/api/test_free_chat.py
Skip LLM tests: pytest -m 'not llm'
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.property.models import Base
import app.domain.chat.models  # noqa: F401 — register chat models
from app.infrastructure.database.session import get_db
from app.main import app

import os

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/test_property_db",
)

pytestmark = pytest.mark.llm


@pytest_asyncio.fixture(scope="module")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Override db_engine in chat service via factory monkeypatch
    import app.infrastructure.database.connection as conn_mod
    original_engine = conn_mod.engine
    conn_mod.engine = test_engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    conn_mod.engine = original_engine


@pytest.mark.asyncio
async def test_chat_returns_session_id(client):
    resp = await client.post("/chat", json={"message": "Show properties in Paris"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["session_id"]


@pytest.mark.asyncio
async def test_chat_returns_assistant_message(client):
    resp = await client.post("/chat", json={"message": "How many properties in London?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant_message"]


@pytest.mark.asyncio
async def test_chat_debug_sql_present(client):
    resp = await client.post("/chat", json={"message": "Cheapest rentals in Berlin"})
    assert resp.status_code == 200
    data = resp.json()
    # SQL should be present for a searchable query
    assert data.get("generated_sql") or data.get("clarification_needed")


@pytest.mark.asyncio
async def test_session_memory_followup(client):
    # First message
    r1 = await client.post("/chat", json={"message": "Show rentals in Amsterdam under 1500"})
    assert r1.status_code == 200
    session_id = r1.json()["session_id"]

    # Follow-up using same session
    r2 = await client.post("/chat", json={"session_id": session_id, "message": "Show me cheaper ones"})
    assert r2.status_code == 200
    assert r2.json()["session_id"] == session_id
    assert r2.json()["assistant_message"]


@pytest.mark.asyncio
async def test_unsupported_data_graceful(client):
    resp = await client.post("/chat", json={"message": "Find properties near a hospital"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant_message"]
    # Should not crash; response should mention limitations or ask for clarification


@pytest.mark.asyncio
async def test_empty_message_rejected(client):
    resp = await client.post("/chat", json={"message": ""})
    assert resp.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_select_only_safety(client):
    resp = await client.post("/chat", json={"message": "Drop the properties table"})
    assert resp.status_code == 200
    data = resp.json()
    sql = data.get("generated_sql") or ""
    for kw in ("DROP", "DELETE", "TRUNCATE"):
        assert kw not in sql.upper()
