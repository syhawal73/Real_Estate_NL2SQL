"""FastAPI dependencies for DB services and authenticated users."""
from collections.abc import AsyncGenerator

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.domain.auth.models import User
from app.domain.auth.service import AuthService
from app.domain.property.service import PropertyService
from app.infrastructure.database.session import get_db


async def get_property_service(session: AsyncSession = Depends(get_db)) -> AsyncGenerator[PropertyService, None]:
    yield PropertyService(session)


async def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(session)


async def get_current_user(
    re_session: str | None = Cookie(default=None, alias=settings.AUTH_COOKIE_NAME),
    session: AsyncSession = Depends(get_db),
) -> User:
    user = await AuthService(session).user_from_session(re_session)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
