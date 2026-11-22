"""supplier_logins: a "supplier" user's Supplier account and the sales channels they may see.

Revision ID: 0042_supplier_logins
Revises: 0041_channel_orders
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0042_supplier_logins"
down_revision = "0041_channel_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_logins",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channels", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_supplier_logins_account_id", "supplier_logins", ["account_id"])


def downgrade() -> None:
    op.drop_table("supplier_logins")
