"""The public side of the inbox (SPEC §3.9): a channel that isn't a mailbox handing the CRM a message.

    POST /inbox/messages   one signed message in from a chat, an Etsy poller, an SMS gateway, ...

No login, and nothing else belongs in this file: the HMAC signature is the authentication
(docs/INBOX_CHANNELS.md), and a connector has no session to give. What arrives is filed by `filing.py`,
the same rules a mailbox's mail goes through, so both kinds of message land in a ticket the same way.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.rate_limit import RateLimiter
from app.core.request import client_ip
from app.modules.users.deps import SessionDep

from .intake import IntakeRejected, InboxIntakeService

router = APIRouter(prefix="/inbox", tags=["inbox"])
bad_signatures = RateLimiter(max_hits=30, window_seconds=600)


@router.post("/messages", include_in_schema=False)
async def inbox_message(request: Request, session: SessionDep) -> JSONResponse:
    """One message from a channel: a chat, an Etsy message, an SMS. Signed, not signed in."""
    ip = client_ip(request)
    if bad_signatures.is_blocked(ip):
        return JSONResponse({"detail": "Too many invalid requests"}, status_code=429)
    body = await request.body()
    try:
        filed = await InboxIntakeService(session).accept(
            body, request.headers.get("x-wcw-timestamp"), request.headers.get("x-wcw-signature"))
    except IntakeRejected as exc:
        if exc.status_code == 401:
            bad_signatures.hit(ip)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    # 201 when the message opened or joined a ticket; 200 for one we have seen before, so a connector
    # that retries a message it already sent can read the answer as "yes, that one is in".
    return JSONResponse(filed.model_dump(mode="json"), status_code=201 if filed.status == "filed" else 200)
