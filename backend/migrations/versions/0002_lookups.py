"""Admin-editable type lists.

Revision ID: 0002_lookups
Revises: 0001_users_audit
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_lookups"
down_revision = "0001_users_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lookup_values",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_lookup_values_created_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name=op.f("fk_lookup_values_updated_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lookup_values")),
        sa.UniqueConstraint("kind", "key", name="uq_lookup_values_kind_key"),
    )
    op.create_index(op.f("ix_lookup_values_kind"), "lookup_values", ["kind"], unique=False)


def downgrade() -> None:
    op.drop_table("lookup_values")
