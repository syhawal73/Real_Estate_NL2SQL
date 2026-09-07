from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.infrastructure.security.passwords import validate_password_strength


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str = Field(min_length=5, max_length=320)
    role: str
    is_active: bool
    email_verified: bool
    created_at: datetime
    profile: dict


class AuthResponse(BaseModel):
    user: UserSchema
    message: str


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=10, max_length=128)
    role: str = Field(default="USER", pattern="^(USER|ADMIN)$")
    email_verified: bool = True
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UpdateUserRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(USER|ADMIN)$")
    is_active: bool | None = None
    full_name: str | None = Field(default=None, max_length=120)
