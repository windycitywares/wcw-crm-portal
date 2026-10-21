"""Live / Test switch: work on a copy of the live data, refresh the copy, and delete it when done (admins only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.config import get_settings
from app.core.database import engine
from app.core.permissions import Permission
from app.modules.users.deps import CurrentUser, SessionDep, require
from app.modules.users.models import User
from app.services.testenv import TestEnvironment

router = APIRouter(prefix="/settings/environment", tags=["settings: environment"])
Admin = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]


async def _out(stats: dict | None = None) -> dict:
    return await TestEnvironment(engine).status()


@router.get("", response_model=dict)
async def environment(response: Response, _: Admin):
    response.headers["Cache-Control"] = "no-store"
    return await _out()


@router.put("/mode", response_model=dict)
async def switch_mode(session: SessionDep, user: Admin, mode: str):
    """Test: copy the live data afresh and work on the copy. Live: back to the real data (the copy is kept until deleted)."""
    await session.close()
    stats = await TestEnvironment(engine).switch(mode, user)
    return await _out(stats)


@router.post("/sync", response_model=dict)
async def sync(session: SessionDep, user: Admin):
    """Replace the test data with a fresh copy of the live data (anything done during testing is lost)."""
    await session.close()
    return await _out(await TestEnvironment(engine).sync(user, switch_on=False))


@router.delete("/test-data", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_data(session: SessionDep, user: Admin):
    """Delete the test copy. Only while on live data."""
    await session.close()
    await TestEnvironment(engine).delete_copy(user)


@router.put("/mail-to", response_model=dict)
async def set_mail_to(session: SessionDep, user: Admin, email: str | None = None):
    """Where every email goes while test mode is on (none: emails are not sent at all)."""
    await session.close()
    await TestEnvironment(engine).set_mail_to(email, user)
    return await _out()
