from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.config import get_settings
from app.core.permissions import Permission
from app.modules.users.deps import SessionDep, require
from app.modules.users.models import User
from app.modules.users.service import UserService

from .schemas import DeployConfig, DeployStatus
from .service import DeployService, log_tail

router = APIRouter(prefix="/deploy", tags=["deploy"])
Admin = Annotated[User, Depends(require(Permission.SETTINGS_MANAGE))]


async def _status(session) -> DeployStatus:
    names = {e.id: e.full_name for e in await UserService(session).directory()}
    return await DeployService(session).status(names)


@router.get("", response_model=DeployStatus)
async def deploy_status(session: SessionDep, _: Admin) -> DeployStatus:
    return await _status(session)


@router.put("/config", response_model=DeployStatus)
async def deploy_configure(session: SessionDep, actor: Admin, data: DeployConfig) -> DeployStatus:
    await DeployService(session).configure(data, actor)
    return await _status(session)


@router.post("/now", response_model=DeployStatus, status_code=status.HTTP_202_ACCEPTED)
async def deploy_now(session: SessionDep, actor: Admin) -> DeployStatus:
    await DeployService(session).request_now(actor)
    return await _status(session)


@router.delete("/now", response_model=DeployStatus)
async def cancel_deploy_now(session: SessionDep, actor: Admin) -> DeployStatus:
    await DeployService(session).cancel_request(actor)
    return await _status(session)


@router.get("/log", response_model=dict)
async def deploy_log(_: Admin, lines: Annotated[int, Query(ge=10, le=400)] = 200) -> dict:
    return {"log": log_tail(get_settings().deploy_log, lines)}
