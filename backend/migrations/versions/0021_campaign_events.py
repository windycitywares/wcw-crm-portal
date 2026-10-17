"""Campaign tracking: what a recipient did with the message (SPEC §3.6).

`campaign_events` records an open (the message asked for the one-pixel image), a click (a link in the message
was followed, and redirected through us) and an unsubscribe (the footer's link was used). One row per recipient
per kind — per link for a click — enforced by the unique key, so a mail client that fetches the image twice, or
somebody who clicks a link again, does not inflate the report: it counts people, not requests.

The rows hang off the recipient (and so off the campaign), which is also what ties an event to the customer
whose timeline it lands on. `campaign_id` is a deliberate shortcut: it is implied by the recipient, but every
report question is asked by campaign and this keeps it off a join.

Revision ID: 0021_campaign_events
Revises: 0020_campaigns_send
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_campaign_events"
down_revision = "0020_campaigns_send"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaign_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("campaign_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("url", sa.String(length=500), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"],
                                name="fk_campaign_events_campaign_id_campaigns", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["campaign_recipients.id"],
                                name="fk_campaign_events_recipient_id_campaign_recipients", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_campaign_events"),
        sa.UniqueConstraint("recipient_id", "kind", "url", name="uq_campaign_events_recipient_kind_url"),
    )
    op.create_index("ix_campaign_events_campaign_kind", "campaign_events", ["campaign_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_campaign_events_campaign_kind", table_name="campaign_events")
    op.drop_table("campaign_events")
