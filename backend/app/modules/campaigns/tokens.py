"""Signed links for campaign email (SPEC §3.6).

An unsubscribe link has to work without a login, from a stranger's mail client, so it carries a token
instead of a session: the customer id and an expiry, signed with the app's own secret (HMAC-SHA256). A
token can only act on the customer it was minted for, and it stops working once it expires.

    url = unsubscribe_url(customer_id, base_url=get_settings().site_url)
    customer_id = read_unsubscribe_token(token)  # None when forged, malformed or expired
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from app.core.config import get_settings

UNSUBSCRIBE = "unsubscribe"
TTL_DAYS = 400  # a year and a bit: a link in an old email still works


def _sign(payload: str) -> str:
    key = get_settings().jwt_secret.encode()
    digest = hmac.new(key, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def sign(subject_id: int, purpose: str = UNSUBSCRIBE, *, ttl_days: int = TTL_DAYS,
         now: float | None = None) -> str:
    """A token for one customer (or campaign) and purpose, valid for `ttl_days`."""
    expires = int((now if now is not None else time.time()) + ttl_days * 86_400)
    payload = f"{purpose}:{subject_id}:{expires}"
    return f"{payload}:{_sign(payload)}"


def read(token: str, purpose: str = UNSUBSCRIBE, *, now: float | None = None) -> int | None:
    """The id a token was minted for, or None when it is forged, malformed, expired or for another purpose."""
    try:
        want_purpose, subject_id, expires, signature = (token or "").split(":")
        if want_purpose != purpose:
            return None
        if not hmac.compare_digest(signature, _sign(f"{want_purpose}:{subject_id}:{expires}")):
            return None
        if int(expires) < (now if now is not None else time.time()):
            return None
        return int(subject_id)
    except (AttributeError, TypeError, ValueError):
        return None


def read_unsubscribe_token(token: str, *, now: float | None = None) -> int | None:
    """The customer an unsubscribe link is for."""
    return read(token, UNSUBSCRIBE, now=now)


def unsubscribe_url(customer_id: int, *, base_url: str, campaign_id: int | None = None) -> str:
    """The public page a customer lands on — the web app, not the API, so it works without a login.

    `campaign_id` is added for the record only ("they left from the Spring sale"): it is not signed, because
    the token is what grants the action and a wrong campaign id could never widen it.
    """
    url = f"{base_url.rstrip('/')}/unsubscribe?token={sign(customer_id)}"
    return f"{url}&c={campaign_id}" if campaign_id else url
