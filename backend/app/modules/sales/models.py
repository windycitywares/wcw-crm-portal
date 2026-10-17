"""Sales (SPEC §3.3): pipelines, their stages, the deals that move through them, and what is on a deal.

Four tables:
- `pipelines` — a board ("Sales", "Custom order", "Wholesale"), one of them the default for new deals;
- `pipeline_stages` — the columns of a board, in order, each with a default probability and the
  `is_won` / `is_lost` flags that decide the outcome when a deal lands on it;
- `deals` — one opportunity: value, expected close, probability, owner, stage;
- `deal_items` — the products on a deal, from the shop catalog or typed in by hand (SPEC §3.3).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import AuthorMixin, Base, CustomFieldsMixin, IdMixin, OwnedMixin, SoftDeleteMixin, TimestampMixin

STATUSES = ("open", "won", "lost")


class Pipeline(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """A board of stages (SPEC §3.3), edited in Admin → Settings → Pipelines. Deals point at a stage,
    which belongs to a pipeline, so a deal's pipeline is really its stage's pipeline."""

    __tablename__ = "pipelines"

    name: Mapped[str] = mapped_column(String(80))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class PipelineStage(IdMixin, TimestampMixin, Base):
    """One column of a board. `position` is the left-to-right order (0 first); `probability` (0–100) is the
    default for a deal in this stage — it makes the weighted forecast. `is_won` / `is_lost` mark the end
    columns: a deal dropped there is won or lost."""

    __tablename__ = "pipeline_stages"
    __table_args__ = (Index("ix_pipeline_stages_pipeline", "pipeline_id", "position"),)

    pipeline_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pipelines.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    probability: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_won: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_lost: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    color: Mapped[str | None] = mapped_column(String(20))  # a token name the web app maps to a colour


class Deal(IdMixin, TimestampMixin, AuthorMixin, OwnedMixin, SoftDeleteMixin, CustomFieldsMixin, Base):
    """An opportunity (SPEC §3.3). `owner_id` is the salesperson who has it; the own/any permission rule
    uses that. `status` follows the stage: a stage with `is_won` / `is_lost` sets it as the deal lands."""

    __tablename__ = "deals"
    __table_args__ = (
        Index("ix_deals_stage_position", "stage_id", "position"),
        Index("ix_deals_customer", "customer_id"),
        Index("ix_deals_open_close", "expected_close_on",
              postgresql_where=text("deleted_at IS NULL AND status = 'open'")),
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    customer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("customers.id", ondelete="SET NULL"))
    stage_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("pipeline_stages.id", ondelete="SET NULL"))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # order within its stage

    status: Mapped[str] = mapped_column(String(10), default="open", server_default="open")  # open | won | lost
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    probability: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # 0–100
    expected_close_on: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped[str | None] = mapped_column(String(60))  # lookup key (kind lead_source)
    lost_reason: Mapped[str | None] = mapped_column(String(60))  # lookup key (kind lost_reason)


class DealItem(IdMixin, TimestampMixin, AuthorMixin, SoftDeleteMixin, Base):
    """A line on a deal (SPEC §3.3): a product from the shop catalog, or a one-off typed in by hand.

    `shop_product_id` is the catalog's id when the line came from there (`sku` travels with it, so the
    line still reads after the product is renamed or withdrawn — and a hand-typed line can carry a SKU
    without ever having been in the shop). `total` is quantity × unit price; the deal's own `value`
    stays whatever the salesperson quoted, so the two can be compared (and brought in line) rather than
    one silently overwriting the other.
    """

    __tablename__ = "deal_items"
    __table_args__ = (Index("ix_deal_items_deal", "deal_id", "position"),)

    deal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("deals.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str | None] = mapped_column(String(80))
    shop_product_id: Mapped[int | None] = mapped_column(BigInteger)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("1"), server_default="1")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    @property
    def total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))
