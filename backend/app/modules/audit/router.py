from fastapi import APIRouter, Depends

from app.core.pagination import PageDep
from app.core.permissions import Permission
from app.modules.users.deps import SessionDep, require

from .schemas import AuditPage
from .service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditPage, dependencies=[Depends(require(Permission.AUDIT_VIEW))])
async def list_audit(
    session: SessionDep, page: PageDep, action: str | None = None, entity_type: str | None = None,
    entity_id: int | None = None, actor_id: int | None = None,
) -> AuditPage:
    return await AuditService(session).search(
        page, action=action, entity_type=entity_type, entity_id=entity_id, actor_id=actor_id
    )
