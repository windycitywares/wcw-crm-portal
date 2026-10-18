"""Ticket channels: how a conversation reached the CRM (SPEC §3.9, the unified inbox).

A ticket is the CRM's one conversation: the shop's contact form already opens one (M3), inbound email will
(the inbox phase), and a channel says which. It is a `ticket_channel` lookup key, so the queue can read
"Shop form" while the row keeps a stable word and an admin can rename a label without a migration.

Everything already in the table was typed in by a member of staff, so the column starts at `manual` rather
than NULL: nobody has to wonder later what an empty channel meant. A channel is decided when the ticket is
opened, and staff can correct it after the fact.

Revision ID: 0024_ticket_channels
Revises: 0022_suppliers
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_ticket_channels"
down_revision = "0022_suppliers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("channel", sa.String(length=30), server_default="manual",
                                       nullable=False))


def downgrade() -> None:
    op.drop_column("tickets", "channel")
