"""Email in: the same message never lands twice, and a customer's answer finds its ticket (SPEC §3.9).

Two small changes, both about mail arriving on a mailbox the CRM reads (0025):

- `ticket_messages.external_id` holds the email's own `Message-ID` (angle brackets off) for both
  directions. It is unique, so a re-poll — or a crash between storing a message and marking it read —
  cannot store the same message twice; and it is where a customer's answer lands, because their
  `In-Reply-To`/`References` name the id our reply went out with. Internal notes have none.
- `email_accounts` gains the two columns that say how the last poll went (`last_polled_at`, and
  `last_error`, which is cleared by a good poll), written by the `inbox` job and shown to the admin who
  set the mailbox up.

Revision ID: 0026_email_in
Revises: 0025_email_accounts
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0026_email_in"
down_revision = "0025_email_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ticket_messages", sa.Column("external_id", sa.String(length=400), nullable=True))
    op.create_unique_constraint("uq_ticket_messages_external_id", "ticket_messages", ["external_id"])
    op.add_column("email_accounts", sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_accounts", sa.Column("last_error", sa.String(length=400), nullable=True))


def downgrade() -> None:
    op.drop_column("email_accounts", "last_error")
    op.drop_column("email_accounts", "last_polled_at")
    op.drop_constraint("uq_ticket_messages_external_id", "ticket_messages", type_="unique")
    op.drop_column("ticket_messages", "external_id")
