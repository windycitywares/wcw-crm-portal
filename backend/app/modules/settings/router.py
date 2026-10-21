from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Response
from pydantic import EmailStr

from app.core.config import get_settings
from app.core.database import engine
from app.core.permissions import Permission
from app.integrations.email import Mail, SmtpEmailSender
from app.modules.users.deps import SessionDep, require
from app.modules.users.models import User
from app.services.testenv import TestEnvironment

from .groups import GROUPS, EmailSettings
from .service import SettingsService, smtp_config

router = APIRouter(prefix="/settings", tags=["settings"])
Admin = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]


@router.get("", response_model=list[dict])
async def list_groups(_: Admin) -> list[dict]:
    return [{"key": k, "label": label} for k, (label, _) in GROUPS.items()]


@router.get("/{key}", response_model=dict)
async def get_group(session: SessionDep, _: Admin, key: str) -> dict[str, Any]:
    return await SettingsService(session).get_public(key)


@router.put("/{key}", response_model=dict)
async def save_group(session: SessionDep, actor: Admin, key: str, values: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return await SettingsService(session).update(key, values, actor)


# ---- test mode (live/test switch) ----
import json as _json

@router.get("/environment")
async def environment(response: Response, _: Admin):
    response.headers["Cache-Control"] = "no-store"
    return await TestEnvironment(engine).status()


@router.put("/environment/mode")
async def switch_mode(session: SessionDep, user: Admin, mode: str):
    await session.close()
    stats = await TestEnvironment(engine).switch(mode, user)
    return await TestEnvironment(engine).status()


@router.post("/environment/sync")
async def sync_env(session: SessionDep, user: Admin):
    await session.close()
    return await TestEnvironment(engine).sync(user, switch_on=False)


@router.delete("/environment/test-data", status_code=204)
async def delete_test_data(session: SessionDep, user: Admin):
    await session.close()
    await TestEnvironment(engine).delete_copy(user)


@router.put("/environment/mail-to")
async def set_mail_to(session: SessionDep, user: Admin, email: str | None = None):
    await session.close()
    await TestEnvironment(engine).set_mail_to(email, user)
    return await TestEnvironment(engine).status()


@router.post("/email/test", response_model=dict)
async def send_test_email(session: SessionDep, actor: Admin, to: Annotated[EmailStr, Body(embed=True)]) -> dict[str, Any]:
    """Send one message with the saved settings right now and report the SMTP server's answer."""
    settings: EmailSettings = await SettingsService(session).get_model("email", factory=EmailSettings)
    if not settings.smtp_host or not settings.from_address:
        return {"ok": False, "detail": "Save the SMTP host and From address first."}
    try:
        await SmtpEmailSender(smtp_config(settings)).send(Mail(
            to=to, subject="Test email from the Windy City Wares CRM",
            text=f"This is a test sent by {actor.full_name} from Admin → Settings → Email.\n\nIf you can read it, outgoing email works.",
            reply_to=str(settings.reply_to) or None,
        ))
    except Exception as exc:  # noqa: BLE001 - show the SMTP error to the admin
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"[:500]}
    return {"ok": True, "detail": f"Sent to {to}. Check the inbox (and spam folder)."}
