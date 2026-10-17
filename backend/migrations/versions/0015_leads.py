"""Leads: the funnel before a customer.

Revision ID: 0015_leads
Revises: 0014_sales
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_leads"
down_revision = "0014_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=True),
        sa.Column("last_name", sa.String(length=80), nullable=True),
        sa.Column("company", sa.String(length=160), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="new", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_customer_id", sa.BigInteger(), nullable=True),
        sa.Column("converted_deal_id", sa.BigInteger(), nullable=True),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["converted_customer_id"], ["customers.id"],
                                name="fk_leads_converted_customer_id_customers", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["converted_deal_id"], ["deals.id"],
                                name="fk_leads_converted_deal_id_deals", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_leads_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_leads_updated_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_leads_owner_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_leads"),
    )
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_owner_id", "leads", ["owner_id"])
    op.create_index("ix_leads_deleted_at", "leads", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("leads")
