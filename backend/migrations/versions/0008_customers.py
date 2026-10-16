"""Customers.

Revision ID: 0008_customers
Revises: 0007_deploy_control
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_customers"
down_revision = "0007_deploy_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=80), server_default="", nullable=False),
        sa.Column("last_name", sa.String(length=80), server_default="", nullable=False),
        sa.Column("company", sa.String(length=160), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("alt_emails", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("customer_type", sa.String(length=60), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("marketing_consent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_source", sa.String(length=60), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shop_user_id", sa.BigInteger(), nullable=True),
        sa.Column("orders_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_spent", sa.Numeric(precision=12, scale=2), server_default=sa.text("0"), nullable=False),
        sa.Column("first_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_order_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_customers_owner_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_customers_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_customers_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
        sa.UniqueConstraint("shop_user_id", name="uq_customers_shop_user_id"),
    )
    op.create_index("uq_customers_email_active", "customers", ["email"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_customers_last_order_at", "customers", ["last_order_at"], unique=False)
    op.create_index("ix_customers_customer_type", "customers", ["customer_type"], unique=False)
    op.create_index("ix_customers_status", "customers", ["status"], unique=False)
    op.create_index("ix_customers_owner_id", "customers", ["owner_id"], unique=False)
    op.create_index("ix_customers_deleted_at", "customers", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_table("customers")
