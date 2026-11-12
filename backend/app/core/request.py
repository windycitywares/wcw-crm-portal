"""Request helpers shared by routers."""

from fastapi import Request

from app.core.client_ip import real_client_ip


def client_ip(request: Request) -> str:
    """The address the rate limits count a request under. A caller can't choose it: `X-Forwarded-For` is only
    believed from this machine or a private network (see app/core/client_ip.py)."""
    return real_client_ip(request)
