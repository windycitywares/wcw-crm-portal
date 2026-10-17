"""Canned responses: saved answers staff can drop into a ticket reply.

Revision ID: 0013_canned_responses
Revises: 0012_tickets
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_canned_responses"
down_revision = "0012_tickets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canned_responses",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_canned_responses_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_canned_responses_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_canned_responses"),
    )


def downgrade() -> None:
    op.drop_table("canned_responses")
