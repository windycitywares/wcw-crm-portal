"""Campaigns and their recipients: one send, and the customers it goes to.

A campaign is a template plus an audience plus a time (SPEC §3.6). When it starts, the audience is copied
into `campaign_recipients` — a static list's members, or a segment's matches evaluated at that moment — and
each row then follows its message through the existing `email_outbox`, so the throttling, pacing and retries
set up in Admin → Settings → Email apply to campaigns unchanged.

`outbox_id` points at the message that was actually sent (kept even after that row is purged, by nulling the
link), which is what the tracking and per-campaign report in the next batch build on.

Revision ID: 0020_campaigns_send
Revises: 0019_segments
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_campaigns_send"
down_revision = "0019_segments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("template_id", sa.BigInteger(), nullable=False),
        sa.Column("target_list_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="draft", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["email_templates.id"], name="fk_campaigns_template_id_email_templates",
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_list_id"], ["target_lists.id"],
                                name="fk_campaigns_target_list_id_target_lists", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_campaigns_created_by_users",
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_campaigns_updated_by_users",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_campaigns"),
    )
    op.create_index("ix_campaigns_deleted_at", "campaigns", ["deleted_at"])
    op.create_index("ix_campaigns_status_scheduled", "campaigns", ["status", "scheduled_at"])

    op.create_table(
        "campaign_recipients",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("campaign_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=True),
        sa.Column("outbox_id", sa.BigInteger(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"],
                                name="fk_campaign_recipients_campaign_id_campaigns", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"],
                                name="fk_campaign_recipients_customer_id_customers", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["outbox_id"], ["email_outbox.id"],
                                name="fk_campaign_recipients_outbox_id_email_outbox", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_campaign_recipients"),
        sa.UniqueConstraint("campaign_id", "customer_id", name="uq_campaign_recipients_campaign_customer"),
    )
    op.create_index("ix_campaign_recipients_campaign_status", "campaign_recipients", ["campaign_id", "status"])
    op.create_index("ix_campaign_recipients_customer", "campaign_recipients", ["customer_id"])


def downgrade() -> None:
    op.drop_table("campaign_recipients")
    op.drop_table("campaigns")
