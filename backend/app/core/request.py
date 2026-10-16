"""Request helpers shared by routers."""

from fastapi import Request


def client_ip(request: Request) -> str:
    """The visitor's address. LiteSpeed puts the real client first in X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]
