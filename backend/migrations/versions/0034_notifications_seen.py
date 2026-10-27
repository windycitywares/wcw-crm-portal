"""Users: when each person last opened the bell (anything newer counts as unread).

Revision ID: 0034_notifications_seen
Revises: 0033_contact_subscriptions
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_notifications_seen"
down_revision = "0033_contact_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("notifications_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "notifications_seen_at")
