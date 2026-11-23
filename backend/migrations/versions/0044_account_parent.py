"""accounts.parent_id: parent organisations (a group above its companies, a head office above its branches).

Revision ID: 0044_account_parent
Revises: 0043_account_contacts
Create Date: 2026-11-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0044_account_parent"
down_revision = "0043_account_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("parent_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_accounts_parent_id_accounts", "accounts", "accounts", ["parent_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_accounts_parent_id", "accounts", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_accounts_parent_id", table_name="accounts")
    op.drop_constraint("fk_accounts_parent_id_accounts", "accounts", type_="foreignkey")
    op.drop_column("accounts", "parent_id")
