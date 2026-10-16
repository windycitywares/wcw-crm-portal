"""Deploy control (Admin → Deployments).

Revision ID: 0007_deploy_control
Revises: 0006_email_outbox
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_deploy_control"
down_revision = "0006_email_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deploy_control",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=10), server_default="auto", nullable=False),
        sa.Column("interval_minutes", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("schedule_times", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reason", sa.String(length=40), nullable=True),
        sa.Column("last_result", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], name="fk_deploy_control_requested_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_deploy_control_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_deploy_control"),
    )


def downgrade() -> None:
    op.drop_table("deploy_control")
