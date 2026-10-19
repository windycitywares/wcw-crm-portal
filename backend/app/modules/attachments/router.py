from urllib.parse import quote

from fastapi import APIRouter, Response, status

from app.modules.attachments.service import AttachmentService
from app.modules.users.deps import CurrentUser, SessionDep

from .schemas import AttachmentOut

router = APIRouter(tags=["attachments"])
BASE = "/entities/{entity_type}/{entity_id}"


def _disposition(filename: str) -> str:
    """`Content-Disposition` for a name a mail client wrote.

    Always `attachment` (never `inline`): what a stranger sent is handed over as a file, not rendered as
    a page of the CRM — and the API sets `X-Content-Type-Options: nosniff` on every response, so a
    browser can't decide a `.jpg` is really HTML. The ASCII name comes first, with the real one after it
    (RFC 5987) so an accented filename survives the trip.
    """
    ascii_name = "".join(c if c.isascii() and c not in '"\\' else "_" for c in filename) or "file"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


@router.get(BASE + "/attachments", response_model=list[AttachmentOut])
async def list_attachments(session: SessionDep, user: CurrentUser, entity_type: str,
                           entity_id: int) -> list[AttachmentOut]:
    """The files kept against a record, oldest first."""
    return await AttachmentService(session).list_for(user, entity_type, entity_id)


@router.get("/attachments/{attachment_id}")
async def download_attachment(session: SessionDep, user: CurrentUser, attachment_id: int) -> Response:
    row, data = await AttachmentService(session).download(user, attachment_id)
    # `clean_type` stored a plain `type/subtype`; hand it back exactly. Setting the header rather than
    # `media_type` stops Starlette appending a charset to `text/*`, so the client gets what was stored.
    return Response(data, headers={"Content-Type": row.content_type,
                                   "Content-Disposition": _disposition(row.filename)})


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(session: SessionDep, user: CurrentUser, attachment_id: int) -> None:
    await AttachmentService(session).delete(user, attachment_id)
