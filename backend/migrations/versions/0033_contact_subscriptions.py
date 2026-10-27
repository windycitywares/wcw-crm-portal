"""Contacts: newsletter subscription (shop subscribers live in the directory).

Revision ID: 0033_contact_subscriptions
Revises: 0032_app_mode
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0033_contact_subscriptions"
down_revision = "0032_app_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("subscribed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("subscribe_source", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("contacts", "subscribe_source")
    op.drop_column("contacts", "unsubscribed_at")
    op.drop_column("contacts", "subscribed_at")
