"""campaign_recipient_synced_to_timeline: track which sent messages have been logged to the timeline.

The `dispatch_due` job calls `sync_outbox` to learn what the outbox sent, and records a timeline entry for
each newly-sent message. This column marks which ones have already been logged, so we don't add duplicates.

Revision ID: 0029_campaign_recipient_synced
Revises: 11139ab4a128
Create Date: 2026-10-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0029_campaign_recipient_synced"
down_revision = "11139ab4a128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campaign_recipients", sa.Column("synced_to_timeline", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("campaign_recipients", "synced_to_timeline")