"""Sales channels (External shops): which marketplaces exist and are connected, and the Etsy connection."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.core.permissions import Permission
from app.modules.users.deps import SessionDep, require
from app.modules.users.models import User

from .catalog import CHANNELS
from .connection import EtsyConnectionService

router = APIRouter(prefix="/channels", tags=["channels"], dependencies=[Depends(require(Permission.CHANNELS_VIEW))])
Manager = Annotated[User, Depends(require(Permission.CHANNELS_MANAGE))]


class CredentialsIn(BaseModel):
    client_id: str | None = Field(default=None, max_length=100)
    client_secret: str | None = Field(default=None, max_length=200)


@router.get("")
async def channels(response: Response, session: SessionDep) -> dict[str, Any]:
    """Every marketplace, whether it can be connected yet and whether it is: the sidebar's External shops group
    shows one entry per connected channel."""
    response.headers["Cache-Control"] = "no-store"
    etsy = await EtsyConnectionService(session).connected()
    return {"items": [{"key": c.key, "label": c.label, "available": c.available,
                       "connected": etsy if c.key == "etsy" else False} for c in CHANNELS.values()]}


@router.get("/etsy/connection")
async def etsy_connection(response: Response, session: SessionDep) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await EtsyConnectionService(session).status()


@router.put("/etsy/credentials")
async def save_credentials(body: CredentialsIn, session: SessionDep, actor: Manager) -> dict[str, Any]:
    service = EtsyConnectionService(session)
    await service.save_credentials(actor, body.client_id, body.client_secret)
    return await service.status()


@router.post("/etsy/connect")
async def connect(session: SessionDep, actor: Manager) -> dict[str, str]:
    """The address of Etsy's "Allow access" screen; the browser goes there and Etsy sends it back to the callback."""
    return {"url": await EtsyConnectionService(session).start(actor)}


@router.post("/etsy/disconnect")
async def disconnect(session: SessionDep, actor: Manager) -> dict[str, Any]:
    service = EtsyConnectionService(session)
    await service.disconnect(actor)
    return await service.status()
