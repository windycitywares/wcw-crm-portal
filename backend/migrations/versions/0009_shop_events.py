"""Shop integration: received events and order copies.

Revision ID: 0009_shop_events
Revises: 0008_customers
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_shop_events"
down_revision = "0008_customers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shop_events")),
        sa.UniqueConstraint("event_id", name=op.f("uq_shop_events_event_id")),
    )
    op.create_index(op.f("ix_shop_events_event_type"), "shop_events", ["event_type"])
    op.create_index(op.f("ix_shop_events_received_at"), "shop_events", ["received_at"])
    op.create_index("ix_shop_events_status_id", "shop_events", ["status", "id"])

    op.create_table(
        "shop_orders",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("payment_status", sa.String(length=20), server_default="unpaid", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("grand_total", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False),
        sa.Column("refunded_total", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shop_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name=op.f("fk_shop_orders_customer_id_customers"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shop_orders")),
    )
    op.create_index(op.f("ix_shop_orders_customer_id"), "shop_orders", ["customer_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_shop_orders_customer_id"), table_name="shop_orders")
    op.drop_table("shop_orders")
    op.drop_index("ix_shop_events_status_id", table_name="shop_events")
    op.drop_index(op.f("ix_shop_events_received_at"), table_name="shop_events")
    op.drop_index(op.f("ix_shop_events_event_type"), table_name="shop_events")
    op.drop_table("shop_events")
