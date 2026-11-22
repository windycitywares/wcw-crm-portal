"""Turn one Etsy listing (Open API v3 JSON) into the columns we keep. Pure: no database, no network."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

STATES = ("active", "inactive", "sold_out", "draft", "expired")


def money(value: Any) -> Decimal | None:
    """Etsy sends money as {"amount": 1999, "divisor": 100, "currency_code": "USD"}."""
    if not isinstance(value, dict) or value.get("amount") is None:
        return None
    divisor = int(value.get("divisor") or 100)
    return (Decimal(int(value["amount"])) / Decimal(divisor)).quantize(Decimal("0.01"))


def when(epoch: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _variations(inventory: Any) -> list[dict[str, Any]]:
    """[{"sku", "options": {"Size": "M"}, "price", "quantity"}] for each purchasable combination."""
    out: list[dict[str, Any]] = []
    products = inventory.get("products") if isinstance(inventory, dict) else None
    for p in products or []:
        if p.get("is_deleted"):
            continue
        options = {pv.get("property_name"): ", ".join(pv.get("values") or []) for pv in p.get("property_values") or [] if pv.get("property_name")}
        offering = next((o for o in p.get("offerings") or [] if o.get("is_enabled", True) and not o.get("is_deleted")), None)
        out.append({
            "sku": p.get("sku") or None, "options": options,
            "price": str(money(offering.get("price"))) if offering and money(offering.get("price")) is not None else None,
            "quantity": offering.get("quantity") if offering else None,
        })
    return out


def parse(payload: dict[str, Any]) -> dict[str, Any]:
    state = payload.get("state") or "active"
    variations = _variations(payload.get("inventory"))
    skus = [s for s in (payload.get("skus") or []) if s] or [v["sku"] for v in variations if v["sku"]]
    return {
        "etsy_listing_id": int(payload["listing_id"]),
        "title": (payload.get("title") or "").strip()[:300] or f"Listing {payload['listing_id']}",
        "description": payload.get("description"),
        "state": state if state in STATES else "inactive",
        "price": money(payload.get("price")),
        "currency": ((payload.get("price") or {}).get("currency_code") or "USD")[:3],
        "quantity": payload.get("quantity"),
        "skus": list(dict.fromkeys(skus)),
        "url": (payload.get("url") or None),
        "images": [im["url_fullxfull"] for im in payload.get("images") or [] if im.get("url_fullxfull")][:10],
        "variations": variations,
        "tags": list(payload.get("tags") or []),
        "etsy_updated_at": when(payload.get("last_modified_timestamp") or payload.get("updated_timestamp")),
    }
