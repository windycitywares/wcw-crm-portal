from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from pydantic import EmailStr

from app.core.permissions import Permission
from app.integrations.email import Mail, SmtpConfig, SmtpEmailSender
from app.modules.users.deps import SessionDep, require
from app.modules.users.models import User

from .groups import GROUPS, EmailSettings
from .service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])
Admin = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]


def smtp_config(s: EmailSettings) -> SmtpConfig:
    return SmtpConfig(host=s.smtp_host, port=s.smtp_port, security=s.smtp_security, user=s.smtp_user or None,
                      password=s.smtp_password or None, from_address=str(s.from_address), from_name=s.from_name)


@router.get("", response_model=list[dict])
async def list_groups(_: Admin) -> list[dict]:
    return [{"key": k, "label": label} for k, (label, _) in GROUPS.items()]


@router.get("/{key}", response_model=dict)
async def get_group(session: SessionDep, _: Admin, key: str) -> dict[str, Any]:
    return await SettingsService(session).get_public(key)


@router.put("/{key}", response_model=dict)
async def save_group(session: SessionDep, actor: Admin, key: str, values: dict[str, Any] = Body(...)) -> dict[str, Any]:
    return await SettingsService(session).update(key, values, actor)


@router.post("/email/test", response_model=dict)
async def send_test_email(session: SessionDep, actor: Admin, to: Annotated[EmailStr, Body(embed=True)]) -> dict[str, Any]:
    """Send one message with the saved settings right now and report the SMTP server's answer."""
    settings: EmailSettings = await SettingsService(session).get_model("email")  # type: ignore[assignment]
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
