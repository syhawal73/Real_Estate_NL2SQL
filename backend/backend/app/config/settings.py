"""
Application settings loaded from environment variables (or .env file).

Usage:
    from app.config.settings import settings

    engine = create_async_engine(settings.DATABASE_URL)
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level application settings.

    All values are read from the process environment first, then from an
    optional ``.env`` file in the working directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str
    """Async-compatible PostgreSQL connection string.

    Accepted schemes (all auto-promoted to ``postgresql+asyncpg://``):
    - ``postgresql+asyncpg://``  – preferred, used as-is
    - ``postgresql://``          – promoted automatically
    - ``postgres://``            – promoted automatically (Heroku-style)
    """

    DB_ECHO: bool = False
    """When True, SQLAlchemy logs every SQL statement it emits."""

    # ------------------------------------------------------------------
    # Phase 4 — LLM
    # ------------------------------------------------------------------
    LLM_PROVIDER: str = "lmstudio"
    """Provider name: ollama | lmstudio | openai | anthropic | gemini"""

    LLM_MODEL: str = "google/gemma-3-4b"
    LLM_BASE_URL: str = "http://localhost:1234/v1"
    LLM_API_KEY: str = "lm-studio"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 1024

    # Authentication / session
    AUTH_COOKIE_NAME: str = "re_session"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: str = "lax"
    AUTH_COOKIE_DOMAIN: str | None = None
    FRONTEND_URL: str = "http://localhost:5173"
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "ChangeMe_12345!"

    # SMTP
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "no-reply@lumina-estates.local"

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _ensure_async_driver(cls, v: str) -> str:
        """Guarantee the connection URL uses the asyncpg driver.

        Accepts bare ``postgresql://`` and ``postgres://`` and upgrades
        them so callers never have to think about the driver string.
        """
        if not isinstance(v, str):
            return v
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


# Module-level singleton — import this everywhere.
settings = Settings()
