"""Reads from the shop's read-only API (`/integrations/crm/*`, shop docs/CRM_SYNC.md). Behind a small interface
so tests and other sources can stand in for it."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

TIMEOUT = 20.0


class ShopApiError(Exception):
    pass


class ShopClient(Protocol):
    async def page(self, resource: str, after_id: int, limit: int = 200) -> dict[str, Any]: ...


class HttpShopClient:
    def __init__(self, base_url: str, token: str):
        self.base_url, self.token = base_url.rstrip("/"), token

    def _get(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json",
                                                   "User-Agent": "wcw-crm/shop-client"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as res:  # noqa: S310 - admin-configured URL
                return json.loads(res.read())
        except urllib.error.HTTPError as exc:
            hint = {401: "the shop refused the API token", 404: "the shop's read API is off (CRM_API_TOKEN not set there)"}
            raise ShopApiError(f"HTTP {exc.code}: {hint.get(exc.code, exc.reason)}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ShopApiError(f"{type(exc).__name__}: {exc}") from None

    async def page(self, resource: str, after_id: int, limit: int = 200) -> dict[str, Any]:
        query = urllib.parse.urlencode({"after_id": after_id, "limit": limit})
        return await asyncio.to_thread(self._get, f"{self.base_url}/integrations/crm/{resource}?{query}")


_factory = None


def set_shop_client_factory(factory) -> None:
    """Tests: replace the HTTP client (`factory(settings) -> ShopClient`)."""
    global _factory
    _factory = factory


def shop_client(settings) -> ShopClient:
    if _factory is not None:
        return _factory(settings)
    if not settings.shop_api_url or not settings.shop_api_token:
        raise ShopApiError("Save the shop API address and token first")
    return HttpShopClient(settings.shop_api_url, settings.shop_api_token)
