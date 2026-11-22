"""Turn one Etsy receipt (an Etsy order, Open API v3) into our columns. Pure: no database, no network."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from . import status as etsy_status
from .listing import money, when


def _m(value: Any) -> Decimal:
    return money(value) or Decimal("0.00")


def _address(r: dict[str, Any]) -> dict[str, str]:
    keys = ("name", "first_line", "second_line", "city", "state", "zip", "country_iso")
    out = {k: str(r[k]) for k in keys if r.get(k)}
    return out


def _items(r: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for t in r.get("transactions") or []:
        variations = [{"name": v.get("formatted_name"), "value": v.get("formatted_value")} for v in t.get("variations") or []]
        out.append({
            "etsy_transaction_id": int(t["transaction_id"]),
            "etsy_listing_id": int(t["listing_id"]) if t.get("listing_id") else None,
            "title": (t.get("title") or "Item").strip()[:300],
            "sku": (t.get("sku") or None),
            "variations": variations,
            "quantity": int(t.get("quantity") or 1),
            "unit_price": _m(t.get("price")),
        })
    return out


def ship_by(r: dict[str, Any]) -> datetime | None:
    dates = [when(t.get("expected_ship_date")) for t in r.get("transactions") or []]
    dates = [d for d in dates if d]
    return min(dates) if dates else None


def _shipment_time(r: dict[str, Any]) -> datetime | None:
    found = [when(s.get("shipment_notification_timestamp")) for s in r.get("shipments") or []]
    found = [d for d in found if d]
    return min(found) if found else None


def tracking(r: dict[str, Any]) -> tuple[str | None, str | None]:
    """(tracking number, carrier) from the newest shipment Etsy knows about."""
    for s in reversed(r.get("shipments") or []):
        if s.get("tracking_code"):
            return str(s["tracking_code"])[:100], (s.get("carrier_name") or None)
    return None, None


def _first(r: dict[str, Any], key: str) -> datetime | None:
    found = [when(t.get(key)) for t in r.get("transactions") or [] if t.get(key)]
    found = [d for d in found if d]
    return min(found) if found else None


def is_paid(r: dict[str, Any]) -> bool:
    return bool(r.get("is_paid")) or (r.get("status") or "").lower() in ("paid", "completed")


def parse(r: dict[str, Any]) -> dict[str, Any]:
    # Only cancelled / shipped / delivered move an order on their own (the brief). A refund on Etsy is recorded by the
    # team (phase 3), so "Fully refunded" does not cancel anything here.
    state = (r.get("status") or "").lower()
    canceled = state in ("canceled", "cancelled")
    delivered = state == "delivered" or any(s.get("is_delivered") for s in r.get("shipments") or [])
    items = _items(r)
    items_total = sum((i["unit_price"] * i["quantity"] for i in items), Decimal("0.00"))
    track, carrier = tracking(r)
    order = {
        "etsy_receipt_id": int(r["receipt_id"]),
        "etsy_state": r.get("status"),
        "ordered_at": when(r.get("created_timestamp") or r.get("create_timestamp")),
        "paid_at": (_first(r, "paid_timestamp") or when(r.get("created_timestamp") or r.get("create_timestamp"))) if is_paid(r) else None,
        "etsy_shipped_at": _first(r, "shipped_timestamp") or _shipment_time(r),
        "ship_by": ship_by(r),
        "buyer_name": (r.get("name") or None),
        "etsy_buyer_id": r.get("buyer_user_id"),
        "buyer_email": (r.get("buyer_email") or None),
        "ship_address": _address(r),
        "gift_message": (r.get("gift_message") or None) if r.get("is_gift") or r.get("gift_message") else None,
        "buyer_note": (r.get("message_from_buyer") or None),
        "currency": ((r.get("grandtotal") or {}).get("currency_code") or "USD")[:3],
        "items_total": items_total,
        "shipping_charged": _m(r.get("total_shipping_cost")),
        "discounts": _m(r.get("discount_amt")),
        "tax": _m(r.get("total_tax_cost")),
        "grand_total": _m(r.get("grandtotal")),
        "etsy_updated_at": when(r.get("updated_timestamp") or r.get("update_timestamp")),
        "implied_status": etsy_status.etsy_status(canceled=canceled, shipped=bool(r.get("is_shipped")), delivered=delivered),
        "etsy_tracking": track,
        "etsy_carrier": carrier,
    }
    return {"order": order, "items": items}
