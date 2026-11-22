"""accounts: the organisations the business deals with; a contact can be at one.

Revision ID: 0036_accounts
Revises: 0035_subscriber_pause
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0036_accounts"
down_revision = "0035_subscriber_pause"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("account_type", sa.String(60), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("industry", sa.String(120)),
        sa.Column("website", sa.String(500)),
        sa.Column("email", sa.String(320)),
        sa.Column("phone", sa.String(40)),
        sa.Column("address", postgresql.JSONB()),
        sa.Column("notes", sa.Text()),
        sa.Column("custom_fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_accounts_name", "accounts", ["name"])
    op.create_index("ix_accounts_account_type", "accounts", ["account_type"])
    op.create_index("ix_accounts_status", "accounts", ["status"])
    op.create_index("ix_accounts_type_status", "accounts", ["account_type", "status"])
    op.create_index("ix_accounts_owner_id", "accounts", ["owner_id"])
    op.create_index("ix_accounts_deleted_at", "accounts", ["deleted_at"])

    op.add_column("contacts", sa.Column("account_id", sa.BigInteger(),
                                        sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_contacts_account_id", "contacts", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_contacts_account_id", table_name="contacts")
    op.drop_column("contacts", "account_id")
    op.drop_table("accounts")
