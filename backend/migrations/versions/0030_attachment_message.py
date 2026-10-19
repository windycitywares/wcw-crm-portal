"""attachment message: which message brought a file (SPEC §4.2, §3.9).

A file the inbox filed came with a message, and staff want to know which one. `attachments.message_id`
holds the id of that `ticket_messages` row (plain id, no cross-module foreign key — this block knows
nothing about the module that owns the message). A file a member of staff added has none, so the column
is nullable and existing rows keep NULL.

Revision ID: 0030_attachment_message
Revises: 0029_campaign_recipient_synced
Create Date: 2026-10-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0030_attachment_message"
down_revision = "0029_campaign_recipient_synced"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attachments", sa.Column("message_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("attachments", "message_id")
