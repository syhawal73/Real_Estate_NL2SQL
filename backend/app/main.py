"""FastAPI application entry point — Phase 4."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.free_chat import router as free_chat_router
from app.api.routes.auth import router as auth_router
from app.api.routes.account import router as account_router
from app.api.routes.admin import router as admin_router
from app.api.routes.health import router as health_router
from app.api.routes.metadata import router as metadata_router
from app.api.routes.properties import router as properties_router
from app.api.routes.stats import router as stats_router
from app.infrastructure.database.connection import engine
from app.config.settings import settings

# Import chat models to register them with Base.metadata
import app.domain.chat.models  # noqa: F401
import app.domain.auth.models  # noqa: F401
import app.domain.admin.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create all tables on startup (idempotent), dispose engine on shutdown."""
    from app.domain.property.models import Base
    from app.domain.auth.models import User
    from app.infrastructure.security.passwords import hash_password
    from sqlalchemy import select
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from app.infrastructure.database.session import get_db_context
    async with get_db_context() as db:
        existing = (await db.execute(select(User).where(User.email == settings.ADMIN_EMAIL.lower()))).scalar_one_or_none()
        if not existing:
            db.add(User(email=settings.ADMIN_EMAIL.lower(), password_hash=hash_password(settings.ADMIN_PASSWORD), role="ADMIN", is_active=True, email_verified=True, profile={"full_name": "Administrator"}))
        await db.commit()

        from app.domain.admin.models import AdminSetting
        from app.infrastructure.llm.factory import create_llm_provider, set_llm_provider
        rows = (await db.execute(select(AdminSetting).where(AdminSetting.key.like("llm.%")))).scalars().all()
        if rows:
            values = {r.key.removeprefix("llm."): r.value for r in rows}
            set_llm_provider(create_llm_provider(
                values.get("provider"), values.get("model"), values.get("api_key"), values.get("base_url"),
                float(values.get("temperature", settings.LLM_TEMPERATURE)), int(values.get("max_tokens", settings.LLM_MAX_TOKENS)),
            ))
    yield
    await engine.dispose()


app = FastAPI(
    title="Property Discovery Platform",
    description="REST API for property search with NL2SQL free-chat assistant.",
    version="4.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(account_router)
app.include_router(admin_router)
app.include_router(properties_router)
app.include_router(metadata_router)
app.include_router(stats_router)
app.include_router(free_chat_router)
