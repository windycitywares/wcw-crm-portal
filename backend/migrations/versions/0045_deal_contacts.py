"""deal_contacts: the people on a deal and the part each plays (decision maker, signer…).

Revision ID: 0045_deal_contacts
Revises: 0044_account_parent
Create Date: 2026-11-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0045_deal_contacts"
down_revision = "0044_account_parent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deal_contacts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(60)),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger()),
        sa.Column("updated_by", sa.BigInteger()),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], name="fk_deal_contacts_deal_id_deals", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name="fk_deal_contacts_contact_id_contacts",
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_deal_contacts_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_deal_contacts_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_deal_contacts"),
    )
    op.create_index("uq_deal_contacts_deal_contact", "deal_contacts", ["deal_id", "contact_id"], unique=True)
    op.create_index("ix_deal_contacts_contact", "deal_contacts", ["contact_id"])


def downgrade() -> None:
    op.drop_table("deal_contacts")
