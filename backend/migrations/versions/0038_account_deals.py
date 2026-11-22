"""deals (opportunities) belong to an account; a converted lead remembers the account it became.

Existing deals are placed at the account their customer's contact works at, when there is one.

Revision ID: 0038_account_deals
Revises: 0037_supplier_accounts
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0038_account_deals"
down_revision = "0037_supplier_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("account_id", sa.BigInteger(),
                                     sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_deals_account_id", "deals", ["account_id"])
    op.add_column("leads", sa.Column("converted_account_id", sa.BigInteger(),
                                     sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.execute("""
        UPDATE deals d SET account_id = c.account_id
        FROM contacts c
        WHERE c.customer_id = d.customer_id AND c.account_id IS NOT NULL AND d.account_id IS NULL
    """)


def downgrade() -> None:
    op.drop_column("leads", "converted_account_id")
    op.drop_index("ix_deals_account_id", table_name="deals")
    op.drop_column("deals", "account_id")
