"""Shop backfill progress (one row).

Revision ID: 0010_shop_backfill
Revises: 0009_shop_events
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_shop_backfill"
down_revision = "0009_shop_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_backfill",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="idle", nullable=False),
        sa.Column("phase", sa.String(length=12), server_default="customers", nullable=False),
        sa.Column("after_id", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("counts", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_by", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shop_backfill")),
    )


def downgrade() -> None:
    op.drop_table("shop_backfill")
