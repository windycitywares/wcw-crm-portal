"""Contacts: a subscriber can be paused, and has a language.

Revision ID: 0035_subscriber_pause
Revises: 0034_notifications_seen
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0035_subscriber_pause"
down_revision = "0034_notifications_seen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("language", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("contacts", "language")
    op.drop_column("contacts", "paused_at")
