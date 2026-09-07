from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.config.settings import settings
from app.domain.auth.models import User
from app.domain.auth.schemas import AuthResponse, ChangePasswordRequest, LoginRequest, PasswordResetConfirm, PasswordResetRequest, RegisterRequest, UserSchema
from app.domain.auth.service import AuthService
from app.infrastructure.email.service import send_email
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/auth", tags=["authentication"])


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        user, token = await service.register(body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    send_email(user.email, "Verify your Lumina Estates account", f"Verify your account: {verification_url}")
    return AuthResponse(user=UserSchema.model_validate(user), message="Account created. Check your email to verify it.")


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    ok = await AuthService(db).verify_email(token)
    if not ok:
        raise HTTPException(status_code=400, detail="Verification token is invalid or expired")
    await db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        user = await service.authenticate(body.email, body.password)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    token = await service.create_session(user, request.headers.get("user-agent"))
    await db.commit()
    _set_cookie(response, token)
    return AuthResponse(user=UserSchema.model_validate(user), message="Signed in successfully")


@router.post("/logout")
async def logout(
    response: Response,
    re_session: str | None = Cookie(default=None, alias=settings.AUTH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    await AuthService(db).revoke_session(re_session)
    await db.commit()
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/", domain=settings.AUTH_COOKIE_DOMAIN)
    return {"message": "Signed out"}


@router.post("/logout-all")
async def logout_all(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await AuthService(db).revoke_all_sessions(user.id)
    await db.commit()
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/", domain=settings.AUTH_COOKIE_DOMAIN)
    return {"message": "Signed out from all devices"}


@router.get("/me", response_model=UserSchema)
async def me(user: User = Depends(get_current_user)):
    return UserSchema.model_validate(user)


@router.post("/forgot-password")
async def forgot_password(body: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    token = await AuthService(db).create_password_reset(body.email)
    await db.commit()
    if token:
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        send_email(body.email, "Reset your Lumina Estates password", f"Reset your password: {reset_url}")
    return {"message": "If that email is registered, password reset instructions have been sent."}


@router.post("/reset-password")
async def reset_password(body: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    ok = await AuthService(db).reset_password(body.token, body.password)
    if not ok:
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    await db.commit()
    return {"message": "Password updated. Please sign in again."}


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.infrastructure.security.passwords import hash_password, verify_password
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current password")
    user.password_hash = hash_password(body.new_password)
    await AuthService(db).revoke_all_sessions(user.id)
    await db.commit()
    return {"message": "Password changed. Please sign in again."}
