"""Webhook signatures (the same scheme on both sides — see docs/SHOP_EVENTS.md, docs/INBOX_CHANNELS.md).

    X-WCW-Timestamp: <unix seconds>
    X-WCW-Signature: sha256=<hex HMAC-SHA256(secret, f"{timestamp}." + raw body)>

Requests older or newer than TOLERANCE seconds are refused, so a captured request can't be replayed later.

Shared by everything that takes a signed call from outside the CRM: the shop's events and the inbox's
channels. Every signed caller signs the same way, and the signature is the only authentication, so this
is the one place the scheme lives.
"""

from __future__ import annotations

import hashlib
import hmac
import time

TOLERANCE = 300


def sign(secret: str, timestamp: int | str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify(secret: str, timestamp: str | None, signature: str | None, body: bytes, *, now: float | None = None) -> str | None:
    """None when valid, otherwise the reason it isn't."""
    if not secret:
        return "not configured"
    if not timestamp or not signature:
        return "missing signature headers"
    try:
        ts = int(timestamp)
    except ValueError:
        return "bad timestamp"
    if abs((now if now is not None else time.time()) - ts) > TOLERANCE:
        return "timestamp too old or in the future"
    if not hmac.compare_digest(sign(secret, ts, body), signature.strip()):
        return "signature mismatch"
    return None
