"""Deal items: the products and one-off lines on a deal.

Revision ID: 0016_deal_items
Revises: 0015_leads
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_deal_items"
down_revision = "0015_leads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deal_items",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=True),
        sa.Column("shop_product_id", sa.BigInteger(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=2), server_default="1", nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], name="fk_deal_items_deal_id_deals", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_deal_items_created_by_users",
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_deal_items_updated_by_users",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_deal_items"),
    )
    op.create_index("ix_deal_items_deal", "deal_items", ["deal_id", "position"])
    op.create_index("ix_deal_items_deleted_at", "deal_items", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("deal_items")
