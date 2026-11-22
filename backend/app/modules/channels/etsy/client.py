"""Talks to Etsy's Open API v3 (and nothing else). Plain HTTP in a worker thread, like the CRM sync; tests replace `_send`.

Only official API calls are made here: no page scraping or browser automation (Etsy forbids both).
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import oauth


class EtsyError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _send(req: urllib.request.Request) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - fixed https hosts
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EtsyError(f"Could not reach Etsy: {exc}") from exc


async def _call(req: urllib.request.Request) -> Any:
    status, body = await asyncio.to_thread(_send, req)
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        data = {}
    if status >= 400:
        detail = (data.get("error_description") or data.get("error") or "") if isinstance(data, dict) else ""
        raise EtsyError(f"Etsy answered {status}. {detail}".strip(), status)
    return data


async def exchange_code(*, client_id: str, redirect_uri: str, code: str, verifier: str) -> dict[str, Any]:
    form = urllib.parse.urlencode({
        "grant_type": "authorization_code", "client_id": client_id, "redirect_uri": redirect_uri,
        "code": code, "code_verifier": verifier,
    }).encode()
    req = urllib.request.Request(oauth.TOKEN_URL, data=form, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    return await _call(req)


async def refresh(*, client_id: str, refresh_token: str) -> dict[str, Any]:
    form = urllib.parse.urlencode({"grant_type": "refresh_token", "client_id": client_id, "refresh_token": refresh_token}).encode()
    req = urllib.request.Request(oauth.TOKEN_URL, data=form, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    return await _call(req)


async def get(path: str, *, api_key: str, access_token: str, params: dict[str, Any] | None = None) -> Any:
    url = oauth.API_BASE + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    req = urllib.request.Request(url, headers={"x-api-key": api_key, "Authorization": f"Bearer {access_token}"})
    return await _call(req)


def api_key(client_id: str, shared_secret: str | None) -> str:
    """Etsy wants `keystring:shared_secret` in x-api-key on every API call (the OAuth token calls take the keystring alone)."""
    if not shared_secret:
        raise EtsyError("The Etsy shared secret is not saved. Add it in Settings → Sales channels → Etsy.")
    return f"{client_id}:{shared_secret}"
