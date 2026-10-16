"""Email outbox.

Revision ID: 0006_email_outbox
Revises: 0005_app_settings
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_email_outbox"
down_revision = "0005_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("html", sa.Text(), nullable=True),
        sa.Column("reply_to", sa.String(length=320), nullable=True),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("category", sa.String(length=20), server_default="system", nullable=False),
        sa.Column("status", sa.String(length=10), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("send_after", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_email_outbox"),
    )
    op.create_index("ix_email_outbox_due", "email_outbox", ["status", "send_after"], unique=False)
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"], unique=False)
    op.create_index("ix_email_outbox_sent_at", "email_outbox", ["sent_at"], unique=False)


def downgrade() -> None:
    op.drop_table("email_outbox")
