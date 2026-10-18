"""The mailboxes the CRM reads (SPEC §3.9, the unified inbox).

One row per mailbox: where it is, who the CRM logs in as, and the password — stored as the Fernet token
(`imap_password_enc`) that DATA_ENCRYPTION_KEY can open, so a database dump alone gets nobody into a
mailbox. This is configuration, like the SMTP account in Admin → Settings → Email, so the row is deleted
for real rather than archived: a mailbox nobody reads any longer should not keep a password around. The
conversations its mail opened are tickets (batch 1 gave them a channel), and those stay.

Revision ID: 0025_email_accounts
Revises: 0024_ticket_channels
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_email_accounts"
down_revision = "0024_ticket_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_accounts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("address", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column("imap_host", sa.String(length=255), nullable=False),
        sa.Column("imap_port", sa.Integer(), server_default="993", nullable=False),
        sa.Column("imap_security", sa.String(length=10), server_default="ssl", nullable=False),
        sa.Column("imap_user", sa.String(length=320), nullable=True),
        sa.Column("imap_password_enc", sa.Text(), nullable=False),
        sa.Column("folder", sa.String(length=120), server_default="INBOX", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_email_accounts_created_by_users",
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_email_accounts_updated_by_users",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_email_accounts"),
        sa.UniqueConstraint("address", name="uq_email_accounts_address"),
    )


def downgrade() -> None:
    op.drop_table("email_accounts")
