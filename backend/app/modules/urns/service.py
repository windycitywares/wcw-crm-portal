"""Urns: setting them up from Etsy listings, their sizes and SKU format, supplier prices, extras and variations.

Nothing here writes to Etsy. The SKU each variation should carry is worked out and shown next to what Etsy has;
sending it is a separate, switched-off step (see `EtsySkuPush`).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.modules.audit.service import AuditService
from app.modules.channels.models import ChannelListing
from app.modules.suppliers.models import Supplier

from . import reading, skus
from .models import CostExtra, ProductType, Urn, UrnPrice, UrnSize, UrnVariation

ENTITY = "urn"


ITEM = "item"  # the one "size" of a type sold as a single item


class SkuSettings(BaseModel):
    """What is left of the old shop-wide SKU settings: the switch for writing SKUs to Etsy. Each product type now has
    its own SKU format (Settings → Product settings → Product types). Old keys stored here are ignored."""

    # Writing SKUs to Etsy stays off until the owner asks for it; nothing in the app turns it on.
    etsy_push_enabled: bool = False


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _qty(raw: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for k, v in (raw or {}).items():
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n > 0:
            out[str(k)] = n
    return out


class UrnService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    # ── settings, types and sizes ─────────────────────────────────────────────────────────────────────────
    async def sku_settings(self) -> SkuSettings:
        from app.modules.settings.service import SettingsService

        try:
            return await SettingsService(self.session).get_model("sku", factory=SkuSettings)
        except Exception:  # noqa: BLE001 - an unreadable group falls back to "off"
            return SkuSettings()

    async def types(self, *, active_only: bool = False) -> list[ProductType]:
        stmt = select(ProductType).order_by(ProductType.position, ProductType.id)
        if active_only:
            stmt = stmt.where(ProductType.active.is_(True))
        return list((await self.session.execute(stmt)).scalars())

    async def _type(self, type_id: int) -> ProductType:
        t = await self.session.get(ProductType, type_id)
        if t is None:
            raise NotFoundError("Product type not found")
        return t

    async def default_type(self) -> ProductType:
        t = (await self.types(active_only=True)) or await self.types()
        if not t:
            raise ValidationFailedError("Add a product type in Settings → Product settings first")
        return t[0]

    @staticmethod
    def fmt(t: ProductType) -> skus.SkuFormat:
        return skus.SkuFormat(template=t.template.strip(), size_format=t.size_format, separator=t.separator)

    async def sizes(self, type_id: int | None = None, *, active_only: bool = False) -> list[UrnSize]:
        stmt = select(UrnSize).order_by(UrnSize.type_id, UrnSize.position, UrnSize.id)
        if type_id is not None:
            stmt = stmt.where(UrnSize.type_id == type_id)
        if active_only:
            stmt = stmt.where(UrnSize.active.is_(True))
        return list((await self.session.execute(stmt)).scalars())

    async def _codes(self, type_id: int) -> list[str]:
        return [s.code for s in await self.sizes(type_id)]

    async def has_sizes(self, type_id: int) -> bool:
        return bool(await self.sizes(type_id, active_only=True))

    async def check_format(self, type_id: int | None, values: dict[str, Any]) -> tuple[skus.SkuFormat, list[str], list[str]]:
        """(the format, problems, example SKUs) for a type's format someone is about to save."""
        t = await self._type(type_id) if type_id else None
        merged = {"template": t.template if t else skus.SkuFormat.template, "size_format": t.size_format if t else
                  skus.SkuFormat.size_format, "separator": t.separator if t else skus.SkuFormat.separator,
                  "code": t.code if t else None}
        merged.update({k: v for k, v in values.items() if k in merged and v is not None})
        fmt = skus.SkuFormat(template=str(merged["template"]).strip(), size_format=merged["size_format"],
                             separator=merged["separator"])
        codes = await self._codes(t.id) if t else []
        with_sizes = (await self.has_sizes(t.id)) if t else bool(values.get("has_sizes", True))
        max_sup = (await self.session.execute(select(func.max(Supplier.id)))).scalar() or 1
        max_urn = max((await self.session.execute(select(func.max(Urn.id)))).scalar() or 1, 1)
        problems = skus.check(fmt, size_codes=codes, max_supplier=max_sup, max_urn=max_urn, has_sizes=with_sizes,
                              type_code=merged["code"])
        if problems:
            return fmt, problems, []
        samples = ([[(codes[0], 1)], [(c, 2 if i else 1) for i, c in enumerate(codes[:2])]] if with_sizes and codes
                   else [[]])
        examples = list(dict.fromkeys(skus.render(fmt, supplier_id=7, urn_id=345, sizes=x, type_code=merged["code"])
                                      for x in samples))
        return fmt, problems, examples

    async def save_type(self, type_id: int | None, values: dict[str, Any], actor) -> ProductType:
        """Create or change a product type. A new format changes that type's SKUs in the CRM (never on Etsy)."""
        name = (values.get("name") or "").strip()
        if name:
            clash = (await self.session.execute(select(ProductType.id).where(
                func.lower(ProductType.name) == name.lower(), ProductType.id != (type_id or 0)))).first()
            if clash:
                raise ValidationFailedError(f"There is already a type called {name}")
        if type_id is None:
            if not name:
                raise ValidationFailedError("Give the type a name, e.g. Jewelry")
            t = ProductType(name=name, template=skus.SkuFormat.template, position=((await self.session.execute(
                select(func.max(ProductType.position)))).scalar() or 0) + 10)
            if "template" not in values or not values.get("template"):  # a new type starts as one item
                t.template = "WCW-{supplier:3}-{product:4}{-option}"
            self.session.add(t)
            await self.session.flush()
        else:
            t = await self._type(type_id)
        if name:
            t.name = name[:60]
        if "code" in values:
            code = (values["code"] or "").strip().upper()
            if code and not code.isalnum():
                raise ValidationFailedError("A type code is letters or digits, e.g. J")
            t.code = code[:10] or None
        for f in ("position", "active"):
            if values.get(f) is not None:
                setattr(t, f, values[f])
        if any(values.get(k) is not None for k in ("template", "size_format", "separator")) or "code" in values:
            fmt, problems, _ = await self.check_format(t.id, values)
            if problems:
                raise ValidationFailedError(problems[0])
            t.template, t.size_format, t.separator = fmt.template, fmt.size_format, fmt.separator
        await self.session.flush()
        await self.audit.record("product_type.save", actor=actor, entity_type="product_type", entity_id=t.id,
                                changes={"name": t.name, "code": t.code, "template": t.template, "active": t.active})
        await self.recompute_skus(t.id)
        await self.session.commit()
        return t

    async def save_size(self, size_id: int | None, values: dict[str, Any], actor) -> UrnSize:
        code = str(values.get("code") or "").strip()
        if size_id is None:
            t = await self._type(values.get("type_id") or (await self.default_type()).id)
            if not code or not code.replace(".", "").isalnum() or code.lower() == ITEM:
                raise ValidationFailedError("A size code is letters or digits, e.g. 10 or 7")
            if (await self.session.execute(select(UrnSize).where(
                    UrnSize.type_id == t.id, func.lower(UrnSize.code) == code.lower()))).first():
                raise ValidationFailedError(f"{t.name} already has a size {code}")
            first = not await self.sizes(t.id)
            if first and "{sizes}" not in t.template:  # a one-item type gets its first size: the SKU needs {sizes}
                t.template = t.template.replace("{-option}", "-{sizes}{-option}") if "{-option}" in t.template \
                    else t.template + "-{sizes}"
            size = UrnSize(type_id=t.id, code=code, label=values.get("label") or f"{code} inch", aliases=[], active=True,
                           position=values.get("position") or ((await self.session.execute(
                               select(func.max(UrnSize.position)).where(UrnSize.type_id == t.id))).scalar() or 0) + 10)
            self.session.add(size)
        else:
            size = await self.session.get(UrnSize, size_id)
            if size is None:
                raise NotFoundError("Size not found")
            if code and code != size.code:
                used = (await self.session.execute(select(func.count()).select_from(UrnPrice).join(
                    Urn, Urn.id == UrnPrice.urn_id).where(UrnPrice.size_code == size.code,
                                                          Urn.type_id == size.type_id))).scalar_one()
                if used:
                    raise ValidationFailedError("This size already has prices: its code can't change (SKUs use it)")
                size.code = code
        for field in ("label", "position", "active"):
            if values.get(field) is not None:
                setattr(size, field, values[field])
        if values.get("aliases") is not None:
            size.aliases = sorted({a.strip().lower() for a in values["aliases"] if a and a.strip()})[:30]
        await self.session.flush()
        if size_id is None and first:  # its products were "one item": read their variations again with sizes
            for urn in (await self.session.execute(select(Urn).where(Urn.type_id == size.type_id,
                                                                     Urn.deleted_at.is_(None)))).scalars().all():
                await self._refresh_variations(urn, everything=True)
        await self.audit.record("urn_size.save", actor=actor, entity_type="urn_size", entity_id=size.id,
                                changes={"type_id": size.type_id, "code": size.code, "label": size.label,
                                         "active": size.active})
        await self.recompute_skus(size.type_id)
        await self.session.commit()
        return size

    # ── urns ──────────────────────────────────────────────────────────────────────────────────────────────
    async def _urn(self, urn_id: int) -> Urn:
        urn = await self.session.get(Urn, urn_id)
        if urn is None or urn.deleted_at is not None:
            raise NotFoundError("Product not found")
        return urn

    async def setup_from_listings(self, actor) -> dict[str, int]:
        """A urn draft for every Etsy listing that has none yet, with its variations read. Safe to run again."""
        have = set((await self.session.execute(
            select(Urn.listing_id).where(Urn.listing_id.is_not(None), Urn.deleted_at.is_(None)))).scalars())
        listings = (await self.session.execute(select(ChannelListing).where(
            ChannelListing.channel == "etsy", ChannelListing.state != "removed"))).scalars().all()
        created = 0
        default = await self.default_type()
        for lst in listings:
            if lst.id in have:
                continue
            urn = Urn(name=reading.short_name(lst.title), listing_id=lst.id, type_id=default.id,
                      created_by=getattr(actor, "id", None), updated_by=getattr(actor, "id", None))
            self.session.add(urn)
            await self.session.flush()
            created += 1
        refreshed = 0
        for urn in (await self.session.execute(select(Urn).where(Urn.deleted_at.is_(None),
                                                                 Urn.listing_id.is_not(None)))).scalars().all():
            refreshed += await self._refresh_variations(urn)
        if created:
            await self.audit.record("urn.setup", actor=actor, entity_type=ENTITY, entity_id=None,
                                    changes={"created": created})
        await self.session.commit()
        return {"created": created, "variations_added": refreshed}

    async def _refresh_variations(self, urn: Urn, *, everything: bool = False) -> int:
        """Bring the product's variation rows in line with its listing: new ones read, gone ones marked removed,
        Etsy's current SKU copied. Approved quantities are kept unless `everything` (its type changed)."""
        lst = await self.session.get(ChannelListing, urn.listing_id) if urn.listing_id else None
        if lst is None:
            return 0
        type_sizes = await self.sizes(urn.type_id, active_only=True)
        sizes = [reading.Size(s.code, tuple(s.aliases or ()) + (s.label,)) for s in type_sizes]
        wanted: dict[str, tuple[str, str | None, str]] = {}
        for v in lst.variations or []:
            opts = v.get("options") or {}
            key = reading.options_key(opts)
            wanted[key] = (reading.options_label(opts) or lst.title, v.get("sku"), " ".join(str(x) for x in opts.values()))
        if not wanted:
            sku = (lst.skus or [None])[0]
            wanted[""] = ("(no variations)", sku, lst.title)
        rows = {r.key: r for r in (await self.session.execute(
            select(UrnVariation).where(UrnVariation.urn_id == urn.id))).scalars()}
        added = 0
        for key, (label, etsy_sku, words) in wanted.items():
            row = rows.get(key)
            if row is None or row.state != "approved" or everything:  # unapproved rows follow the latest sizes
                read = reading.read(words, sizes) if type_sizes else reading.Reading({ITEM: 1}, True, None)
                if row is None:
                    row = UrnVariation(urn_id=urn.id, key=key, label=label[:300])
                    self.session.add(row)
                    added += 1
                row.quantities, row.note = read.quantities, read.note
                row.state = "proposed" if read.clear else "unclear"
            row.label, row.etsy_sku, row.removed = label[:300], etsy_sku, False
        for key, row in rows.items():
            if key not in wanted:
                row.removed = True
        await self.session.flush()
        await self._skus_for(urn)
        return added

    async def refresh(self, urn_id: int) -> None:
        await self._refresh_variations(await self._urn(urn_id))
        await self.session.commit()

    async def _skus_for(self, urn: Urn, t: ProductType | None = None, order: list[str] | None = None) -> int:
        t = t or await self._type(urn.type_id)
        fmt = self.fmt(t)
        order = order if order is not None else await self._codes(t.id)
        changed = 0
        for row in (await self.session.execute(select(UrnVariation).where(UrnVariation.urn_id == urn.id))).scalars():
            q = _qty(row.quantities)
            new = None
            if urn.supplier_id and row.state == "approved" and q:
                new = skus.render(fmt, supplier_id=urn.supplier_id, urn_id=urn.id, type_code=t.code,
                                  sizes=[(c, q[c]) for c in order if c in q])
            if new != row.sku:
                row.sku, changed = new, changed + 1
        return changed

    async def recompute_skus(self, type_id: int | None = None) -> int:
        n = 0
        for t in await self.types():
            if type_id is not None and t.id != type_id:
                continue
            order = await self._codes(t.id)
            for urn in (await self.session.execute(select(Urn).where(Urn.deleted_at.is_(None),
                                                                     Urn.type_id == t.id))).scalars().all():
                n += await self._skus_for(urn, t, order)
        await self.session.flush()
        return n

    async def update(self, urn_id: int, values: dict[str, Any], actor) -> Urn:
        urn = await self._urn(urn_id)
        before = {"name": urn.name, "supplier_id": urn.supplier_id, "notes": urn.notes, "type_id": urn.type_id}
        if "name" in values and values["name"] is not None:
            if not values["name"].strip():
                raise ValidationFailedError("Give the product a name")
            urn.name = values["name"].strip()[:120]
        if "supplier_id" in values:
            if values["supplier_id"] is not None:
                sup = await self.session.get(Supplier, values["supplier_id"])
                if sup is None or sup.deleted_at is not None:
                    raise ValidationFailedError(f"Supplier #{values['supplier_id']} doesn't exist")
            urn.supplier_id = values["supplier_id"]
        if "notes" in values:
            urn.notes = (values["notes"] or "").strip() or None
        retyped = values.get("type_id") is not None and values["type_id"] != urn.type_id
        if retyped:  # another type: its variations are read again with that type's sizes; old orders keep their costs
            await self._type(values["type_id"])
            urn.type_id = values["type_id"]
            await self.session.flush()
            await self._refresh_variations(urn, everything=True)
        urn.updated_by = actor.id
        await self._skus_for(urn)
        after = {"name": urn.name, "supplier_id": urn.supplier_id, "notes": urn.notes, "type_id": urn.type_id}
        changes = {k: [before[k], after[k]] for k in before if before[k] != after[k]}
        if changes:
            await self.audit.record("urn.update", actor=actor, entity_type=ENTITY, entity_id=urn.id, changes=changes)
        await self.session.commit()
        return urn

    async def assign_supplier(self, urn_ids: list[int], supplier_id: int | None, actor) -> int:
        """The same supplier on several urns at once."""
        n = 0
        for urn_id in dict.fromkeys(urn_ids):
            await self.update(urn_id, {"supplier_id": supplier_id}, actor)
            n += 1
        return n

    async def assign_type(self, urn_ids: list[int], type_id: int, actor) -> int:
        """The same type on several products at once (their variations are read again)."""
        await self._type(type_id)
        n = 0
        for urn_id in dict.fromkeys(urn_ids):
            await self.update(urn_id, {"type_id": type_id}, actor)
            n += 1
        return n

    async def delete(self, urn_id: int, actor) -> None:
        urn = await self._urn(urn_id)
        urn.deleted_at, urn.updated_by = datetime.now(timezone.utc), actor.id
        await self.audit.record("urn.delete", actor=actor, entity_type=ENTITY, entity_id=urn.id,
                                changes={"name": urn.name})
        await self.session.commit()

    # ── variations ────────────────────────────────────────────────────────────────────────────────────────
    async def _variation(self, urn_id: int, variation_id: int) -> UrnVariation:
        row = await self.session.get(UrnVariation, variation_id)
        if row is None or row.urn_id != urn_id:
            raise NotFoundError("Variation not found")
        return row

    async def set_variation(self, urn_id: int, variation_id: int, quantities: dict[str, Any], actor) -> UrnVariation:
        """A person's quantities for one variation: approved as given."""
        urn = await self._urn(urn_id)
        row = await self._variation(urn.id, variation_id)
        codes = set(await self._codes(urn.type_id)) or {ITEM}
        q = _qty(quantities)
        unknown = [c for c in q if c not in codes]
        if unknown:
            raise ValidationFailedError(f"Unknown size {unknown[0]}. Add it to the product type in Settings → Product settings first.")
        if not q:
            raise ValidationFailedError("Give at least one size a quantity")
        before = dict(row.quantities or {})
        row.quantities, row.state, row.note = q, "approved", None
        row.approved_at, row.approved_by = datetime.now(timezone.utc), actor.id
        await self._skus_for(urn)
        await self.audit.record("urn.variation", actor=actor, entity_type=ENTITY, entity_id=urn.id,
                                changes={"variation": row.label, "quantities": [before, q]})
        await self.session.commit()
        return row

    async def approve(self, urn_ids: list[int] | None, actor, variation_ids: list[int] | None = None) -> int:
        """Approve what was read. Only `proposed` rows (never `unclear` ones) are approved this way."""
        cond = [UrnVariation.state == "proposed", UrnVariation.removed.is_(False)]
        if variation_ids:
            cond.append(UrnVariation.id.in_(variation_ids))
        if urn_ids:
            cond.append(UrnVariation.urn_id.in_(urn_ids))
        rows = (await self.session.execute(select(UrnVariation).where(*cond))).scalars().all()
        now = datetime.now(timezone.utc)
        for r in rows:
            if _qty(r.quantities):
                r.state, r.approved_at, r.approved_by = "approved", now, actor.id
        for urn_id in {r.urn_id for r in rows}:
            await self._skus_for(await self._urn(urn_id))
        if rows:
            await self.audit.record("urn.approve", actor=actor, entity_type=ENTITY, entity_id=None,
                                    changes={"variations": len(rows)})
        await self.session.commit()
        return len(rows)

    # ── prices and extras ─────────────────────────────────────────────────────────────────────────────────
    async def set_price(self, urn_id: int, size_code: str, amount: Decimal, effective_from: date | None, actor) -> None:
        urn = await self._urn(urn_id)
        if size_code not in (await self._codes(urn.type_id) or [ITEM]):
            raise ValidationFailedError(f"Unknown size {size_code} for this product's type")
        if amount < 0:
            raise ValidationFailedError("A supplier price can't be negative; use an extra for a discount")
        on = effective_from or _today()
        row = (await self.session.execute(select(UrnPrice).where(
            UrnPrice.urn_id == urn.id, UrnPrice.size_code == size_code, UrnPrice.effective_from == on))).scalar_one_or_none()
        old = row.amount if row else None
        if row is None:
            row = UrnPrice(urn_id=urn.id, size_code=size_code, effective_from=on, amount=amount, created_by=actor.id)
            self.session.add(row)
        row.amount, row.updated_by = amount, actor.id
        await self.audit.record("urn.price", actor=actor, entity_type=ENTITY, entity_id=urn.id,
                                changes={"size": size_code, "from": str(on), "amount": [str(old) if old else None, str(amount)]})
        await self.session.commit()

    async def delete_price(self, urn_id: int, price_id: int, actor) -> None:
        row = await self.session.get(UrnPrice, price_id)
        if row is None or row.urn_id != urn_id:
            raise NotFoundError("Price not found")
        await self.session.delete(row)
        await self.audit.record("urn.price_delete", actor=actor, entity_type=ENTITY, entity_id=urn_id,
                                changes={"size": row.size_code, "from": str(row.effective_from), "amount": str(row.amount)})
        await self.session.commit()

    async def prices(self, urn_ids: list[int]) -> dict[int, list[UrnPrice]]:
        if not urn_ids:
            return {}
        out: dict[int, list[UrnPrice]] = {}
        for p in (await self.session.execute(select(UrnPrice).where(UrnPrice.urn_id.in_(urn_ids))
                                             .order_by(UrnPrice.size_code, UrnPrice.effective_from.desc()))).scalars():
            out.setdefault(p.urn_id, []).append(p)
        return out

    @staticmethod
    def price_on(prices: list[UrnPrice], size_code: str, on: date) -> UrnPrice | None:
        return next((p for p in prices if p.size_code == size_code and p.effective_from <= on), None)

    async def save_extra(self, extra_id: int | None, values: dict[str, Any], actor) -> CostExtra:
        """An extra for one product (`urn_id`), every product of a type (`type_id`), or every product (neither)."""
        if values.get("urn_id") is not None and values.get("type_id") is not None:
            raise ValidationFailedError("An extra is for one product or one type, not both")
        scope_type = None
        if values.get("urn_id") is not None:
            scope_type = (await self._urn(values["urn_id"])).type_id
        elif values.get("type_id") is not None:
            scope_type = (await self._type(values["type_id"])).id
        if values.get("size_code"):
            codes = set(await self._codes(scope_type)) if scope_type else {s.code for s in await self.sizes()}
            if values["size_code"] not in codes:
                raise ValidationFailedError(f"Unknown size {values['size_code']}")
        if extra_id is None:
            row = CostExtra(created_by=actor.id, effective_from=values.get("effective_from") or _today())
            self.session.add(row)
        else:
            row = await self.session.get(CostExtra, extra_id)
            if row is None:
                raise NotFoundError("Extra cost not found")
        for f in ("urn_id", "type_id", "name", "mode", "value", "applies", "size_code", "party", "effective_from",
                  "effective_to"):
            if f in values and (values[f] is not None or f in ("size_code", "effective_to", "urn_id", "type_id")):
                setattr(row, f, values[f])
        if row.mode == "percent" and row.applies == "order":
            raise ValidationFailedError("A percentage applies to the supplier price of each piece: choose 'per piece'")
        if row.effective_to and row.effective_to < row.effective_from:
            raise ValidationFailedError("The end date is before the start date")
        row.updated_by = actor.id
        await self.session.flush()
        await self.audit.record("cost_extra.save", actor=actor, entity_type=ENTITY, entity_id=row.urn_id,
                                changes={"extra": row.name, "value": str(row.value), "mode": row.mode,
                                         "applies": row.applies, "party": row.party})
        await self.session.commit()
        return row

    async def end_extra(self, extra_id: int, on: date | None, actor) -> None:
        """Stop an extra from a date (default today). Kept, so orders before then still show it."""
        row = await self.session.get(CostExtra, extra_id)
        if row is None:
            raise NotFoundError("Extra cost not found")
        row.effective_to, row.updated_by = on or _today(), actor.id
        await self.audit.record("cost_extra.end", actor=actor, entity_type=ENTITY, entity_id=row.urn_id,
                                changes={"extra": row.name, "until": str(row.effective_to)})
        await self.session.commit()

    async def extras(self, urn_id: int | None, *, type_id: int | None = None, include_ended: bool = True) -> list[CostExtra]:
        """For a product: its own, its type's and everyone's. For a type: its own (and everyone's). Else everyone's."""
        everyone = and_(CostExtra.urn_id.is_(None), CostExtra.type_id.is_(None))
        if urn_id:
            urn = await self._urn(urn_id)
            cond = [or_(everyone, CostExtra.urn_id == urn.id,
                        and_(CostExtra.urn_id.is_(None), CostExtra.type_id == urn.type_id))]
        elif type_id:
            cond = [and_(CostExtra.urn_id.is_(None), CostExtra.type_id == type_id)]
        else:
            cond = [everyone]
        if not include_ended:
            cond.append(or_(CostExtra.effective_to.is_(None), CostExtra.effective_to >= _today()))
        return list((await self.session.execute(select(CostExtra).where(*cond)
                                                .order_by(CostExtra.urn_id.nulls_first(), CostExtra.type_id.nulls_first(),
                                                          CostExtra.id))).scalars())

    # ── reading out ───────────────────────────────────────────────────────────────────────────────────────
    async def summary(self) -> dict[str, int]:
        """The setup to-do list on the Urns page."""
        live = Urn.deleted_at.is_(None)
        listings = (await self.session.execute(select(func.count()).select_from(ChannelListing).where(
            ChannelListing.channel == "etsy", ChannelListing.state != "removed"))).scalar_one()
        urns = (await self.session.execute(select(func.count()).select_from(Urn).where(live))).scalar_one()
        no_supplier = (await self.session.execute(select(func.count()).select_from(Urn).where(
            live, Urn.supplier_id.is_(None)))).scalar_one()
        to_review = (await self.session.execute(select(func.count()).select_from(UrnVariation).join(
            Urn, Urn.id == UrnVariation.urn_id).where(live, UrnVariation.removed.is_(False),
                                                      UrnVariation.state != "approved"))).scalar_one()
        unclear = (await self.session.execute(select(func.count()).select_from(UrnVariation).join(
            Urn, Urn.id == UrnVariation.urn_id).where(live, UrnVariation.removed.is_(False),
                                                      UrnVariation.state == "unclear"))).scalar_one()
        priced = select(UrnPrice.urn_id).distinct()
        no_prices = (await self.session.execute(select(func.count()).select_from(Urn).where(
            live, Urn.id.not_in(priced)))).scalar_one()
        mismatched = (await self.session.execute(select(func.count()).select_from(UrnVariation).join(
            Urn, Urn.id == UrnVariation.urn_id).where(live, UrnVariation.removed.is_(False),
                                                      UrnVariation.sku.is_not(None),
                                                      or_(UrnVariation.etsy_sku.is_(None),
                                                          UrnVariation.etsy_sku != UrnVariation.sku)))).scalar_one()
        open_rows = select(UrnVariation.urn_id).where(UrnVariation.removed.is_(False), UrnVariation.state != "approved")
        ready = (await self.session.execute(select(func.count()).select_from(Urn).where(
            live, Urn.supplier_id.is_not(None), Urn.id.not_in(open_rows), Urn.id.in_(priced)))).scalar_one()
        return {"listings_without_urn": max(listings - urns, 0), "urns": urns, "ready": ready, "no_supplier": no_supplier,
                "to_review": to_review, "unclear": unclear, "no_prices": no_prices, "sku_differs": mismatched}

    async def list(self, *, q: str | None, supplier_id: int | None, needs: str | None, page: int,
                   page_size: int, type_id: int | None = None) -> dict[str, Any]:
        cond = [Urn.deleted_at.is_(None)]
        if type_id:
            cond.append(Urn.type_id == type_id)
        if q:
            match = Urn.name.ilike(f"%{q.strip()}%")
            if q.strip().isdigit():
                match = or_(match, Urn.id == int(q.strip()))
            cond.append(match)
        if supplier_id:
            cond.append(Urn.supplier_id == supplier_id)
        open_rows = select(UrnVariation.urn_id).where(UrnVariation.removed.is_(False), UrnVariation.state != "approved")
        if needs == "supplier":
            cond.append(Urn.supplier_id.is_(None))
        elif needs == "review":
            cond.append(Urn.id.in_(open_rows))
        elif needs == "prices":
            cond.append(Urn.id.not_in(select(UrnPrice.urn_id).distinct()))
        elif needs == "ready":
            cond += [Urn.supplier_id.is_not(None), Urn.id.not_in(open_rows), Urn.id.in_(select(UrnPrice.urn_id).distinct())]
        total = (await self.session.execute(select(func.count()).select_from(Urn).where(*cond))).scalar_one()
        urns = (await self.session.execute(select(Urn).where(*cond).order_by(func.lower(Urn.name), Urn.id)
                                           .offset((page - 1) * page_size).limit(page_size))).scalars().all()
        return {"items": await self.out(list(urns), detail=False), "total": total, "page": page, "page_size": page_size}

    async def out(self, urns: list[Urn], *, detail: bool) -> list[dict[str, Any]]:
        ids = [u.id for u in urns]
        suppliers = {s.id: s.name for s in (await self.session.execute(select(Supplier).where(
            Supplier.id.in_({u.supplier_id for u in urns if u.supplier_id})))).scalars()} if urns else {}
        listings = {l.id: l for l in (await self.session.execute(select(ChannelListing).where(
            ChannelListing.id.in_({u.listing_id for u in urns if u.listing_id})))).scalars()} if urns else {}
        variations: dict[int, list[UrnVariation]] = {}
        if ids:
            for v in (await self.session.execute(select(UrnVariation).where(UrnVariation.urn_id.in_(ids))
                                                 .order_by(UrnVariation.removed, UrnVariation.id))).scalars():
                variations.setdefault(v.urn_id, []).append(v)
        prices = await self.prices(ids)
        types = {t.id: t for t in await self.types()}
        all_sizes = await self.sizes()
        today = _today()
        out = []
        for u in urns:
            lst = listings.get(u.listing_id) if u.listing_id else None
            vs = [v for v in variations.get(u.id, []) if detail or not v.removed]
            ps = prices.get(u.id, [])
            sizes = [s for s in all_sizes if s.type_id == u.type_id]
            codes = [s.code for s in sizes if s.active] or [ITEM]
            current = {c: (str(p.amount) if (p := self.price_on(ps, c, today)) else None) for c in codes}
            t = types.get(u.type_id)
            live = [v for v in vs if not v.removed]
            row = {
                "id": u.id, "name": u.name, "supplier_id": u.supplier_id, "supplier_name": suppliers.get(u.supplier_id),
                "type_id": u.type_id, "type_name": t.name if t else None, "has_sizes": codes != [ITEM],
                "listing_id": u.listing_id, "listing_title": lst.title if lst else None,
                "listing_url": lst.url if lst else None, "listing_state": lst.state if lst else None,
                "image": (lst.images or [None])[0] if lst else None, "notes": u.notes,
                "prices": current,
                "variations_total": len(live),
                "variations_open": sum(1 for v in live if v.state != "approved"),
                "variations_unclear": sum(1 for v in live if v.state == "unclear"),
                "skus_differ": sum(1 for v in live if v.sku and v.sku != v.etsy_sku),
                "updated_at": u.updated_at,
            }
            if detail:
                row["variations"] = [self.variation_out(v) for v in vs]
                row["price_history"] = [{"id": p.id, "size_code": p.size_code, "amount": str(p.amount),
                                         "effective_from": p.effective_from} for p in ps]
                row["extras"] = [self.extra_out(e) for e in await self.extras(u.id)]
                row["sizes"] = [{"code": s.code, "label": s.label, "active": s.active} for s in sizes]
            out.append(row)
        return out

    @staticmethod
    def variation_out(v: UrnVariation) -> dict[str, Any]:
        return {"id": v.id, "urn_id": v.urn_id, "label": v.label, "quantities": v.quantities or {}, "state": v.state,
                "note": v.note, "sku": v.sku, "etsy_sku": v.etsy_sku, "removed": v.removed,
                "approved_at": v.approved_at}

    @staticmethod
    def extra_out(e: CostExtra) -> dict[str, Any]:
        return {"id": e.id, "urn_id": e.urn_id, "type_id": e.type_id, "name": e.name, "mode": e.mode, "value": format(e.value.normalize(), "f") if e.value is not None else None,
                "applies": e.applies, "size_code": e.size_code, "party": e.party,
                "effective_from": e.effective_from, "effective_to": e.effective_to,
                "active": e.effective_to is None or e.effective_to >= _today()}

    async def detail(self, urn_id: int) -> dict[str, Any]:
        return (await self.out([await self._urn(urn_id)], detail=True))[0]

    async def review(self, *, state: str | None, page: int, page_size: int) -> dict[str, Any]:
        """Every variation still waiting for a person (or all of them), with its urn — the review table."""
        cond = [Urn.deleted_at.is_(None), UrnVariation.removed.is_(False)]
        if state in ("proposed", "unclear", "approved"):
            cond.append(UrnVariation.state == state)
        elif state != "all":
            cond.append(UrnVariation.state != "approved")
        base = select(UrnVariation, Urn).join(Urn, Urn.id == UrnVariation.urn_id).where(*cond)
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await self.session.execute(base.order_by(
            (UrnVariation.state == "unclear").desc(), func.lower(Urn.name), UrnVariation.id)
            .offset((page - 1) * page_size).limit(page_size))).all()
        sup = {s.id: s.name for s in (await self.session.execute(select(Supplier).where(
            Supplier.id.in_({u.supplier_id for _, u in rows if u.supplier_id})))).scalars()} if rows else {}
        types = {t.id: t.name for t in await self.types()}
        items = [{**self.variation_out(v), "urn_name": u.name, "supplier_id": u.supplier_id,
                  "supplier_name": sup.get(u.supplier_id), "type_id": u.type_id, "type_name": types.get(u.type_id)}
                 for v, u in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def sku_preview(self, *, only_different: bool) -> list[dict[str, Any]]:
        """What Etsy has next to what the CRM would write, per variation. Read-only."""
        cond = [Urn.deleted_at.is_(None), UrnVariation.removed.is_(False)]
        if only_different:
            cond.append(and_(UrnVariation.sku.is_not(None),
                             or_(UrnVariation.etsy_sku.is_(None), UrnVariation.etsy_sku != UrnVariation.sku)))
        rows = (await self.session.execute(select(UrnVariation, Urn).join(Urn, Urn.id == UrnVariation.urn_id)
                                           .where(*cond).order_by(func.lower(Urn.name), UrnVariation.id))).all()
        types = {t.id: t.name for t in await self.types()}
        dup: dict[str, int] = {}
        for v, _ in rows:
            if v.sku:
                dup[v.sku] = dup.get(v.sku, 0) + 1
        return [{"urn_id": u.id, "urn_name": u.name, "type_name": types.get(u.type_id), "variation_id": v.id, "label": v.label, "etsy_sku": v.etsy_sku,
                 "crm_sku": v.sku, "state": v.state,
                 "status": ("not_ready" if not v.sku else "same" if v.sku == v.etsy_sku else
                            "new" if not v.etsy_sku else "different"),
                 "shared": bool(v.sku and dup.get(v.sku, 0) > 1)} for v, u in rows]

    async def match(self, listing_external_id: int | None, options: list | dict | None, sku: str | None) -> UrnVariation | None:
        """The approved variation an order line is for: by its listing + chosen options, else by its SKU."""
        if listing_external_id:
            urn_id = (await self.session.execute(select(Urn.id).join(ChannelListing, ChannelListing.id == Urn.listing_id)
                                                 .where(ChannelListing.external_id == listing_external_id,
                                                        Urn.deleted_at.is_(None)))).scalar_one_or_none()
            if urn_id:
                key = reading.options_key(options)
                row = (await self.session.execute(select(UrnVariation).where(
                    UrnVariation.urn_id == urn_id, UrnVariation.key == key))).scalar_one_or_none()
                if row is None and key:  # a listing without options ordered as one
                    row = None
                if row is None:
                    rows = (await self.session.execute(select(UrnVariation).where(
                        UrnVariation.urn_id == urn_id, UrnVariation.removed.is_(False)))).scalars().all()
                    row = rows[0] if len(rows) == 1 else None
                if row is not None and row.state == "approved":
                    return row
        if sku:
            row = (await self.session.execute(select(UrnVariation).where(
                UrnVariation.state == "approved", or_(UrnVariation.sku == sku, UrnVariation.etsy_sku == sku))
                .limit(1))).scalar_one_or_none()
            return row
        return None


class EtsySkuPush:
    """Writing SKUs to Etsy. Switched off: the owner asked that nothing is sent to Etsy until they say so. Turning it
    on needs the `etsy_push_enabled` setting (not editable in the app) and the Etsy `listings_w` permission."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def apply(self, actor) -> None:
        settings = await UrnService(self.session).sku_settings()
        if not settings.etsy_push_enabled:
            raise ConflictError("Updating SKUs on Etsy is switched off for now. The CRM keeps the SKUs and uses them "
                                "for costs; ask to have Etsy updates turned on when you are ready.")
        raise ConflictError("Updating SKUs on Etsy isn't built yet.")
