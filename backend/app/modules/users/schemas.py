from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.core.permissions import Role

PASSWORD_MIN = 10


def _password(value: str) -> str:
    if len(value) < PASSWORD_MIN:
        raise ValueError(f"Use at least {PASSWORD_MIN} characters")
    if value.strip() != value or not value.strip():
        raise ValueError("Password can't start or end with a space")
    return value


Password = Annotated[str, Field(max_length=200), AfterValidator(_password)]


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    title: str | None
    phone: str | None
    timezone: str
    last_login_at: datetime | None
    created_at: datetime


class MeOut(UserOut):
    permissions: list[str]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeOut


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    title: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    timezone: str | None = Field(default=None, max_length=64)


class PasswordChange(BaseModel):
    current_password: str
    new_password: Password


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: Password


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    role: Role
    password: Password
    title: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    title: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)


class AdminSetPassword(BaseModel):
    new_password: Password


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class DirectoryEntry(BaseModel):
    """What every signed-in user may see about colleagues (names on notes, assignees …)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    title: str | None
    is_active: bool


class RoleOut(BaseModel):
    key: Role
    label: str
    permissions: list[str]


class Message(BaseModel):
    detail: str
