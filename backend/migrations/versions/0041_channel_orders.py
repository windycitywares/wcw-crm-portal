"""channel_orders, their items and history: marketplace (Etsy) orders worked by the team.

Revision ID: 0041_channel_orders
Revises: 0040_channel_listings
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0041_channel_orders"
down_revision = "0040_channel_listings"
branch_labels = None
depends_on = None

money = lambda: sa.Numeric(12, 2)  # noqa: E731


def upgrade() -> None:
    op.create_table(
        "channel_orders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("external_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("external_state", sa.String(30)),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("ship_by", sa.DateTime(timezone=True)),
        sa.Column("buyer_name", sa.String(200)),
        sa.Column("external_buyer_id", sa.BigInteger()),
        sa.Column("buyer_email", sa.String(320)),
        sa.Column("buyer_phone", sa.String(50)),
        sa.Column("ship_address", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("gift_message", sa.Text()),
        sa.Column("buyer_note", sa.Text()),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("items_total", money(), nullable=False, server_default="0"),
        sa.Column("shipping_charged", money(), nullable=False, server_default="0"),
        sa.Column("discounts", money(), nullable=False, server_default="0"),
        sa.Column("tax", money(), nullable=False, server_default="0"),
        sa.Column("grand_total", money(), nullable=False, server_default="0"),
        sa.Column("marketplace_fees", money()),
        sa.Column("marketplace_fees_at", sa.DateTime(timezone=True)),
        sa.Column("purchase_cost", money()),
        sa.Column("costs_prefilled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("past_order", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supplier_account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("supplier_order_number", sa.String(100)),
        sa.Column("supplier_paid_at", sa.DateTime(timezone=True)),
        sa.Column("supplier_paid_amount", money()),
        sa.Column("supplier_payment_ref", sa.String(100)),
        sa.Column("supplier_paid_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("shipping_cost", money()),
        sa.Column("carrier", sa.String(60)),
        sa.Column("tracking_number", sa.String(100)),
        sa.Column("tracking_sent_at", sa.DateTime(timezone=True)),
        sa.Column("tracking_error", sa.String(300)),
        sa.Column("purchased_at", sa.DateTime(timezone=True)),
        sa.Column("shipped_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("external_updated_at", sa.DateTime(timezone=True)),
        sa.Column("synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("channel", "external_id", name="uq_channel_orders_channel_external_id"),
    )
    for column in ("channel", "status", "ordered_at", "supplier_account_id", "supplier_paid_at"):
        op.create_index(f"ix_channel_orders_{column}", "channel_orders", [column])

    op.create_table(
        "channel_order_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("channel_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.BigInteger(), nullable=False),
        sa.Column("listing_external_id", sa.BigInteger()),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("sku", sa.String(100)),
        sa.Column("variations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", money(), nullable=False, server_default="0"),
        sa.UniqueConstraint("order_id", "external_id", name="uq_channel_order_items_order_external_id"),
    )
    op.create_index("ix_channel_order_items_order_id", "channel_order_items", ["order_id"])
    op.create_index("ix_channel_order_items_listing_external_id", "channel_order_items", ["listing_external_id"])

    op.create_table(
        "channel_order_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("order_id", sa.BigInteger(), sa.ForeignKey("channel_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20)),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("source", sa.String(10), nullable=False, server_default="team"),
        sa.Column("actor_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_name", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_channel_order_events_order_id", "channel_order_events", ["order_id"])


def downgrade() -> None:
    op.drop_table("channel_order_events")
    op.drop_table("channel_order_items")
    op.drop_table("channel_orders")
