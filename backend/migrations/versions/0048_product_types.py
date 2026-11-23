"""Product types: each with its own SKU format and sizes. Everything so far becomes the type "Urn", with the SKU
format that was saved in Settings (its {urn:N} written as {product:N} — the same SKUs).

Revision ID: 0048_product_types
Revises: 0047_order_costs
Create Date: 2026-11-24
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0048_product_types"
down_revision = "0047_order_costs"
branch_labels = None
depends_on = None

DEFAULT = {"template": "WCW-{supplier:3}-{product:4}-{sizes}{-option}", "size_format": "{code}x{qty}", "separator": "-"}


def upgrade() -> None:
    op.create_table(
        "product_types",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("code", sa.String(10)),
        sa.Column("template", sa.String(80), nullable=False),
        sa.Column("size_format", sa.String(20), nullable=False, server_default="{code}x{qty}"),
        sa.Column("separator", sa.String(3), nullable=False, server_default="-"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_product_types"),
        sa.UniqueConstraint("name", name="uq_product_types_name"),
    )
    conn = op.get_bind()
    saved = conn.execute(sa.text("SELECT value FROM app_settings WHERE key = 'sku'")).scalar()
    if isinstance(saved, str):
        saved = json.loads(saved)
    fmt = {k: (saved or {}).get(k) or v for k, v in DEFAULT.items()}
    fmt["template"] = fmt["template"].replace("{urn:", "{product:")
    type_id = conn.execute(sa.text(
        "INSERT INTO product_types (name, code, template, size_format, separator, position) "
        "VALUES ('Urn', 'U', :t, :f, :s, 10) RETURNING id"), {"t": fmt["template"], "f": fmt["size_format"],
                                                             "s": fmt["separator"]}).scalar()

    op.add_column("urn_sizes", sa.Column("type_id", sa.BigInteger()))
    conn.execute(sa.text("UPDATE urn_sizes SET type_id = :id"), {"id": type_id})
    op.alter_column("urn_sizes", "type_id", nullable=False)
    op.create_foreign_key("fk_urn_sizes_type_id_product_types", "urn_sizes", "product_types", ["type_id"], ["id"],
                          ondelete="CASCADE")
    op.create_index("ix_urn_sizes_type_id", "urn_sizes", ["type_id"])
    op.drop_constraint("uq_urn_sizes_code", "urn_sizes", type_="unique")
    op.create_index("uq_urn_sizes_type_code", "urn_sizes", ["type_id", "code"], unique=True)

    op.add_column("urns", sa.Column("type_id", sa.BigInteger()))
    conn.execute(sa.text("UPDATE urns SET type_id = :id"), {"id": type_id})
    op.alter_column("urns", "type_id", nullable=False)
    op.create_foreign_key("fk_urns_type_id_product_types", "urns", "product_types", ["type_id"], ["id"],
                          ondelete="RESTRICT")
    op.create_index("ix_urns_type_id", "urns", ["type_id"])

    op.add_column("cost_extras", sa.Column("type_id", sa.BigInteger()))
    op.create_foreign_key("fk_cost_extras_type_id_product_types", "cost_extras", "product_types", ["type_id"], ["id"],
                          ondelete="CASCADE")
    op.create_index("ix_cost_extras_type_id", "cost_extras", ["type_id"])


def downgrade() -> None:
    op.drop_index("ix_cost_extras_type_id", table_name="cost_extras")
    op.drop_constraint("fk_cost_extras_type_id_product_types", "cost_extras", type_="foreignkey")
    op.drop_column("cost_extras", "type_id")
    op.drop_index("ix_urns_type_id", table_name="urns")
    op.drop_constraint("fk_urns_type_id_product_types", "urns", type_="foreignkey")
    op.drop_column("urns", "type_id")
    op.drop_index("uq_urn_sizes_type_code", table_name="urn_sizes")
    op.create_unique_constraint("uq_urn_sizes_code", "urn_sizes", ["code"])
    op.drop_index("ix_urn_sizes_type_id", table_name="urn_sizes")
    op.drop_constraint("fk_urn_sizes_type_id_product_types", "urn_sizes", type_="foreignkey")
    op.drop_column("urn_sizes", "type_id")
    op.drop_table("product_types")
