from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.permissions import Role
from app.modules.accounts.service import AccountService
from app.modules.audit.service import AuditService
from app.modules.channels.catalog import CHANNELS
from app.modules.channels.connection import EtsyConnectionService
from app.modules.channels.etsy import payments as etsy_payments
from app.modules.channels.etsy import status as etsy_status
from app.modules.channels.models import ChannelOrder, ChannelOrderEvent, ChannelOrderItem
from app.modules.channels.orders import OrderService
from app.modules.users.models import User

from .models import SupplierLogin

VIEWS = {"to_ship": ("new", "purchased"), "shipped": ("shipped", "delivered", "closed")}
SUPPLIER_EVENT_KINDS = ("created", "status", "tracking", "payment")  # never "costs" or team notes
SUPPLIER_TYPE = "supplier"


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def clean_channels(values: list[str]) -> list[str]:
    out = [v for v in dict.fromkeys((v or "").strip().lower() for v in values) if v]
    unknown = [v for v in out if v not in CHANNELS]
    if unknown:
        raise ValidationFailedError(f"Unknown sales channel: {', '.join(unknown)}")
    if not out:
        raise ValidationFailedError("Choose at least one sales channel the supplier may see")
    return out


class SupplierPortal:
    def __init__(self, session: AsyncSession, user: User):
        self.session = session
        self.user = user

    async def link(self) -> SupplierLogin | None:
        return await self.session.get(SupplierLogin, self.user.id)

    async def channels(self) -> list[str]:
        """Allowed for this supplier and connected right now."""
        link = await self.link()
        allowed = [c for c in (link.channels if link else []) if c in CHANNELS]
        return ["etsy"] if "etsy" in allowed and await EtsyConnectionService(self.session).connected() else []

    async def me(self) -> dict[str, Any]:
        link = await self.link()
        names = await AccountService(self.session).names([link.account_id]) if link else {}
        return {"account_id": link.account_id if link else None,
                "supplier_name": names.get(link.account_id) if link else None,
                "channels": await self.channels(), "names": {c.key: c.label for c in CHANNELS.values()}}

    async def _guard(self, channel: str) -> int:
        link = await self.link()
        if self.user.role != Role.SUPPLIER.value or link is None:
            raise PermissionDeniedError("This login isn't linked to a supplier yet. Ask the business owner.")
        if channel not in await self.channels():
            raise PermissionDeniedError("You don't have access to this shop")
        return link.account_id

    async def orders(self, view: str, q: str | None, page: int, page_size: int) -> dict[str, Any]:
        account = await self._guard("etsy")
        mine = [ChannelOrder.channel == "etsy", ChannelOrder.supplier_account_id == account]
        cond = list(mine)
        if view in VIEWS:
            cond.append(ChannelOrder.status.in_(VIEWS[view]))
        if q:
            term = q.strip().lstrip("#")
            like = _like(term.lower())
            parts = [func.lower(func.coalesce(ChannelOrder.buyer_name, "")).like(like, escape="\\"),
                     func.lower(func.coalesce(ChannelOrder.supplier_order_number, "")).like(like, escape="\\"),
                     exists().where(ChannelOrderItem.order_id == ChannelOrder.id,
                                    func.lower(ChannelOrderItem.title).like(like, escape="\\"))]
            if term.isdigit():
                parts.append(ChannelOrder.external_id == int(term))
            cond.append(or_(*parts))
        total = (await self.session.execute(select(func.count()).select_from(ChannelOrder).where(*cond))).scalar_one()
        order_by = ((ChannelOrder.ship_by.asc().nulls_last(), ChannelOrder.ordered_at) if view == "to_ship"
                    else (ChannelOrder.ordered_at.desc(),))
        rows = (await self.session.execute(select(ChannelOrder).where(*cond).order_by(*order_by, ChannelOrder.id)
                                           .limit(page_size).offset((page - 1) * page_size))).scalars().all()
        orders = OrderService(self.session)
        items = await orders._items([r.id for r in rows])
        images = await orders._images([i for its in items.values() for i in its])
        counts = dict((await self.session.execute(select(ChannelOrder.status, func.count()).where(*mine)
                                                  .group_by(ChannelOrder.status))).all())
        now = datetime.now(timezone.utc)
        return {
            "items": [self._row(o, items.get(o.id, []), images, now) for o in rows], "total": total, "page": page,
            "page_size": page_size,
            "counts": {"to_ship": sum(counts.get(s, 0) for s in VIEWS["to_ship"]),
                       "shipped": sum(counts.get(s, 0) for s in VIEWS["shipped"]), "all": sum(counts.values())},
        }

    @staticmethod
    def _row(o: ChannelOrder, items: list[ChannelOrderItem], images: dict[int, str], now: datetime) -> dict[str, Any]:
        waiting = o.status in VIEWS["to_ship"]
        return {
            "id": o.id, "external_id": o.external_id, "ordered_at": o.ordered_at, "ship_by": o.ship_by,
            "late": bool(waiting and o.ship_by and now > o.ship_by), "status": o.status,
            "status_label": etsy_status.LABELS.get(o.status, o.status), "buyer_name": o.buyer_name,
            "supplier_order_number": o.supplier_order_number, "carrier": o.carrier, "tracking_number": o.tracking_number,
            "items": [{"title": i.title, "quantity": i.quantity, "sku": i.sku, "variations": i.variations,
                       "image": images.get(i.listing_external_id or 0)} for i in items],
            "owed": etsy_payments.owed(o.purchase_cost, o.shipping_cost),
            "payment": etsy_payments.status(order_status=o.status, purchase_cost=o.purchase_cost,
                                            paid=o.supplier_paid_at is not None),
            "paid_at": o.supplier_paid_at, "paid_amount": o.supplier_paid_amount,
        }

    async def _own(self, order_id: int) -> ChannelOrder:
        account = await self._guard("etsy")
        o = await self.session.get(ChannelOrder, order_id)
        if o is None or o.supplier_account_id != account:
            raise NotFoundError("Order not found")  # someone else's order looks the same as a missing one
        return o

    async def detail(self, order_id: int) -> dict[str, Any]:
        o = await self._own(order_id)
        orders = OrderService(self.session)
        items = (await orders._items([o.id])).get(o.id, [])
        events = (await self.session.execute(select(ChannelOrderEvent).where(
            ChannelOrderEvent.order_id == o.id, ChannelOrderEvent.kind.in_(SUPPLIER_EVENT_KINDS))
            .order_by(ChannelOrderEvent.id.desc()))).scalars().all()
        return {
            **self._row(o, items, await orders._images(items), datetime.now(timezone.utc)),
            "ship_address": o.ship_address, "gift_message": o.gift_message, "buyer_note": o.buyer_note,
            "shipped_at": o.shipped_at, "payment_ref": o.supplier_payment_ref,
            "history": [{"id": e.id, "message": e.message, "source": e.source, "actor_name": e.actor_name,
                         "created_at": e.created_at} for e in events],
        }

    async def update(self, order_id: int, patch: dict[str, Any]) -> dict[str, Any]:
        o = await self._own(order_id)
        allowed = {k: v for k, v in patch.items() if k in ("supplier_order_number", "carrier", "tracking_number")}
        await OrderService(self.session).update(o.id, self.user, allowed, source="supplier")
        return await self.detail(o.id)

    async def mark_shipped(self, order_id: int, carrier: str | None, tracking_number: str) -> dict[str, Any]:
        o = await self._own(order_id)
        if o.status not in VIEWS["to_ship"]:
            raise ValidationFailedError("Only an order that is still to ship can be marked shipped")
        if not tracking_number.strip():
            raise ValidationFailedError("Enter the tracking number")
        orders = OrderService(self.session)
        await orders.update(o.id, self.user, {"tracking_number": tracking_number, **({"carrier": carrier} if carrier else {})},
                            source="supplier")
        await orders.set_status(o.id, self.user, etsy_status.SHIPPED, "Marked shipped by the supplier", source="supplier")
        return await self.detail(o.id)

    async def payments_filter(self) -> str:
        return str(await self._guard("etsy"))


class SupplierLogins:
    """Admins give a supplier a login: a user with role "supplier", linked to a Supplier account and the channels it
    may see. The person is also a contact at that account, so the supplier's people stay in one place."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def _out(self, rows: list[tuple[User, SupplierLogin | None]]) -> list[dict[str, Any]]:
        names = await AccountService(self.session).names([l.account_id for _, l in rows if l])
        return [{"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active,
                 "last_login_at": u.last_login_at, "account_id": l.account_id if l else None,
                 "supplier_name": names.get(l.account_id) if l else None, "channels": l.channels if l else []}
                for u, l in rows]

    async def list(self) -> list[dict[str, Any]]:
        rows = (await self.session.execute(
            select(User, SupplierLogin).outerjoin(SupplierLogin, SupplierLogin.user_id == User.id)
            .where(User.role == Role.SUPPLIER.value).order_by(User.email))).all()
        return await self._out([(u, l) for u, l in rows])

    async def _supplier_account(self, account_id: int) -> int:
        account = await AccountService(self.session).model(account_id)
        if account is None or account.account_type != SUPPLIER_TYPE:
            raise ValidationFailedError("Choose a supplier account")
        return account.id

    async def create(self, actor, *, email: str, password: str, full_name: str, account_id: int,
                     channels: list[str]) -> dict[str, Any]:
        from app.modules.contacts.service import ContactService
        from app.modules.users.schemas import UserCreate
        from app.modules.users.service import UserService

        account_id, shops = await self._supplier_account(account_id), clean_channels(channels)
        created = await UserService(self.session).create(
            UserCreate(email=email, full_name=full_name, role=Role.SUPPLIER, password=password), actor)
        user = await self.session.get(User, created.id)
        self.session.add(SupplierLogin(user_id=user.id, account_id=account_id, channels=shops))
        contact = await ContactService(self.session).sync_user(user, actor=actor)
        if contact is not None and contact.account_id is None:
            contact.account_id = account_id
            contact.types = sorted({*(contact.types or []), "vendor"})
        await self.audit.record("supplier_login.create", actor=actor, entity_type="user", entity_id=user.id,
                                changes={"account_id": account_id, "channels": shops})
        await self.session.commit()
        return (await self._out([(user, await self.session.get(SupplierLogin, user.id))]))[0]

    async def update(self, actor, user_id: int, *, account_id: int | None, channels: list[str] | None) -> dict[str, Any]:
        user = await self.session.get(User, user_id)
        if user is None or user.role != Role.SUPPLIER.value:
            raise NotFoundError("Supplier login not found")
        link = await self.session.get(SupplierLogin, user.id)
        if link is None:
            if account_id is None:
                raise ValidationFailedError("Choose a supplier account")
            link = SupplierLogin(user_id=user.id, account_id=await self._supplier_account(account_id),
                                 channels=clean_channels(channels or ["etsy"]))
            self.session.add(link)
        else:
            if account_id is not None:
                link.account_id = await self._supplier_account(account_id)
            if channels is not None:
                link.channels = clean_channels(channels)
        await self.audit.record("supplier_login.update", actor=actor, entity_type="user", entity_id=user.id,
                                changes={"account_id": link.account_id, "channels": link.channels})
        await self.session.commit()
        return (await self._out([(user, link)]))[0]
