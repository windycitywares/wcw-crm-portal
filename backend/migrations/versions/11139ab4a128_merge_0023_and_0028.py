"""merge 0023 and 0028

Revision ID: 11139ab4a128
Revises: 0023_supplier_products, 0028_message_phone
Create Date: 2026-10-18 09:43:13.418546
"""
from alembic import op
import sqlalchemy as sa


revision = '11139ab4a128'
down_revision = ('0023_supplier_products', '0028_message_phone')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
