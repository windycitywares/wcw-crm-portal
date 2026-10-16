from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.pagination import PageDep
from app.core.permissions import Permission, Role
from app.core.request import client_ip

from . import service
from .deps import CurrentUser, EmailSenderDep, SessionDep, require
from .models import User
from .schemas import (
    AdminSetPassword, DirectoryEntry, ForgotPasswordIn, LoginIn, MeOut, Message, PasswordChange, ProfileUpdate, ResetPasswordIn,
    RoleOut, TokenOut, UserCreate, UserOut, UserPage, UserUpdate,
)
from .service import AuthService, UserService

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])
Admin = Annotated[User, Depends(require(Permission.USERS_MANAGE))]


@auth_router.post("/login", response_model=TokenOut)
async def login(request: Request, session: SessionDep, data: LoginIn) -> TokenOut:
    return await AuthService(session).login(data.email, data.password, client_ip(request))


@auth_router.get("/me", response_model=MeOut)
async def me(user: CurrentUser) -> MeOut:
    return service.me_out(user)


@auth_router.patch("/me", response_model=MeOut)
async def update_me(session: SessionDep, user: CurrentUser, data: ProfileUpdate) -> MeOut:
    return await AuthService(session).update_profile(user, data)


@auth_router.post("/change-password", response_model=TokenOut)
async def change_password(request: Request, session: SessionDep, user: CurrentUser, data: PasswordChange) -> TokenOut:
    return await AuthService(session).change_password(user, data, client_ip(request))


@auth_router.post("/forgot-password", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(request: Request, session: SessionDep, sender: EmailSenderDep, data: ForgotPasswordIn) -> Message:
    await AuthService(session, sender).forgot_password(data.email, client_ip(request))
    return Message(detail="If that email belongs to an active account, a reset link is on its way.")


@auth_router.post("/reset-password", response_model=TokenOut)
async def reset_password(request: Request, session: SessionDep, data: ResetPasswordIn) -> TokenOut:
    return await AuthService(session).reset_password(data.token, data.new_password, client_ip(request))


@users_router.get("/roles", response_model=list[RoleOut])
async def list_roles(_: CurrentUser) -> list[RoleOut]:
    return service.roles()


@users_router.get("/directory", response_model=list[DirectoryEntry])
async def directory(session: SessionDep, _: CurrentUser) -> list[DirectoryEntry]:
    """Colleagues' names for every signed-in user (no emails, roles or sign-in data)."""
    return await UserService(session).directory()


@users_router.get("", response_model=UserPage)
async def list_users(
    session: SessionDep, _: Admin, page: PageDep, q: str | None = None, role: Role | None = None,
    active: bool | None = None,
) -> UserPage:
    return await UserService(session).list(page, q=q, role=role, active=active)


@users_router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(session: SessionDep, actor: Admin, data: UserCreate) -> UserOut:
    return await UserService(session).create(data, actor)


@users_router.get("/{user_id}", response_model=UserOut)
async def get_user(session: SessionDep, _: Admin, user_id: int) -> UserOut:
    return await UserService(session).get(user_id)


@users_router.patch("/{user_id}", response_model=UserOut)
async def update_user(session: SessionDep, actor: Admin, user_id: int, data: UserUpdate) -> UserOut:
    return await UserService(session).update(user_id, data, actor)


@users_router.post("/{user_id}/password", response_model=Message)
async def set_user_password(session: SessionDep, actor: Admin, user_id: int, data: AdminSetPassword) -> Message:
    await UserService(session).set_password(user_id, data.new_password, actor)
    return Message(detail="Password updated. The user must sign in again.")


router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
