"""channel_listings: marketplace listings (Etsy), with the team's supplier account, purchase cost and notes.

Revision ID: 0040_channel_listings
Revises: 0039_channel_connections
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0040_channel_listings"
down_revision = "0039_channel_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_listings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("external_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("state", sa.String(20), nullable=False, server_default="active"),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("quantity", sa.Integer()),
        sa.Column("skus", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("url", sa.String(500)),
        sa.Column("images", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("variations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("external_updated_at", sa.DateTime(timezone=True)),
        sa.Column("synced_at", sa.DateTime(timezone=True)),
        sa.Column("supplier_account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="SET NULL")),
        sa.Column("purchase_cost", sa.Numeric(12, 2)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("channel", "external_id", name="uq_channel_listings_channel_external_id"),
    )
    op.create_index("ix_channel_listings_channel", "channel_listings", ["channel"])
    op.create_index("ix_channel_listings_state", "channel_listings", ["state"])
    op.create_index("ix_channel_listings_supplier_account_id", "channel_listings", ["supplier_account_id"])


def downgrade() -> None:
    op.drop_table("channel_listings")
