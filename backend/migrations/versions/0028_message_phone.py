"""Message phone: a channel that has no address still tells staff who texted (SPEC §3.9).

A text gateway or a live chat hands the CRM a phone number instead of an email. The number is stored on
the message (`ticket_messages.from_phone`) so staff can see who wrote in and link the ticket by hand — it
never creates a customer on its own (a phone is shared and recycled, and a wrong record is harder to undo
than an unlinked ticket).

Revision ID: 0028_message_phone
Revises: 0027_attachments
Create Date: 2026-10-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0028_message_phone"
down_revision = "0027_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ticket_messages", sa.Column("from_phone", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("ticket_messages", "from_phone")