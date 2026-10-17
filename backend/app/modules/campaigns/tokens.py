"""Signed links for campaign email (SPEC §3.6).

A link in an email has to work without a login, from a stranger's mail client, so it carries a token instead
of a session: the row it is about and an expiry, signed with the app's own secret (HMAC-SHA256). A token can
only act on the row it was minted for, and it stops working once it expires.

    url = unsubscribe_url(customer_id, base_url=get_settings().site_url)
    customer_id = read_unsubscribe_token(token)  # None when forged, malformed or expired

    img = open_url(recipient_id, base_url=get_settings().api_url)
    link = click_url(recipient_id, "https://shop.example.com/sale", base_url=get_settings().api_url)

The unsubscribe link points at the web app (it is a page a customer reads). The two **tracking** links point
at the API, because a mail client fetches them directly: one is the pixel that says a message was opened, the
other is a redirect that says a link was followed and then sends the customer on their way.

A click's destination travels **inside** the signed payload, so a click token can only ever redirect where
that email pointed — nobody can take a link out of somebody's inbox and turn it into a redirect to their own
site (which a token that merely named a target would allow).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time

from app.core.config import get_settings

UNSUBSCRIBE = "unsubscribe"
OPEN = "open"
CLICK = "click"
TTL_DAYS = 400  # a year and a bit: a link in an old email still works


def _sign(payload: str) -> str:
    key = get_settings().jwt_secret.encode()
    digest = hmac.new(key, payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _expires(ttl_days: int, now: float | None) -> int:
    return int((now if now is not None else time.time()) + ttl_days * 86_400)


def _pack(value: str) -> str:
    """A URL as one query-safe word: base64 with the padding left off, so it holds no `&`, `?` or `#`."""
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _unpack(body: str) -> str:
    return base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()


def sign(subject_id: int, purpose: str = UNSUBSCRIBE, *, ttl_days: int = TTL_DAYS,
         now: float | None = None) -> str:
    """A token for one customer (or campaign) and purpose, valid for `ttl_days`."""
    expires = _expires(ttl_days, now)
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


def open_url(recipient_id: int, *, base_url: str, ttl_days: int = TTL_DAYS,
             now: float | None = None) -> str:
    """The one-pixel image address for one recipient: the open is recorded by the message asking for it."""
    return f"{base_url.rstrip('/')}/campaigns/open?token={sign(recipient_id, OPEN, ttl_days=ttl_days, now=now)}"


def read_open_token(token: str, *, now: float | None = None) -> int | None:
    """The recipient an open pixel is for."""
    return read(token, OPEN, now=now)


def click_url(recipient_id: int, destination: str, *, base_url: str, ttl_days: int = TTL_DAYS,
              now: float | None = None) -> str:
    """One link in one recipient's message, wrapped so following it tells us so and then sends them on.

    The token reads `click:<recipient>:<expiry>:<destination>:<signature>`; the destination is base64 so it
    cannot break the token's shape, and it is part of what is signed, so it cannot be swapped either.
    """
    payload = f"{CLICK}:{recipient_id}:{_expires(ttl_days, now)}:{_pack(destination)}"
    return f"{base_url.rstrip('/')}/campaigns/click?token={payload}:{_sign(payload)}"


def read_click_token(token: str, *, now: float | None = None) -> tuple[int, str] | None:
    """The recipient and the destination a click link carries — None when it is forged, malformed or expired."""
    try:
        purpose, recipient_id, expires, body, signature = (token or "").split(":")
        if purpose != CLICK:
            return None
        payload = f"{purpose}:{recipient_id}:{expires}:{body}"
        if not hmac.compare_digest(signature, _sign(payload)):
            return None
        if int(expires) < (now if now is not None else time.time()):
            return None
        return int(recipient_id), _unpack(body)
    except (AttributeError, TypeError, ValueError, UnicodeDecodeError, binascii.Error):
        return None
