"""Suppliers and their contacts (SPEC §3.7).

Revision ID: 0022_suppliers
Revises: 0021_campaign_events
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022_suppliers"
down_revision = "0021_campaign_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("supplier_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("payment_terms", sa.String(length=300), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_suppliers_rating_range"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_suppliers_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_suppliers_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_suppliers"),
    )
    op.create_index("ix_suppliers_deleted_at", "suppliers", ["deleted_at"])
    op.create_index("ix_suppliers_name", "suppliers", ["name"])
    op.create_index("ix_suppliers_supplier_type", "suppliers", ["supplier_type"])
    op.create_index("ix_suppliers_status", "suppliers", ["status"])
    op.create_index("ix_suppliers_type_status", "suppliers", ["supplier_type", "status"])

    op.create_table(
        "supplier_contacts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_supplier_contacts_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_supplier_contacts_updated_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], name="fk_supplier_contacts_supplier_id_suppliers", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_supplier_contacts"),
    )
    op.create_index("ix_supplier_contacts_deleted_at", "supplier_contacts", ["deleted_at"])
    op.create_index("ix_supplier_contacts_supplier_id", "supplier_contacts", ["supplier_id"])
    op.create_index("uq_supplier_contacts_primary", "supplier_contacts", ["supplier_id"], unique=True,
                    postgresql_where=sa.text("is_primary IS TRUE AND deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_supplier_contacts_primary", table_name="supplier_contacts")
    op.drop_index("ix_supplier_contacts_supplier_id", table_name="supplier_contacts")
    op.drop_index("ix_supplier_contacts_deleted_at", table_name="supplier_contacts")
    op.drop_table("supplier_contacts")
    op.drop_index("ix_suppliers_type_status", table_name="suppliers")
    op.drop_index("ix_suppliers_status", table_name="suppliers")
    op.drop_index("ix_suppliers_supplier_type", table_name="suppliers")
    op.drop_index("ix_suppliers_name", table_name="suppliers")
    op.drop_index("ix_suppliers_deleted_at", table_name="suppliers")
    op.drop_table("suppliers")