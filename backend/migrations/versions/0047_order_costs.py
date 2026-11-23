"""Order costs from SKUs: the split (supplier's part vs ours), where the cost came from, its lines, and one-off
adjustments per order.

Revision ID: 0047_order_costs
Revises: 0046_urns
Create Date: 2026-11-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0047_order_costs"
down_revision = "0046_urns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channel_orders", sa.Column("other_costs", sa.Numeric(12, 2)))
    op.add_column("channel_orders", sa.Column("cost_source", sa.String(10)))
    op.add_column("channel_orders", sa.Column("cost_breakdown", postgresql.JSONB(), nullable=False,
                                              server_default=sa.text("'{}'::jsonb")))
    # What is there today: a prefilled cost came from the listing; any other cost was typed by a person.
    op.execute("UPDATE channel_orders SET cost_source = CASE WHEN costs_prefilled THEN 'listing' ELSE 'manual' END "
               "WHERE purchase_cost IS NOT NULL")
    op.create_table(
        "channel_order_adjustments",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("party", sa.String(10), nullable=False, server_default="supplier"),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["order_id"], ["channel_orders.id"], name="fk_channel_order_adjustments_order_id_channel_orders",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_channel_order_adjustments_created_by_users",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_channel_order_adjustments"),
    )
    op.create_index("ix_channel_order_adjustments_order_id", "channel_order_adjustments", ["order_id"])


def downgrade() -> None:
    op.drop_table("channel_order_adjustments")
    op.drop_column("channel_orders", "cost_breakdown")
    op.drop_column("channel_orders", "cost_source")
    op.drop_column("channel_orders", "other_costs")
