"""urns: sizes (10 and 3 inch to start), urns, dated supplier prices, extra costs and mapped variations.

Revision ID: 0046_urns
Revises: 0045_deal_contacts
Create Date: 2026-11-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0046_urns"
down_revision = "0045_deal_contacts"
branch_labels = None
depends_on = None

def _ts():
    return (sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def _author(table: str):
    return (sa.Column("created_by", sa.BigInteger()), sa.Column("updated_by", sa.BigInteger()),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=f"fk_{table}_created_by_users", ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name=f"fk_{table}_updated_by_users", ondelete="SET NULL"))


def upgrade() -> None:
    op.create_table(
        "urn_sizes",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("label", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("aliases", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_ts(),
        sa.PrimaryKeyConstraint("id", name="pk_urn_sizes"),
        sa.UniqueConstraint("code", name="uq_urn_sizes_code"),
    )
    op.execute("INSERT INTO urn_sizes (code, label, position, aliases) VALUES "
               "('10', '10 inch', 10, '[\"large\", \"adult\", \"full size\"]'::jsonb), "
               "('3', '3 inch', 20, '[\"keepsake\", \"keepsakes\", \"mini\", \"small\"]'::jsonb)")
    op.create_table(
        "urns",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("supplier_id", sa.BigInteger()),
        sa.Column("listing_id", sa.BigInteger()),
        sa.Column("notes", sa.Text()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_ts(),
        *_author("urns"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], name="fk_urns_supplier_id_suppliers", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["listing_id"], ["channel_listings.id"], name="fk_urns_listing_id_channel_listings",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_urns"),
    )
    op.create_index("ix_urns_name", "urns", ["name"])
    op.create_index("ix_urns_supplier_id", "urns", ["supplier_id"])
    op.create_index("ix_urns_deleted_at", "urns", ["deleted_at"])
    op.create_index("uq_urns_listing", "urns", ["listing_id"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_table(
        "urn_prices",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("urn_id", sa.BigInteger(), nullable=False),
        sa.Column("size_code", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        *_author("urn_prices"),
        sa.ForeignKeyConstraint(["urn_id"], ["urns.id"], name="fk_urn_prices_urn_id_urns", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_urn_prices"),
    )
    op.create_index("uq_urn_prices_urn_size_from", "urn_prices", ["urn_id", "size_code", "effective_from"], unique=True)
    op.create_table(
        "cost_extras",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("urn_id", sa.BigInteger()),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False, server_default="amount"),
        sa.Column("value", sa.Numeric(12, 4), nullable=False),
        sa.Column("applies", sa.String(10), nullable=False, server_default="piece"),
        sa.Column("size_code", sa.String(10)),
        sa.Column("party", sa.String(10), nullable=False, server_default="supplier"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        *_ts(),
        *_author("cost_extras"),
        sa.ForeignKeyConstraint(["urn_id"], ["urns.id"], name="fk_cost_extras_urn_id_urns", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_cost_extras"),
    )
    op.create_index("ix_cost_extras_urn_id", "cost_extras", ["urn_id"])
    op.create_table(
        "urn_variations",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("urn_id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(400), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("quantities", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state", sa.String(10), nullable=False, server_default="proposed"),
        sa.Column("note", sa.String(300)),
        sa.Column("sku", sa.String(64)),
        sa.Column("etsy_sku", sa.String(100)),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by", sa.BigInteger()),
        *_ts(),
        sa.ForeignKeyConstraint(["urn_id"], ["urns.id"], name="fk_urn_variations_urn_id_urns", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], name="fk_urn_variations_approved_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_urn_variations"),
    )
    op.create_index("uq_urn_variations_urn_key", "urn_variations", ["urn_id", "key"], unique=True)
    op.create_index("ix_urn_variations_sku", "urn_variations", ["sku"])
    op.create_index("ix_urn_variations_state", "urn_variations", ["state"])


def downgrade() -> None:
    for t in ("urn_variations", "cost_extras", "urn_prices", "urns", "urn_sizes"):
        op.drop_table(t)
