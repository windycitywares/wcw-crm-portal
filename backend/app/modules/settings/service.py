"""Typed settings with encrypted secrets.

Other modules read a group with `await SettingsService(session).get_model("business_hours")`
(returns the pydantic model, secrets decrypted — server-side use only).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.security import SecretBox
from app.modules.audit.service import AuditService, diff

from app.integrations.email import SmtpConfig

from .groups import GROUPS, SECRET_FIELDS, EmailSettings
from .models import AppSetting

ENC_PREFIX = "enc:"


def _group(key: str) -> tuple[str, type[BaseModel]]:
    try:
        return GROUPS[key]
    except KeyError:
        raise NotFoundError(f"Unknown settings group: {key}") from None


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err.get("loc", ()) if p != "__root__")
    msg = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
    return f"{where.replace('_', ' ')}: {msg}" if where else msg


def smtp_config(s: EmailSettings) -> SmtpConfig:
    return SmtpConfig(host=s.smtp_host, port=s.smtp_port, security=s.smtp_security, user=s.smtp_user or None,
                      password=s.smtp_password or None, from_address=str(s.from_address), from_name=s.from_name)


T = TypeVar("T", bound=BaseModel)


class SettingsService:
    def __init__(self, session: AsyncSession, box: SecretBox | None = None):
        self.session = session
        self._box = box
        self.audit = AuditService(session)

    @property
    def box(self) -> SecretBox:
        if self._box is None:
            self._box = SecretBox()
        return self._box

    async def _row(self, key: str) -> AppSetting | None:
        return await self.session.get(AppSetting, key)

    async def get_model[T: BaseModel](self, key: str, *, factory: Callable[[], T] | None = None) -> T:
        """The group's values with secrets decrypted (server-side use only).

        Pass `factory=` for a typed call site (e.g. `get_model("email", factory=EmailSettings)`)
        so the return type is inferred without `# type: ignore`."""
        _, model = _group(key)
        row = await self._row(key)
        raw = dict(row.value) if row else {}
        for field in SECRET_FIELDS.get(key, ()):
            value = raw.get(field)
            if isinstance(value, str) and value.startswith(ENC_PREFIX):
                raw[field] = self.box.decrypt(value[len(ENC_PREFIX):])
        if factory is not None:
            return factory() if not raw else cast(T, model.model_validate(raw))
        return model.model_validate(raw) if raw else model()  # type: ignore[return-value]

    async def get_public(self, key: str) -> dict[str, Any]:
        """For the API: secrets replaced by `<field>_set: bool`."""
        label, _ = _group(key)
        data = (await self.get_model(key)).model_dump(mode="json")
        for field in SECRET_FIELDS.get(key, ()):
            data[f"{field}_set"] = bool(data.pop(field, ""))
        return {"key": key, "label": label, "values": data}

    async def update(self, key: str, incoming: dict[str, Any], actor) -> dict[str, Any]:
        _, model = _group(key)
        current = (await self.get_model(key)).model_dump()
        merged = {**current, **{k: v for k, v in incoming.items() if k in model.model_fields}}
        for field in SECRET_FIELDS.get(key, ()):
            if incoming.get(field) in (None, ""):  # empty = keep the stored secret
                merged[field] = current.get(field, "")
        try:
            validated = model.model_validate(merged)
        except ValidationError as exc:
            raise ValidationFailedError(_first_error(exc)) from None
        stored = validated.model_dump(mode="json")
        for field in SECRET_FIELDS.get(key, ()):
            if stored.get(field):
                stored[field] = ENC_PREFIX + self.box.encrypt(stored[field])
        row = await self._row(key)
        if row is None:
            self.session.add(AppSetting(key=key, value=stored, updated_by=actor.id))
        else:
            row.value, row.updated_by = stored, actor.id
        before = {k: v for k, v in current.items() if k not in SECRET_FIELDS.get(key, ())}
        after = {k: v for k, v in validated.model_dump(mode="json").items() if k not in SECRET_FIELDS.get(key, ())}
        changes = diff(before, after)
        for field in SECRET_FIELDS.get(key, ()):
            if incoming.get(field):
                changes[field] = ["••••", "••••"]
        await self.audit.record(f"settings.{key}", actor=actor, entity_type="settings", changes=changes)
        await self.session.commit()
        return await self.get_public(key)
