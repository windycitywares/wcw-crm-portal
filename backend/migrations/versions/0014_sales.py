"""Sales: pipelines, their stages and deals.

Revision ID: 0014_sales
Revises: 0013_canned_responses
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_sales"
down_revision = "0013_canned_responses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipelines",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_pipelines_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_pipelines_updated_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_pipelines"),
    )
    op.create_index("ix_pipelines_deleted_at", "pipelines", ["deleted_at"])

    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("pipeline_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("probability", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_won", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_lost", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"],
                                name="fk_pipeline_stages_pipeline_id_pipelines", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_pipeline_stages"),
    )
    op.create_index("ix_pipeline_stages_pipeline", "pipeline_stages", ["pipeline_id", "position"])

    op.create_table(
        "deals",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("stage_id", sa.BigInteger(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=10), server_default="open", nullable=False),
        sa.Column("value", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("probability", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expected_close_on", sa.Date(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=True),
        sa.Column("lost_reason", sa.String(length=60), nullable=True),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_deals_customer_id_customers", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["stage_id"], ["pipeline_stages.id"],
                                name="fk_deals_stage_id_pipeline_stages", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_deals_created_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name="fk_deals_updated_by_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_deals_owner_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_deals"),
    )
    op.create_index("ix_deals_owner_id", "deals", ["owner_id"])
    op.create_index("ix_deals_deleted_at", "deals", ["deleted_at"])
    op.create_index("ix_deals_stage_position", "deals", ["stage_id", "position"])
    op.create_index("ix_deals_customer", "deals", ["customer_id"])
    op.create_index("ix_deals_open_close", "deals", ["expected_close_on"],
                    postgresql_where=sa.text("deleted_at IS NULL AND status = 'open'"))


def downgrade() -> None:
    op.drop_table("deals")
    op.drop_table("pipeline_stages")
    op.drop_table("pipelines")
