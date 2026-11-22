"""The connection to the Etsy shop: credentials, "Allow access", token refresh, disconnect.

Only Etsy's official Open API v3 is used (OAuth 2.0 + PKCE); nothing is scraped or automated. Secrets are sealed
with DATA_ENCRYPTION_KEY and never leave the server.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.core.security import SecretBox
from app.modules.audit.service import AuditService

from .etsy import client as etsy_client
from .etsy import oauth
from .etsy.client import EtsyError
from .models import ChannelConnection

OAUTH_VALID_FOR = timedelta(minutes=15)
CHANNEL = "etsy"


def redirect_uri() -> str:
    """Where Etsy sends the browser back: must be listed exactly like this in the Etsy app's callback URLs."""
    return get_settings().api_url.rstrip("/") + "/channels/etsy/callback"


def _seal(plain: str) -> str:
    return SecretBox().encrypt(plain)


def _unseal(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return SecretBox().decrypt(token)
    except (ValueError, RuntimeError):
        return None


class EtsyConnectionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def row(self) -> ChannelConnection:
        row = await self.session.get(ChannelConnection, CHANNEL)
        if row is None:
            row = ChannelConnection(channel=CHANNEL)
            self.session.add(row)
            await self.session.flush()
        return row

    async def connected(self) -> bool:
        row = await self.session.get(ChannelConnection, CHANNEL)
        return bool(row and row.access_token_enc and row.refresh_token_enc)

    async def status(self) -> dict[str, Any]:
        row = await self.row()
        return {
            "client_id": row.client_id,
            "secret_set": bool(_unseal(row.client_secret_enc)),
            "connected": bool(row.access_token_enc and row.refresh_token_enc),
            "shop_name": row.shop_name, "external_shop_id": row.external_shop_id, "connected_at": row.connected_at,
            "listings_synced_at": row.listings_synced_at, "orders_synced_at": row.orders_synced_at,
            "last_error": row.last_error, "last_error_at": row.last_error_at,
            "redirect_uri": redirect_uri(), "scopes": row.scopes,
        }

    async def save_credentials(self, actor, client_id: str | None, client_secret: str | None) -> None:
        row = await self.row()
        if client_id is not None:
            client_id = client_id.strip()
            if not client_id or len(client_id) > 100 or " " in client_id:
                raise ValidationFailedError("That doesn't look like an Etsy keystring")
            row.client_id = client_id
        if client_secret:
            if len(client_secret.strip()) > 200:
                raise ValidationFailedError("The shared secret is too long")
            row.client_secret_enc = _seal(client_secret.strip())
        await self.audit.record("channel.credentials", actor=actor, entity_type="channel",
                                changes={"channel": CHANNEL, "client_id": row.client_id,
                                         "secret_changed": bool(client_secret)})
        await self.session.commit()

    async def start(self, actor) -> str:
        row = await self.row()
        if not row.client_id:
            raise ValidationFailedError("Save the Etsy keystring first")
        verifier, state = oauth.new_verifier(), oauth.new_state()
        row.oauth_state = f"{state}|{datetime.now(timezone.utc).isoformat()}|{actor.id}"
        row.oauth_verifier_enc = _seal(verifier)
        await self.session.commit()
        return oauth.authorize_url(client_id=row.client_id, redirect_uri=redirect_uri(), state=state, verifier=verifier)

    async def finish(self, state: str, code: str) -> str:
        """The browser came back from Etsy. Returns the connected shop's name; raises EtsyError / ValidationFailedError."""
        row = await self.row()
        stored = (row.oauth_state or "").split("|")
        if len(stored) != 3 or stored[0] != state:
            raise ValidationFailedError("This connection attempt is not recognised. Start again from Settings → Sales channels.")
        if datetime.now(timezone.utc) - datetime.fromisoformat(stored[1]) > OAUTH_VALID_FOR:
            raise ValidationFailedError("This connection attempt expired. Start again from Settings → Sales channels.")
        verifier = _unseal(row.oauth_verifier_enc)
        if not row.client_id or not verifier:
            raise ValidationFailedError("The connection attempt could not be completed. Start again.")
        row.oauth_state = row.oauth_verifier_enc = None  # one use
        await self.session.commit()
        tokens = await etsy_client.exchange_code(client_id=row.client_id, redirect_uri=redirect_uri(), code=code,
                                                 verifier=verifier)
        access = tokens["access_token"]
        user_id = oauth.user_id_from_token(access)
        if user_id is None:
            raise EtsyError("Etsy's answer did not identify the account")
        key = etsy_client.api_key(row.client_id, _unseal(row.client_secret_enc))
        shops = await etsy_client.get(f"/users/{user_id}/shops", api_key=key, access_token=access)
        shop = shops if "shop_id" in shops else (shops.get("results") or [None])[0]
        if not shop:
            raise EtsyError("That Etsy account has no shop")
        self._store_tokens(row, tokens)
        row.external_shop_id, row.shop_name = shop["shop_id"], shop.get("shop_name")
        row.scopes = tokens.get("scope") or " ".join(oauth.SCOPES)
        row.connected_at, row.connected_by = datetime.now(timezone.utc), int(stored[2])
        row.last_error = row.last_error_at = None
        await self.audit.record("channel.connect", entity_type="channel",
                                changes={"channel": CHANNEL, "shop": row.shop_name})
        await self.session.commit()
        return row.shop_name or "your shop"

    @staticmethod
    def _store_tokens(row: ChannelConnection, tokens: dict[str, Any]) -> None:
        row.access_token_enc = _seal(tokens["access_token"])
        row.refresh_token_enc = _seal(tokens["refresh_token"])
        row.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600)))

    async def access_token(self) -> tuple[str, str]:
        """(the x-api-key value, a valid access token), refreshed when about to expire. Records a failure."""
        row = await self.row()
        if not (row.client_id and row.access_token_enc and row.refresh_token_enc):
            raise EtsyError("Etsy is not connected")
        if row.token_expires_at and row.token_expires_at - datetime.now(timezone.utc) < timedelta(minutes=5):
            try:
                tokens = await etsy_client.refresh(client_id=row.client_id,
                                                   refresh_token=_unseal(row.refresh_token_enc) or "")
            except EtsyError as exc:
                await self.fail(str(exc))
                raise
            self._store_tokens(row, tokens)
            await self.session.commit()
        token = _unseal(row.access_token_enc)
        if not token:
            raise EtsyError("The stored Etsy access can't be read. Reconnect Etsy in Settings → Sales channels.")
        return etsy_client.api_key(row.client_id, _unseal(row.client_secret_enc)), token

    async def fail(self, message: str) -> None:
        row = await self.row()
        row.last_error, row.last_error_at = message[:500], datetime.now(timezone.utc)
        await self.session.commit()

    async def disconnect(self, actor) -> None:
        row = await self.row()
        row.access_token_enc = row.refresh_token_enc = None
        row.token_expires_at = None
        row.scopes = row.oauth_state = row.oauth_verifier_enc = None
        await self.audit.record("channel.disconnect", actor=actor, entity_type="channel", changes={"channel": CHANNEL})
        await self.session.commit()
