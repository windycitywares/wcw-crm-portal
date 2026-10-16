"""Shop → CRM events (SPEC §6): receive, store once, apply; the background job retries failures.

Event types (docs/SHOP_EVENTS.md):
- customer.upserted        a shop account was created or changed → find/create the customer, link the account
- order.updated            an order was placed or changed → customer, order copy, totals, timeline
- newsletter.subscribed    → marketing consent (creates the customer if needed)
- newsletter.unsubscribed  → consent withdrawn (only for customers we already have)
Anything else is stored and marked "ignored", so the shop can send new types before the CRM handles them.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.pagination import PageParams
from app.modules.activity.service import TimelineService
from app.modules.customers.service import CustomerService
from app.modules.settings.service import SettingsService

from . import signing
from .models import DONE, FAILED, IGNORED, PENDING, ShopEvent, ShopOrder
from .repository import ShopEventRepository, ShopOrderRepository
from .schemas import CustomerData, Envelope, NewsletterData, OrderData, ShopEventOut, ShopEventPage, ShopStatus
from .settings import ShopSettings

log = logging.getLogger("wcw.crm.shop")

MAX_BODY = 256 * 1024
MAX_ATTEMPTS = 5
KEEP_DAYS = 90
STATUS_WORDS = {"paid": "paid", "processing": "being prepared", "shipped": "shipped", "delivered": "delivered",
                "cancelled": "cancelled", "refunded": "refunded"}


class WebhookRejected(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _money(value: Any, currency: str) -> str:
    return f"${value:,.2f}" if currency == "USD" else f"{value:,.2f} {currency}"


class ShopEventService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.events = ShopEventRepository(session)
        self.orders = ShopOrderRepository(session)
        self.customers = CustomerService(session)
        self.timeline = TimelineService(session)
        self.quiet = False  # backfill: no timeline lines for history
        self.handlers: dict[str, Callable[[dict[str, Any]], Awaitable[int | None]]] = {
            "customer.upserted": self._customer,
            "order.updated": self._order,
            "newsletter.subscribed": self._subscribed,
            "newsletter.unsubscribed": self._unsubscribed,
        }

    async def settings(self) -> ShopSettings:
        return await SettingsService(self.session).get_model("shop")  # type: ignore[return-value]

    # ---- webhook ---------------------------------------------------------
    async def receive(self, body: bytes, timestamp: str | None, signature: str | None) -> str:
        """Verify, store and apply one webhook. Returns "accepted" or "duplicate"; raises WebhookRejected."""
        if len(body) > MAX_BODY:
            raise WebhookRejected(413, "Event too large")
        cfg = await self.settings()
        if not cfg.enabled or not cfg.webhook_secret:
            raise WebhookRejected(503, "The shop connection is switched off in the CRM")
        problem = signing.verify(cfg.webhook_secret, timestamp, signature, body)
        if problem:
            log.warning("shop webhook refused: %s", problem)
            raise WebhookRejected(401, "Invalid signature")
        try:
            envelope = Envelope.model_validate(json.loads(body))
        except (ValueError, ValidationError):
            raise WebhookRejected(400, "Not a valid event") from None

        if await self.events.by_event_id(envelope.id):
            return "duplicate"
        event = ShopEvent(event_id=envelope.id, event_type=envelope.type, occurred_at=envelope.occurred_at,
                          payload=envelope.data)
        await self.events.add(event)
        await self.session.commit()  # stored first: if applying fails, the job tries again
        await self.apply(event)
        return "accepted"

    # ---- applying ----------------------------------------------------------
    async def apply(self, event: ShopEvent) -> None:
        handler = self.handlers.get(event.event_type)
        event.attempts += 1
        if handler is None:
            event.status, event.processed_at = IGNORED, _now()
            await self.session.commit()
            return
        try:
            async with self.session.begin_nested():
                event.customer_id = await handler(event.payload)
        except (ValidationError, ValidationFailedError, NotFoundError) as exc:
            event.status, event.error = FAILED, str(exc)[:2000]
            event.attempts = MAX_ATTEMPTS  # bad data won't get better by retrying
        except Exception as exc:  # noqa: BLE001 - keep the event, retry later
            log.exception("shop event %s failed", event.event_id)
            event.status, event.error = FAILED, f"{type(exc).__name__}: {exc}"[:2000]
        else:
            event.status, event.error, event.processed_at = DONE, None, _now()
        await self.session.commit()

    async def _customer(self, payload: dict[str, Any]) -> int:
        data = CustomerData.model_validate(payload)
        return await self.customers.sync_from_shop(email=data.email, shop_user_id=data.id, full_name=data.full_name,
                                                   phone=data.phone)

    async def _order(self, payload: dict[str, Any]) -> int:
        data = OrderData.model_validate(payload)
        address = data.billing_address or data.shipping_address
        customer_id = await self.customers.sync_from_shop(
            email=data.email, shop_user_id=data.user_id, full_name=data.customer_name, phone=data.phone,
            address=address.for_crm() if address else None)

        order = await self.orders.get_order(data.id)
        if order is not None and order.shop_updated_at and data.updated_at and data.updated_at < order.shop_updated_at:
            return customer_id  # an older copy of this order arrived late: nothing to change
        previous = order.status if order else None
        if order is None:
            order = ShopOrder(id=data.id)
            self.session.add(order)
        order.customer_id, order.number, order.email = customer_id, data.number, data.email.strip().lower()
        order.status, order.payment_status, order.currency = data.status, data.payment_status, data.currency
        order.grand_total, order.refunded_total = data.grand_total, data.refunded_total
        order.placed_at, order.shop_updated_at = data.placed_at, data.updated_at
        await self.session.flush()

        if data.marketing_opt_in:
            await self.customers.set_consent_from_shop(customer_id, True, "shop checkout")
        count, total, first, last = await self.orders.stats(customer_id)
        await self.customers.set_order_stats(customer_id, count=count, total=total, first=first, last=last)

        if data.status != previous and data.status in STATUS_WORDS and not self.quiet:
            title = f"Order {data.number} {STATUS_WORDS[data.status]}"
            if data.status == "paid" or (previous in (None, "pending") and data.status != "cancelled"):
                title += f" — {_money(data.grand_total, data.currency)}"
            await self.timeline.record("customer", customer_id, "shop.order", title,
                                       data={"order_id": data.id, "number": data.number, "status": data.status})
        return customer_id

    async def apply_data(self, event_type: str, data: dict[str, Any]) -> int | None:
        """Apply one item outside the webhook flow (the backfill). Raises on bad data."""
        handler = self.handlers.get(event_type)
        return await handler(data) if handler else None

    async def _subscribed(self, payload: dict[str, Any]) -> int:
        data = NewsletterData.model_validate(payload)
        customer_id = await self.customers.sync_from_shop(email=data.email)
        how = f"shop newsletter, {data.source}" if data.source else "shop newsletter"
        await self.customers.set_consent_from_shop(customer_id, True, how)
        return customer_id

    async def _unsubscribed(self, payload: dict[str, Any]) -> int | None:
        data = NewsletterData.model_validate(payload)
        customer_id = await self.customers.find_by_email(data.email)
        if customer_id is not None:
            await self.customers.set_consent_from_shop(customer_id, False, "shop newsletter")
        return customer_id

    # ---- job + admin ---------------------------------------------------------
    async def retry_due(self, limit: int = 50) -> str | None:
        due = await self.events.due(max_attempts=MAX_ATTEMPTS, older_than=_now() - timedelta(minutes=1), limit=limit)
        for event in due:
            await self.apply(event)
        purged = await self.events.purge(_now() - timedelta(days=KEEP_DAYS))
        await self.session.commit()
        parts = [f"{len(due)} retried"] if due else []
        if purged:
            parts.append(f"{purged} old purged")
        return f"shop events: {', '.join(parts)}" if parts else None

    async def retry(self, event_id: int) -> ShopEventOut:
        event = await self.events.get(event_id)
        if event is None:
            raise NotFoundError("Event not found")
        if event.status in (FAILED, PENDING):
            event.attempts = min(event.attempts, MAX_ATTEMPTS - 1)
            await self.apply(event)
        return ShopEventOut.model_validate(event)

    async def status(self, webhook_url: str) -> ShopStatus:
        cfg = await self.settings()
        return ShopStatus(enabled=cfg.enabled, secret_set=bool(cfg.webhook_secret), webhook_url=webhook_url,
                          last_event_at=await self.events.last_received(),
                          counts=await self.events.counts_since(_now() - timedelta(days=1)))

    async def list(self, params: PageParams, status: str | None = None) -> ShopEventPage:
        rows, total = await self.events.paginate(self.events.recent(status), params)
        return ShopEventPage(items=[ShopEventOut.model_validate(r) for r in rows], total=total,
                             page=params.page, page_size=params.page_size)
