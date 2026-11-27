"""Help feedback: "Was this helpful?" answers, one row per answer, per guide.

Revision ID: 0049_help_feedback
Revises: 0048_product_types
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0049_help_feedback"
down_revision = "0048_product_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "help_feedback",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.String(60), nullable=False),
        sa.Column("page", sa.String(200), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("user_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_help_feedback_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_help_feedback"),
    )
    op.create_index("ix_help_feedback_topic", "help_feedback", ["topic_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_help_feedback_topic", table_name="help_feedback")
    op.drop_table("help_feedback")
