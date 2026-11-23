"""account_contacts: a person's links to organisations, with a role and dates; one active link is their main account.

Every contact that already has an account gets one active, primary link starting the day the contact was created.

Revision ID: 0043_account_contacts
Revises: 0042_supplier_logins
Create Date: 2026-11-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0043_account_contacts"
down_revision = "0042_supplier_logins"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_contacts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("account_id", sa.BigInteger(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(80)),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_on", sa.Date()),
        sa.Column("ended_on", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_account_contacts_account", "account_contacts", ["account_id", "ended_on"])
    op.create_index("ix_account_contacts_contact", "account_contacts", ["contact_id", "ended_on"])
    op.create_index("uq_account_contacts_active", "account_contacts", ["account_id", "contact_id"], unique=True,
                    postgresql_where=sa.text("ended_on IS NULL"))
    op.execute(
        "INSERT INTO account_contacts (account_id, contact_id, is_primary, started_on) "
        "SELECT account_id, id, true, created_at::date FROM contacts WHERE account_id IS NOT NULL")


def downgrade() -> None:
    op.drop_table("account_contacts")
