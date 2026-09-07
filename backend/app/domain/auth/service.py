from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth.models import AuthSession, EmailVerificationToken, PasswordResetToken, User, UserFavorite, SavedSearch, RecentlyViewedProperty
from app.domain.auth.schemas import RegisterRequest, UpdateUserRequest
from app.infrastructure.security.passwords import hash_password, verify_password
from app.infrastructure.security.tokens import generate_token, hash_token

SESSION_DAYS = 14
TOKEN_HOURS = 24
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email.lower().strip()))
        return result.scalar_one_or_none()

    async def get_user(self, user_id: str) -> User | None:
        return await self.session.get(User, user_id)

    async def register(self, request: RegisterRequest) -> tuple[User, str]:
        if await self.get_user_by_email(request.email):
            raise ValueError("An account with that email already exists")
        user = User(
            email=request.email.lower().strip(),
            password_hash=hash_password(request.password),
            profile={"full_name": request.full_name} if request.full_name else {},
            email_verified=False,
        )
        self.session.add(user)
        await self.session.flush()
        token = generate_token()
        self.session.add(EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
        ))
        return user, token

    async def verify_email(self, token: str) -> bool:
        result = await self.session.execute(select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(token),
            EmailVerificationToken.used_at.is_(None),
        ))
        record = result.scalar_one_or_none()
        if not record or record.expires_at <= datetime.now(timezone.utc):
            return False
        user = await self.get_user(record.user_id)
        if not user:
            return False
        user.email_verified = True
        record.used_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.get_user_by_email(email)
        if not user:
            raise PermissionError("Invalid email or password")
        now = datetime.now(timezone.utc)
        if user.locked_until and user.locked_until > now:
            raise PermissionError("Account temporarily locked. Please try again later.")
        if not user.is_active:
            raise PermissionError("This account is disabled")
        if not verify_password(password, user.password_hash):
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                user.failed_login_count = 0
            await self.session.flush()
            raise PermissionError("Invalid email or password")
        if not user.email_verified:
            raise PermissionError("Please verify your email before signing in")
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        await self.session.flush()
        return user

    async def create_session(self, user: User, user_agent: str | None = None) -> str:
        raw = generate_token()
        self.session.add(AuthSession(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
            user_agent=user_agent,
        ))
        await self.session.flush()
        return raw

    async def user_from_session(self, raw_token: str | None) -> User | None:
        if not raw_token:
            return None
        result = await self.session.execute(select(AuthSession).where(
            AuthSession.token_hash == hash_token(raw_token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
        ))
        auth_session = result.scalar_one_or_none()
        if not auth_session:
            return None
        user = await self.get_user(auth_session.user_id)
        if not user or not user.is_active:
            return None
        return user

    async def revoke_session(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        result = await self.session.execute(select(AuthSession).where(AuthSession.token_hash == hash_token(raw_token)))
        row = result.scalar_one_or_none()
        if row:
            row.revoked_at = datetime.now(timezone.utc)

    async def revoke_all_sessions(self, user_id: str) -> None:
        await self.session.execute(
            delete(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        )

    async def create_password_reset(self, email: str) -> str | None:
        user = await self.get_user_by_email(email)
        if not user:
            return None
        raw = generate_token()
        self.session.add(PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        ))
        await self.session.flush()
        return raw

    async def reset_password(self, token: str, password: str) -> bool:
        result = await self.session.execute(select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(token),
            PasswordResetToken.used_at.is_(None),
        ))
        record = result.scalar_one_or_none()
        if not record or record.expires_at <= datetime.now(timezone.utc):
            return False
        user = await self.get_user(record.user_id)
        if not user:
            return False
        user.password_hash = hash_password(password)
        record.used_at = datetime.now(timezone.utc)
        await self.revoke_all_sessions(user.id)
        await self.session.flush()
        return True
