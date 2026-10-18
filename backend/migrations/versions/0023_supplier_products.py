"""Products supplied by each vendor (SPEC §3.7).

Revision ID: 0023_supplier_products
Revises: 0022_suppliers
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_supplier_products"
down_revision = "0022_suppliers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_products",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supplier_id", sa.BigInteger(), nullable=False),
        sa.Column("shop_sku", sa.String(length=80), nullable=False),
        sa.Column("supplier_sku", sa.String(length=80), nullable=True),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("minimum_order_quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("unit_cost >= 0", name="ck_supplier_products_unit_cost_nonnegative"),
        sa.CheckConstraint("minimum_order_quantity IS NULL OR minimum_order_quantity > 0",
                           name="ck_supplier_products_moq_positive"),
        sa.CheckConstraint("lead_time_days IS NULL OR lead_time_days >= 0",
                           name="ck_supplier_products_lead_time_nonnegative"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_supplier_products_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_supplier_products_updated_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], name="fk_supplier_products_supplier_id_suppliers", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_supplier_products"),
    )
    op.create_index("ix_supplier_products_deleted_at", "supplier_products", ["deleted_at"])
    op.create_index("ix_supplier_products_supplier_id", "supplier_products", ["supplier_id"])
    op.create_index("ix_supplier_products_supplier_shop_sku", "supplier_products", ["supplier_id", "shop_sku"])
    op.create_index("uq_supplier_products_supplier_sku", "supplier_products", ["supplier_id", "supplier_sku"],
                    unique=True, postgresql_where=sa.text("supplier_sku IS NOT NULL AND deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_supplier_products_supplier_sku", table_name="supplier_products")
    op.drop_index("ix_supplier_products_supplier_shop_sku", table_name="supplier_products")
    op.drop_index("ix_supplier_products_supplier_id", table_name="supplier_products")
    op.drop_index("ix_supplier_products_deleted_at", table_name="supplier_products")
    op.drop_table("supplier_products")